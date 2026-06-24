#!/usr/bin/env python3
"""
One-time OAuth setup for Gmail sending.
Reads client_secret.json, opens browser for consent, writes .env with credentials.
Run once: python gmail_auth_setup.py
"""

import json
import os
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

CLIENT_SECRET_FILE = "client_secret.json"
ENV_FILE = ".env"
SCOPES = "https://www.googleapis.com/auth/gmail.send"
REDIRECT_URI = "http://localhost:8080"

if not os.path.exists(CLIENT_SECRET_FILE):
    print(f"ERROR: {CLIENT_SECRET_FILE} not found. Download it from Google Cloud Console first.")
    raise SystemExit(1)

with open(CLIENT_SECRET_FILE) as f:
    secret = json.load(f)

creds = secret.get("installed") or secret.get("web")
client_id = creds["client_id"]
client_secret = creds["client_secret"]

auth_url = (
    "https://accounts.google.com/o/oauth2/v2/auth?"
    + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    })
)

auth_code = []

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in params:
            auth_code.append(params["code"][0])
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Authorization complete. You can close this tab.</h2>")

    def log_message(self, *args):
        pass

print("Opening browser for Google authorization...")
webbrowser.open(auth_url)
server = HTTPServer(("localhost", 8080), Handler)
server.handle_request()

if not auth_code:
    print("ERROR: No authorization code received.")
    raise SystemExit(1)

token_data = urllib.parse.urlencode({
    "code": auth_code[0],
    "client_id": client_id,
    "client_secret": client_secret,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}).encode()

req = urllib.request.Request(
    "https://oauth2.googleapis.com/token",
    data=token_data,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    method="POST",
)
resp = json.loads(urllib.request.urlopen(req).read())

refresh_token = resp.get("refresh_token")
if not refresh_token:
    print("ERROR: No refresh token in response. Make sure prompt=consent was set.")
    raise SystemExit(1)

existing = {}
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

existing["GMAIL_CLIENT_ID"] = client_id
existing["GMAIL_CLIENT_SECRET"] = client_secret
existing["GMAIL_REFRESH_TOKEN"] = refresh_token

with open(ENV_FILE, "w") as f:
    for k, v in existing.items():
        f.write(f"{k}={v}\n")

print(f"Success! Credentials written to {ENV_FILE}")
print("You can now run: python send_email.py --test")
