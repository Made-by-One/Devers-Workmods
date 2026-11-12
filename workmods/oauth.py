"""GitHub OAuth device-less flow: local redirect server on ``localhost``.

The GitHub OAuth app must be configured with the callback
``http://localhost:8080``.
"""

from __future__ import annotations

import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from workmods.config import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, OAUTH_CALLBACK_PORT

SUCCESS_HTML = """<!DOCTYPE html>
<html><head><title>Authentication Successful</title>
<style>
body { background:#0a0a0b; color:#c9c5c7; font-family:Consolas,'Courier New',monospace;
       display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }
.container { text-align:center; border:1px solid #262326; padding:40px; background:#0e0d0f;
             border-radius:8px; box-shadow:0 4px 20px rgba(0,0,0,.5); }
h1 { color:#a78bfa; margin-bottom:10px; font-size:24px; }
p { color:#858080; font-size:14px; } .icon { font-size:40px; margin-bottom:20px; color:#a78bfa; }
</style></head>
<body><div class="container"><div class="icon">&#10003;</div>
<h1>Auth Successful</h1><p>You can close this window and return to Workmods.</p>
</div></body></html>"""

ERROR_HTML = """<!DOCTYPE html>
<html><head><title>Authentication Failed</title>
<style>
body { background:#0a0a0b; color:#c9c5c7; font-family:Consolas,'Courier New',monospace;
       display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }
.container { text-align:center; border:1px solid #5a1a1a; padding:40px; background:#1a0000;
             border-radius:8px; }
h1 { color:#ff8888; margin-bottom:10px; font-size:24px; }
p { color:#858080; font-size:14px; } .icon { font-size:40px; margin-bottom:20px; color:#ff8888; }
</style></head>
<body><div class="container"><div class="icon">&#10007;</div>
<h1>Auth Failed</h1><p>Could not authenticate. Please try again in the app.</p>
</div></body></html>"""


def authorize_url() -> str:
    return (
        "https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}&scope=repo"
    )


class OAuthServerThread(QThread):
    auth_success = pyqtSignal(str)
    auth_failed = pyqtSignal(str)

    def __init__(self, port: int = OAUTH_CALLBACK_PORT, timeout: int = 120, parent=None):
        super().__init__(parent)
        self.port = port
        self.timeout = timeout
        self._resolved = False

    def run(self) -> None:
        thread = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence stderr access logs
                pass

            def do_GET(self):  # noqa: N802 - http.server API
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                code = (query.get("code") or [None])[0]

                if parsed.path != "/" or not code:
                    self._respond(400, ERROR_HTML)
                    return

                token = self._exchange_code(code)
                if token:
                    thread._resolved = True
                    self._respond(200, SUCCESS_HTML)
                    thread.auth_success.emit(token)
                elif not thread._resolved:
                    thread._resolved = True
                    self._respond(400, ERROR_HTML)
                    thread.auth_failed.emit("GitHub rejected the authorization code.")

            def _exchange_code(self, code: str) -> str:
                try:
                    response = requests.post(
                        "https://github.com/login/oauth/access_token",
                        headers={"Accept": "application/json"},
                        data={
                            "client_id": GITHUB_CLIENT_ID,
                            "client_secret": GITHUB_CLIENT_SECRET,
                            "code": code,
                        },
                        timeout=20,
                    )
                    if response.status_code == 200:
                        return str(response.json().get("access_token") or "")
                except requests.RequestException:
                    pass
                return ""

            def _respond(self, status: int, html: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

        try:
            server = HTTPServer(("127.0.0.1", self.port), Handler)
        except OSError as exc:
            self.auth_failed.emit(f"Cannot listen on port {self.port}: {exc}")
            return

        server.timeout = 1
        deadline = time.time() + self.timeout
        try:
            while time.time() < deadline and not self.isInterruptionRequested():
                server.handle_request()
        finally:
            server.server_close()
            if not self._resolved and not self.isInterruptionRequested():
                self.auth_failed.emit("Login timed out — no authorization code received.")


__all__ = ["OAuthServerThread", "authorize_url"]
