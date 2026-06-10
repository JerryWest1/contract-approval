---
name: nj-foreclosure-audit
description: >
  Weekly NJ foreclosure categorization audit. Finds the most recently modified
  CSV file inside any subfolder of the NJForeclosures Google Drive folder, reviews
  every row using Claude's intelligence (no API key needed), flags rows that are
  uncategorized or likely miscategorized (Tax / Condo / Mortgage), and emails a
  professional report to Jerry@westmarq.com. Trigger on requests like "run the
  foreclosure audit", "check the NJ foreclosure file", or "/nj-foreclosure-audit".
---

# NJ Foreclosure Categorization Audit

Every Monday at 2 PM, run this skill to catch rows your VBA macro missed —
misspelled attorney names, partial matches, blanks, or wrong category assignments.

## What it does

1. **Finds** the newest CSV in any subfolder under the NJForeclosures Google Drive folder
2. **Parses** every row (up to 500; samples if larger)
3. **Reviews** each row as a professional analyst:
   - Blank Foreclosure Type → suggest the correct one
   - Type assigned but attorney/plaintiff doesn't match the known list → flag it
   - Fuzzy/misspelled names that VBA missed → catch them
4. **Emails** a formatted HTML report to Jerry@westmarq.com

## Categorization Rules

### Foreclosure Type = TAX
Attorney (column 9, 0-indexed col 8) fuzzy-matches any of:
- Pellegrino And Feldstein
- Gary C. Zeitz Llc
- Boudwin Ross Roy Leodori Pc
- Taylor And Keyser
- Honig And Greenberg
- Robert A. Delvecchio
- Goldenberg, Mackler, Sayegh
- Lamb Mcerlane Pc
- Anthony L. Velasquez
- Simeone And Raynor
- Patrick O. Lacsina Law Offices

### Foreclosure Type = CONDO
Plaintiff (column 8, 0-indexed col 7) contains (case-insensitive):
- Association
- HOA
- Condo

### Foreclosure Type = MORTGAGE
Everything else (standard bank/lender foreclosures)

## Column Layout (1-indexed per the instructions doc)
1:Name | 2:Address | 3:City | 4:State | 5:Zip | 6:County
7:Docket No | 8:Plaintiff | 9:Attorney | 10:Orig Mtg | 11:Mtg Date
12:Lot/Block | 13:Foreclosure Type | 14:File Date

## Pipeline

```
Google Drive: search NJForeclosures for newest CSV in any subfolder
        ↓
Read CSV content
        ↓
scripts/parse_and_flag.py  →  flags.json  (rule-based pre-screen)
        ↓
You (Claude): review all rows + flags, apply fuzzy judgment
        ↓
scripts/build_email.py  →  email_body.html
        ↓
Gmail: send to Jerry@westmarq.com
```

## How to run it

### Step 1 — Find the newest CSV

Use Google Drive MCP tools:
1. Search for the NJForeclosures parent folder (shared drive: LIGHTHOUSE > Business Development EOS > EXPORTS > NJForeclosures)
2. List its subfolders — pick the one modified most recently (it will be a date-range folder like "05-29 06-05")
3. List files inside that subfolder — get the CSV file ID

### Step 2 — Download and parse

1. Use `mcp__Google_Drive__read_file_content` or `mcp__Google_Drive__download_file_content` to get the CSV text
2. Run the parse script:
```bash
python3 .claude/skills/nj-foreclosure-audit/scripts/parse_and_flag.py "<csv_content_file>" > /tmp/nj_flags.json
```
Or parse inline if the CSV is small enough to hold in context.

### Step 3 — Review as a professional analyst

Read every row in the CSV. For each row apply this logic:

**Rule-based (definitive):**
- If col 13 (Foreclosure Type) is blank/empty → needs categorization
- If col 9 (Attorney) exactly matches a Tax attorney → should be Tax
- If col 8 (Plaintiff) contains Association/HOA/Condo (case-insensitive) → should be Condo

**Fuzzy judgment (this is where you add value over VBA):**
- Common misspellings to catch: "Gary Zeitz", "Pellegrino & Feldstein", "Goldenberg Mackler", "Simeone & Raynor", "Boudwin Ross", "Honig & Greenberg"
- Abbreviations: "LLC" vs "Llc", "PC" vs "Pc", "&" vs "And"
- Partial matches: "Goldenberg" alone → still Tax
- HOA variants: "Homeowners Assoc", "Home Owners Association", "Condo Assn"
- Flag rows where the CURRENT type disagrees with what the rules say

Build a list of flagged rows:
```json
[
  {
    "row": 47,
    "docket": "F-12345-24",
    "plaintiff": "NJ Tax Lien LLC",
    "attorney": "Gary Zeitz LLC",
    "current_type": "",
    "suggested_type": "Tax",
    "reason": "Attorney 'Gary Zeitz LLC' is likely 'Gary C. Zeitz Llc' (Tax attorney)"
  }
]
```

### Step 4 — Build and send the email

```bash
python3 .claude/skills/nj-foreclosure-audit/scripts/build_email.py \
  /tmp/nj_flags.json \
  "<filename>" \
  "<total_rows>" \
  > /tmp/nj_email.html
```

Then use Gmail MCP to send:
- **To:** Jerry@westmarq.com
- **Subject:** `NJ Foreclosure Audit — <filename> — <date>`
- **Body:** the HTML from nj_email.html

### Step 5 — Report back

Tell the user:
- How many rows were reviewed
- How many were flagged and why
- Confirmation the email was sent
