# Stage 2 — Comparable Sales & Suggested Sale Price

Adds a **one-page comp analysis** on top of the Stage-1 board report: finds
recently SOLD, renovated homes near the property, suggests a sale price from
them, and shows the resulting profit against your Stage-1 all-in / breakeven.

> Built on a **separate branch** (`claude/stage2-comps`). It does not touch the
> live Stage-1 tooling on `main` until you choose to merge it.

## What it produces
`<Property> - Comp Analysis <date>.pdf` — suggested price + range, profit at
that price vs. your all-in position and breakeven, and **6 comps (3 Zillow +
3 Redfin)** each with a Street View photo, sold price/date, $/sqft, beds/baths/
sqft/year, and distance. Plus `comps.json` (the raw data + notes).

## Data sources (honest status)
| Source | How | Needs |
|---|---|---|
| **Zillow** | RapidAPI Zillow endpoint (Zillow has no open public API) | RapidAPI key |
| **Redfin** | Redfin's `gis-csv` data endpoint (unofficial, ToS-gray, may break) | none |
| **Photos** | Google Street View Static API | Google Maps key |
| **--mock** | built-in sample comps, renders with no keys | none |

This is for your own comp research. It does **not** bypass CAPTCHAs or rotate
proxies; if a source blocks or changes, that source returns nothing and the run
says so in `comps.json` / `comps_NEEDS_REVIEW.txt` — it never invents a comp.
Listing photos are MLS-licensed, so the report uses Street View instead.

## One-time setup
1. **RapidAPI key** — sign up at rapidapi.com, subscribe to a Zillow data API
   (e.g. "Zillow.com" / "zillow-com1"), copy the key. Set its host in config.
2. **Google Maps key** — console.cloud.google.com → enable **Street View Static
   API** → create an API key.
3. `pip install reportlab`
4. Copy `comps\config_stage2.example.json` to `comps\config_stage2.json` and
   paste the keys (or set `RAPIDAPI_KEY` / `GOOGLE_MAPS_KEY` env vars). The real
   config is gitignored so keys never reach GitHub.

## Run it
```powershell
cd stage2\comps
# live:
python run_comps.py --address "52 Hawkin Road, Medford, NJ 08055" `
  --summary "..\..\outputs\52 Hawkin\summary.json" `
  --output  "..\..\outputs\52 Hawkin" `
  --property-name "52 Hawkin Road" --subject-sqft 1850
# demo with no keys:
python run_comps.py --address "52 Hawkin Road, Medford, NJ 08055" `
  --summary "..\..\outputs\52 Hawkin\summary.json" `
  --output  "..\..\outputs\52 Hawkin" --property-name "52 Hawkin Road" --mock
```
`--summary` is the Stage-1 `summary.json` (gives the profit/breakeven line).
`--subject-sqft` lets the suggestion use $/sqft; omit it to use median sale price.

## How the suggested price is derived
Median $/sqft of the chosen comps × subject sqft (range = inter-quartile $/sqft).
Then profit = `suggested x (1 - 6%) - all_in_position`, with breakeven shown for
context. All assumptions live in `config_stage2.json`.

## Notes / next steps
- The "renovated" filter is a keyword/condition heuristic on the listing data;
  tune `RENOVATED_KEYWORDS` in `run_comps.py`.
- Distance/2-mile filtering is best when the source returns lat/long; the Zillow
  endpoint's radius depends on the chosen provider.
- To make this fully automatic, the Stage-1 watcher could call `run_comps.py`
  after each board report — wire that once the live keys are confirmed.
