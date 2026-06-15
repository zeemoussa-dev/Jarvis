"""
One-time Microsoft OAuth2 authorization.
Run:  python -m agents.outlook_auth
Opens browser for consent, captures the token, saves MS_REFRESH_TOKEN to .env
"""

import http.server
import threading
import urllib.parse
import urllib.request
import json
import webbrowser
import sys
from pathlib import Path

CLIENT_ID     = None
CLIENT_SECRET = None

TENANT        = "consumers"
REDIRECT_URI  = "http://localhost:8888/callback"
SCOPES        = "Mail.Read Mail.Send Calendars.Read Calendars.ReadWrite User.Read offline_access"
AUTH_URL      = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize"
TOKEN_URL     = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"

_code_received = threading.Event()
_auth_code = None


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authorization successful! You can close this tab.</h2>")
            _code_received.set()
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>Authorization failed. Check the terminal.</h2>")

    def log_message(self, *args):
        pass  # suppress server logs


def authorize():
    import config
    global CLIENT_ID, CLIENT_SECRET
    CLIENT_ID     = config.MS_CLIENT_ID
    CLIENT_SECRET = config.MS_CLIENT_SECRET

    params = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
        "scope":         SCOPES,
        "response_mode": "query",
    })
    url = f"{AUTH_URL}?{params}"

    server = http.server.HTTPServer(("localhost", 8888), _Handler)
    t = threading.Thread(target=server.handle_request)
    t.daemon = True
    t.start()

    print("[Auth] Opening browser for Microsoft sign-in...")
    webbrowser.open(url)

    _code_received.wait(timeout=120)
    if not _auth_code:
        print("[Auth] Timed out waiting for authorization.")
        sys.exit(1)

    # Exchange code for tokens
    data = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code":          _auth_code,
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code",
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read())

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print(f"[Auth] Error: {tokens}")
        sys.exit(1)

    # Write refresh token into .env
    env_path = Path(__file__).parent.parent / ".env"
    env_text = env_path.read_text(encoding="utf-8")
    if "MS_REFRESH_TOKEN=" in env_text:
        lines = env_text.splitlines()
        lines = [f"MS_REFRESH_TOKEN={refresh_token}" if l.startswith("MS_REFRESH_TOKEN=") else l for l in lines]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        env_path.write_text(env_text + f"\nMS_REFRESH_TOKEN={refresh_token}\n", encoding="utf-8")

    print(f"\n[Auth] Success! Refresh token saved to .env")
    print(f"[Auth] You can now run Jarvis normally.")


if __name__ == "__main__":
    authorize()
