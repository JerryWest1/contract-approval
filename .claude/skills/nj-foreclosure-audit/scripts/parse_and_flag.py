#!/usr/bin/env python3
"""
Parse NJ foreclosure CSV and apply rule-based categorization flags.
Usage: python3 parse_and_flag.py <csv_file>
Outputs JSON array of all rows with a 'flag' field for suspicious ones.
"""

import csv
import json
import sys
import re

TAX_ATTORNEYS = [
    # Pellegrino & Feldstein
    "pellegrino and feldstein",
    "pellegrino feldstein",
    # Gary Zeitz
    "gary c. zeitz",
    "gary zeitz",
    "zeitz",
    # Boudwin Ross Roy Leodori
    "boudwin ross roy leodori",
    "boudwin ross",
    # Taylor & Keyser
    "taylor and keyser",
    "taylor keyser",
    # Honig & Greenberg
    "honig and greenberg",
    "honig greenberg",
    # Robert Del Vecchio — confirmed missing; multiple spellings in use
    "robert a. delvecchio",
    "robert delvecchio",
    "delvecchio",
    "del vecchio",
    # Goldenberg Mackler — Keith Bonchi files under personal name, bypassing firm lookup
    "goldenberg, mackler, sayegh",
    "goldenberg mackler",
    "keith bonchi",
    "bonchi",
    # Lamb McErlane
    "lamb mcerlane",
    # Anthony Velasquez — confirmed misspellings appearing in scraped data
    "anthony l. velasquez",
    "anthony velasquez",
    "anthony valesquez",
    "anthony valazquez",
    "anthony valesuez",
    "velasquez",
    "valesquez",
    "valazquez",
    "valesuez",
    # Simeone & Raynor
    "simeone and raynor",
    "simeone raynor",
    # Lacsina
    "patrick o. lacsina",
    "patrick lacsina",
    "lacsina",
]

CONDO_KEYWORDS = ["association", "hoa", "condo", "homeowners", "home owners", "community corporation"]
BANK_EXCLUSIONS = ["bank", "trust", "national assoc", "savings", "mortgage", "loan", "financial",
                   "credit union", "fund", "llc", "corp", "fbo", "capital", "servic"]


def normalize(s):
    """Lowercase, strip punctuation for fuzzy matching."""
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


def fuzzy_match_tax(attorney):
    n = normalize(attorney)
    n_words = set(n.split())
    for pattern in TAX_ATTORNEYS:
        # Require significant words to match as whole words (not substrings)
        sig_words = [w for w in pattern.split() if len(w) > 4]
        if sig_words and any(w in n_words for w in sig_words):
            return pattern
    return None


def is_condo_plaintiff(plaintiff):
    n = normalize(plaintiff)
    if not any(kw in n for kw in CONDO_KEYWORDS):
        return False
    # Don't flag banks/financial entities that happen to contain "association"
    if any(ex in n for ex in BANK_EXCLUSIONS):
        return False
    return True


def main():
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"

    rows = []
    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        for i, row in enumerate(reader, start=2):
            if not any(row):
                continue

            # 0-indexed: col 7=Plaintiff, col 8=Attorney, col 12=ForeclosureType
            def get(idx):
                return row[idx].strip() if idx < len(row) else ""

            plaintiff = get(7)
            attorney = get(8)
            current_type = get(12)
            docket = get(6)

            flag = None
            suggested = None
            reason = None

            matched_attorney = fuzzy_match_tax(attorney)
            condo = is_condo_plaintiff(plaintiff)

            if not current_type:
                if matched_attorney:
                    suggested = "Tax"
                    reason = f"Attorney '{attorney}' matches known Tax attorney pattern '{matched_attorney}'"
                elif condo:
                    suggested = "Condo"
                    reason = f"Plaintiff '{plaintiff}' contains condo/HOA keyword"
                else:
                    suggested = "Mortgage"
                    reason = "No Tax attorney or Condo keyword found; likely Mortgage"
                flag = "UNCATEGORIZED"
            else:
                # Check for mismatches
                ct = current_type.lower()
                if matched_attorney and "tax" not in ct:
                    flag = "MISMATCH"
                    suggested = "Tax"
                    reason = f"Marked '{current_type}' but attorney '{attorney}' matches Tax pattern '{matched_attorney}'"
                elif condo and "condo" not in ct and "association" not in ct:
                    flag = "MISMATCH"
                    suggested = "Condo"
                    reason = f"Marked '{current_type}' but plaintiff '{plaintiff}' contains condo/HOA keyword"

            record = {
                "row": i,
                "docket": docket,
                "plaintiff": plaintiff,
                "attorney": attorney,
                "current_type": current_type,
                "suggested_type": suggested,
                "flag": flag,
                "reason": reason,
            }
            rows.append(record)

    flagged = [r for r in rows if r["flag"]]
    print(json.dumps({"total": len(rows), "flagged": flagged}, indent=2))


if __name__ == "__main__":
    main()
