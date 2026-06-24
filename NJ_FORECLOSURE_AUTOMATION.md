# Automation — standing instructions for the NJ Foreclosure weekly audit

This file is the "job description" for the automated weekly run (a Claude Code
**Routine**). It reuses the `nj-foreclosure-audit` skill in this repo — the
routine is just the *trigger*; the recipe lives in `.claude/skills/nj-foreclosure-audit/`.

## The job (fired every Monday at 2 PM)

Using the **Google Drive** connector, look in the **NJForeclosures** export
folder inside the **LIGHTHOUSE** shared drive:
`LIGHTHOUSE > Business Development EOS > EXPORTS > NJForeclosures`

### Step 1 — Find the newest file

1. List all subfolders inside NJForeclosures (they are named by date range,
   e.g. `05-29 06-05`).
2. Pick the subfolder modified most recently.
3. Find the CSV file inside it (e.g. `05-29 06-05-.csv`).
4. **Record the file's Google Drive file ID** (the `id` field returned by the Drive API).
   You MUST save this exact ID — it is required in Step 4 to generate the review button.
5. Download its content.

### Step 2 — Parse and flag

Read every data row. The column layout is:

| Col (0-indexed) | Field |
|---|---|
| 6 | Foreclosure Docket |
| 8 | Plaintiff Name |
| 10 | Plaintiff Atty Firm |
| 13 | Foreclosure Case Type |

Apply these rules to flag rows:

**Foreclosure Type = Tax** when Attorney (col 10) fuzzy-matches any of:
- Pellegrino And Feldstein / Pellegrino / Feldstein
- Gary C Zeitz / Gary Zeitz / Zeitz
- Boudwin Ross Roy Leodori / Boudwin / Leodori
- Taylor And Keyser / Keyser
- Honig And Greenberg / Honig
- Robert A Delvecchio / Robert Delvecchio / Delvecchio / Del Vecchio
- Goldenberg Mackler Sayegh / Goldenberg / Mackler / Sayegh
- Keith Bonchi / Bonchi  ← files under personal name, same firm as Goldenberg Mackler
- Lamb Mcerlane / Mcerlane
- Anthony L Velasquez / Anthony Velasquez / Velasquez / Velazquez / Valesquez / Valazquez / Valesuez
- Simeone And Raynor / Simeone / Raynor
- Patrick O Lacsina / Patrick Lacsina / Lacsina

**Fuzzy matching rule:** split attorney name into individual words, compare
each word against the patterns above using whole-word matching (not substring).
Tolerance: names >8 chars allow 3 edit-distance; 5-8 chars allow 2; ≤4 chars
must match exactly. This prevents false positives (e.g. "Robertson" must NOT
match "Robert").

**Foreclosure Type = Condo** when Plaintiff (col 8) contains (case-insensitive):
- Association, Assoc, Asso, HOA, Condo, Homeowner, Community Corporation

**Exception:** if Plaintiff also contains Bank, Trust, Savings, Mortgage,
National Association, Fund, FBO, Capital, or Servic — it is a financial entity,
NOT a condo. Mark it MTG.

**Flag types:**
- `UNCATEGORIZED` — col 13 is blank; suggest the correct type
- `MISMATCH` — col 13 is filled but conflicts with the rules above
- `REVIEW` — attorney known but entity type is ambiguous (flag for human review)

### Step 3 — Run the parse script

```bash
python3 .claude/skills/nj-foreclosure-audit/scripts/parse_and_flag.py \
  <csv_file> > /tmp/nj_flags.json
```

Or parse inline if reading the CSV directly into memory.

### Step 4 — Build the HTML email

Replace `<google_drive_file_id>` with the actual Drive file ID captured in Step 1.
This is critical — without it, the "Review & Confirm" button will NOT appear in the email.

```bash
python3 .claude/skills/nj-foreclosure-audit/scripts/build_email.py \
  /tmp/nj_flags.json "<filename>" "<total_rows>" "<google_drive_file_id>" > /tmp/nj_email.html
```

Example (if the file ID were `1aBcD2eFgH`):
```bash
python3 .claude/skills/nj-foreclosure-audit/scripts/build_email.py \
  /tmp/nj_flags.json "06-16 06-22-.csv" "312" "1aBcD2eFgH" > /tmp/nj_email.html
```

### Step 5 — Send the report

Use `send_email.py` to send directly via Gmail API (no drafts):

```bash
python send_email.py \
  --to Jerry@westmarq.com \
  --subject "NJ Foreclosure Audit — <filename> — <today's date>" \
  --html /tmp/nj_email.html
```

Prerequisites: `.env` must contain `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`,
`GMAIL_REFRESH_TOKEN`. Run `python gmail_auth_setup.py` once to create it.
See `SETUPGMAILSEND.md` for the full one-time setup.

### Step 6 — Log and finish

Write a one-line summary to `nj_audit.log`:
```
[YYYY-MM-DD HH:MM] Audited <filename> — <N> rows, <M> flagged. Email sent.
```

## Guardrails

- **Never fabricate.** Only flag what the data actually shows.
- **Idempotent.** Check `nj_audit.log` — if the same filename was already
  audited this week, skip it.
- **One file per run.** Only process the single newest file each Monday.
- If the Drive folder cannot be reached or the file cannot be parsed, write
  `[YYYY-MM-DD HH:MM] ERROR: <reason>` to `nj_audit.log` and stop — do not
  send a partial or empty report.
