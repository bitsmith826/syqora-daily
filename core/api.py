import random
import threading
from typing import Any, Callable, Dict, List, Optional
import requests

import config
from core.utils import log


class SyqoraAPI:
    """Direct API client for Syqora Airdrop platform with auto-token refresh."""

    _refresh_lock = threading.Lock()

    def __init__(
        self,
        cookies: Any,
        user_agent: Optional[str] = None,
        proxy: Optional[str] = None,
        browser_type: str = config.BROWSER_TYPE,
        on_cookies_updated: Optional[Callable[[Dict[str, str]], None]] = None
    ):
        self.session = requests.Session()
        self.base_url = config.BASE_URL
        self.browser_type = browser_type.lower()
        self.on_cookies_updated = on_cookies_updated

        # Browser fingerprint matching:
        # Camoufox uses Firefox Gecko engine, so API requests MUST mirror authentic Firefox headers
        # without Chromium Client Hints (Sec-Ch-Ua) to avoid anti-bot anomalies.
        if self.browser_type == "camoufox":
            self.user_agent = user_agent or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0"
            )
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.5",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        else:
            self.user_agent = user_agent or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }

        self.session.headers.update(headers)

        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

        self._set_cookies(cookies)

    def _set_cookies(self, cookies: Any):
        if isinstance(cookies, dict):
            for k, v in cookies.items():
                self.session.cookies.set(k, v, domain="airdrop.syqora.app")
        elif isinstance(cookies, list):
            # Playwright cookie format
            for c in cookies:
                self.session.cookies.set(
                    c["name"],
                    c["value"],
                    domain=c.get("domain", "airdrop.syqora.app"),
                    path=c.get("path", "/")
                )
        elif isinstance(cookies, str):
            for item in cookies.split(";"):
                if "=" in item:
                    k, v = item.strip().split("=", 1)
                    self.session.cookies.set(k, v, domain="airdrop.syqora.app")

    def get_cookies_dict(self) -> Dict[str, str]:
        """Extract dictionary of current cookies."""
        return requests.utils.dict_from_cookiejar(self.session.cookies)

    def refresh_session(self) -> bool:
        """
        POST /auth/refresh - Refresh short-lived syqa_access token using rotating syqa_refresh token.
        Thread-safe execution to protect single-use token rotation from race conditions.
        Automatically notifies on_cookies_updated callback to persist the new token.
        """
        with self._refresh_lock:
            try:
                url = f"{self.base_url}/auth/refresh"
                headers = {"Referer": f"{self.base_url}/"}
                res = self.session.post(url, json={}, headers=headers, timeout=15)
                if res.status_code == 200:
                    log("Session token successfully refreshed via /auth/refresh!", "SUCCESS")
                    if self.on_cookies_updated:
                        try:
                            self.on_cookies_updated(self.get_cookies_dict())
                        except Exception as e:
                            log(f"Callback on_cookies_updated error: {e}", "WARNING")
                    return True
                else:
                    log(f"Session refresh returned {res.status_code}: {res.text[:80]}", "WARNING")
                    return False
            except Exception as e:
                log(f"Error during session refresh: {e}", "WARNING")
                return False

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Execute request with automatic 401 retry via session refresh."""
        res = self.session.request(method, url, **kwargs)
        if res.status_code == 401 and "/auth/refresh" not in url:
            log("Access token expired (401). Attempting automatic session refresh...", "INFO")
            if self.refresh_session():
                # Retry once with newly acquired access token
                res = self.session.request(method, url, **kwargs)
        return res

    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """GET /auth/me - Check current authentication and profile."""
        try:
            url = f"{self.base_url}/auth/me"
            res = self._request("GET", url, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get("user") or data
            return None
        except Exception as e:
            log(f"Failed to fetch /auth/me: {e}", "ERROR")
            return None

    def get_airdrop_me(self) -> Optional[Dict[str, Any]]:
        """GET /airdrop/me - Fetch balance and airdrop status."""
        try:
            url = f"{self.base_url}/airdrop/me"
            res = self._request("GET", url, timeout=15)
            if res.status_code == 200:
                return res.json()
            return None
        except Exception as e:
            log(f"Failed to fetch /airdrop/me: {e}", "ERROR")
            return None

    def update_receiving_address(self, wallet_address: str, name: Optional[str] = None) -> bool:
        """PATCH /auth/profile - Set or update EVM receiving address."""
        try:
            url = f"{self.base_url}/auth/profile"
            headers = {"Referer": f"{self.base_url}/profile"}
            payload = {
                "name": name or "Syqora User",
                "walletAddress": wallet_address.strip()
            }
            res = self._request("PATCH", url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                log(f"EVM Address set successfully: {wallet_address}", "SUCCESS")
                return True
            else:
                log(f"Failed to set EVM Address ({res.status_code}): {res.text}", "WARNING")
                return False
        except Exception as e:
            log(f"Error setting EVM address: {e}", "ERROR")
            return False

    def get_streak_info(self) -> Optional[Dict[str, Any]]:
        """GET /airdrop/streak - Get daily streak and check-in eligibility."""
        try:
            url = f"{self.base_url}/airdrop/streak"
            res = self._request("GET", url, timeout=15)
            if res.status_code == 200:
                return res.json()
            return None
        except Exception as e:
            log(f"Error fetching streak: {e}", "ERROR")
            return None

    def daily_checkin(self) -> Dict[str, Any]:
        """POST /airdrop/check-in - Claim daily reward."""
        try:
            url = f"{self.base_url}/airdrop/check-in"
            headers = {"Referer": f"{self.base_url}/rewards"}
            res = self._request("POST", url, json={}, headers=headers, timeout=15)

            if res.status_code == 200:
                data = res.json()
                log("Daily Check-In: Berhasil diklaim (+10 PTS)!", "SUCCESS")
                return {"success": True, "data": data}
            else:
                err_text = res.text
                if "already" in err_text.lower():
                    log("Daily Check-In: Sudah diklaim hari ini (Up-to-date).", "INFO")
                    return {"success": True, "already_claimed": True}
                log(f"Daily Check-In ({res.status_code}): {err_text[:60]}", "WARNING")
                return {"success": False, "error": err_text}
        except Exception as e:
            log(f"Error during Daily Check-In: {e}", "ERROR")
            return {"success": False, "error": str(e)}

    def get_quests(self) -> Optional[Dict[str, Any]]:
        """GET /airdrop/quests - List active quest phases and tasks."""
        try:
            url = f"{self.base_url}/airdrop/quests"
            res = self._request("GET", url, timeout=15)
            if res.status_code == 200:
                return res.json()
            return None
        except Exception as e:
            log(f"Error fetching quests: {e}", "ERROR")
            return None

    def submit_task(
        self,
        task_id: str,
        evidence: Optional[str] = None,
        messenger_handle: Optional[str] = None,
        task_name: str = ""
    ) -> bool:
        """POST /airdrop/tasks/{task_id}/submit - Submit a task for reward."""
        try:
            url = f"{self.base_url}/airdrop/tasks/{task_id}/submit"
            headers = {"Referer": f"{self.base_url}/quests"}
            payload = {}
            if messenger_handle:
                payload["messengerHandle"] = messenger_handle
            elif evidence is not None:
                payload["evidence"] = evidence

            res = self._request("POST", url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                return True
            else:
                msg = ""
                try:
                    err_json = res.json()
                    msg = err_json.get("message") or err_json.get("error") or ""
                except Exception:
                    msg = res.text[:60]
                label = f"Quest '{task_name}'" if task_name else f"Task {task_id[:8]}"
                if res.status_code == 429:
                    log(f"{label}: Rate limited (akan dicoba lagi pada siklus berikutnya).", "INFO")
                elif any(k in msg.lower() for k in ["incomplete", "not open", "not linked"]):
                    log(f"{label}: Belum memenuhi syarat ({msg}).", "INFO")
                else:
                    log(f"{label} ({res.status_code}): {msg}", "WARN")
                return False
        except Exception as e:
            log(f"Error submitting task {task_id}: {e}", "ERROR")
            return False

    def auto_complete_easy_quests(self, fallback_handle: str = "syqora_user") -> int:
        """Fetch quests and submit all auto-approvable and social tasks."""
        quests_data = self.get_quests()
        if not quests_data or "phases" not in quests_data:
            return 0

        completed_count = 0
        phases = quests_data.get("phases", [])

        for phase in phases:
            tasks = phase.get("tasks", [])
            for task in tasks:
                task_id = task.get("id")
                task_name = task.get("title") or task.get("name") or task_id
                status = str(task.get("status", "")).lower()
                is_claimed = task.get("claimed", False) or status in ["completed", "claimed", "locked", "closed"]

                if is_claimed:
                    continue

                # Skip streak milestones, app downloads, and external bot links that require external interaction
                kind = str(task.get("kind", "")).lower()
                if kind in ["attendance", "streak", "starter", "full_start", "messenger", "telegram"]:
                    continue

                evidence = ""
                messenger_handle = None
                if kind == "messenger" or "messenger" in task_name.lower():
                    messenger_handle = fallback_handle
                elif task.get("evidenceType") == "x_username" or task.get("platform") == "x":
                    evidence = f"@{fallback_handle}"
                elif kind == "telegram":
                    evidence = f"@{fallback_handle}"

                success = self.submit_task(
                    task_id,
                    evidence=evidence if not messenger_handle else None,
                    messenger_handle=messenger_handle,
                    task_name=task_name
                )
                if success:
                    completed_count += 1
                    log(f"Quest selesai: {task_name} (+{task.get('reward', 0)} PTS)!", "SUCCESS")

        return completed_count
