import asyncio
import os
import time
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

import config
from core.utils import generate_name_from_email, is_valid_evm_address, log


class SyqoraBrowser:
    """Automates registration, Cloudflare Turnstile handling, and EVM address setup."""

    def __init__(
        self,
        headless: bool = config.HEADLESS_BROWSER,
        proxy: Optional[str] = None,
        browser_type: str = config.BROWSER_TYPE
    ):
        self.headless = headless
        self.proxy = proxy
        self.browser_type = browser_type.lower()
        self.playwright = None
        self.camoufox_cm = None
        self.browser: Optional[Browser] = None

    async def start(self):
        proxy_dict = {"server": self.proxy} if self.proxy else None

        if self.browser_type == "camoufox":
            try:
                from camoufox.async_api import AsyncCamoufox
                log("Launching Camoufox Anti-Detect Browser (Firefox C++ engine)...", "INFO")
                
                launch_kwargs: Dict[str, Any] = {
                    "headless": self.headless,
                }
                if proxy_dict:
                    launch_kwargs["proxy"] = proxy_dict
                if getattr(config, "CAMOUFOX_GEOIP", False):
                    launch_kwargs["geoip"] = True

                self.camoufox_cm = AsyncCamoufox(**launch_kwargs)
                self.browser = await self.camoufox_cm.start()
                log("Camoufox browser initialized successfully!", "SUCCESS")
                return
            except Exception as e:
                log(f"Failed to initialize Camoufox: {e}. Falling back to standard Chromium...", "WARNING")
                self.browser_type = "chrome"

        # Standard Playwright Chromium / Chrome fallback
        self.playwright = await async_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1280,800",
        ]

        try:
            log(f"Launching standard browser (channel: {config.BROWSER_CHANNEL})...", "INFO")
            self.browser = await self.playwright.chromium.launch(
                channel=config.BROWSER_CHANNEL,
                headless=self.headless,
                args=launch_args,
                proxy=proxy_dict
            )
        except Exception:
            log("Falling back to bundled Chromium...", "INFO")
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=launch_args,
                proxy=proxy_dict
            )

    async def close(self):
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None

        if self.camoufox_cm:
            try:
                await self.camoufox_cm.__aexit__(None, None, None)
            except Exception:
                pass
            self.camoufox_cm = None

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    async def register_account(
        self,
        email: str,
        password: str,
        evm_address: str,
        referral_code: str = config.DEFAULT_REF_CODE,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute full registration flow:
        1. Open register page with referral
        2. Fill Name, Email, Password
        3. Solve/Bypass Cloudflare Turnstile (automated natively in Camoufox)
        4. Submit account creation
        5. Set Receiving Address & Confirm Address
        6. Return session cookies
        """
        if not self.browser:
            await self.start()

        # In Camoufox, do NOT override user_agent or viewport so C++ spoofing remains internally consistent
        if self.browser_type == "camoufox":
            context: BrowserContext = await self.browser.new_context()
        else:
            context: BrowserContext = await self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US"
            )

        page: Page = await context.new_page()
        account_name = name or generate_name_from_email(email)

        try:
            reg_url = f"{config.BASE_URL}/register?ref={referral_code}"
            log(f"Navigating to: {reg_url}", "STEP")
            await page.goto(reg_url, wait_until="networkidle", timeout=45000)

            # Wait for registration form inputs to mount
            await page.wait_for_selector("input#name", timeout=20000)
            await page.wait_for_selector("input#reg-email", timeout=15000)
            await page.wait_for_selector("input#reg-password", timeout=15000)

            log(f"Filling credentials for: {email} (Name: {account_name})", "INFO")
            await page.fill("input#name", account_name)
            await page.fill("input#reg-email", email)
            await page.fill("input#reg-password", password)

            submit_btn = await page.wait_for_selector("button[type='submit']", timeout=10000)
            await page.wait_for_timeout(1000)

            log("Submitting registration form & verifying Cloudflare Turnstile...", "STEP")
            if self.browser_type == "camoufox":
                log("Camoufox active: Cloudflare Turnstile will verify automatically...", "INFO")
            elif not self.headless:
                log("NOTE: If Cloudflare challenge box appears, please click it to verify.", "INFO")

            await submit_btn.click()

            # Wait for navigation away from /register or error response
            redirected = False
            for _ in range(40):
                await page.wait_for_timeout(1000)
                current_url = page.url
                if "/register" not in current_url:
                    redirected = True
                    break

                # Check if an alert/error appeared
                error_elem = await page.query_selector(".au-error, [role='alert']")
                if error_elem:
                    err_text = (await error_elem.inner_text()).strip()
                    if err_text:
                        log(f"Registration message on page: {err_text}", "WARNING")
                        low = err_text.lower()
                        if "already" in low or "signing in" in low or "unable to create" in low or "exists" in low:
                            return {
                                "success": False,
                                "email": email,
                                "error": f"Account already exists ({err_text})"
                            }
                        else:
                            return {
                                "success": False,
                                "email": email,
                                "error": err_text
                            }

            current_url = page.url
            log(f"Current page after registration: {current_url}", "INFO")

            # If not redirected to /profile, explicitly navigate to /profile
            if "/profile" not in current_url:
                log("Navigating to /profile to configure receiving address...", "STEP")
                await page.goto(f"{config.BASE_URL}/profile", wait_until="networkidle", timeout=25000)

            # Step 2: Set EVM Receiving Address
            wallet_saved = False
            if evm_address and is_valid_evm_address(evm_address):
                log(f"Setting EVM Receiving Address: {evm_address}", "STEP")
                try:
                    await page.wait_for_selector("input#receiving-wallet", timeout=15000)

                    # Check if edit button needs to be clicked
                    edit_btn = await page.query_selector("button[aria-label='Edit wallet address']")
                    if edit_btn:
                        await edit_btn.click()
                        await page.wait_for_timeout(500)

                    # Fill receiving wallet
                    await page.fill("input#receiving-wallet", evm_address.strip())

                    # Fill confirm receiving wallet
                    confirm_input = await page.query_selector("input[placeholder='Repeat your address']")
                    if confirm_input:
                        await confirm_input.fill(evm_address.strip())

                    await page.wait_for_timeout(1000)

                    # Click Save & continue button
                    save_btn = await page.query_selector("button[type='submit'], button:has-text('Save & continue')")
                    if save_btn:
                        await save_btn.click()
                        await page.wait_for_timeout(3000)
                        log("EVM Receiving Address submitted successfully!", "SUCCESS")
                        wallet_saved = True
                except Exception as e:
                    log(f"Browser wallet input note: {e}", "WARNING")
            else:
                log("No valid EVM address provided for this account. Skipping wallet input.", "WARNING")

            # Extract cookies
            cookies = await context.cookies()

            return {
                "success": True,
                "email": email,
                "name": account_name,
                "password": password,
                "wallet": evm_address,
                "wallet_saved": wallet_saved,
                "cookies": cookies,
                "registered_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            log(f"Registration failed for {email}: {e}", "ERROR")
            return {
                "success": False,
                "email": email,
                "error": str(e)
            }
        finally:
            await context.close()

    async def login_account(self, email: str, password: str) -> Dict[str, Any]:
        """
        Execute login flow on https://airdrop.syqora.app/login:
        1. Open login page
        2. Fill Email & Password
        3. Submit form & let Camoufox solve Cloudflare Turnstile
        4. Wait for redirect
        5. Extract session cookies
        """
        if not self.browser:
            await self.start()

        if self.browser_type == "camoufox":
            context: BrowserContext = await self.browser.new_context()
        else:
            context: BrowserContext = await self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US"
            )

        page: Page = await context.new_page()

        try:
            login_url = f"{config.BASE_URL}/login"
            log(f"Navigating to login: {login_url}", "STEP")
            await page.goto(login_url, wait_until="networkidle", timeout=35000)

            await page.wait_for_selector("input#email", timeout=15000)
            await page.wait_for_selector("input#password", timeout=15000)

            log(f"Entering login credentials for: {email}", "INFO")
            await page.fill("input#email", email)
            await page.fill("input#password", password)

            submit_btn = await page.wait_for_selector("button[type='submit']", timeout=10000)
            await page.wait_for_timeout(1000)

            log("Submitting login form & verifying Cloudflare Turnstile...", "STEP")
            await submit_btn.click()

            for _ in range(30):
                await page.wait_for_timeout(1000)
                if "/login" not in page.url:
                    break
                error_elem = await page.query_selector(".au-error, [role='alert']")
                if error_elem:
                    err_text = (await error_elem.inner_text()).strip()
                    if err_text:
                        log(f"Login error on page: {err_text}", "WARNING")
                        return {"success": False, "email": email, "error": err_text}

            if "/login" in page.url:
                return {"success": False, "email": email, "error": "Login timeout"}

            log(f"Successfully logged in as {email}! Redirected to: {page.url}", "SUCCESS")
            cookies = await context.cookies()
            return {
                "success": True,
                "email": email,
                "cookies": cookies,
                "logged_in_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            log(f"Login failed for {email}: {e}", "ERROR")
            return {"success": False, "email": email, "error": str(e)}
        finally:
            await context.close()
