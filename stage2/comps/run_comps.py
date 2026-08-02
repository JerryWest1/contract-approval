#!/usr/bin/env python3
"""
run_comps.py — Stage 2: comparable-sales analysis + suggested sale price.

Finds recently SOLD, renovated comps near a subject property (3 from Zillow,
3 from Redfin), pulls a Street View photo of each, suggests a sale price from
the comps, layers it onto the Stage-1 profit/breakeven numbers, and renders a
one-page board PDF.

Data sources are pluggable and degrade gracefully:
  * Zillow  -> a RapidAPI Zillow endpoint   (RAPIDAPI_KEY / config)
  * Redfin  -> Redfin's gis-csv data endpoint (no key; ToS-gray, may break)
  * Photos  -> Google Street View Static API (GOOGLE_MAPS_KEY / config)
  * --mock  -> built-in sample comps so the report renders with no keys

Nothing here defeats CAPTCHAs or rotates proxies. If a source blocks or
changes, that comp source returns nothing and the run says so — it never
fabricates a comp.

Usage:
  python run_comps.py --address "52 Hawkin Road, Medford, NJ 08055" \
      --summary "../outputs/52 Hawkin/summary.json" \
      --output  "../outputs/52 Hawkin" [--mock]
"""
import argparse
import csv
import io
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

RENOVATED_KEYWORDS = ("renovated", "remodeled", "updated", "rebuilt",
                      "fully renovated", "new construction", "gut",
                      "restored", "modernized", "turnkey")


@dataclass
class Comp:
    source: str
    address: str
    sold_price: float
    sold_date: str = ""
    beds: float = 0
    baths: float = 0
    sqft: int = 0
    year_built: int = 0
    distance_mi: float = 0.0
    url: str = ""
    renovated: bool = False
    description: str = ""
    photo: Path | None = None

    @property
    def ppsf(self) -> float:
        return round(self.sold_price / self.sqft, 2) if self.sqft else 0.0


# --------------------------------------------------------------------------
# config / keys
# --------------------------------------------------------------------------
def load_config(path: Path) -> dict:
    cfg = {}
    if path and path.exists():
        cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.setdefault("radius_miles", 2)
    cfg.setdefault("sold_within_days", 90)
    cfg.setdefault("comps_per_source", 3)
    cfg.setdefault("selling_cost_pct", 0.06)
    cfg.setdefault("rapidapi_zillow_host", "zillow-com1.p.rapidapi.com")
    cfg["rapidapi_key"] = os.environ.get("RAPIDAPI_KEY", cfg.get("rapidapi_key", ""))
    cfg["google_maps_key"] = os.environ.get("GOOGLE_MAPS_KEY",
                                            cfg.get("google_maps_key", ""))
    return cfg


