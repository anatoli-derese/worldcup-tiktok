"""
TikTok Content Posting API Client
Minimal, dependency-light client for uploading videos to TikTok.
Based on the official TikTok Content Posting API (Direct Post).

API docs: https://developers.tiktok.com/products/content-posting-api/

Requirements: pip install requests
"""

import json
import os
import time
import hashlib
import secrets
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import threading
import webbrowser

import requests

log = logging.getLogger("tiktok_api")

# ── Configuration ── (override these before use)
CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("TIKTOK_REDIRECT_URI", "http://localhost:5588/callback")
OAUTH_PORT = int(os.environ.get("TIKTOK_OAUTH_PORT", "5588"))
SCOPES = "user.info.basic,video.upload,video.publish"
TOKENS_FILE = "tokens.json"

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
UPLOAD_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
PUBLISH_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"

MAX_CAPTION_LENGTH = 2200


# ── OAuth Callback Handler ──

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles OAuth redirect callback on localhost."""
    auth_code = None
    state = None
    error = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            OAuthCallbackHandler.state = params.get("state", [None])[0]
            log.info(f"OAuth callback received code: {OAuthCallbackHandler.auth_code[:10]}...")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authorization successful!</h2>"
                b"<p>You can close this window and return to the app.</p>"
                b"</body></html>"
            )
        elif "error" in params:
            OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
            log.error(f"OAuth callback error: {OAuthCallbackHandler.error}")
            self.send_response(400)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress server logs


# ── API Client ──

class TikTokAPI:
    """TikTok Content Posting API wrapper."""

    def __init__(self, tokens_file=TOKENS_FILE):
        self.tokens_file = tokens_file
        self.tokens = self._load_tokens()

    def _load_tokens(self):
        if os.path.exists(self.tokens_file):
            with open(self.tokens_file, "r") as f:
                return json.load(f)
        return {}

    def _save_tokens(self):
        with open(self.tokens_file, "w") as f:
            json.dump(self.tokens, f, indent=2)

    # ── OAuth Flow ──

    def start_oauth(self, callback=None):
        """Start OAuth flow. Opens browser for user authorization.

        Args:
            callback: function(account_name, error) called when OAuth completes
        """
        if not CLIENT_KEY or not CLIENT_SECRET:
            msg = "Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET environment variables first"
            if callback:
                callback(None, msg)
            raise RuntimeError(msg)

        state = secrets.token_urlsafe(16)

        # PKCE: TikTok uses hex-encoded SHA256
        verifier_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
        code_verifier = "".join(secrets.choice(verifier_chars) for _ in range(64))
        code_challenge = hashlib.sha256(code_verifier.encode("ascii")).hexdigest()

        self._code_verifier = code_verifier

        # Reset handler state
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.state = None
        OAuthCallbackHandler.error = None

        params = {
            "client_key": CLIENT_KEY,
            "scope": SCOPES,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        auth_url = f"{AUTH_URL}?{urlencode(params)}"

        def _run_server():
            log.info(f"Starting OAuth callback server on port {OAUTH_PORT}")
            try:
                server = HTTPServer(("localhost", OAUTH_PORT), OAuthCallbackHandler)
                server.timeout = 120
                server.handle_request()
                server.server_close()
            except Exception as e:
                log.error(f"OAuth server error: {e}")
                if callback:
                    callback(None, f"Server error: {e}")
                return

            if OAuthCallbackHandler.error:
                log.error(f"OAuth error: {OAuthCallbackHandler.error}")
                if callback:
                    callback(None, OAuthCallbackHandler.error)
                return

            if not OAuthCallbackHandler.auth_code:
                log.warning("OAuth timed out — no code received")
                if callback:
                    callback(None, "Authorization timed out")
                return

            if OAuthCallbackHandler.state != state:
                log.error(f"State mismatch: expected={state}, got={OAuthCallbackHandler.state}")
                if callback:
                    callback(None, "State mismatch — possible CSRF attack")
                return

            log.info("Exchanging auth code for token...")
            try:
                account_name, error = self._exchange_code(OAuthCallbackHandler.auth_code)
                log.info(f"Token exchange result: account={account_name}, error={error}")
                if callback:
                    callback(account_name, error)
            except Exception as e:
                log.error(f"Token exchange exception: {e}", exc_info=True)
                if callback:
                    callback(None, f"Token exchange failed: {e}")

        thread = threading.Thread(target=_run_server, daemon=True)
        thread.start()
        webbrowser.open(auth_url)
        log.info(f"Opened browser for authorization. The script will wait up to 120 seconds for the callback.")

    def _exchange_code(self, code):
        """Exchange authorization code for access token."""
        log.info(f"Exchanging code {code[:10]}... for token")
        data = {
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": getattr(self, "_code_verifier", ""),
        }

        resp = requests.post(TOKEN_URL, data=data)
        log.info(f"Token response: status={resp.status_code}")
        log.debug(f"Token response body: {resp.text[:500]}")
        if resp.status_code != 200:
            return None, f"Token exchange failed: {resp.status_code} {resp.text}"

        result = resp.json()
        if "access_token" not in result:
            error = result.get("error", "unknown")
            error_desc = result.get("error_description", str(result))
            log.error(f"Token error: {error} — {error_desc}")
            return None, f"Token error: {error} — {error_desc}"

        open_id = result.get("open_id", "unknown")

        # Get username
        display_name = self._fetch_display_name(result["access_token"], open_id)
        account_name = display_name or open_id

        self.tokens[account_name] = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "expires_at": time.time() + result.get("expires_in", 86400),
            "refresh_expires_at": time.time() + result.get("refresh_expires_in", 31536000),
            "open_id": open_id,
            "scopes": result.get("scope", ""),
        }
        self._save_tokens()
        return account_name, None

    def _fetch_display_name(self, access_token, open_id):
        """Fetch user display name from TikTok."""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"fields": "display_name,avatar_url"}
            resp = requests.get(USER_INFO_URL, headers=headers, params=params)
            if resp.status_code == 200:
                data = resp.json().get("data", {}).get("user", {})
                name = data.get("display_name")
                if name:
                    return name
        except Exception:
            pass
        return None

    # ── Token Management ──

    def get_accounts(self):
        """Return list of connected account names."""
        return list(self.tokens.keys())

    def _ensure_token(self, account_name):
        """Refresh token if expired."""
        account = self.tokens.get(account_name)
        if not account:
            return None, "Account not found"

        if time.time() < account.get("expires_at", 0) - 60:
            return account["access_token"], None

        # Refresh
        data = {
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": account["refresh_token"],
        }
        resp = requests.post(TOKEN_URL, data=data)
        if resp.status_code != 200:
            return None, f"Token refresh failed: {resp.status_code}"

        result = resp.json()
        if "access_token" not in result:
            return None, f"Refresh error: {result}"

        account["access_token"] = result["access_token"]
        account["refresh_token"] = result.get("refresh_token", account["refresh_token"])
        account["expires_at"] = time.time() + result.get("expires_in", 86400)
        self._save_tokens()
        return account["access_token"], None

    # ── Upload Video ──

    def upload_video(self, account_name, video_path, caption,
                     privacy="PUBLIC_TO_EVERYONE",
                     progress_callback=None):
        """Upload and publish a video to TikTok.

        Args:
            account_name: Account to post from (name from OAuth flow)
            video_path: Absolute path to MP4 video file
            caption: Video caption (max 2200 chars). Supports #hashtags.
            privacy: PUBLIC_TO_EVERYONE | MUTUAL_FOLLOW_FRIENDS | FOLLOWER_OF_CREATOR | SELF_ONLY
            progress_callback: Optional function(stage, percent, message)

        Returns:
            (publish_id, error): publish_id is None on failure, error is None on success
        """
        token, error = self._ensure_token(account_name)
        if error:
            return None, error

        file_size = os.path.getsize(video_path)
        if file_size == 0:
            return None, "Video file is empty"

        # Single chunk upload (works for files up to 64MB)
        chunk_size = file_size
        total_chunks = 1
        log.info(f"Upload: file_size={file_size}, chunk_size={chunk_size}, total_chunks={total_chunks}")

        if progress_callback:
            progress_callback("init", 0, "Initializing upload...")

        # Step 1: Initialize upload
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        body = {
            "post_info": {
                "title": caption[:MAX_CAPTION_LENGTH],
                "privacy_level": privacy,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }

        log.debug(f"Upload init body: {json.dumps(body, indent=2)}")
        resp = requests.post(UPLOAD_INIT_URL, headers=headers, json=body)
        log.info(f"Upload init response: {resp.status_code} {resp.text[:300]}")
        if resp.status_code != 200:
            return None, f"Upload init failed: {resp.status_code} {resp.text}"

        result = resp.json()
        if result.get("error", {}).get("code") != "ok":
            return None, f"Init error: {result.get('error', {}).get('message', str(result))}"

        publish_id = result["data"]["publish_id"]
        upload_url = result["data"]["upload_url"]

        if progress_callback:
            progress_callback("upload", 5, "Uploading video...")

        # Step 2: Upload video bytes
        with open(video_path, "rb") as f:
            chunk_data = f.read(chunk_size)
            chunk_headers = {
                "Content-Range": f"bytes 0-{len(chunk_data) - 1}/{file_size}",
                "Content-Type": "video/mp4",
            }
            resp = requests.put(upload_url, headers=chunk_headers, data=chunk_data)
            log.info(f"Upload response: {resp.status_code} {resp.text[:200]}")
            if resp.status_code not in (200, 201, 206):
                return None, f"Upload failed: {resp.status_code} {resp.text}"

        if progress_callback:
            progress_callback("processing", 90, "Processing on TikTok...")

        # Step 3: Poll status until complete
        publish_status, error = self._poll_status(token, publish_id, progress_callback)
        if error:
            return publish_id, error

        return publish_id, None

    def _poll_status(self, token, publish_id, progress_callback=None, max_wait=120):
        """Poll publish status until complete or timeout."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        body = {"publish_id": publish_id}

        start_time = time.time()
        while time.time() - start_time < max_wait:
            resp = requests.post(PUBLISH_STATUS_URL, headers=headers, json=body)
            log.debug(f"Status poll: {resp.status_code} {resp.text[:300]}")
            if resp.status_code != 200:
                time.sleep(5)
                continue

            result = resp.json()
            status = result.get("data", {}).get("status", "UNKNOWN")
            log.info(f"Publish status: {status}")

            if progress_callback:
                progress_callback("processing", 95, f"Status: {status}")

            if status == "PUBLISH_COMPLETE":
                return "PUBLISH_COMPLETE", None
            elif status == "FAILED":
                fail_reason = result.get("data", {}).get("fail_reason", "Unknown")
                return status, f"Publish failed: {fail_reason}"
            elif status in ("PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD", "SEND_TO_USER_INBOX"):
                time.sleep(5)
            else:
                time.sleep(5)

        return "TIMEOUT", "Status check timed out after 2 minutes"
