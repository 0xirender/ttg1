"""
Telethon StringSession Binary Decoder, Validator, and Session Manager.

Unpacks Telethon v1 URL-safe Base64 session strings into MTProto connection
parameters, validates active sessions via MTProto preflight check, and provides
an interactive first-time login generator that saves sessions to disk for future launches.
"""

import os
import base64
import ipaddress
import struct
from typing import Dict, Any, Optional, Tuple

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    HAS_TELETHON = True
except ImportError:
    HAS_TELETHON = False

import config


def decode_string_session(session_string: str) -> Dict[str, Any]:
    """
    Decodes a Telethon StringSession into its constituent MTProto connection elements.

    :param session_string: The raw StringSession (starts with '1').
    :return: Dictionary containing dc_id, ip_address, port, auth_key bytes and list.
    """
    cleaned = session_string.strip()
    if not cleaned:
        raise ValueError("Session string is empty.")

    # Drop Telethon version prefix '1'
    if cleaned.startswith("1"):
        encoded_data = cleaned[1:]
    else:
        encoded_data = cleaned

    # URL-safe Base64 decoding with necessary padding
    padding = "=" * (-len(encoded_data) % 4)
    data = base64.urlsafe_b64decode(encoded_data + padding)

    # Telethon v1 packing schemes
    if len(data) == 263:
        # IPv4: 1 byte DC, 4 bytes IP, 2 bytes port, 256 bytes auth_key
        dc_id, ip_bytes, port, auth_key = struct.unpack(">B4sH256s", data)
        ip_addr = str(ipaddress.IPv4Address(ip_bytes))
    elif len(data) == 275:
        # IPv6: 1 byte DC, 16 bytes IP, 2 bytes port, 256 bytes auth_key
        dc_id, ip_bytes, port, auth_key = struct.unpack(">B16sH256s", data)
        ip_addr = str(ipaddress.IPv6Address(ip_bytes))
    else:
        raise ValueError(
            f"Invalid session payload length ({len(data)} bytes). Expected 263 (IPv4) or 275 (IPv6)."
        )

    return {
        "dc_id": int(dc_id),
        "ip_address": ip_addr,
        "port": int(port),
        "auth_key_bytes": auth_key,
        "auth_key_list": list(auth_key),  # Standard list for JavaScript Uint8Array serialization
        "auth_key_hex": auth_key.hex(),
    }


def encode_string_session(dc_id: int, ip_address: str, port: int, auth_key: bytes) -> str:
    """
    Constructs a valid Telethon StringSession from raw parameters (useful for testing).
    """
    ip_obj = ipaddress.ip_address(ip_address)
    if ip_obj.version == 4:
        packed = struct.pack(">B4sH256s", dc_id, ip_obj.packed, port, auth_key)
    else:
        packed = struct.pack(">B16sH256s", dc_id, ip_obj.packed, port, auth_key)

    b64 = base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")
    return f"1{b64}"


