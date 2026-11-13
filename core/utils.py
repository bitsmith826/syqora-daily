import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import config


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Standard colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # High-intensity bright colors
    GRAY = "\033[90m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


ANSI_REGEX = re.compile(r'\x1b\[[0-9;]*m')


def strip_ansi(s: str) -> str:
    """Strip ANSI color/style escape codes from string."""
    return ANSI_REGEX.sub('', str(s))


def visible_len(s: str) -> int:
    """Return visible character length of string (ignoring ANSI codes)."""
    return len(strip_ansi(s))


def pad_visible(s: str, width: int, align: str = "left") -> str:
    """Pad string to exact visible width considering ANSI escape codes."""
    v_len = visible_len(s)
    pad = max(0, width - v_len)
    if align == "right":
        return (" " * pad) + s
    elif align == "center":
        left = pad // 2
        right = pad - left
        return (" " * left) + s + (" " * right)
    return s + (" " * pad)


TAG_MAP = {
    "INFO": f"{Colors.BRIGHT_CYAN}[INFO   ]{Colors.RESET}",
    "STEP": f"{Colors.BRIGHT_MAGENTA}[STEP   ]{Colors.RESET}",
    "SUCCESS": f"{Colors.BRIGHT_GREEN}[SUCCESS]{Colors.RESET}",
    "WARNING": f"{Colors.BRIGHT_YELLOW}[WARN   ]{Colors.RESET}",
    "WARN": f"{Colors.BRIGHT_YELLOW}[WARN   ]{Colors.RESET}",
    "ERROR": f"{Colors.BRIGHT_RED}[ERROR  ]{Colors.RESET}",
}


