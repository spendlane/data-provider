"""Shared helpers for the feed scripts (standard library only)."""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
HTTP_TIMEOUT = 20

# Frankfurter v2 blends daily reference rates from ~100 central banks, so it covers currencies the
# ECB doesn't publish (KWD, VND, RUB, LKR, BDT, NPR, PKR). Each record carries its own rate date.
FX_URL = "https://api.frankfurter.dev/v2/rates?base=USD&quotes={symbols}"
FX_SOURCE = {"text": "Central bank reference rates via Frankfurter", "url": "https://frankfurter.dev"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def get_json(url: str, headers: dict | None = None) -> tuple[dict | list, dict]:
    """Return (parsed JSON body, response headers)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "gold-rates-feed/1.0", **(headers or {})}
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return json.load(response), dict(response.headers)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_pegs() -> dict[str, float]:
    """Fixed USD pegs (single source of truth: config/currencies.json); they override fetched rates."""
    return {code: float(v) for code, v in load_json(CONFIG_DIR / "currencies.json")["pegs_per_usd"].items()}


def fetch_usd_rates(codes: set[str]) -> tuple[dict[str, float], str | None, dict[str, str]]:
    """Return units of each currency per 1 USD (reference rates plus configured pegs), the latest
    rate date, and the rate date of each floating currency (some central banks publish a day later)."""
    pegs = load_pegs()
    rates = {"USD": 1.0}
    rates.update({c: pegs[c] for c in codes if c in pegs})
    floating = sorted(c for c in codes if c != "USD" and c not in pegs)
    dates: dict[str, str] = {}
    if floating:
        records, _ = get_json(FX_URL.format(symbols=",".join(floating)))
        for record in records:
            if record["quote"] in floating:
                rates[record["quote"]] = float(record["rate"])
                dates[record["quote"]] = record["date"]
    fx_date = max(dates.values()) if dates else None
    missing = set(codes) - set(rates)
    if missing:
        fail(f"No rate for {sorted(missing)}: Frankfurter doesn't publish it; add a USD peg in config/currencies.json or remove it")
    bad = [c for c, v in rates.items() if v <= 0]
    if bad:
        fail(f"Non-positive rate for {bad}")
    return rates, fx_date, dates


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
