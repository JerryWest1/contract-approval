#!/usr/bin/env python3
"""
Build an HTML email body for the NJ Foreclosure Audit report.
Usage: python3 build_email.py <flags_json> <filename> <total_rows> [file_id]
"""

import json
import sys
import base64
from datetime import date

flags_file = sys.argv[1]
filename   = sys.argv[2] if len(sys.argv) > 2 else "unknown"
total_rows = sys.argv[3] if len(sys.argv) > 3 else "?"
file_id    = sys.argv[4] if len(sys.argv) > 4 else ""

N8N_REVIEW = "https://n8n.srv958565.hstgr.cloud/webhook/nj-audit-review"

with open(flags_file) as f:
    data = json.load(f)

flagged = data.get("flagged", [])
total   = data.get("total", total_rows)

uncategorized    = sum(1 for r in flagged if r.get("flag") == "UNCATEGORIZED")
mismatched       = sum(1 for r in flagged if r.get("flag") == "MISMATCH")
tax_suggested    = sum(1 for r in flagged if r.get("suggested_type") == "Tax")
condo_suggested  = sum(1 for r in flagged if r.get("suggested_type") == "Condo")
mortgage_suggested = sum(1 for r in flagged if r.get("suggested_type") == "Mortgage")

today = date.today().strftime("%B %d, %Y")

# Build the review page URL: encode all flagged rows as base64 JSON
review_btn_html = ""
if file_id and flagged:
    flags_b64 = base64.b64encode(json.dumps(flagged).encode()).decode()
    review_url = f"{N8N_REVIEW}?file_id={file_id}&flags={flags_b64}"
    review_btn_html = f"""
  <div style="margin:20px 0;text-align:center;">
    <a href="{review_url}"
       style="display:inline-block;padding:14px 36px;background:#1a237e;color:white;
              font-size:16px;font-weight:bold;border-radius:5px;text-decoration:none;">
      &#10003; Review &amp; Confirm Flagged Rows
    </a>
    <p style="margin:8px 0 0;font-size:12px;color:#888;">
      Opens a page where you can uncheck any rows you disagree with before confirming.
      CSV in Google Drive and Invelo will be updated for all confirmed rows.
    </p>
  </div>"""

rows_html = ""
for r in flagged:
    flag_color  = "#d32f2f" if r.get("flag") == "MISMATCH" else "#f57c00"
    flag_label  = r.get("flag", "")
    stype       = r.get("suggested_type", "")
    stype_color = {"Tax": "#1565c0", "Condo": "#6a1b9a", "Mortgage": "#2e7d32"}.get(stype, "#333")
    rows_html += f"""
    <tr>
      <td style="padding:6px 8px;border-bottom:1px solid #eee;color:#555;">{r.get('row','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eee;font-family:monospace;font-size:12px;">{r.get('docket','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eee;">{r.get('plaintiff','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eee;">{r.get('attorney','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eee;color:#888;">{r.get('current_type','') or '<em>blank</em>'}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eee;font-weight:bold;color:{stype_color};">{stype}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eee;font-size:12px;color:#555;">{r.get('reason','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eee;font-size:11px;font-weight:bold;color:{flag_color};">{flag_label}</td>
    </tr>"""

if not flagged:
    rows_html = '<tr><td colspan="8" style="padding:20px;text-align:center;color:#4caf50;font-weight:bold;">No issues found — all rows look correctly categorized!</td></tr>'

html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;color:#333;max-width:1100px;margin:0 auto;padding:20px;">

  <div style="background:#1a237e;color:white;padding:20px 24px;border-radius:6px 6px 0 0;">
    <h2 style="margin:0;font-size:20px;">NJ Foreclosure Categorization Audit</h2>
    <p style="margin:6px 0 0;opacity:0.8;font-size:14px;">{filename} &nbsp;|&nbsp; {today}</p>
  </div>

  <div style="background:#f5f5f5;padding:16px 24px;border:1px solid #ddd;display:flex;gap:24px;flex-wrap:wrap;">
    <div style="text-align:center;padding:10px 20px;background:white;border-radius:4px;border:1px solid #ddd;">
      <div style="font-size:28px;font-weight:bold;color:#1a237e;">{total}</div>
      <div style="font-size:12px;color:#666;margin-top:2px;">Rows Reviewed</div>
    </div>
    <div style="text-align:center;padding:10px 20px;background:white;border-radius:4px;border:1px solid #ddd;">
      <div style="font-size:28px;font-weight:bold;color:#d32f2f;">{len(flagged)}</div>
      <div style="font-size:12px;color:#666;margin-top:2px;">Total Flagged</div>
    </div>
    <div style="text-align:center;padding:10px 20px;background:white;border-radius:4px;border:1px solid #ddd;">
      <div style="font-size:28px;font-weight:bold;color:#f57c00;">{uncategorized}</div>
      <div style="font-size:12px;color:#666;margin-top:2px;">Uncategorized</div>
    </div>
    <div style="text-align:center;padding:10px 20px;background:white;border-radius:4px;border:1px solid #ddd;">
      <div style="font-size:28px;font-weight:bold;color:#d32f2f;">{mismatched}</div>
      <div style="font-size:12px;color:#666;margin-top:2px;">Mismatched</div>
    </div>
    <div style="text-align:center;padding:10px 20px;background:white;border-radius:4px;border:1px solid #ddd;">
      <div style="font-size:28px;font-weight:bold;color:#1565c0;">{tax_suggested}</div>
      <div style="font-size:12px;color:#666;margin-top:2px;">→ Tax</div>
    </div>
    <div style="text-align:center;padding:10px 20px;background:white;border-radius:4px;border:1px solid #ddd;">
      <div style="font-size:28px;font-weight:bold;color:#6a1b9a;">{condo_suggested}</div>
      <div style="font-size:12px;color:#666;margin-top:2px;">→ Condo</div>
    </div>
    <div style="text-align:center;padding:10px 20px;background:white;border-radius:4px;border:1px solid #ddd;">
      <div style="font-size:28px;font-weight:bold;color:#2e7d32;">{mortgage_suggested}</div>
      <div style="font-size:12px;color:#666;margin-top:2px;">→ Mortgage</div>
    </div>
  </div>

  {review_btn_html}

  <table style="width:100%;border-collapse:collapse;margin-top:0;border:1px solid #ddd;font-size:13px;">
    <thead>
      <tr style="background:#e8eaf6;">
        <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;">Row</th>
        <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;">Docket</th>
        <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;">Plaintiff</th>
        <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;">Attorney</th>
        <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;">Current Type</th>
        <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;">Suggested</th>
        <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;">Reason</th>
        <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;">Issue</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>

  <p style="margin-top:16px;font-size:12px;color:#999;">
    Generated by NJ Foreclosure Audit skill &nbsp;|&nbsp; Lighthouse Community Services &nbsp;|&nbsp; {today}
  </p>
</body>
</html>"""

print(html)
