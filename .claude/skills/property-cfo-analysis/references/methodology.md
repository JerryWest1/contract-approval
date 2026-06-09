# Methodology — how the numbers are derived

This document is the audit trail behind every figure on the board PDF. It exists
so a board member, auditor, or partner can reproduce the result by hand.

## 1. Cost basis — "how much am I in it for"

The cost basis is the simple sum of **every dollar the owner has funded** into
the property, regardless of category:

```
total_cost_basis = Σ entry.amount
```

We deliberately cast a wide net (acquisition, CapEx, carrying/soft costs,
owner-funded operating shortfalls, fees) because the business question is *what
must we sell for to make a profit* — every dollar in must be recovered.

Dollars financed by a third-party lender are **not** owner basis. But when the
owner is the funder (member loan / "due to owner" account), each advance is an
entry and accrues interest.

## 2. Accrued interest — simple, actual/365, per entry

Interest is the owner's preferred return on capital. Each entry accrues
independently from the day it was funded:

```
days_out          = (as_of_date − entry.date)        # calendar days, ≥ 0
entry.interest    = entry.amount × rate × (days_out ÷ 365)
total_interest    = Σ entry.interest
```

- **Rate** defaults to **12% per year**. Override per entry with `interest_rate`
  when a loan doc or agreement specifies a different rate.
- **Day count** is **actual/365** (actual days elapsed over a 365-day year), per
  the owner's convention. This is *simple* interest — no compounding.
- Entries dated after the as-of date, or undated, accrue **zero** interest
  (flagged rather than guessed).

### Worked example
$100,000 funded on 2025-01-01, valued as of 2026-06-09:

```
days_out = 524
interest = 100,000 × 0.12 × (524 / 365) = $17,227.40
```

## 3. All-in position

```
all_in_position = total_cost_basis + total_accrued_interest
```

This is the full amount the owner must recover at sale to be made whole.

## 4. Breakeven sale price

A sale incurs selling costs (broker commission, closing, transfer tax) modeled
as a percentage of price, `selling_cost_pct` (default **6%**). Net proceeds must
equal the all-in position:

```
net_proceeds = price × (1 − selling_cost_pct)
set net_proceeds = all_in_position
⇒ breakeven_price = all_in_position ÷ (1 − selling_cost_pct)
```

### Worked example
All-in $1,750,000, selling costs 6%:

```
breakeven = 1,750,000 ÷ 0.94 = $1,861,702
```

## 5. Profit at a target price

```
selling_costs = price × selling_cost_pct
net_proceeds  = price − selling_costs
profit        = net_proceeds − all_in_position
roi_on_basis  = profit ÷ total_cost_basis
```

`roi_on_basis` expresses profit as a percentage of cash invested (excluding the
preferred return, which is already counted as a cost to recover).

## Edge cases & conventions
- **Negative `days_out`** (future-dated entry) → clamped to 0 interest.
- **`accrues_interest: false`** → entry counts toward basis but earns no return
  (e.g., non-refundable deposits, costs explicitly excluded from preferred
  return).
- **`selling_cost_pct ≥ 100%`** → breakeven undefined (returns null); investigate
  the input.
- **Rounding** is to the cent at each entry; totals are sums of rounded entries,
  matching how a ledger foots.
- All assumptions that aren't in the source documents must be written into
  `deal.json`'s `notes` and surfaced verbally to the user.
