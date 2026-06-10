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
    "pellegrino and feldstein",
    "gary c. zeitz",
    "gary zeitz",
    "boudwin ross roy leodori",
    "taylor and keyser",
    "honig and greenberg",
    "robert a. delvecchio",
    "goldenberg, mackler, sayegh",
    "goldenberg mackler",
    "lamb mcerlane",
    "anthony l. velasquez",
    "simeone and raynor",
    "patrick o. lacsina",
    "lacsina law",
]

CONDO_KEYWORDS = ["association", "hoa", "condo", "homeowners", "home owners"]


def normalize(s):
    """Lowercase, strip punctuation for fuzzy matching."""
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


def fuzzy_match_tax(attorney):
    n = normalize(attorney)
    for pattern in TAX_ATTORNEYS:
        # Check if any significant word from the pattern appears
        words = [w for w in pattern.split() if len(w) > 3]
        if any(w in n for w in words):
            return pattern
    return None


def is_condo_plaintiff(plaintiff):
    n = normalize(plaintiff)
    return any(kw in n for kw in CONDO_KEYWORDS)


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
