"""
TikTok browser automation upload via Playwright.
No API approval needed. Login once, then automated uploads.

Usage:
  python src/tiktok_browser.py login    — one-time login (needs display)
  python src/tiktok_browser.py upload <video.mp4> [caption]
"""
import os
import sys
import time
import logging
from pathlib import Path

log = logging.getLogger("tiktok_browser")

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "tiktok_state.json"


def _login():
    """Open browser for manual TikTok login."""
    from playwright.sync_api import sync_playwright

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        page = context.new_page()
        page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")

        print("\n" + "=" * 60)
        print("LOG IN TO TIKTOK IN THE BROWSER WINDOW")
        print("=" * 60 + "\n")

        start = time.time()
        while time.time() - start < 300:
            cookies = context.cookies()
            logged = any(
                c.get("name") in ("sessionid", "sid_guard") and c.get("value")
                for c in cookies
            )
            if logged and "login" not in page.url.lower():
                print("\nLogged in! Saving session...")
                context.storage_state(path=str(STATE_FILE))
                print(f"Saved → {STATE_FILE}")
                browser.close()
                return True
            time.sleep(2)

        print("Timed out")
        return False


def upload_video(video_path: str, caption: str = "") -> tuple:
    """Upload video to TikTok via headless browser. Returns (ok, message)."""
    from playwright.sync_api import sync_playwright

    video_path = os.path.abspath(video_path)
    if not os.path.exists(video_path):
        return False, f"Not found: {video_path}"
    if not STATE_FILE.exists():
        return False, "No session — run login first"

    file_size = os.path.getsize(video_path)
    log.info(f"Upload: {video_path} ({file_size/1024/1024:.1f}MB)")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={"width": 1280, "height": 900},
        )
        
        try:
            page = context.new_page()

            # 1. Open upload page
            page.goto("https://www.tiktok.com/upload", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(
                'input[type="file"][accept*="video"]', state="attached", timeout=30000
            )

            if "login" in page.url.lower():
                return False, "Session expired — re-run login"

            # 2. Upload file
            log.info("Uploading video...")
            page.locator('input[type="file"][accept*="video"]').first.set_input_files(video_path)
            time.sleep(6)

            # 3. Dismiss modals
            modal = page.locator('[role="dialog"]')
            if modal.count():
                for t in ["Turn on", "Continue", "Confirm", "OK", "Got it"]:
                    btn = modal.locator(f'button:has-text("{t}")')
                    if btn.count():
                        btn.first.click()
                        time.sleep(2)
                        break
            
            page.keyboard.press("Escape")
            time.sleep(1)
            page.keyboard.press("Escape")
            time.sleep(1)

            # 4. Fill caption if needed
            if caption:
                try:
                    caption_field = page.locator(
                        '[contenteditable="true"], div[role="textbox"], .public-DraftEditor-content'
                    ).first
                    if caption_field.count():
                        caption_field.click(force=True)
                        time.sleep(0.5)
                        page.keyboard.press("Control+a")
                        page.keyboard.press("Delete")
                        page.keyboard.type(caption)
                        time.sleep(1)
                except Exception as e:
                    log.warning(f"Caption fill skipped: {e}")

            # 5. Click Post button
            btns = page.locator("button")
            post_btn = None
            for i in range(btns.count()):
                try:
                    if btns.nth(i).inner_text().strip().lower() == "post":
                        post_btn = btns.nth(i)
                        break
                except Exception:
                    continue

            if not post_btn:
                page.screenshot(path="/tmp/tiktok_no_post.png")
                return False, "Post button not found"

            post_btn.click(force=True)
            log.info("Post clicked")
            time.sleep(5)

            # 6. Handle confirmation
            time.sleep(3)
            for t in ["Post", "Confirm"]:
                c = page.locator(f'button:has-text("{t}")')
                if c.count():
                    for i in range(c.count()):
                        if c.nth(i).is_visible():
                            c.nth(i).click(force=True)
                            log.info(f"'{t}' confirmed")
                            time.sleep(3)
                            break

            log.info("Upload complete!")
            return True, "Uploaded successfully"

        except Exception as e:
            log.error(f"Error: {e}")
            try:
                page.screenshot(path="/tmp/tiktok_error.png")
            except Exception:
                pass
            return False, str(e)
        finally:
            browser.close()


def is_configured():
    return STATE_FILE.exists()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) < 2:
        print("Usage: python src/tiktok_browser.py login|upload <video> [caption]")
        sys.exit(1)

    if sys.argv[1] == "login":
        sys.exit(0 if _login() else 1)
    elif sys.argv[1] == "upload":
        vid = sys.argv[2] if len(sys.argv) > 2 else None
        if not vid:
            print("Missing video path")
            sys.exit(1)
        cap = sys.argv[3] if len(sys.argv) > 3 else ""
        ok, msg = upload_video(vid, cap)
        print(f"{'OK' if ok else 'FAIL'}: {msg}")
        sys.exit(0 if ok else 1)
