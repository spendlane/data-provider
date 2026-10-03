#!/usr/bin/env python3
"""Publish exchange rates against the base currency (INR by default) as data/fx.json.

Source: central bank reference rates blended by Frankfurter v2 (free, no key, no published limits),
plus fixed USD pegs for Gulf currencies from config/currencies.json.
Runs independently of the gold script, so an FX update still ships if MetalCharts is down.
"""
from common import (CONFIG_DIR, DATA_DIR, FX_SOURCE, fail, fetch_usd_rates, iso, load_json,
                    load_pegs, utc_now, write_json)

SCHEMA_VERSION = 1
LATEST_FILE = DATA_DIR / "fx.json"
DAILY_DIR = DATA_DIR / "fx-daily"
MAX_JUMP_VS_PREVIOUS = 0.25  # reject a >25% move in any floating currency as a likely bad read


def round_rate(value: float) -> float:
    """4 decimal places, or 6 significant figures for small rates (1 VND is ~0.0037 INR)."""
    return round(value, 4) if value >= 1 else float(f"{value:.6g}")


def check_jumps(new_rates: dict, pegs: dict) -> None:
    if not LATEST_FILE.exists():
        return
    try:
        prev = load_json(LATEST_FILE)
        if prev.get("schema") != SCHEMA_VERSION:
            return
        old_rates = prev["rates"]
    except (ValueError, KeyError, OSError):
        return
    for code, entry in new_rates.items():
        if code in pegs or code not in old_rates:
            continue
        old = old_rates[code]["base_per_unit"]
        change = abs(entry["base_per_unit"] - old) / old
        if change > MAX_JUMP_VS_PREVIOUS:
            fail(f"{code} moved {change:.1%} since last run ({old} -> {entry['base_per_unit']}); skipping")


def main() -> None:
    cfg = load_json(CONFIG_DIR / "currencies.json")
    base = cfg["base"]
    codes = [c for c in cfg["currencies"] if c != base]
    pegs = load_pegs()

    usd_rates, fx_date, rate_dates = fetch_usd_rates(set(codes) | {base})
    base_per_usd = usd_rates[base]

    rates = {}
    for code in codes:
        base_per_unit = base_per_usd / usd_rates[code]  # e.g. INR per 1 AED, crossed through USD
        rates[code] = {
            "base_per_unit": round_rate(base_per_unit),   # 1 unit of `code` = this many INR
            "unit_per_base": round(1 / base_per_unit, 8),  # 1 INR = this many units of `code`
            "pegged_to_usd": code in pegs,
            # Pegs are fixed; for floating currencies this is the source's own publication date.
            "rate_date": None if code in pegs else rate_dates.get(code, fx_date),
        }

    check_jumps(rates, pegs)

    now = utc_now()
    payload = {
        "schema": SCHEMA_VERSION,
        "updated_at": iso(now),
        "fx_date": fx_date,
        "base": base,
        "notice": "Daily reference rates for estimates only. Not live trading, bank or card rates.",
        "source": FX_SOURCE,
        "rates": rates,
    }
    write_json(LATEST_FILE, payload)
    write_json(DAILY_DIR / f"{fx_date or now.date().isoformat()}.json", payload)
    print(f"Wrote {LATEST_FILE.name}: {len(rates)} currencies vs {base}, latest rate date {fx_date}")


if __name__ == "__main__":
    import urllib.error
    try:
        main()
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError, ZeroDivisionError) as exc:
        fail(f"{type(exc).__name__}: {exc}")
