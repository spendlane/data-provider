# gold-rates-feed

A free gold price and exchange-rate feed for an offline-first app, focused on India. A GitHub Actions job runs every 6 hours. It publishes two files to GitHub Pages:

- `data/fx.json`: exchange rates against INR for 35 currencies, every currency the SpendLane app supports plus OMR (central bank reference rates via Frankfurter, plus fixed USD pegs for Gulf currencies).
- `data/rates.json`: gold prices for 36 countries, one per supported currency. The job fetches the gold spot price from MetalCharts, computes **derived** local prices (per gram, per 10 grams, per pavan, per tola; by karat; with and without GST), and writes them here.

The app downloads both files when online and stores them in SQLite. The two feeds are independent: if one source fails, the other still publishes, and the failed one keeps its last good file.

The public file contains only derived values, never the raw spot quote.

## Setup

1. Create a new **public** repo (e.g. `gold-rates-feed`) and add these files.
2. Create a free MetalCharts account and generate a key in their API console (no card required).
3. In the repo, go to **Settings › Secrets and variables › Actions › New repository secret**. Name it `METALCHARTS_KEY` and paste the key.
4. Go to **Settings › Actions › General › Workflow permissions** and select **Read and write permissions**.
5. Go to **Settings › Pages** and set **Source** to **GitHub Actions**.
6. Open the **Actions** tab, pick **Update gold and FX rates**, and click **Run workflow**. When it finishes, the run summary shows your Pages URL.
7. Check the India figures in `config/countries.json` (see India pricing below). Every other country ships with `0.0` placeholders for duty, premium and sales tax; set real values before showing that country's prices.
8. Keep the currency list in `config/currencies.json` in step with the currencies the app seeds, and add a matching country to `config/countries.json` for each new currency.

## Files

| Path | Purpose |
| --- | --- |
| `config/currencies.json` | Base currency (INR), currencies to publish, USD pegs for Gulf currencies |
| `config/countries.json` | Gold settings per country: duty, premium, GST, display units |
| `scripts/common.py` | Shared HTTP and exchange-rate helpers |
| `scripts/fetch_fx.py` | Builds `data/fx.json` |
| `scripts/fetch_rates.py` | Builds `data/rates.json` |
| `.github/workflows/update-gold-rates.yml` | Schedule, commit and Pages deploy |

## Feed URLs for the app

```
https://<your-user>.github.io/gold-rates-feed/data/fx.json
https://<your-user>.github.io/gold-rates-feed/data/rates.json
```

Daily snapshots for trend charts at the same base URL: `data/fx-daily/YYYY-MM-DD.json` (named by the latest rate date) and `data/daily/YYYY-MM-DD.json` (gold).

GitHub Pages has a soft bandwidth limit of 100 GB a month. `rates.json` is about 33 KB and `fx.json` about 6 KB, so a full refresh is roughly 40 KB: about 2.5 million refreshes a month. GitHub's terms say Pages isn't meant as free hosting for a commercial business, so move the file to a CDN or object storage if the app grows or earns significant revenue. Only the URL in the app changes.

## Exchange rates (fx.json)

Rates come from Frankfurter's v2 API, a free open-source service with no key and no published limits. It blends the daily reference rates of about 100 central banks, so it covers currencies the European Central Bank doesn't publish (KWD, VND, RUB, LKR, BDT, NPR, PKR). Central banks publish on working days only and some publish a day later than others, so each currency carries its own `rate_date`; `fx_date` is the newest of them and can be a few days old on a Monday morning. These are mid-market reference rates, not bank, card or remittance rates.

AED, SAR, QAR, OMR and BHD use their fixed USD pegs from `config/currencies.json`, crossed through the fetched INR rate; their `rate_date` is `null`. KWD is pegged to an undisclosed basket, so it floats and comes from Frankfurter. NPR is pegged to INR at 1.6, which Frankfurter already applies.

```json
{
  "schema": 1,
  "updated_at": "2026-10-02T06:17:05Z",
  "fx_date": "2026-10-01",
  "base": "INR",
  "notice": "Daily reference rates for estimates only. Not live trading, bank or card rates.",
  "source": { "text": "Central bank reference rates via Frankfurter", "url": "https://frankfurter.dev" },
  "rates": {
    "USD": { "base_per_unit": 88.0, "unit_per_base": 0.01136364, "pegged_to_usd": false, "rate_date": "2026-10-01" },
    "AED": { "base_per_unit": 23.9619, "unit_per_base": 0.04173295, "pegged_to_usd": true, "rate_date": null },
    "VND": { "base_per_unit": 0.00339, "unit_per_base": 294.98525074, "pegged_to_usd": false, "rate_date": "2026-09-30" }
  }
}
```

