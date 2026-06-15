import http.server, threading, urllib.parse, urllib.request, json, webbrowser
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

CLIENT_ID     = os.getenv("MS_CLIENT_ID")
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
TENANT        = "consumers"
REDIRECT_URI  = "http://localhost:8888/callback"
SCOPES        = "Mail.Read Mail.Send Calendars.Read Calendars.ReadWrite User.Read offline_access"
AUTH_URL      = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize"
TOKEN_URL     = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"

_code = [None]
_done = threading.Event()

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in p:
            _code[0] = p["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authorization successful! You can close this tab.</h2>")
            _done.set()
    def log_message(self, *a):
        pass

s = http.server.HTTPServer(("localhost", 8888), H)
t = threading.Thread(target=s.handle_request)
t.daemon = True
t.start()

params = urllib.parse.urlencode({
    "client_id": CLIENT_ID, "response_type": "code",
    "redirect_uri": REDIRECT_URI, "scope": SCOPES, "response_mode": "query"
})
webbrowser.open(f"{AUTH_URL}?{params}")
print("Browser opened — sign in with your Microsoft account and authorize Jarvis...")

_done.wait(120)

if not _code[0]:
    print("Timed out.")
    exit(1)

data = urllib.parse.urlencode({
    "client_id": CLIENT_ID,
    "code": _code[0],
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}).encode()
req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    with urllib.request.urlopen(req) as r:
        tokens = json.loads(r.read())
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print("Token exchange failed:", e.code, body)
    exit(1)

rt = tokens.get("refresh_token", "")
if rt:
    env = Path(".env").read_text(encoding="utf-8")
    lines = [f"MS_REFRESH_TOKEN={rt}" if l.startswith("MS_REFRESH_TOKEN=") else l for l in env.splitlines()]
    Path(".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Refresh token saved to .env!")
else:
    print("Error:", tokens)
