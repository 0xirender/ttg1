"""
Configuration Module for Telegram Client Automation and Session Injection System.
Set your official Telegram API credentials and local clone endpoints here.
"""

import os


def _load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


_load_env_file()


def _get_int(key: str, default: int = 0) -> int:
    val = (os.getenv(key) or "").strip()
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# Telegram MTProto API Credentials (loaded securely from GitHub Action Secrets / Env Vars)
API_ID: int = _get_int("TELEGRAM_API_ID", 0)
API_HASH: str = (os.getenv("TELEGRAM_API_HASH") or "").strip()

# Local Telegram Web Clone Endpoint
LOCAL_WEB_URL: str = (os.getenv("LOCAL_WEB_URL") or "").strip() or "https://0xvarcel.github.io"

# Default Session Storage File
SESSION_FILE: str = (os.getenv("TELEGRAM_SESSION_FILE") or os.getenv("SESSION_FILE") or "").strip() or "session.dat"

# Channel Visit List Source (Remote Cloudflare Pages URL or Local File)
CHANNELS_SOURCE_URL: str = (os.getenv("CHANNELS_SOURCE_URL") or "").strip() or "https://chvisit.pages.dev/chvisit.json"

# Browser Configuration
BROWSER_WINDOW_SIZE = (1280, 800)
# Browser User-Agent:
# When set to None (default), the browser uses its authentic native User-Agent matching
# its installed version (Chrome 153+) and Client Hints (Sec-CH-UA). This eliminates
# the "Inconsistent Fingerprint" alert on Pixelscan and anti-bot systems.
USER_AGENT = os.getenv("TELEGRAM_USER_AGENT", None)

# Optional Proxy Configuration (Format: 'socks5://user:pass@ip:port' or None)
PROXY_URL = os.getenv("TELEGRAM_PROXY_URL", None)

# Simulation & Anti-Ban Parameters
SCROLL_MIN_PAUSE = 2.0
SCROLL_MAX_PAUSE = 5.5
RANDOM_MOUSE_DRIFT = True
