"""
Main CLI Runner for Telegram Web Clone Session Injection and Automation.

Features:
- Automatic session validation: checks if an existing session is valid.
- First-time login generator: if no session exists or it is expired, prompts
  for phone number / OTP in the terminal via Telethon and saves to 'session.dat'.
- Full GUI browser automation: opens Chrome visibly on your screen.
- Humanized channel visit & DOM selector scroll simulation.

Usage Examples:
    # First time or normal run (uses session.dat or prompts login if missing):
    python run_session.py

    # With channel visit simulation:
    python run_session.py --channel "durov" --duration 30

    # With a specific session string:
    python run_session.py --session "1ApWapz..." --channel "@my_channel"
"""

import os
import argparse
import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

import config
from session_decoder import (
    decode_string_session,
    resolve_active_session,
    preflight_session_check,
    HAS_TELETHON
)
from browser_controller import TelegramWebController


def parse_args():
    parser = argparse.ArgumentParser(description="Telegram Web Clone Session Injector & Human Simulator")
    parser.add_argument(
        "--session", "-s",
        type=str,
        default=None,
        help="Optional Telethon StringSession. If omitted, checks session.dat or prompts first-time login."
    )
    parser.add_argument(
        "--session-file", "-f",
        type=str,
        default=config.SESSION_FILE,
        help=f"File path to store/read the session string (default: {config.SESSION_FILE})"
    )
    parser.add_argument(
        "--channel", "-c",
        type=str,
        default="",
        help="Channel username, link, or path to visit and simulate reading (e.g., 'durov' or '@durov')"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=30,
        help="Channel reading simulation duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--visit-list", "-l",
        type=str,
        default=config.CHANNELS_SOURCE_URL,
        help=f"Remote URL or local JSON file containing list of channels to visit continuously (default: {config.CHANNELS_SOURCE_URL})"
    )
    parser.add_argument(
        "--max-cycles", "-m",
        type=int,
        default=None,
        help="Maximum number of channel cycles to execute before cleanly exiting (default: None = continuous loop)"
    )
    parser.add_argument(
        "--cycle-break-min",
        type=int,
        default=120,
        help="Minimum break time in seconds between channel cycles (default: 120s = 2min)"
    )
    parser.add_argument(
        "--cycle-break-max",
        type=int,
        default=300,
        help="Maximum break time in seconds between channel cycles (default: 300s = 5min)"
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        default=config.LOCAL_WEB_URL,
        help=f"Local Telegram Web URL (default: {config.LOCAL_WEB_URL})"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (default: False - visible GUI Chrome window)"
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    print("=" * 70)
    print("TELEGRAM WEB CLONE AUTOMATION & HUMAN SIMULATOR")
    print("=" * 70)
    target_url = (args.url or "").strip() or (config.LOCAL_WEB_URL or "").strip() or "https://0xvarcel.github.io"
    print(f"[*] API ID: {config.API_ID}")
    print(f"[*] Target Web Clone: {target_url}")
    print(f"[*] Mode: {'Headless (Hidden)' if args.headless else 'GUI (Visible Chrome Window)'}")
    print("-" * 70)

    # 1. Resolve and Validate Session
    try:
        session_string, user_id = await resolve_active_session(
            session_arg=args.session,
            session_file=args.session_file,
            api_id=config.API_ID,
            api_hash=config.API_HASH
        )
    except Exception as e:
        print(f"\n[!] Error resolving session: {e}")
        sys.exit(1)

    # 2. Decode MTProto connection parameters
    try:
        decoded = decode_string_session(session_string)
        print(f"\n[+] Active Session Configuration:")
        print(f"    - Target DC: {decoded['dc_id']}")
        print(f"    - Server Endpoint: {decoded['ip_address']}:{decoded['port']}")
        print(f"    - User ID: {user_id}")
        print(f"    - Auth Key Hash: {decoded['auth_key_hex'][:16]}... (256 bytes)")
    except Exception as e:
        print(f"[!] Failed to parse active session: {e}")
        sys.exit(1)

    # 3. Launch GUI Browser & Inject Session
    print("\n" + "-" * 70)
    print("[*] Launching Chrome Browser...")
    controller = TelegramWebController(headless=args.headless)
    
    try:
        success = controller.inject_session(session_string, user_id=user_id, target_url=target_url)
        if not success:
            print("[!] Storage injection failed. Please check the browser console for details.")
            return

        dashboard_ready = controller.wait_for_dashboard(timeout=15)
        if not dashboard_ready:
            print("[!] Notice: Dashboard selector not immediately spotted.")
            print("    Please check the local web clone page in the open browser window.")

        # 4. Humanized Channel Reading / Multi-Channel Automation
        if args.channel:
            print("\n" + "-" * 70)
            controller.simulate_channel_reading(args.channel, duration_seconds=args.duration)
        elif args.visit_list:
            print("\n" + "-" * 70)
            controller.run_channel_visit_cycle(
                source=args.visit_list,
                cycle_break_min=args.cycle_break_min,
                cycle_break_max=args.cycle_break_max,
                max_cycles=args.max_cycles
            )

        print("\n" + "=" * 70)
        print("[OK] Automation task completed successfully!")
        print("=" * 70)

        # If max_cycles was set, exit cleanly without hanging
        if args.max_cycles is not None:
            return

        # Keep browser open until user presses Ctrl+C (only for infinite desktop runs)
        print("     The browser window will remain open.")
        print("     Press Ctrl+C in this terminal to exit and close the browser safely.")
        print("=" * 70)
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[*] Exiting on user interrupt...")

    finally:
        controller.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
