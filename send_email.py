#!/usr/bin/env python3
"""
Send an HTML email via Gmail API using a stored refresh token.
Usage:
  python send_email.py --to Jerry@westmarq.com --subject "..." --html /tmp/nj_email.html
  python send_email.py --test   (sends a test email to yourself)
"""

import argparse
import base64
import email.mime.multipart
import email.mime.text
import json
import os
import sys
import urllib.parse
import urllib.request

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def get_access_token(client_id, client_secret, refresh_token):
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp["access_token"]


def send_email(access_token, to, subject, html_body):
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(email.mime.text.MIMEText(html_body, "html"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = json.dumps({"raw": raw}).encode()
    req = urllib.request.Request(
        SEND_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp.get("id")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", default="Jerry@westmarq.com")
    parser.add_argument("--subject", default="")
    parser.add_argument("--html", default="", help="Path to HTML file")
    parser.add_argument("--test", action="store_true", help="Send a test email")
    args = parser.parse_args()

    env = load_env()
    for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        if key not in env:
            print(f"ERROR: {key} not found in {ENV_FILE}. Run gmail_auth_setup.py first.")
            sys.exit(1)

    access_token = get_access_token(
        env["GMAIL_CLIENT_ID"],
        env["GMAIL_CLIENT_SECRET"],
        env["GMAIL_REFRESH_TOKEN"],
    )

    if args.test:
        html_body = "<h2>Test email from NJ Foreclosure runner</h2><p>If you see this, auto-send is working.</p>"
        subject = "NJ Foreclosure Audit — send test"
        to = args.to
    else:
        if not args.html or not args.subject:
            print("ERROR: --subject and --html are required (or use --test)")
            sys.exit(1)
        with open(args.html) as f:
            html_body = f.read()
        subject = args.subject
        to = args.to

    msg_id = send_email(access_token, to, subject, html_body)
    print(f"Sent. Gmail message ID: {msg_id}")


if __name__ == "__main__":
    main()
