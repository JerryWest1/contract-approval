#!/usr/bin/env python3
"""
Daily email follow-up agent.

Reads yesterday's Gmail inbox, uses Claude to identify emails that need a
reply or action, then sends a professional HTML summary to your own inbox.
If nothing needs follow-up an "all clear" email is sent instead.

Run manually:  python3 email_agent.py
Scheduled via: install_cron.sh  (runs at 07:00 daily)
"""

import base64
import json
import os
import sys
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from openai import OpenAI
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token.json")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            raise RuntimeError(
                "No valid Gmail credentials found. "
                "Run setup_gmail_auth.py first to authorise the agent."
            )

    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Fetch emails
# ---------------------------------------------------------------------------

def fetch_yesterday_emails(service, target_date: date) -> list[dict]:
    """Return metadata + snippet for all inbox emails received on target_date."""
    next_day = target_date + timedelta(days=1)
    query = (
        f"after:{target_date.strftime('%Y/%m/%d')} "
        f"before:{next_day.strftime('%Y/%m/%d')} "
        f"in:inbox"
    )

    messages = []
    page_token = None

    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().messages().list(**kwargs).execute()
        batch = result.get("messages", [])
        messages.extend(batch)

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    emails = []
    for msg in messages:
        detail = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()

        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        emails.append({
            "id": msg["id"],
            "from": headers.get("From", "(unknown sender)"),
            "subject": headers.get("Subject", "(no subject)"),
            "date": headers.get("Date", ""),
            "snippet": detail.get("snippet", ""),
        })

    return emails


# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------

