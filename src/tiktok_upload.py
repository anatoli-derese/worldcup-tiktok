#!/usr/bin/env python3
"""
Pipeline upload script for automated TikTok posting.
This is the script your pipeline calls after producing an MP4.

Usage:
    python3 pipeline_upload.py /data/worldcup-tiktok/data/output/video.mp4 "Match highlights #worldcup #fyp"

Requirements:
    - tokens.json from oauth_setup.py (run once on a machine with a browser)
    - Environment variables: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET
    - pip install requests

The script handles:
    - Token refresh (access tokens last 24h, refresh tokens last 365 days)
    - Single-chunk upload for files up to 64MB
    - Status polling until publish is complete
    - Error reporting with exit codes
"""

import os
import sys
import time
import logging
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tiktok_api import TikTokAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("pipeline_upload")


def progress_callback(stage, percent, message):
    """Print upload progress."""
    bar = "=" * (percent // 5) + "-" * (20 - percent // 5)
    print(f"\r[{bar}] {percent}% {message}", end="", flush=True)
    if percent >= 100:
        print()  # newline at end


def upload_video(video_path: str, caption: str, privacy: str = "PUBLIC_TO_EVERYONE", account: str = None):
    """Upload a video to TikTok. Called from the pipeline.
    
    Returns (publish_id, error) tuple.
    """
    video_path = os.path.abspath(video_path)
    if not os.path.exists(video_path):
        return None, f"Video file not found: {video_path}"
    
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        return None, "Video file is empty"
    
    file_size_mb = file_size / (1024 * 1024)
    log.info(f"Video: {video_path} ({file_size_mb:.1f} MB)")
    log.info(f"Caption: {caption[:80]}{'...' if len(caption) > 80 else ''}")
    
    api = TikTokAPI()
    accounts = api.get_accounts()
    if not accounts:
        return None, (
            "No accounts found. Run oauth_setup.py first on a machine with a browser, "
            "then copy tokens.json to this directory."
        )
    
    if account:
        if account not in accounts:
            return None, f"Account '{account}' not found. Available: {accounts}"
    else:
        account = accounts[0]
        if len(accounts) > 1:
            log.info(f"Using first account: {account}")
    
    return api.upload_video(
        account, video_path, caption, privacy=privacy,
        progress_callback=progress_callback,
    )


def main():
    """CLI entry point for manual uploads."""
    parser = argparse.ArgumentParser(
        description="Upload a video to TikTok via the Content Posting API"
    )
    parser.add_argument(
        "video_path",
        help="Path to MP4 video file (e.g., data/output/video.mp4)",
    )
    parser.add_argument(
        "caption",
        nargs="?",
        default="",
        help="Video caption with #hashtags (max 2200 chars)",
    )
    parser.add_argument(
        "--privacy",
        default="PUBLIC_TO_EVERYONE",
        choices=[
            "PUBLIC_TO_EVERYONE",
            "MUTUAL_FOLLOW_FRIENDS",
            "FOLLOWER_OF_CREATOR",
            "SELF_ONLY",
        ],
        help="Video privacy setting (default: PUBLIC_TO_EVERYONE)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate everything without actually uploading",
    )
    parser.add_argument(
        "--account",
        default=None,
        help="Account name to use (if multiple accounts in tokens.json). Uses first account if not specified.",
    )
    args = parser.parse_args()

    # Validate video file
    video_path = os.path.abspath(args.video_path)
    if not os.path.exists(video_path):
        log.error(f"Video file not found: {video_path}")
        sys.exit(1)

    file_size = os.path.getsize(video_path)
    if file_size == 0:
        log.error("Video file is empty")
        sys.exit(1)

    file_size_mb = file_size / (1024 * 1024)
    log.info(f"Video: {video_path} ({file_size_mb:.1f} MB)")
    log.info(f"Caption: {args.caption[:80]}{'...' if len(args.caption) > 80 else ''}")
    log.info(f"Privacy: {args.privacy}")

    if args.dry_run:
        log.info("DRY RUN: Validation passed. No upload performed.")
        log.info("Remove --dry-run to upload.")
        return

    # Initialize API
    api = TikTokAPI()

    # Choose account
    accounts = api.get_accounts()
    if not accounts:
        log.error(
            "No accounts found. Run oauth_setup.py first on a machine with a browser, "
            "then copy tokens.json to this directory."
        )
        sys.exit(1)

    if args.account:
        if args.account not in accounts:
            log.error(f"Account '{args.account}' not found. Available: {accounts}")
            sys.exit(1)
        account = args.account
    else:
        account = accounts[0]
        if len(accounts) > 1:
            log.info(f"Using first account: {account} (use --account to choose another)")

    log.info(f"Uploading to account: {account}")

    # Upload
    start_time = time.time()
    publish_id, error = api.upload_video(
        account,
        video_path,
        args.caption,
        privacy=args.privacy,
        progress_callback=progress_callback,
    )

    elapsed = time.time() - start_time

    if error:
        log.error(f"Upload FAILED after {elapsed:.0f}s: {error}")
        sys.exit(1)

    log.info(f"Upload SUCCESS! Publish ID: {publish_id}")
    log.info(f"Completed in {elapsed:.0f}s")
    print(f"\nPUBLISH_ID={publish_id}")


if __name__ == "__main__":
    main()
