#!/usr/bin/env python3
"""
One-time OAuth setup script for TikTok Content Posting API.
Run this ONCE on a machine with a browser (your laptop).
Afterwards, copy the generated tokens.json to your headless server.

Usage:
    1. Set env vars: TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET
    2. Run: python3 oauth_setup.py
    3. Authorize in your browser
    4. Copy tokens.json to your server
"""

import os
import sys
import logging

# Add parent dir to path so we can import tiktok_api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tiktok_api import TikTokAPI, CLIENT_KEY, CLIENT_SECRET

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def main():
    print("=" * 60)
    print("TikTok Content Posting API - One-Time OAuth Setup")
    print("=" * 60)
    print()

    if not CLIENT_KEY or not CLIENT_SECRET:
        print("ERROR: Environment variables not set.")
        print()
        print("Set the following environment variables:")
        print("  export TIKTOK_CLIENT_KEY='your_client_key'")
        print("  export TIKTOK_CLIENT_SECRET='your_client_secret'")
        print()
        print("Get these from https://developers.tiktok.com/apps")
        print("  -> Your App -> Sandbox (or Production) -> Client Key / Client Secret")
        sys.exit(1)

    print(f"Using Client Key: {CLIENT_KEY[:8]}...")
    print(f"Redirect URI: http://localhost:5588/callback")
    print()
    print("A browser window will open. Please:")
    print("  1. Log in to TikTok")
    print("  2. Click 'Authorize' to grant permissions")
    print("  3. Wait for the success page")
    print()

    api = TikTokAPI()

    # Event to signal completion
    import threading
    done_event = threading.Event()
    result = {"account": None, "error": None}

    def on_complete(account_name, error):
        result["account"] = account_name
        result["error"] = error
        done_event.set()

    api.start_oauth(callback=on_complete)

    # Wait for OAuth to complete (max 120 seconds)
    if not done_event.wait(timeout=130):
        print()
        print("ERROR: OAuth timed out after 2 minutes.")
        print("Make sure you authorized the app in your browser.")
        sys.exit(1)

    if result["error"]:
        print()
        print(f"ERROR: Authorization failed: {result['error']}")
        sys.exit(1)

    print()
    print("=" * 60)
    print(f"SUCCESS! Account '{result['account']}' connected.")
    print(f"Tokens saved to: {api.tokens_file}")
    print()
    print("Next steps:")
    print("  1. Copy tokens.json to your headless server")
    print("  2. On your server, set the same env vars:")
    print("     export TIKTOK_CLIENT_KEY='...'")
    print("     export TIKTOK_CLIENT_SECRET='...'")
    print("  3. Run: python3 pipeline_upload.py data/output/video.mp4 'My caption #fyp'")
    print("=" * 60)


if __name__ == "__main__":
    main()
