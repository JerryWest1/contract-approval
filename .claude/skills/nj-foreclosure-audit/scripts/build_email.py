#!/usr/bin/env python3
"""
Build an HTML email body for the NJ Foreclosure Audit report.
Outlook-compatible: uses table layout, no flexbox/grid.
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

uncategorized      = sum(1 for r in flagged if r.get("flag") == "UNCATEGORIZED")
mismatched         = sum(1 for r in flagged if r.get("flag") == "MISMATCH")
tax_suggested      = sum(1 for r in flagged if r.get("suggested_type") == "Tax")
condo_suggested    = sum(1 for r in flagged if r.get("suggested_type") == "Condo")
mortgage_suggested = sum(1 for r in flagged if r.get("suggested_type") == "Mortgage")

today = date.today().strftime("%B %d, %Y")

# Review button — shown when we have a file_id and flagged rows
review_btn_html = ""
if file_id and flagged:
    flags_b64 = base64.b64encode(json.dumps(flagged).encode()).decode()
    review_url = f"{N8N_REVIEW}?file_id={file_id}&flags={flags_b64}"
    review_btn_html = f"""
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0;">
    <tr>
      <td align="center">
        <!--[if mso]>
        <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
          href="{review_url}"
          style="height:48px;v-text-anchor:middle;width:300px;" arcsize="8%"
          stroke="f" fillcolor="#1a237e">
          <w:anchorlock/>
          <center style="color:#ffffff;font-family:Arial,sans-serif;font-size:16px;font-weight:bold;">
            &#10003; Review &amp; Confirm Flagged Rows
          </center>
        </v:roundrect>
        <![endif]-->
        <!--[if !mso]><!-->
        <a href="{review_url}"
           style="display:inline-block;padding:14px 36px;background:#1a237e;color:#ffffff;
                  font-size:16px;font-weight:bold;border-radius:5px;text-decoration:none;
                  font-family:Arial,sans-serif;">
          &#10003; Review &amp; Confirm Flagged Rows
        </a>
        <!--<![endif]-->
        <p style="margin:8px 0 0;font-size:12px;color:#888888;font-family:Arial,sans-serif;">
          Opens a page where you can uncheck any rows you disagree with before confirming.
          CSV in Google Drive and Invelo will be updated for all confirmed rows.
        </p>
      </td>
    </tr>
  </table>"""
elif flagged and not file_id:
    review_btn_html = """
  <p style="margin:16px 0;color:#c62828;font-family:Arial,sans-serif;font-size:13px;">
    <strong>Note:</strong> Review button unavailable — Drive file ID was not captured during this audit run.
  </p>"""


def stat_cell(value, label, color):
    return f"""<td align="center" style="padding:0 8px 0 0;">
        <table cellpadding="0" cellspacing="0" border="0"
               style="background:#ffffff;border:1px solid #dddddd;border-radius:4px;">
          <tr>
            <td align="center" style="padding:10px 20px;">
              <p style="margin:0;font-size:28px;font-weight:bold;color:{color};font-family:Arial,sans-serif;line-height:1.2;">{value}</p>
              <p style="margin:2px 0 0;font-size:12px;color:#666666;font-family:Arial,sans-serif;">{label}</p>
            </td>
          </tr>
        </table>
      </td>"""


rows_html = ""
for r in flagged:
    flag_color  = "#d32f2f" if r.get("flag") == "MISMATCH" else "#f57c00"
    flag_label  = r.get("flag", "")
    stype       = r.get("suggested_type", "")
    stype_color = {"Tax": "#1565c0", "Condo": "#6a1b9a", "Mortgage": "#2e7d32"}.get(stype, "#333333")
    current     = r.get("current_type", "") or "<em>blank</em>"
    rows_html += f"""
    <tr>
      <td style="padding:6px 8px;border-bottom:1px solid #eeeeee;color:#555555;font-family:Arial,sans-serif;font-size:13px;">{r.get('row','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eeeeee;font-family:Courier New,monospace;font-size:12px;">{r.get('docket','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eeeeee;font-family:Arial,sans-serif;font-size:13px;">{r.get('plaintiff','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eeeeee;font-family:Arial,sans-serif;font-size:13px;">{r.get('attorney','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eeeeee;color:#888888;font-family:Arial,sans-serif;font-size:13px;">{current}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eeeeee;font-weight:bold;color:{stype_color};font-family:Arial,sans-serif;font-size:13px;">{stype}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eeeeee;font-size:12px;color:#555555;font-family:Arial,sans-serif;">{r.get('reason','')}</td>
      <td style="padding:6px 8px;border-bottom:1px solid #eeeeee;font-size:11px;font-weight:bold;color:{flag_color};font-family:Arial,sans-serif;">{flag_label}</td>
    </tr>"""

if not flagged:
    rows_html = '<tr><td colspan="8" style="padding:20px;text-align:center;color:#4caf50;font-weight:bold;font-family:Arial,sans-serif;">No issues found — all rows look correctly categorized!</td></tr>'

html = f"""<!DOCTYPE html>
<html xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <!--[if mso]>
  <xml><o:OfficeDocumentSettings><o:AllowPNG/></o:OfficeDocumentSettings></xml>
  <![endif]-->
</head>
<body style="font-family:Arial,sans-serif;color:#333333;margin:0;padding:20px;background:#f9f9f9;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="max-width:1100px;margin:0 auto;background:#ffffff;">

    <!-- Header -->
    <tr>
      <td style="background:#1a237e;color:#ffffff;padding:20px 24px;border-radius:6px 6px 0 0;">
        <h2 style="margin:0;font-size:20px;font-family:Arial,sans-serif;color:#ffffff;">NJ Foreclosure Categorization Audit</h2>
        <p style="margin:6px 0 0;font-size:14px;font-family:Arial,sans-serif;color:#cccccc;">{filename} &nbsp;|&nbsp; {today}</p>
      </td>
    </tr>

    <!-- Stats bar -->
    <tr>
      <td style="background:#f5f5f5;padding:16px 24px;border-left:1px solid #dddddd;border-right:1px solid #dddddd;">
        <table cellpadding="0" cellspacing="0" border="0">
          <tr>
            {stat_cell(total, "Rows Reviewed", "#1a237e")}
            {stat_cell(len(flagged), "Total Flagged", "#d32f2f")}
            {stat_cell(uncategorized, "Uncategorized", "#f57c00")}
            {stat_cell(mismatched, "Mismatched", "#d32f2f")}
            {stat_cell(tax_suggested, "&#8594;&nbsp;Tax", "#1565c0")}
            {stat_cell(condo_suggested, "&#8594;&nbsp;Condo", "#6a1b9a")}
            {stat_cell(mortgage_suggested, "&#8594;&nbsp;Mortgage", "#2e7d32")}
          </tr>
        </table>
      </td>
    </tr>

    <!-- Review button row -->
    <tr>
      <td style="padding:0 24px;border-left:1px solid #dddddd;border-right:1px solid #dddddd;">
        {review_btn_html}
      </td>
    </tr>

    <!-- Flagged rows table -->
    <tr>
      <td style="padding:0 0 4px 0;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="border-collapse:collapse;font-size:13px;border:1px solid #dddddd;">
          <thead>
            <tr style="background:#e8eaf6;">
              <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;font-family:Arial,sans-serif;">Row</th>
              <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;font-family:Arial,sans-serif;">Docket</th>
              <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;font-family:Arial,sans-serif;">Plaintiff</th>
              <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;font-family:Arial,sans-serif;">Attorney</th>
              <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;font-family:Arial,sans-serif;">Current Type</th>
              <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;font-family:Arial,sans-serif;">Suggested</th>
              <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;font-family:Arial,sans-serif;">Reason</th>
              <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #9fa8da;font-family:Arial,sans-serif;">Issue</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="padding:12px 0 16px 0;">
        <p style="margin:0;font-size:12px;color:#999999;font-family:Arial,sans-serif;">
          Generated by NJ Foreclosure Audit skill &nbsp;|&nbsp; Lighthouse Community Services &nbsp;|&nbsp; {today}
        </p>
      </td>
    </tr>

  </table>

</body>
</html>"""

print(html)