`base_per_unit` reads as "1 USD = ₹88.00". It has 4 decimal places, or 6 significant figures when below 1 (VND, IDR, KRW, JPY). Numbers above come from a test run with made-up inputs.

Safety checks: a currency Frankfurter doesn't publish and that has no peg stops the run, and a move of more than 25% in any floating currency since the last run is rejected as a likely bad read.

## India pricing (INR)

Indian gold prices are higher than the international price converted to rupees because of customs duty and GST. The feed models this with three settings in `config/countries.json`:

| Setting | India value | Meaning |
| --- | --- | --- |
| `import_duty` | 0.06 | Customs duty incl. AIDC (6%), included in the market price |
| `market_premium` | 0.0 | Extra domestic premium or discount vs. the landed price; tune if your prices run consistently off local benchmarks |
| `sales_tax` | 0.03 | GST (3%), shown separately as the `incl_tax` price |

**Verify these before launch and after every Union Budget**, since duty rates change. The values here reflect rules as of mid-2026.

Display units for India: gram, 8 grams (pavan, common in South India), 10 grams (the usual quoted unit), and tola (11.6638 g). Add or remove units in the config; the app reads them from the feed.

Which price to show:
- **Net worth value:** use `ex_tax` 22K or 24K per gram × the user's weight. Resale value doesn't include GST.
- **"Today's gold rate" display:** most Indian rate boards quote per 10 grams, often without GST. Show `ex_tax` with a small "+3% GST" note, or show both.
- Always label values as **estimated market value**. Jeweler rates vary by city and shop, and making charges are never recoverable.

## Supported countries

`config/countries.json` has one entry per currency the app supports. `EU` covers every eurozone country, so the app should map a eurozone device region (DE, FR, IT, …) to `EU`.

| Region | Countries (currency) |
| --- | --- |
| South Asia | IN (INR), PK (PKR), BD (BDT), LK (LKR), NP (NPR) |
| Gulf | AE (AED), SA (SAR), QA (QAR), KW (KWD), BH (BHD), OM (OMR) |
| East and Southeast Asia | SG (SGD), MY (MYR), TH (THB), ID (IDR), PH (PHP), VN (VND), KR (KRW), JP (JPY), CN (CNY), HK (HKD) |
| Europe | EU (EUR), GB (GBP), CH (CHF), SE (SEK), NO (NOK), DK (DKK), TR (TRY), RU (RUB) |
| Americas and Oceania | US (USD), CA (CAD), MX (MXN), BR (BRL), AU (AUD), NZ (NZD) |
| Africa | ZA (ZAR) |

Only India has real duty and tax values. All other countries use `0.0` placeholders, so their prices are the plain international price converted to local currency.

Display units follow local custom: tola (PK, NP, AE), vori/bhori (BD, the same weight as a tola), pavan (IN, LK), tael (HK 37.429 g, VN luong 37.5 g), chi (VN, 3.75 g), don (KR, 3.75 g) and baht weight (TH, 15.244 g). Most others use grams and troy ounces.

## Gold feed format (rates.json, schema 2)

```json
{
  "schema": 2,
  "updated_at": "2026-10-02T06:17:05Z",
  "fx_date": "2026-10-01",
  "notice": "Estimated market values derived for in-app display only. Not a dealer quote.",
  "attribution": { "text": "Metal prices by MetalCharts", "url": "https://metalcharts.org" },
  "countries": {
    "IN": {
      "currency": "INR",
      "fx_per_usd": 88.0,
      "adjustments": { "import_duty": 0.06, "market_premium": 0.0, "sales_tax": 0.03 },
      "units": { "gram": 1, "8 grams (pavan)": 8, "10 grams": 10, "tola": 11.6638038 },
      "prices": {
        "gram":     { "ex_tax": { "24K": 11996.09, "22K": 10988.42, "18K": 8997.06, "14K": 7017.71 },
                      "incl_tax": { "24K": 12355.97, "22K": 11318.07, "18K": 9266.98, "14K": 7228.24 } },
        "10 grams": { "ex_tax": { "24K": 119960.87, "22K": 109884.15, "...": 0 },
                      "incl_tax": { "24K": 123559.69, "22K": 113180.68, "...": 0 } }
      }
    }
  }
}
```

