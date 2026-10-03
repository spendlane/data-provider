#!/usr/bin/env python3
"""Fetch the gold spot price (MetalCharts) and FX rates, then publish DERIVED local gold prices as JSON.

The public file contains only derived values (local ex-tax price per gram, by karat), never the
raw spot quote. The app applies display units (config 'units', in grams) and sales tax itself.

Uses only the Python standard library, so the workflow needs no pip install.
If any step fails, the script exits non-zero WITHOUT touching the existing files,
so the app keeps reading the last good rates.
"""
import json
import os
import urllib.error

from common import CONFIG_DIR, DATA_DIR, fail, fetch_usd_rates, get_json, iso, utc_now

CONFIG_FILE = CONFIG_DIR / "countries.json"
LATEST_FILE = DATA_DIR / "rates.json"
DAILY_DIR = DATA_DIR / "daily"

SCHEMA_VERSION = 3
TROY_OUNCE_GRAMS = 31.1034768
PURITY = {"24K": 1.0, "22K": 0.916, "18K": 0.75, "14K": 0.585}

SPOT_SANITY_RANGE = (500.0, 20000.0)  # USD per troy ounce; reject anything outside this
MAX_JUMP_VS_PREVIOUS = 0.15           # reject a >15% move since the last run as a likely bad read
SPOT_URL = "https://api.metalcharts.org/v1/prices"

# MetalCharts free tier requires a visible credit link wherever prices are shown.
ATTRIBUTION = {"text": "Metal prices by MetalCharts", "url": "https://metalcharts.org"}

ADJUSTMENT_KEYS = ("import_duty", "market_premium", "sales_tax")


def load_config() -> dict:
    countries = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))["countries"]
    for code, cfg in countries.items():
        for key in ADJUSTMENT_KEYS:
            value = float(cfg.get(key, 0.0))
            if not 0.0 <= value < 1.0:
                fail(f"{code}.{key} = {value} must be a fraction between 0 and 1 (e.g. 0.06 for 6%)")
        units = cfg.get("units") or {"gram": 1}
        if "gram" not in units:
            fail(f"{code}.units must include 'gram'")
        if not isinstance(cfg.get("adjustments_verified", False), bool):
            fail(f"{code}.adjustments_verified must be true or false")
    return countries


def fetch_spot_usd_per_oz() -> float:
    api_key = os.environ.get("METALCHARTS_KEY")
    if not api_key:
        fail("METALCHARTS_KEY is not set (add it under Settings > Secrets and variables > Actions)")
    data, headers = get_json(SPOT_URL, {"Authorization": f"Bearer {api_key}"})

    remaining = headers.get("X-RateLimit-Month-Remaining")
    if remaining is not None:
        print(f"MetalCharts monthly requests remaining: {remaining}")

    price = float(data["data"]["XAU"]["price"])
    low, high = SPOT_SANITY_RANGE
    if not low <= price <= high:
        fail(f"Spot price {price} is outside the sanity range {SPOT_SANITY_RANGE}")
    return price


def previous_usd_per_gram() -> float | None:
    """Recover last run's base USD/gram from the published derived prices (for the jump check)."""
    if not LATEST_FILE.exists():
        return None
    try:
        prev = json.loads(LATEST_FILE.read_text(encoding="utf-8"))
        schema = prev.get("schema")
        if schema not in (2, SCHEMA_VERSION):
            return None
        for entry in prev["countries"].values():
            adj = entry["adjustments"]
            # Schema 2 published every unit with and without tax; schema 3 only the per-gram price.
            local = entry["price_per_gram"]["24K"] if schema == SCHEMA_VERSION else entry["prices"]["gram"]["ex_tax"]["24K"]
            return local / (1 + adj["import_duty"] + adj["market_premium"]) / entry["fx_per_usd"]
    except (json.JSONDecodeError, OSError, KeyError, ZeroDivisionError, TypeError):
        return None
    return None


def build_country(cfg: dict, usd_per_gram: float, fx: dict[str, float]) -> dict:
    currency = cfg["currency"]
    fx_per_usd = float(fx[currency])
    adjustments = {key: float(cfg.get(key, 0.0)) for key in ADJUSTMENT_KEYS}
    units = cfg.get("units") or {"gram": 1}

    # Duty and market premium are part of the local market price; the app adds sales tax for display.
    local_24k_ex_tax = usd_per_gram * fx_per_usd * (1 + adjustments["import_duty"] + adjustments["market_premium"])

    return {
        "currency": currency,
        "fx_per_usd": round(fx_per_usd, 6),
        "adjustments": adjustments,
        # False while duty/premium/tax are 0.0 placeholders: the price is the plain international price.
        "adjustments_verified": cfg.get("adjustments_verified", False),
        "units": units,
        # 4 decimals so per-gram × unit weight stays exact to the paisa (and fits 3-decimal currencies).
        "price_per_gram": {k: round(local_24k_ex_tax * f, 4) for k, f in PURITY.items()},
    }


def main() -> None:
    countries_cfg = load_config()

    spot = fetch_spot_usd_per_oz()
    usd_per_gram = spot / TROY_OUNCE_GRAMS

    old = previous_usd_per_gram()
    if old:
        change = abs(usd_per_gram - old) / old
        if change > MAX_JUMP_VS_PREVIOUS:
            fail(f"Gold moved {change:.1%} since last run; skipping as a likely bad read")

    fx, fx_date, _ = fetch_usd_rates({c["currency"] for c in countries_cfg.values()})

    countries = {code: build_country(cfg, usd_per_gram, fx) for code, cfg in sorted(countries_cfg.items())}

    now = utc_now()
    output = {
        "schema": SCHEMA_VERSION,
        "updated_at": iso(now),
        "fx_date": fx_date,
        "notice": "Estimated market values derived for in-app display only. Not a dealer quote.",
        "attribution": ATTRIBUTION,
        "countries": countries,
    }

    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    LATEST_FILE.write_text(text, encoding="utf-8")
    (DAILY_DIR / f"{now.date().isoformat()}.json").write_text(text, encoding="utf-8")
    print(f"Wrote {LATEST_FILE.name} for {len(countries)} countries")


if __name__ == "__main__":
    try:
        main()
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
        fail(f"{type(exc).__name__}: {exc}")
