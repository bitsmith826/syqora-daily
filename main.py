import argparse
import asyncio
import os
import sys

import config
from core.bot import SyqoraBot
from core.utils import Colors, load_accounts, load_sessions, log, show_banner, show_dashboard


async def auto_run(
    browser_type: str = config.BROWSER_TYPE,
    headless: bool = config.HEADLESS_BROWSER,
    proxy: str = None,
    mode: str = "all"
):
    if mode == "status":
        show_dashboard()
        return

    show_banner(
        title="SYQORA SEASON 1 AIRDROP AUTOMATION",
        subtitle="Anti-Detect Multi-Account Onboarding & Daily Check-In",
        details={
            "Engine": browser_type.upper(),
            "Headless": str(headless),
            "Pool": "10M PTS"
        }
    )

    accounts = load_accounts()
    if not accounts:
        log("Belum ada akun di data/accounts.txt!", "WARNING")
        print("\nSilakan tambahkan akun ke data/accounts.txt (lihat data/accounts.example.txt).")
        return

    sessions = load_sessions()
    unregistered = [a for a in accounts if a["email"] not in sessions or not sessions[a["email"]].get("registered")]
    registered = [a for a in accounts if a["email"] in sessions and sessions[a["email"]].get("registered")]

    print(f"📊 Total Akun Ditemukan : {Colors.BOLD}{len(accounts)}{Colors.RESET}")
    print(f"🆕 Perlu Registrasi     : {Colors.YELLOW}{Colors.BOLD}{len(unregistered)}{Colors.RESET}")
    print(f"✅ Sudah Terdaftar      : {Colors.GREEN}{Colors.BOLD}{len(registered)}{Colors.RESET}\n")

    bot = SyqoraBot(
        headless=headless,
        proxy=proxy,
        browser_type=browser_type
    )

    # 1. Registrasi akun baru (jika ada dan tidak dalam mode checkin-only)
    if unregistered and mode in ["all", "register"]:
        log(f"Memulai registrasi otomatis untuk {len(unregistered)} akun baru via {browser_type.upper()}...", "STEP")
        await bot.run_batch_onboarding(unregistered, referral_code=config.DEFAULT_REF_CODE)

    # 2. Daily check-in via direct API (jika ada akun terdaftar dan tidak dalam mode register-only)
    if registered and mode in ["all", "checkin"]:
        log(f"Menjalankan Daily Check-In & Claim Quests (API) untuk {len(registered)} akun...", "STEP")
        await bot.run_daily_checkin_all()

    # 3. Tampilkan dashboard ringkasan akhir
    print("\n" + "=" * 50)
    log("Semua proses selesai! Menampilkan dashboard status:", "SUCCESS")
    print("=" * 50)
    show_dashboard()


def main():
    parser = argparse.ArgumentParser(description="Syqora Season 1 Airdrop - Auto All-In-One Bot")
    parser.add_argument(
        "--browser",
        type=str,
        default=config.BROWSER_TYPE,
        choices=["camoufox", "chrome", "chromium"],
        help="Browser engine ('camoufox' untuk bypass Turnstile otomatis, atau 'chrome')"
    )
    parser.add_argument("--headless", action="store_true", default=None, help="Paksa mode headless")
    parser.add_argument("--no-headless", action="store_true", help="Buka jendela UI browser nyata")
    parser.add_argument("--proxy", type=str, default=None, help="Proxy opsional (http://user:pass@ip:port)")
    parser.add_argument("--status", action="store_true", help="Hanya tampilkan dashboard status akun")
    parser.add_argument("--checkin-only", action="store_true", help="Hanya jalankan Daily Check-In cepat via API")
    parser.add_argument("--register-only", action="store_true", help="Hanya jalankan registrasi akun baru via browser")
    args = parser.parse_args()

    if args.status:
        show_dashboard()
        return

    mode = "all"
    if args.checkin_only:
        mode = "checkin"
    elif args.register_only:
        mode = "register"

    if args.no_headless:
        headless = False
    elif args.headless is not None:
        headless = args.headless
    else:
        headless = config.HEADLESS_BROWSER

    try:
        asyncio.run(auto_run(browser_type=args.browser, headless=headless, proxy=args.proxy, mode=mode))
    except KeyboardInterrupt:
        print("\n\nProses dihentikan oleh pengguna.")


if __name__ == "__main__":
    main()