Numbers above come from a test run with made-up inputs (gold at 4,000 USD/oz, 88 INR/USD); they are not real rates.

## How the price is calculated

```
local 24K per gram (ex tax) = (USD per troy oz ÷ 31.1035) × FX rate × (1 + import_duty + market_premium)
price (ex tax)   = local 24K per gram × grams in unit × purity factor
price (incl tax) = price (ex tax) × (1 + sales_tax)
```

Purity factors: 24K = 1.0, 22K = 0.916, 18K = 0.75, 14K = 0.585.

## Gold safety checks

- A spot price outside 500–20,000 USD/oz is rejected.
- A move of more than 15% since the last run is rejected as a likely bad read.
- Adjustment values outside 0–1 in the config stop the run (catches "6" typed instead of "0.06").
- A failed gold run leaves `rates.json` at the last good values; exchange rates still publish, and the job is marked failed so you notice.

## MetalCharts free-tier rules

- **200 requests a month, 10 a minute.** At 4 runs a day the job uses about 124 a month, leaving room for manual test runs. Each run logs how many requests remain.
- **Credit link required.** Show "Metal prices by MetalCharts" linking to https://metalcharts.org wherever gold prices appear in the app. The feed's `attribution` field carries the text and link.
- **No competing feed or bulk redistribution.** This feed serves only your own app, but it is publicly reachable. Email MetalCharts to confirm the setup in writing.
- Don't publicise the feed URL; keep it inside the app.

## App integration (SQLite)

```sql
CREATE TABLE IF NOT EXISTS fx_rates (
  fx_date        TEXT NOT NULL,   -- feed's fx_date, e.g. '2026-10-01'
  currency       TEXT NOT NULL,   -- 'USD', 'AED', ...
  base           TEXT NOT NULL,   -- 'INR'
  base_per_unit  REAL NOT NULL,   -- 1 unit = this many INR
  PRIMARY KEY (fx_date, currency)
);

CREATE TABLE IF NOT EXISTS gold_rates (
  updated_at              TEXT NOT NULL,  -- feed's updated_at (UTC ISO 8601)
  country                 TEXT NOT NULL,  -- ISO code, e.g. 'IN'
  currency                TEXT NOT NULL,
  karat                   TEXT NOT NULL,  -- '24K', '22K', '18K', '14K'
  price_per_gram          REAL NOT NULL,  -- ex tax
  price_per_gram_incl_tax REAL NOT NULL,
  PRIMARY KEY (updated_at, country, karat)
);

CREATE TABLE IF NOT EXISTS gold_holdings (
  id             INTEGER PRIMARY KEY,
  name           TEXT NOT NULL,   -- 'Wedding necklace', 'Coin 10g'
  form           TEXT NOT NULL,   -- jewelry | coin | bar | digital | etf
  weight_grams   REAL NOT NULL,   -- store grams; convert pavan/tola on input
  karat          TEXT NOT NULL,
  purchase_price REAL,            -- optional, in user's currency
  purchased_on   TEXT
);
```

Refresh logic in the app:

1. On app open (and on pull-to-refresh), if online and the latest stored `updated_at` is older than 6 hours, download both files. Treat them independently: a failed or invalid download of one doesn't block the other.
2. Reject `rates.json` if `schema` is not 2 or the user's country is missing; reject `fx.json` if `schema` is not 1.
3. Insert only the user's country rows (from `prices.gram`) in one transaction. Keep the last 400 days for trend charts and delete older rows.
4. Value each gold holding as `weight_grams × price_per_gram` for its karat, and add the total to net worth.
5. Convert each foreign-currency account to INR as `balance × base_per_unit` using the latest `fx_rates` row for its currency. Store balances in their own currency and convert only for display and totals.
6. For unit displays (10 g, pavan, tola), multiply the per-gram price by the gram values in the feed's `units`.
7. Show "Last updated" plus the MetalCharts attribution link next to gold values, and "Rates: central bank reference, <fx_date>" next to converted amounts. Show a gentle "rates may be out of date" note if gold is older than 48 hours or `fx_date` is older than 5 days.

## Notes

- GitHub can delay scheduled runs during busy periods; exact timing isn't guaranteed.
- GitHub may disable scheduled workflows in public repos after 60 days without repository activity. Check the Actions tab now and then and re-enable it if needed.
- If GitHub warns that an action version is deprecated, bump it to the latest major version. The runner is pinned to `ubuntu-24.04`; move to a newer image when GitHub announces its retirement.
