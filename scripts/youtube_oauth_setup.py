#!/usr/bin/env python3
"""One-time OAuth setup for the YouTube uploader.

Run this ONCE on your Mac, then upload_to_youtube.py can run forever
(refresh token is long-lived).

Prerequisites:
  1. Create a Google Cloud project at https://console.cloud.google.com
  2. Enable "YouTube Data API v3" under APIs & Services → Library
  3. Create OAuth 2.0 Credentials → "OAuth client ID" → type "Desktop app"
  4. Click DOWNLOAD JSON → save as client_secret.json in the project root
     (next to this scripts/ folder)
  5. Add yourself as a "Test user" under APIs & Services → OAuth consent screen
     (required while the app is in "Testing" state — fine indefinitely for
      personal use, no review needed)

Then run:
    python scripts/youtube_oauth_setup.py

A browser window opens. Sign in with the Google account that owns the YouTube
channel, click "Allow" on the YouTube upload scope, and you're done.

Writes:
    token.json  (kept in project root; gitignored — DO NOT COMMIT)
"""

from __future__ import annotations
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import atomic_write_text  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLIENT_SECRET = PROJECT_ROOT / "client_secret.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]


def main() -> None:
    if not CLIENT_SECRET.exists():
        sys.exit(
            f"[FATAL] {CLIENT_SECRET} not found.\n\n"
            "  Steps:\n"
            "    1. https://console.cloud.google.com → create project\n"
            "    2. APIs & Services → Library → enable 'YouTube Data API v3'\n"
            "    3. APIs & Services → Credentials → Create Credentials\n"
            "         → OAuth client ID → Application type: Desktop app\n"
            "    4. DOWNLOAD JSON → save as client_secret.json in project root\n"
            "    5. APIs & Services → OAuth consent screen → add yourself as Test user\n"
            "    6. Re-run this script.\n"
        )

    if TOKEN_PATH.exists():
        print(f"[INFO] {TOKEN_PATH} already exists.")
        ans = input("Overwrite and re-run OAuth? [y/N] ").strip().lower()
        if ans != "y":
            print("Aborted. (Existing token left in place.)")
            return

    print("Opening browser for OAuth consent…")
    print("If a browser doesn't pop, copy the URL below and open it manually.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    # port=0 picks a random free port for the loopback redirect
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        authorization_prompt_message=(
            "Sign in with the Google account that owns the YouTube channel, "
            "then click Allow. Press Ctrl+C here to cancel.\n\n  → {url}\n"
        ),
        success_message="OAuth complete. You can close this browser tab.",
    )

    atomic_write_text(TOKEN_PATH, creds.to_json())
    print(f"\n✓ Saved {TOKEN_PATH}")
    print("  This file contains a long-lived refresh token. Do NOT commit it.")
    print("  Verify with: python scripts/upload_to_youtube.py --list")


if __name__ == "__main__":
    main()
