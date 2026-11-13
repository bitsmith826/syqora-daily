import asyncio
import time
from typing import Dict, List, Optional

import config
from core.api import SyqoraAPI
from core.browser import SyqoraBrowser
from core.utils import Colors, is_valid_evm_address, load_sessions, log, random_sleep, save_sessions


class SyqoraBot:
    """Master workflow coordinator for Syqora Airdrop operations."""

    def __init__(
        self,
        headless: bool = config.HEADLESS_BROWSER,
        proxy: Optional[str] = None,
        browser_type: str = config.BROWSER_TYPE
    ):
        self.headless = headless
        self.proxy = proxy
        self.browser_type = browser_type
        self.sessions = load_sessions()

    async def register_and_onboard_account(
        self,
        account: Dict[str, str],
        referral_code: str = config.DEFAULT_REF_CODE,
        browser: Optional[SyqoraBrowser] = None
    ) -> Dict[str, any]:
        """
        Full onboarding flow for a single account:
        1. Register via browser + Set EVM Address
        2. Extract session cookies
        3. Perform API check: Quests & Daily Check-in
        4. Update and persist in sessions.json
        """
        email = account["email"]
        password = account.get("password") or config.DEFAULT_PASSWORD
        wallet = account.get("wallet") or ""

        log(f"==================================================", "INFO")
        log(f"Starting onboarding for: {email}", "STEP")
        if wallet:
            log(f"Target EVM Address: {wallet}", "INFO")

        # Check if already registered
        if email in self.sessions and self.sessions[email].get("registered"):
            log(f"Account {email} is already registered in sessions.json. Checking session...", "INFO")
            session_data = self.sessions[email]
            api = SyqoraAPI(session_data.get("cookies", {}), proxy=self.proxy)
            profile = api.get_user_profile()
            if profile:
                log(f"Session valid for {email}!", "SUCCESS")
                # Set wallet via API if not set yet
                if wallet and not profile.get("walletAddress"):
                    log(f"Updating EVM address via API...", "STEP")
                    api.update_receiving_address(wallet, name=profile.get("name"))

                # Complete Quests & Daily Check-in
                self._run_daily_tasks(api, email)
                return self.sessions[email]

        # Register via browser
        should_close_browser = False
        if browser is None:
            browser = SyqoraBrowser(headless=self.headless, proxy=self.proxy, browser_type=self.browser_type)
            await browser.start()
            should_close_browser = True

        result = await browser.register_account(
            email=email,
            password=password,
            evm_address=wallet,
            referral_code=referral_code
        )

        if not result.get("success"):
            err_msg = str(result.get("error", "")).lower()
            if any(k in err_msg for k in ["already", "exists", "signing in", "unable to create"]):
                log(f"Account {email} already registered on Syqora. Attempting login via browser...", "STEP")
                login_res = await browser.login_account(email=email, password=password)
                if login_res.get("success"):
                    result = login_res
                    result["name"] = result.get("name") or email.split("@")[0]
                else:
                    if should_close_browser:
                        await browser.close()
                    log(f"Login failed for {email}: {login_res.get('error')}", "ERROR")
                    return login_res
            else:
                if should_close_browser:
                    await browser.close()
                log(f"Failed to onboard account {email}: {result.get('error')}", "ERROR")
                return result

        if should_close_browser:
            await browser.close()

        # Test API access with returned cookies
        cookies = result.get("cookies", [])
        api = SyqoraAPI(cookies, proxy=self.proxy, browser_type=self.browser_type)
        user_profile = api.get_user_profile() or {}
        user_name = user_profile.get("name") or result.get("name") or email.split("@")[0]
        wallet_on_server = user_profile.get("walletAddress") or wallet

        # Fallback: if browser didn't set wallet, set via direct API call
        if wallet and not user_profile.get("walletAddress") and is_valid_evm_address(wallet):
            log("Saving EVM receiving address via API...", "STEP")
            api.update_receiving_address(wallet, name=user_name)

        # Run Quests and Daily Check-In
        tasks_result = self._run_daily_tasks(api, email)

        # Build session record
        session_record = {
            "email": email,
            "password": password,
            "name": user_name,
            "wallet": wallet_on_server,
            "registered": True,
            "registered_at": result.get("registered_at") or result.get("logged_in_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
            "cookies": api.get_cookies_dict(),
            "points": tasks_result.get("points", 0),
            "streak": tasks_result.get("streak", 0),
            "today_claimed": tasks_result.get("today_claimed", False),
            "last_checkin": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self.sessions[email] = session_record
        save_sessions(self.sessions)
        log(f"Account {email} saved successfully! Current Balance: {session_record['points']} PTS", "SUCCESS")
        return session_record

    def _run_daily_tasks(self, api: SyqoraAPI, email: str) -> Dict[str, any]:
        """Run daily check-in and auto-claim easy quests."""
        # 1. Daily Check-in
        checkin_res = api.daily_checkin()

        # 2. Easy Quests
        easy_handle = email.split("@")[0].replace(".", "_")[:15]
        quests_done = api.auto_complete_easy_quests(fallback_handle=easy_handle)

        # 3. Retrieve stats
        streak_info = api.get_streak_info() or {}
        airdrop_me = api.get_airdrop_me() or {}

        balance = airdrop_me.get("balance", 0)
        streak = streak_info.get("currentStreak", 0)
        today_claimed = streak_info.get("todayClaimed", False)

        claimed_str = f"{Colors.BRIGHT_GREEN}✔ CLAIMED{Colors.RESET}" if today_claimed else f"{Colors.BRIGHT_YELLOW}⏳ PENDING{Colors.RESET}"
        streak_str = f"{Colors.BRIGHT_MAGENTA}🔥 {streak} Hari{Colors.RESET}" if streak > 0 else "-"
        pts_str = f"{Colors.BRIGHT_GREEN}{balance:,} PTS{Colors.RESET}"
        log(f"Status: Saldo {pts_str} | Streak: {streak_str} | Check-In: {claimed_str}", "SUCCESS")

        return {
            "points": balance,
            "streak": streak,
            "today_claimed": today_claimed,
            "quests_done": quests_done
        }

    async def run_batch_onboarding(self, accounts: List[Dict[str, str]], referral_code: str = config.DEFAULT_REF_CODE):
        """Run onboarding across all loaded accounts sequentially."""
        log(f"Starting batch onboarding for {len(accounts)} accounts using [{self.browser_type.upper()}]...", "INFO")
        browser = SyqoraBrowser(headless=self.headless, proxy=self.proxy, browser_type=self.browser_type)
        await browser.start()

        try:
            for idx, account in enumerate(accounts, start=1):
                email = account.get("email")
                log(f"\n--- Processing account {idx}/{len(accounts)}: {email} ---", "INFO")
                await self.register_and_onboard_account(
                    account=account,
                    referral_code=referral_code,
                    browser=browser
                )
                if idx < len(accounts):
                    random_sleep()
        finally:
            await browser.close()
            log("Batch onboarding finished!", "SUCCESS")

    async def _reauth_via_browser(self, email: str, password: str) -> Optional[Dict[str, str]]:
        """Log in via Camoufox browser to recover completely expired session tokens."""
        log(f"Session fully expired for {email}. Auto-reauthenticating via {self.browser_type.upper()}...", "STEP")
        browser = SyqoraBrowser(headless=self.headless, proxy=self.proxy, browser_type=self.browser_type)
        await browser.start()
        try:
            res = await browser.login_account(email, password)
            if res.get("success"):
                cookies = res.get("cookies", [])
                cookie_dict = {c["name"]: c["value"] for c in cookies if "syqa_" in c["name"]}
                log(f"Re-authentication successful for {email}!", "SUCCESS")
                return cookie_dict
            else:
                log(f"Re-authentication failed for {email}: {res.get('error')}", "ERROR")
                return None
        finally:
            await browser.close()

    async def run_daily_checkin_all(self):
        """Ultra-fast headless API daily check-in with self-healing auto-token refresh."""
        self.sessions = load_sessions()
        if not self.sessions:
            log("No accounts found in sessions.json. Please register accounts first!", "WARNING")
            return

        log(f"Starting Daily Check-In for {len(self.sessions)} accounts via API...", "STEP")

        for idx, (email, data) in enumerate(self.sessions.items(), start=1):
            log(f"─── [{idx}/{len(self.sessions)}] {Colors.BOLD}{email}{Colors.RESET} ───", "INFO")
            try:
                cookies = data.get("cookies", {})
                password = data.get("password") or config.DEFAULT_PASSWORD
                if not cookies:
                    log(f"No cookies saved for {email}. Skipping.", "WARNING")
                    continue

                def on_cookie_update(new_cookies):
                    self.sessions[email]["cookies"] = new_cookies
                    save_sessions(self.sessions)

                api = SyqoraAPI(cookies, proxy=self.proxy, browser_type=self.browser_type, on_cookies_updated=on_cookie_update)
                user = api.get_user_profile()

                # Tier 2 Fallback: If both access token and refresh token failed, auto-login via Camoufox
                if not user:
                    new_cookie_dict = await self._reauth_via_browser(email, password)
                    if new_cookie_dict:
                        self.sessions[email]["cookies"] = new_cookie_dict
                        save_sessions(self.sessions)
                        api = SyqoraAPI(new_cookie_dict, proxy=self.proxy, browser_type=self.browser_type, on_cookies_updated=on_cookie_update)
                        user = api.get_user_profile()

                if not user:
                    log(f"Unable to validate session for {email}. Skipping.", "WARNING")
                    continue

                # Check EVM address
                wallet = data.get("wallet", "")
                if wallet and not user.get("walletAddress") and is_valid_evm_address(wallet):
                    api.update_receiving_address(wallet, name=user.get("name"))

                # Run daily tasks
                res = self._run_daily_tasks(api, email)

                # Update session record
                self.sessions[email]["points"] = res.get("points", data.get("points", 0))
                self.sessions[email]["streak"] = res.get("streak", data.get("streak", 0))
                self.sessions[email]["today_claimed"] = res.get("today_claimed", False)
                self.sessions[email]["last_checkin"] = time.strftime("%Y-%m-%d %H:%M:%S")

                save_sessions(self.sessions)
                time.sleep(1.5)
            except Exception as e:
                log(f"Error processing account {email}: {e}", "ERROR")

        log("Daily check-in for all accounts completed!", "SUCCESS")
