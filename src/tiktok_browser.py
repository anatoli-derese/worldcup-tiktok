"""
TikTok browser automation upload via Playwright.
No API approval needed. Login once, then automated uploads.

Usage:
  # One-time login (needs a visible browser - run on laptop or with VNC)
  python src/tiktok_browser.py login

  # Upload a video
  python src/tiktok_browser.py upload data/output/video.mp4 "caption #hashtags"

  # Programmatic use from pipeline:
  from src.tiktok_browser import upload_video
  ok, msg = upload_video("data/output/video.mp4", "my caption")
"""
import os
import sys
import time
import logging
from pathlib import Path

log = logging.getLogger("tiktok_browser")

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "tiktok_state.json"
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/creator-tools/upload"
TIKTOK_LOGIN_URL = "https://www.tiktok.com/login"


def login():
    """Open browser for manual TikTok login. Saves browser state to STATE_FILE."""
    from playwright.sync_api import sync_playwright

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.goto(TIKTOK_LOGIN_URL, wait_until="domcontentloaded")
        
        print("\n" + "=" * 60)
        print("LOG IN TO TIKTOK IN THE BROWSER WINDOW")
        print("Use QR code or email/phone login")
        print("The script will auto-detect when you're logged in")
        print("=" * 60 + "\n")

        # Wait for login - detect by URL change or cookie presence
        timeout = 300  # 5 minutes
        start = time.time()
        while time.time() - start < timeout:
            try:
                cookies = context.cookies()
                logged_in = any(
                    c.get("name") in ("sessionid", "sid_guard", "tt_webid") 
                    and c.get("value") 
                    for c in cookies
                )
                if logged_in and "login" not in page.url.lower():
                    print("\n✓ Login detected! Saving session...")
                    context.storage_state(path=str(STATE_FILE))
                    print(f"✓ Session saved to {STATE_FILE}")
                    browser.close()
                    return True
            except Exception:
                pass
            time.sleep(2)

        print("✗ Login timed out (5 minutes)")
        return False


def upload_video(video_path: str, caption: str, headless: bool = True) -> tuple:
    """Upload a video to TikTok using saved browser session.
    
    Returns (success: bool, message: str)
    """
    from playwright.sync_api import sync_playwright

    video_path = os.path.abspath(video_path)
    if not os.path.exists(video_path):
        return False, f"Video not found: {video_path}"
    
    if not STATE_FILE.exists():
        return False, f"No session state. Run 'python src/tiktok_browser.py login' first on a machine with a display."

    file_size = os.path.getsize(video_path)
    log.info(f"Uploading: {video_path} ({file_size / 1024 / 1024:.1f} MB)")
    log.info(f"Caption: {caption[:80]}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,  # Always headless for pipeline
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )
        
        try:
            page = context.new_page()
            
            # Navigate to upload page
            log.info("Navigating to upload page...")
            page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            
            # Check if we're still logged in
            if "login" in page.url.lower():
                return False, "Session expired. Re-run: python src/tiktok_browser.py login"
            
            # TikTok upload flow: file input is hidden, need to trigger it
            # The upload page typically has an iframe or a "Select file" area
            
            # Try finding file input - TikTok's upload uses a hidden <input type="file">
            file_input = page.locator('input[type="file"]').first
            
            if not file_input.count():
                # Sometimes the upload page loads inside an iframe
                for frame in page.frames:
                    file_input = frame.locator('input[type="file"]').first
                    if file_input.count():
                        log.info(f"Found file input in iframe: {frame.url[:80]}")
                        break
            
            if not file_input or not file_input.count():
                # Try clicking the upload area to trigger file dialog, then set file
                upload_area = page.locator('div:has-text("Select video"), div:has-text("Upload video"), [data-e2e="file-upload"]').first
                if upload_area.count():
                    upload_area.click()
                    time.sleep(1)
                    file_input = page.locator('input[type="file"]').first
            
            if not file_input or not file_input.count():
                # Last resort: set file on any file input in the page
                log.warning("Could not find file input via selectors, trying direct approach...")
                file_input = page.locator('input[type="file"]')
            
            if file_input.count():
                log.info("Setting video file...")
                file_input.set_input_files(video_path)
                time.sleep(5)  # Wait for upload processing
            else:
                return False, "Could not find file upload element. TikTok UI may have changed."
            
            # Wait for video to process - look for caption field appearing
            log.info("Waiting for video processing...")
            try:
                # Wait for caption/description field to appear (indicates upload done)
                caption_field = page.locator(
                    '[contenteditable="true"], [data-e2e="caption"], [data-e2e="post-description"], '
                    'div[role="textbox"], .public-DraftEditor-content'
                ).first
                caption_field.wait_for(state="visible", timeout=120000)
                log.info("Video processed, filling caption...")
                
                # Type caption
                caption_field.click()
                time.sleep(0.5)
                # Clear existing text
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                # Type new caption
                page.keyboard.type(caption)
                time.sleep(1)
            except Exception as e:
                log.warning(f"Caption field interaction failed: {e}")
                # Try alternative: just type into the page
                page.keyboard.type(caption)
                time.sleep(1)
            
            # Click post/publish button
            log.info("Clicking post button...")
            post_button = page.locator(
                'button:has-text("Post"), button:has-text("Publish"), '
                '[data-e2e="post-video"], [data-e2e="publish-button"]'
            ).first
            
            if post_button.count():
                post_button.click()
                log.info("Post button clicked")
                time.sleep(5)
                
                # Check for success
                if "upload" not in page.url.lower():
                    log.info("Upload appears successful (URL changed from upload page)")
                    browser.close()
                    return True, "Uploaded successfully"
                else:
                    # Might have a confirmation modal
                    confirm_btn = page.locator('button:has-text("Post"), button:has-text("Confirm")').first
                    if confirm_btn.count():
                        confirm_btn.click()
                        time.sleep(3)
                    browser.close()
                    return True, "Upload completed"
            else:
                return False, "Could not find post button. TikTok UI may have changed."
                
        except Exception as e:
            log.error(f"Upload error: {e}")
            # Take screenshot for debugging
            try:
                page.screenshot(path="/tmp/tiktok_error.png")
                log.info("Error screenshot saved to /tmp/tiktok_error.png")
            except:
                pass
            return False, str(e)
        finally:
            browser.close()


def is_configured() -> bool:
    """Check if browser session exists for TikTok uploads."""
    return STATE_FILE.exists()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python src/tiktok_browser.py login")
        print("  python src/tiktok_browser.py upload <video.mp4> [caption]")
        sys.exit(1)
    
    action = sys.argv[1]
    if action == "login":
        success = login()
        sys.exit(0 if success else 1)
    elif action == "upload":
        if len(sys.argv) < 3:
            print("Usage: python src/tiktok_browser.py upload <video.mp4> [caption]")
            sys.exit(1)
        vid = sys.argv[2]
        cap = sys.argv[3] if len(sys.argv) > 3 else "#WorldCup2026 #FIFA"
        ok, msg = upload_video(vid, cap)
        print(f"\n{'✓' if ok else '✗'} {msg}")
        sys.exit(0 if ok else 1)
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
