#!/usr/bin/env python3
"""
Parse NJ foreclosure CSV and apply rule-based categorization flags.
Usage: python3 parse_and_flag.py <csv_file>
Outputs JSON with total row count and array of flagged rows.
"""

import csv
import json
import sys
import re

# Each entry is a phrase; all significant words (len>4) must appear in the
# attorney name for it to match. Single-word entries match on that word alone.
TAX_ATTORNEYS = [
    # Pellegrino & Feldstein
    "pellegrino and feldstein",
    "pellegrino",
    "feldstein",
    # Gary Zeitz
    "gary zeitz",
    "zeitz",
    # Boudwin Ross Roy Leodori
    "boudwin ross leodori",
    "boudwin",
    "leodori",
    # Taylor & Keyser
    "taylor and keyser",
    "keyser",
    # Honig & Greenberg — "greenberg" alone is NOT a tax indicator
    "honig and greenberg",
    "honig greenberg",
    "honig",
    # Robert Del Vecchio
    "robert delvecchio",
    "delvecchio",
    "del vecchio",
    # Goldenberg Mackler Sayegh
    "goldenberg mackler sayegh",
    "goldenberg",
    "mackler",
    "sayegh",
    # Keith Bonchi (files under personal name, same firm as Goldenberg Mackler)
    "keith bonchi",
    "bonchi",
    # Lamb McErlane
    "lamb mcerlane",
    "mcerlane",
    # Anthony Velasquez — multiple confirmed misspellings in scraped data
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
    "simeone",
    "raynor",
    # Lacsina
    "patrick lacsina",
    "lacsina",
]

CONDO_KEYWORDS = [
    "association", "assoc", "asso", "hoa", "condo",
    "homeowners", "home owners", "community corporation",
]

# Plaintiffs containing any of these are financial entities, NOT condos —
# even if they also contain a condo keyword (e.g. "National Association" in a bank name)
BANK_EXCLUSIONS = [
    "bank", "trust", "national assoc", "national asso", "savings",
    "mortgage", "loan", "financial", "credit union", "fund",
    "llc", "corp", "fbo", "capital", "servic",
    "fifth third", "first", "federal",
]

# Plaintiff keywords that strongly suggest a financial/mortgage lender —
# if type=Tax but plaintiff is clearly a financial entity and attorney is not
# a known tax firm, flag as MISMATCH.
FINANCIAL_PLAINTIFF_KEYWORDS = [
    "capital", "fund", "mortgage", "lending", "investment", "asset",
    "reit", "holdings", "partners", "ventures",
]


def normalize(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


def fuzzy_match_tax(attorney):
    """Return the matched pattern string if this attorney is a known Tax firm, else None.
    All significant words (len>4) in a pattern must appear in the attorney name.
    This prevents 'Greenberg' alone from matching 'Honig Greenberg'.
    """
    n = normalize(attorney)
    n_words = set(n.split())
    for pattern in TAX_ATTORNEYS:
        sig_words = [w for w in pattern.split() if len(w) > 4]
        if sig_words and all(w in n_words for w in sig_words):
            return pattern
    return None


def is_condo_plaintiff(plaintiff):
    """Return True if plaintiff looks like a real condo/HOA entity."""
    n = normalize(plaintiff)
    if not any(kw in n for kw in CONDO_KEYWORDS):
        return False
    # Financial entities containing 'association' (e.g. 'Fifth Third National Asso')
    # are banks, not condos.
    if any(ex in n for ex in BANK_EXCLUSIONS):
        return False
    return True


def main():
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"

    rows = []
    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for i, row in enumerate(reader, start=2):
            if not any(row):
                continue

            def get(idx):
                return row[idx].strip() if idx < len(row) else ""

            # Correct column indices (0-based):
            # 6=Docket, 8=Plaintiff, 10=Attorney, 13=ForeclosureType
            docket       = get(6)
            plaintiff    = get(8)
            attorney     = get(10)
            current_type = get(13)

            flag      = None
            suggested = None
            reason    = None

            matched_attorney = fuzzy_match_tax(attorney)
            condo_plaintiff  = is_condo_plaintiff(plaintiff)

            if not current_type:
                # Uncategorized — suggest what it should be
                if matched_attorney:
                    suggested = "Tax"
                    reason = f"Attorney '{attorney}' matches known Tax firm '{matched_attorney}'"
                elif condo_plaintiff:
                    suggested = "Condo"
                    reason = f"Plaintiff '{plaintiff}' looks like a condo/HOA"
                else:
                    suggested = "Mortgage"
                    reason = "No Tax attorney or Condo keyword; likely Mortgage"
                flag = "UNCATEGORIZED"
            else:
                ct = current_type.lower()
                if matched_attorney and "tax" not in ct:
                    # Marked something other than Tax but attorney is a known Tax firm
                    flag = "MISMATCH"
                    suggested = "Tax"
                    reason = (f"Marked '{current_type}' but attorney '{attorney}' "
                              f"matches Tax firm '{matched_attorney}'")
                elif "condo" in ct and not condo_plaintiff:
                    # Marked Condo but plaintiff doesn't look like a real condo/HOA
                    flag = "MISMATCH"
                    suggested = "Mortgage"
                    reason = (f"Marked 'Condo' but plaintiff '{plaintiff}' is not a "
                              f"condo/HOA entity — likely a financial entity or MTG case")
                elif condo_plaintiff and "condo" not in ct and "association" not in ct:
                    # Plaintiff is a condo/HOA but not marked as Condo
                    flag = "MISMATCH"
                    suggested = "Condo"
                    reason = f"Plaintiff '{plaintiff}' looks like a condo/HOA but marked '{current_type}'"
                elif "tax" in ct and not matched_attorney:
                    # Marked Tax but attorney is not a known tax firm
                    pn = normalize(plaintiff)
                    if any(kw in pn for kw in FINANCIAL_PLAINTIFF_KEYWORDS):
                        flag = "MISMATCH"
                        suggested = "Mortgage"
                        reason = (f"Marked 'Tax' but attorney '{attorney}' is not a known Tax firm "
                                  f"and plaintiff '{plaintiff}' appears to be a financial/mortgage entity")

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