def _get(url: str, headers: dict | None = None, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers=headers or {
        "User-Agent": "Mozilla/5.0 (compatible; cfo-comps/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def is_renovated(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in RENOVATED_KEYWORDS)


# --------------------------------------------------------------------------
# Zillow (RapidAPI)
# --------------------------------------------------------------------------
def zillow_comps(address: str, cfg: dict, notes: list) -> list[Comp]:
    key = cfg.get("rapidapi_key")
    if not key:
        notes.append("Zillow: no RAPIDAPI_KEY set — skipped.")
        return []
    host = cfg["rapidapi_zillow_host"]
    params = urllib.parse.urlencode({
        "location": address, "status_type": "RecentlySold",
        "home_type": "Houses", "soldInLast": "3"})
    url = f"https://{host}/propertyExtendedSearch?{params}"
    try:
        data = json.loads(_get(url, headers={
            "X-RapidAPI-Key": key, "X-RapidAPI-Host": host}))
    except Exception as e:  # network / quota / shape change
        notes.append(f"Zillow: request failed ({e}). No comps from Zillow.")
        return []
    out = []
    for r in data.get("props", []):
        if not r.get("price") or not r.get("livingArea"):
            continue
        desc = r.get("description", "") or r.get("statusText", "")
        out.append(Comp(
            source="Zillow", address=r.get("address", ""),
            sold_price=float(r["price"]),
            sold_date=str(r.get("dateSold", "") or ""),
            beds=r.get("bedrooms", 0) or 0, baths=r.get("bathrooms", 0) or 0,
            sqft=int(r.get("livingArea", 0) or 0),
            year_built=int(r.get("yearBuilt", 0) or 0),
            url=("https://www.zillow.com" + r.get("detailUrl", ""))
                if r.get("detailUrl") else "",
            renovated=is_renovated(desc), description=desc))
    return out


# --------------------------------------------------------------------------
# Redfin (gis-csv data endpoint)
# --------------------------------------------------------------------------
def redfin_comps(address: str, cfg: dict, notes: list) -> list[Comp]:
    """Redfin exposes a CSV of search results at /stingray/api/gis-csv.
    We resolve the address to a Redfin region, then pull SOLD-3mo results.
    This is unofficial and may break or be blocked — it fails cleanly."""
    try:
        loc = urllib.parse.quote(address)
        auto = json.loads(_get(
            f"https://www.redfin.com/stingray/do/location-autocomplete"
            f"?location={loc}&v=2",
            headers={"User-Agent": "Mozilla/5.0"}).split(b"{", 1)[1].join(
                [b"{", b""]))
    except Exception as e:
        notes.append(f"Redfin: region lookup failed ({e}). No comps from Redfin.")
        return []
    try:
        region = auto["payload"]["sections"][0]["rows"][0]
        region_id = region["id"].split("_")[-1]
        region_type = region.get("type", 2)
    except Exception:
        notes.append("Redfin: could not resolve a region for the address.")
        return []
    csv_url = (f"https://www.redfin.com/stingray/api/gis-csv?al=1"
               f"&region_id={region_id}&region_type={region_type}"
               f"&sold_within_days={cfg['sold_within_days']}"
               f"&uipt=1&v=8")
    try:
        raw = _get(csv_url, headers={"User-Agent": "Mozilla/5.0"}).decode(
            "utf-8", "replace")
        rows = list(csv.DictReader(io.StringIO(raw)))
    except Exception as e:
        notes.append(f"Redfin: CSV pull failed/blocked ({e}). No comps from Redfin.")
        return []
    out = []
    for r in rows:
        try:
            price = float(r.get("PRICE") or 0)
            sqft = int(float(r.get("SQUARE FEET") or 0))
        except ValueError:
            continue
        if not price or not sqft:
            continue
        addr = ", ".join(x for x in [r.get("ADDRESS", ""), r.get("CITY", ""),
                         r.get("STATE OR PROVINCE", ""),
                         r.get("ZIP OR POSTAL CODE", "")] if x)
        out.append(Comp(
            source="Redfin", address=addr, sold_price=price,
            sold_date=r.get("SOLD DATE", ""),
            beds=float(r.get("BEDS") or 0), baths=float(r.get("BATHS") or 0),
            sqft=sqft, year_built=int(float(r.get("YEAR BUILT") or 0)),
            url=r.get("URL", ""), renovated=is_renovated(r.get("ADDRESS", ""))))
    return out


# --------------------------------------------------------------------------
# mock provider (renders with no keys)
# --------------------------------------------------------------------------
def researched_comps(path: Path, notes: list) -> list[Comp]:
    """Load comps from a JSON file of researched/verified sales.

    This is the compliant path: comps gathered by search or from your agent /
    MLS and recorded in a file, rather than scraped. Same schema as Comp.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("comps", data) if isinstance(data, dict) else data
    for n in (data.get("notes", []) if isinstance(data, dict) else []):
        notes.append(n)
    out = []
    for r in entries:
        out.append(Comp(
            source=r.get("source", "Research"), address=r.get("address", ""),
            sold_price=float(r.get("sold_price", 0)),
            sold_date=str(r.get("sold_date", "")),
            beds=r.get("beds", 0) or 0, baths=r.get("baths", 0) or 0,
            sqft=int(r.get("sqft", 0) or 0),
            year_built=int(r.get("year_built", 0) or 0),
            distance_mi=float(r.get("distance_mi", 0) or 0),
            url=r.get("url", ""), renovated=bool(r.get("renovated", False)),
            description=r.get("description", "")))
    return out


def mock_comps(address: str, cfg: dict, notes: list) -> list[Comp]:
    notes.append("MOCK DATA — illustrative comps only (no live sources).")
    base = [
        ("Zillow", "14 Birch Ln, Medford, NJ 08055", 372000, 1820, 3, 2, 1968, 0.6),
        ("Zillow", "8 Cedar Ct, Medford, NJ 08055", 415000, 2080, 4, 2.5, 1975, 1.1),
        ("Zillow", "121 Hartford Rd, Medford, NJ 08055", 358000, 1700, 3, 2, 1962, 1.7),
        ("Redfin", "27 Tuckerton Rd, Medford, NJ 08055", 389000, 1910, 3, 2.5, 1971, 0.9),
        ("Redfin", "5 Jackson Rd, Medford, NJ 08055", 442000, 2210, 4, 3, 1979, 1.4),
        ("Redfin", "63 Mill St, Medford, NJ 08055", 365000, 1755, 3, 2, 1965, 1.9),
    ]
    today = date.today()
    out = []
    for i, (src, addr, price, sqft, bd, ba, yr, dist) in enumerate(base):
        out.append(Comp(source=src, address=addr, sold_price=price, sqft=sqft,
                        beds=bd, baths=ba, year_built=yr, distance_mi=dist,
                        renovated=True,
                        sold_date=(today - timedelta(days=18 + i * 11)).isoformat(),
                        description="Fully renovated; updated kitchen & baths."))
    return out


# --------------------------------------------------------------------------
# Street View photos
# --------------------------------------------------------------------------
def fetch_photos(comps: list[Comp], cfg: dict, tmp: Path, notes: list):
    key = cfg.get("google_maps_key")
    if not key:
        notes.append("Photos: no GOOGLE_MAPS_KEY — comps shown without images.")
        return
    tmp.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(comps):
        params = urllib.parse.urlencode({
            "size": "600x400", "location": c.address, "fov": "80", "key": key})
        try:
            img = _get(f"https://maps.googleapis.com/maps/api/streetview?{params}")
            p = tmp / f"comp_{i}.jpg"
            p.write_bytes(img)
            c.photo = p
        except Exception as e:
            notes.append(f"Photos: Street View failed for {c.address} ({e}).")


# --------------------------------------------------------------------------
# comp selection + suggested price
# --------------------------------------------------------------------------
def select_comps(comps: list[Comp], cfg: dict) -> list[Comp]:
    n = cfg["comps_per_source"]
    chosen = []
    for source in ("Zillow", "Redfin"):
        pool = [c for c in comps if c.source == source and c.sqft]
        pool.sort(key=lambda c: (not c.renovated, c.distance_mi or 0,
                                 _age_days(c.sold_date)))
        chosen.extend(pool[:n])
    return chosen


def _age_days(sold_date: str) -> int:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return (date.today() - datetime.strptime(sold_date[:10], fmt).date()).days
        except (ValueError, TypeError):
            continue
    return 999


def suggest_price(comps: list[Comp], subject_sqft: int, cfg: dict) -> dict:
    ppsfs = sorted(c.ppsf for c in comps if c.ppsf)
    prices = sorted(c.sold_price for c in comps if c.sold_price)
    if not ppsfs:
        return {}
    med_ppsf = statistics.median(ppsfs)
    lo_ppsf, hi_ppsf = ppsfs[len(ppsfs) // 4], ppsfs[(len(ppsfs) * 3) // 4]
    if subject_sqft:
        suggested = round(med_ppsf * subject_sqft, -3)
        low = round(lo_ppsf * subject_sqft, -3)
        high = round(hi_ppsf * subject_sqft, -3)
        basis_note = f"median ${med_ppsf:,.0f}/sqft x {subject_sqft:,} sqft"
    else:
        suggested = round(statistics.median(prices), -3)
        low, high = prices[0], prices[-1]
        basis_note = "median comp sale price (subject sqft unknown)"
    return {"suggested": suggested, "low": low, "high": high,
            "median_ppsf": med_ppsf, "basis_note": basis_note}


def profit_at(price: float, summary: dict, cfg: dict) -> dict:
    all_in = summary.get("all_in_position")
    if not all_in or not price:
        return {}
    sell_pct = cfg["selling_cost_pct"]
    net = round(price * (1 - sell_pct), 2)
    profit = round(net - all_in, 2)
    basis = summary.get("total_cost_basis") or 0
    return {"net_proceeds": net, "profit": profit,
            "roi": round(profit / basis, 4) if basis else None,
            "all_in": all_in,
            "breakeven": summary.get("breakeven_sale_price")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--address", required=True)
    ap.add_argument("--summary", help="Stage-1 outputs/<prop>/summary.json")
    ap.add_argument("--output", required=True, help="output folder")
    ap.add_argument("--config", default=str(Path(__file__).parent / "config_stage2.json"))
    ap.add_argument("--subject-sqft", type=int, default=0)
    ap.add_argument("--property-name", default="")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--comps-file",
                    help="JSON file of researched comps (compliant path)")
    ap.add_argument("--suggested", type=float, default=0,
                    help="Override the suggested price with a concluded ARV")
    ap.add_argument("--arv-low", type=float, default=0)
    ap.add_argument("--arv-high", type=float, default=0)
    ap.add_argument("--basis-note", default="")
    args = ap.parse_args(argv)

    cfg = load_config(Path(args.config))
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    summary = {}
    if args.summary and Path(args.summary).exists():
        summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))

    if args.comps_file:
        comps = researched_comps(Path(args.comps_file), notes)
    elif args.mock:
        comps = mock_comps(args.address, cfg, notes)
    else:
        comps = zillow_comps(args.address, cfg, notes) + \
                redfin_comps(args.address, cfg, notes)
    if not comps:
        (out_dir / "comps_NEEDS_REVIEW.txt").write_text(
            "No comps returned.\n" + "\n".join(notes), encoding="utf-8")
        print("No comps found. See comps_NEEDS_REVIEW.txt:\n  " +
              "\n  ".join(notes))
        return 2

    chosen = comps if args.comps_file else select_comps(comps, cfg)
    fetch_photos(chosen, cfg, out_dir / ".photos", notes)
    pricing = suggest_price(chosen, args.subject_sqft, cfg)
    if args.suggested:
        pricing = {"suggested": args.suggested,
                   "low": args.arv_low or pricing.get("low"),
                   "high": args.arv_high or pricing.get("high"),
                   "median_ppsf": pricing.get("median_ppsf"),
                   "basis_note": args.basis_note or pricing.get("basis_note", "")}
    economics = profit_at(pricing.get("suggested", 0), summary, cfg)

    import render_comps as renderer
    name = args.property_name or args.address.split(",")[0]
    pdf = out_dir / f"{name} - Comp Analysis {date.today().isoformat()}.pdf"
    renderer.render(pdf, name, args.address, chosen, pricing, economics, notes)

    (out_dir / "comps.json").write_text(json.dumps({
        "address": args.address, "pricing": pricing, "economics": economics,
        "comps": [c.__dict__ | {"photo": str(c.photo) if c.photo else None}
                  for c in chosen], "notes": notes}, indent=2, default=str),
        encoding="utf-8")
    print(f"Comps: {len(chosen)}  Suggested: ${pricing.get('suggested', 0):,.0f}")
    if economics:
        print(f"Profit at suggested: ${economics['profit']:,.0f} "
              f"(all-in ${economics['all_in']:,.0f})")
    print(f"PDF: {pdf}")
    for nfo in notes:
        print("  -", nfo)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(main())