def analyze_emails_with_claude(emails: list[dict]) -> list[dict]:
    """
    Ask Claude to identify which emails need a follow-up.
    Returns enriched list: [{id, from, subject, date, reason}, ...]
    """
    if not emails:
        return []

    email_index = {e["id"]: e for e in emails}

    email_list_text = "\n\n".join(
        f"Email #{i + 1}\n"
        f"ID: {e['id']}\n"
        f"From: {e['from']}\n"
        f"Subject: {e['subject']}\n"
        f"Date: {e['date']}\n"
        f"Preview: {e['snippet']}"
        for i, e in enumerate(emails)
    )

    prompt = f"""You are an email assistant. Review the emails received yesterday and identify which ones genuinely need a follow-up reply or action from the recipient.

INCLUDE emails that have:
- Direct questions or requests awaiting an answer
- Action items or tasks assigned to the recipient
- Time-sensitive matters (deadlines, meetings, decisions)
- Contracts, proposals, or agreements needing a response
- Messages from real people expecting a reply

EXCLUDE:
- Automated notifications, system alerts, or receipts
- Marketing or promotional emails
- Newsletters or digest emails
- Calendar invitations already accepted/declined
- Emails where no action is required

For each email that needs follow-up, write a 1–2 sentence reason explaining exactly what action is needed.

Return ONLY a valid JSON array — no other text. If no emails need follow-up, return an empty array [].

Format:
[
  {{
    "id": "<original email ID>",
    "reason": "<1-2 sentence explanation of required action>"
  }}
]

Emails to analyse:
{email_list_text}"""

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
    response = client.chat.completions.create(
        model="meta-llama/llama-3.3-70b-instruct:free",
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content.strip()

    try:
        results = json.loads(raw)
    except json.JSONDecodeError:
        # Try extracting a JSON array if Claude wrapped it in prose
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start != -1 and end > start:
            try:
                results = json.loads(raw[start:end])
            except json.JSONDecodeError:
                results = None
        else:
            results = None

    if results is None:
        print(f"WARNING: Could not parse Claude response as JSON. Raw output:\n{raw}", file=sys.stderr)
        return []

    followups = []
    for item in results:
        email_id = item.get("id", "")
        if email_id in email_index:
            base = email_index[email_id]
            followups.append({
                "id": email_id,
                "from": base["from"],
                "subject": base["subject"],
                "date": base["date"],
                "reason": item.get("reason", ""),
            })

    return followups


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------

_BASE_STYLES = """
  body { margin:0; padding:0; background:#f4f6f8; font-family: Arial, Helvetica, sans-serif; }
  a { color:#1a73e8; text-decoration:none; }
"""

def _email_card(email: dict, index: int) -> str:
    gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{email['id']}"
    return f"""
    <tr>
      <td style="padding:8px 32px;">
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border:1px solid #e0e0e0; border-left:4px solid #fbbc04;
                      border-radius:4px; background:#ffffff;">
          <tr>
            <td style="padding:20px 24px;">
              <p style="margin:0 0 4px; font-size:11px; color:#888;
                        text-transform:uppercase; letter-spacing:0.5px;">From</p>
              <p style="margin:0 0 14px; font-size:15px; font-weight:bold;
                        color:#202124;">{email['from']}</p>

              <p style="margin:0 0 4px; font-size:11px; color:#888;
                        text-transform:uppercase; letter-spacing:0.5px;">Subject</p>
              <p style="margin:0 0 14px; font-size:15px; color:#202124;">{email['subject']}</p>

              <p style="margin:0 0 4px; font-size:11px; color:#888;
                        text-transform:uppercase; letter-spacing:0.5px;">Received</p>
              <p style="margin:0 0 14px; font-size:13px; color:#5f6368;">{email['date']}</p>

              <p style="margin:0 0 4px; font-size:11px; color:#888;
                        text-transform:uppercase; letter-spacing:0.5px;">Why it needs follow-up</p>
              <p style="margin:0 0 18px; font-size:14px; color:#333;
                        font-style:italic; line-height:1.5;">{email['reason']}</p>

              <a href="{gmail_link}"
                 style="display:inline-block; padding:10px 22px;
                        background:#1a73e8; color:#ffffff; font-size:14px;
                        font-weight:bold; border-radius:4px; text-decoration:none;">
                Open in Gmail &rarr;
              </a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr><td style="height:8px;"></td></tr>
    """


def build_followup_html(followups: list[dict], report_date: date) -> str:
    count = len(followups)
    noun = "email" if count == 1 else "emails"
    cards = "".join(_email_card(e, i) for i, e in enumerate(followups))
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Email Follow-up Summary</title>
  <style>{_BASE_STYLES}</style>
</head>
<body>
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#f4f6f8">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff; border-radius:8px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td bgcolor="#1a73e8" style="padding:32px; border-radius:8px 8px 0 0;">
            <p style="margin:0 0 6px; font-size:22px; font-weight:bold;
                      color:#ffffff; letter-spacing:-0.3px;">
              Daily Email Follow-up Summary
            </p>
            <p style="margin:0; font-size:14px; color:#c2d9ff;">
              Emails from {report_date.strftime('%A, %B %-d, %Y')} &middot; {count} {noun} need attention
            </p>
          </td>
        </tr>

        <!-- Intro -->
        <tr>
          <td style="padding:24px 32px 8px;">
            <p style="margin:0; font-size:14px; color:#5f6368; line-height:1.6;">
              The following {noun} from your inbox {('require' if count > 1 else 'requires')} a
              follow-up. Click <strong>Open in Gmail</strong> to go directly to the email.
            </p>
          </td>
        </tr>

        <!-- Email cards -->
        {cards}

        <!-- Spacer -->
        <tr><td style="height:16px;"></td></tr>

        <!-- Footer -->
        <tr>
          <td bgcolor="#f8f9fa"
              style="padding:20px 32px; border-top:1px solid #e0e0e0;
                     border-radius:0 0 8px 8px; font-size:12px; color:#9aa0a6;">
            Generated by Email Follow-up Agent &middot; {generated}
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def build_allclear_html(report_date: date, error_note: str = "") -> str:
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    error_block = ""
    if error_note:
        error_block = f"""
        <tr>
          <td style="padding:0 32px 24px;">
            <p style="margin:0; font-size:13px; color:#d93025; line-height:1.5;">
              <strong>Note:</strong> {error_note}
            </p>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All Clear — No Follow-ups Needed</title>
  <style>{_BASE_STYLES}</style>
</head>
<body>
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#f4f6f8">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff; border-radius:8px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td bgcolor="#1a73e8" style="padding:32px; border-radius:8px 8px 0 0;">
            <p style="margin:0 0 6px; font-size:22px; font-weight:bold; color:#ffffff;">
              Daily Email Follow-up Summary
            </p>
            <p style="margin:0; font-size:14px; color:#c2d9ff;">
              {report_date.strftime('%A, %B %-d, %Y')}
            </p>
          </td>
        </tr>

        <!-- All clear body -->
        <tr>
          <td align="center" style="padding:48px 32px 40px;">
            <div style="width:64px; height:64px; background:#e6f4ea;
                        border-radius:50%; margin:0 auto 20px;
                        display:flex; align-items:center; justify-content:center;
                        font-size:32px; line-height:64px; text-align:center;">
              &#10003;
            </div>
            <p style="margin:0 0 10px; font-size:22px; font-weight:bold;
                      color:#137333;">
              You&rsquo;re all caught up!
            </p>
            <p style="margin:0; font-size:15px; color:#5f6368; line-height:1.6;">
              No emails from yesterday require follow-up.<br>
              Enjoy your day!
            </p>
          </td>
        </tr>

        {error_block}

        <!-- Footer -->
        <tr>
          <td bgcolor="#f8f9fa"
              style="padding:20px 32px; border-top:1px solid #e0e0e0;
                     border-radius:0 0 8px 8px; font-size:12px; color:#9aa0a6;">
            Generated by Email Follow-up Agent &middot; {generated}
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Send email
# ---------------------------------------------------------------------------

def send_email(service, to_address: str, subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.chdir(SCRIPT_DIR)
    load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    user_email = profile["emailAddress"]

    yesterday = date.today() - timedelta(days=1)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching emails for {yesterday} ({user_email})...")

    emails = fetch_yesterday_emails(service, yesterday)
    print(f"  Found {len(emails)} email(s) in inbox.")

    if not emails:
        html = build_allclear_html(yesterday)
        subject = f"[Email Agent] All clear — {yesterday}"
        send_email(service, user_email, subject, html)
        print(f"  No emails found. All clear sent to {user_email}.")
        return

    print(f"  Analysing with Claude...")
    followups = analyze_emails_with_claude(emails)
    print(f"  {len(followups)} email(s) identified as needing follow-up.")

    if followups:
        noun = "email" if len(followups) == 1 else "emails"
        html = build_followup_html(followups, yesterday)
        subject = f"[Email Agent] {len(followups)} {noun} need{'s' if len(followups) == 1 else ''} follow-up — {yesterday}"
        send_email(service, user_email, subject, html)
        print(f"  Follow-up summary sent to {user_email}.")
    else:
        html = build_allclear_html(yesterday)
        subject = f"[Email Agent] All clear — {yesterday}"
        send_email(service, user_email, subject, html)
        print(f"  All clear sent to {user_email}.")


if __name__ == "__main__":
    main()
