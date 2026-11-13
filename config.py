import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Syqora URLs & Settings
DEFAULT_REF_CODE = os.getenv("SYQORA_REF_CODE", "SIC6VCmb3Okl")
BASE_URL = "https://airdrop.syqora.app"
REGISTER_URL = f"{BASE_URL}/register?ref={DEFAULT_REF_CODE}"

# Default Password used if account doesn't specify one (min 6 chars required)
DEFAULT_PASSWORD = os.getenv("SYQORA_DEFAULT_PASSWORD", "SyqoraUser123!")

# Browser settings:
# BROWSER_TYPE: 'camoufox' (Recommended: anti-detect Firefox C++ engine, bypasses Cloudflare Turnstile automatically)
# or 'chrome' / 'chromium' (Standard Playwright browser)
BROWSER_TYPE = "camoufox"

# Headless mode:
# With Camoufox, headless=True is supported and automatically bypasses Cloudflare Turnstile.
# Set to False if you want to visually observe the browser window during registration.
HEADLESS_BROWSER = True

# Chrome specific setting (used only if BROWSER_TYPE is 'chrome')
BROWSER_CHANNEL = "chrome"

# Camoufox specific settings:
# Match proxy exit IP location/timezone if geoip is installed
CAMOUFOX_GEOIP = False

# Delays (in seconds) between multi-account actions to stay natural
MIN_DELAY_BETWEEN_ACCOUNTS = 3
MAX_DELAY_BETWEEN_ACCOUNTS = 7

# File Paths
ACCOUNTS_FILE = DATA_DIR / "accounts.txt"
EMAILS_FILE = DATA_DIR / "emails.txt"
WALLETS_FILE = DATA_DIR / "wallets.txt"
PROXIES_FILE = DATA_DIR / "proxies.txt"
SESSIONS_FILE = DATA_DIR / "sessions.json"