def save_session_file(session_string: str, file_path: str = config.SESSION_FILE):
    """
    Saves the StringSession to disk for future launches.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(session_string.strip())
    print(f"[+] Saved valid session to '{file_path}' for future automatic launch.")


def load_session_file(file_path: str = config.SESSION_FILE) -> Optional[str]:
    """
    Loads saved StringSession from disk if available.
    """
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content.startswith("1"):
                    return content
        except Exception as e:
            print(f"[!] Warning reading '{file_path}': {e}")
    return None


async def preflight_session_check(
    session_string: str,
    api_id: int = config.API_ID,
    api_hash: str = config.API_HASH,
    proxy: Optional[tuple] = None
) -> Dict[str, Any]:
    """
    Performs a lightweight MTProto pre-flight ping using Telethon to verify
    the session key's validity and extract the authenticated user ID.
    """
    if not HAS_TELETHON:
        raise RuntimeError("Telethon library is not installed.")

    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
        proxy=proxy,
        device_model="Automation Client",
        system_version="Windows 10",
        app_version="1.0"
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            return {
                "authorized": False,
                "error": "Session key is not authorized or was revoked on the server."
            }

        me = await client.get_me()
        return {
            "authorized": True,
            "user_id": str(me.id),
            "first_name": me.first_name,
            "username": me.username,
            "phone": me.phone
        }
    except Exception as e:
        return {
            "authorized": False,
            "error": str(e)
        }
    finally:
        await client.disconnect()


async def interactive_login_and_save(
    api_id: int = config.API_ID,
    api_hash: str = config.API_HASH,
    session_file: str = config.SESSION_FILE,
    proxy: Optional[tuple] = None
) -> Tuple[str, str]:
    """
    First-time login workflow:
    Prompts the user interactively in the terminal for their phone number and login OTP,
    generates a persistent StringSession, and saves it to session_file for future launches.
    """
    if not HAS_TELETHON:
        raise RuntimeError("Telethon library is required for interactive login.")

    print("\n" + "=" * 65)
    print("TELEGRAM FIRST-TIME AUTHENTICATION (TELETHON LOGIN)")
    print("=" * 65)
    print(f"[*] API ID: {api_id}")
    print("[*] Please enter your phone number (+country_code...), OTP code,")
    print("    and 2FA password (if enabled) when prompted below:\n")

    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
        proxy=proxy,
        device_model="Automation Client",
        system_version="Windows 10",
        app_version="1.0"
    )

    await client.start()

    session_string = client.session.save()
    me = await client.get_me()
    user_id = str(me.id)
    user_display = f"{me.first_name or ''} {me.last_name or ''}".strip()
    print("\n[OK] Authentication successful!")
    print(f"     Account: {user_display} (@{me.username or 'no_username'})")
    print(f"     User ID: {user_id}")

    save_session_file(session_string, session_file)
    await client.disconnect()

    return session_string, user_id


async def resolve_active_session(
    session_arg: Optional[str] = None,
    session_file: str = config.SESSION_FILE,
    api_id: int = config.API_ID,
    api_hash: str = config.API_HASH,
    proxy: Optional[tuple] = None
) -> Tuple[str, str]:
    """
    Resolves an active session with full automatic fallback:
    1. If session_arg is provided: validates it; if valid, saves to file and returns.
    2. Else if session_file exists: reads and validates it; if valid, returns.
    3. If invalid or not found: prompts interactive login, saves to file, and returns.
    """
    # Check environment variable (e.g. TELEGRAM_SESSION from GitHub Secrets / CI)
    env_session = os.getenv("TELEGRAM_SESSION") or os.getenv("SESSION_STRING")
    if (not session_arg or not session_arg.strip()) and env_session and env_session.strip():
        print("[*] Found active session string from environment variable (TELEGRAM_SESSION)...")
        session_arg = env_session.strip()

    # 1. User provided command line or environment session
    if session_arg and session_arg.strip():
        print("[*] Checking provided session string...")
        check = await preflight_session_check(session_arg, api_id, api_hash, proxy)
        if check.get("authorized"):
            print(f"[OK] Session is VALID! User: {check.get('first_name')} (ID: {check.get('user_id')})")
            save_session_file(session_arg, session_file)
            return session_arg, check.get("user_id")
        else:
            print(f"[!] Provided session is INVALID or expired: {check.get('error')}")
            print("[*] Falling back to interactive login...")

    # 2. Check saved session file
    saved_session = load_session_file(session_file)
    if saved_session:
        print(f"[*] Found existing session file '{session_file}'. Validating...")
        check = await preflight_session_check(saved_session, api_id, api_hash, proxy)
        if check.get("authorized"):
            print(f"[OK] Existing session is VALID! User: {check.get('first_name')} (ID: {check.get('user_id')})")
            return saved_session, check.get("user_id")
        else:
            print(f"[!] Saved session in '{session_file}' is expired or revoked: {check.get('error')}")
            print("[*] Starting fresh login to generate a new session...")

    # 3. First time / Fallback interactive login
    print(f"[*] No valid active session found in '{session_file}'.")
    return await interactive_login_and_save(api_id, api_hash, session_file, proxy)


if __name__ == "__main__":
    import os
    print("[*] Running Session Decoder Self-Test...")
    dummy_key = os.urandom(256)
    dummy_session = encode_string_session(2, "149.154.167.51", 443, dummy_key)
    print(f"[+] Generated Test StringSession (truncated): {dummy_session[:30]}...")

    decoded = decode_string_session(dummy_session)
    assert decoded["dc_id"] == 2, "DC ID mismatch"
    assert decoded["ip_address"] == "149.154.167.51", "IP mismatch"
    assert decoded["port"] == 443, "Port mismatch"
    assert decoded["auth_key_bytes"] == dummy_key, "Auth key mismatch"
    assert len(decoded["auth_key_list"]) == 256, "Auth key list length mismatch"
    print("[OK] Session Decoder Self-Test Passed Successfully!")