def log(msg: str, level: str = "INFO"):
    """Thread-safe, perfectly aligned console logger."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    tag = TAG_MAP.get(level.upper(), f"[{level.upper():<7}]")
    print(f"{Colors.GRAY}[{timestamp}]{Colors.RESET} {tag} {msg}", flush=True)


def show_banner(title: str, subtitle: str = "", details: Optional[Dict[str, str]] = None):
    """Display a polished terminal banner with Rich or ANSI fallback."""
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        content = f"[bold bright_cyan]{title}[/bold bright_cyan]"
        if subtitle:
            content += f"\n[dim]{subtitle}[/dim]"
        if details:
            details_str = "   |   ".join([f"[white]{k}:[/white] [bold cyan]{v}[/bold cyan]" for k, v in details.items()])
            content += f"\n\n{details_str}"

        panel = Panel(content, border_style="bright_blue", box=box.ROUNDED, expand=False, padding=(0, 2))
        console.print()
        console.print(panel)
        console.print()
    except Exception:
        print(f"\n{Colors.CYAN}{Colors.BOLD}==========================================================")
        print(f"  {title}")
        if subtitle:
            print(f"  {subtitle}")
        if details:
            details_str = " | ".join([f"{k}: {v}" for k, v in details.items()])
            print(f"  {details_str}")
        print(f"=========================================================={Colors.RESET}\n")


def generate_name_from_email(email: str) -> str:
    """Generate a clean human-like name from email username."""
    user_part = email.split("@")[0]
    cleaned = re.sub(r"[._\-+0-9]+", " ", user_part).strip()
    if not cleaned or len(cleaned) < 2:
        cleaned = "Syqora User"
    words = [w.capitalize() for w in cleaned.split()]
    name = " ".join(words)
    if len(name) < 2:
        name = "Syqora Hunter"
    return name[:50]


def is_valid_evm_address(address: str) -> bool:
    """Validate 42-character Ethereum 0x hex address."""
    if not address or not isinstance(address, str):
        return False
    addr = address.strip()
    if not re.match(r"^0x[0-9a-fA-F]{40}$", addr):
        return False
    if re.match(r"^0x0{40}$", addr):
        return False
    return True


def load_accounts() -> List[Dict[str, str]]:
    """
    Load accounts from data/accounts.txt OR combine data/emails.txt + data/wallets.txt.
    Returns: List of {"email": ..., "password": ..., "wallet": ...}
    """
    accounts = []

    # Case 1: Check accounts.txt (format: email|password|evm_address or email:password:evm_address)
    if config.ACCOUNTS_FILE.exists():
        with open(config.ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("#"):
                    continue

                delimiter = "|" if "|" in clean_line else (":" if ":" in clean_line else ",")
                parts = [p.strip() for p in clean_line.split(delimiter)]

                if len(parts) >= 3:
                    email, password, wallet = parts[0], parts[1], parts[2]
                elif len(parts) == 2:
                    if "@" in parts[0] and parts[1].startswith("0x"):
                        email, password, wallet = parts[0], config.DEFAULT_PASSWORD, parts[1]
                    else:
                        email, password, wallet = parts[0], parts[1], ""
                else:
                    email = parts[0]
                    password = config.DEFAULT_PASSWORD
                    wallet = ""

                accounts.append({
                    "email": email,
                    "password": password if len(password) >= 6 else config.DEFAULT_PASSWORD,
                    "wallet": wallet
                })

    # Case 2: If accounts.txt is empty or doesn't exist, check emails.txt & wallets.txt
    if not accounts:
        emails = []
        wallets = []

        if config.EMAILS_FILE.exists():
            with open(config.EMAILS_FILE, "r", encoding="utf-8") as f:
                emails = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        if config.WALLETS_FILE.exists():
            with open(config.WALLETS_FILE, "r", encoding="utf-8") as f:
                wallets = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        for idx, email in enumerate(emails):
            wallet = wallets[idx] if idx < len(wallets) else ""
            accounts.append({
                "email": email,
                "password": config.DEFAULT_PASSWORD,
                "wallet": wallet
            })

    return accounts


def load_sessions() -> Dict[str, dict]:
    """Load existing sessions from data/sessions.json."""
    if not config.SESSIONS_FILE.exists():
        return {}
    try:
        with open(config.SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"Error loading sessions file: {e}", "WARNING")
        return {}


def save_sessions(sessions: Dict[str, dict]):
    """Save sessions to data/sessions.json atomically."""
    temp_file = config.SESSIONS_FILE.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)
    temp_file.replace(config.SESSIONS_FILE)


def random_sleep(min_sec: float = None, max_sec: float = None):
    min_s = min_sec or config.MIN_DELAY_BETWEEN_ACCOUNTS
    max_s = max_sec or config.MAX_DELAY_BETWEEN_ACCOUNTS
    delay = random.uniform(min_s, max_s)
    log(f"Cooldown delay {delay:.1f}s...", "INFO")
    time.sleep(delay)


def format_address(addr: str) -> str:
    if not addr or addr == "None":
        return "-"
    addr = str(addr).strip()
    if len(addr) > 16:
        return f"{addr[:6]}...{addr[-4:]}"
    return addr


def show_dashboard():
    """Display modern rounded Rich dashboard table or ANSI fallback."""
    sessions = load_sessions()
    if not sessions:
        print(f"\n{Colors.YELLOW}[!] Belum ada akun yang terdaftar di data/sessions.json.{Colors.RESET}")
        print(f"Jalankan: {Colors.GREEN}python main.py{Colors.RESET} untuk mendaftarkan akun.\n")
        return

    try:
        import shutil
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        cols = max(shutil.get_terminal_size((100, 24)).columns, 98)
        console = Console(width=cols)

        table = Table(
            title="✨ SYQORA SEASON 1 — AIRDROP ACCOUNT DASHBOARD ✨",
            title_style="bold bright_cyan",
            box=box.ROUNDED,
            header_style="bold bright_white on grey23",
            border_style="bright_blue",
            show_lines=False,
        )

        table.add_column("#", justify="center", style="dim", width=3)
        table.add_column("Account Email", justify="left", style="bold white", width=29)
        table.add_column("EVM Wallet", justify="center", style="bright_cyan", width=15)
        table.add_column("Points", justify="right", style="bold bright_green", width=10)
        table.add_column("Streak", justify="center", style="bright_magenta", width=8)
        table.add_column("Check-In", justify="center", width=11)

        total_points = 0
        today_claimed_count = 0
        wallets_linked = 0

        for idx, (email, data) in enumerate(sessions.items(), start=1):
            points = data.get("points", 0)
            total_points += points
            streak = data.get("streak", 0)
            wallet = data.get("wallet", "")
            if wallet and wallet != "None":
                wallets_linked += 1
                wallet_display = format_address(wallet)
            else:
                wallet_display = "[dim]-[/dim]"

            claimed = data.get("today_claimed", False)
            if claimed:
                today_claimed_count += 1
                checkin_badge = "[bold bright_green]✔ CLAIMED[/bold bright_green]"
            else:
                checkin_badge = "[bold bright_yellow]⏳ PENDING[/bold bright_yellow]"

            streak_display = f"🔥 {streak} d" if streak > 0 else "[dim]-[/dim]"

            table.add_row(
                str(idx),
                email,
                wallet_display,
                f"{points:,} PTS",
                streak_display,
                checkin_badge,
            )

        console.print()
        console.print(table)

        claim_rate = (today_claimed_count / len(sessions) * 100) if sessions else 0
        summary_text = (
            f"📊 [bold]Akun:[/] [cyan]{len(sessions)}[/]   |   "
            f"💎 [bold]Points:[/] [bright_green]{total_points:,} PTS[/]   |   "
            f"📅 [bold]Check-In:[/] [bold {'bright_green' if today_claimed_count == len(sessions) else 'bright_yellow'}]{today_claimed_count}/{len(sessions)} ({claim_rate:.0f}%)[/]   |   "
            f"👛 [bold]Wallets:[/] [cyan]{wallets_linked}/{len(sessions)}[/]"
        )
        console.print(
            Panel(
                summary_text,
                border_style="bright_blue",
                box=box.ROUNDED,
                padding=(0, 2),
                expand=False,
            )
        )
        console.print()
    except Exception:
        # ANSI fallback
        print(f"\n{Colors.CYAN}{Colors.BOLD}┌{'─'*88}┐{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}│{pad_visible('SYQORA AIRDROP ACCOUNT DASHBOARD', 88, align='center')}│{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}├{'─'*88}┤{Colors.RESET}")

        col_no = pad_visible("No", 4, "center")
        col_email = pad_visible("Account Email", 30, "left")
        col_wallet = pad_visible("EVM Wallet", 15, "center")
        col_pts = pad_visible("Points", 10, "right")
        col_streak = pad_visible("Streak", 8, "center")
        col_today = pad_visible("Check-In", 11, "center")

        print(f"{Colors.BOLD}│ {col_no} │ {col_email} │ {col_wallet} │ {col_pts} │ {col_streak} │ {col_today} │{Colors.RESET}")
        print(f"{Colors.GRAY}├{'─'*6}┼{'─'*32}┼{'─'*17}┼{'─'*12}┼{'─'*10}┼{'─'*13}┤{Colors.RESET}")

        total_points = 0
        today_claimed_count = 0

        for idx, (email, data) in enumerate(sessions.items(), start=1):
            points = data.get("points", 0)
            total_points += points
            streak = data.get("streak", 0)
            wallet = format_address(data.get("wallet", ""))
            claimed = data.get("today_claimed", False)

            claimed_str = f"{Colors.GREEN}✔ CLAIMED{Colors.RESET}" if claimed else f"{Colors.YELLOW}⏳ PENDING{Colors.RESET}"
            streak_str = f"🔥 {streak} d" if streak > 0 else "-"

            c_no = pad_visible(str(idx), 4, "center")
            c_email = pad_visible(email[:28], 30, "left")
            c_wallet = pad_visible(wallet, 15, "center")
            c_pts = pad_visible(f"{points:,} PTS", 10, "right")
            c_streak = pad_visible(streak_str, 8, "center")
            c_today = pad_visible(claimed_str, 11, "center")

            print(f"│ {c_no} │ {c_email} │ {c_wallet} │ {Colors.GREEN}{c_pts}{Colors.RESET} │ {Colors.MAGENTA}{c_streak}{Colors.RESET} │ {c_today} │")

        print(f"{Colors.CYAN}└{'─'*6}┴{'─'*32}┴{'─'*17}┴{'─'*12}┴{'─'*10}┴{'─'*13}┘{Colors.RESET}")
