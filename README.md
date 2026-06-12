# Kalshi Trading Bot

A safety-first Python scaffold for a Kalshi event-contract trading bot. It uses Kalshi Trade API v2, signs authenticated requests with RSA-PSS, and defaults to dry-run mode so you can inspect decisions before any order is submitted.

> This project is engineering scaffolding, not financial advice. Replace the sample strategy before risking capital.

## What is included

- Public market browsing (`GET /markets`).
- Authenticated balance and order endpoints with `KALSHI-ACCESS-*` headers.
- RSA private-key request signing.
- A tiny starter strategy that selects open markets with displayed asks at or below a configurable maximum.
- A combo-prediction strategy that requires multiple independent prediction inputs for the same market before considering an order.
- Dry-run safeguards that require both `KALSHI_DRY_RUN=false` and `--live` before submitting an order.
- Optional Kalshi social leaderboard ingestion from a local JSON export or the third-party Apify scraper, with copy-trading filters for profit, ROI, rank, history, market volume, category, and price.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Edit `.env` with your Kalshi credentials:

```dotenv
KALSHI_API_KEY_ID=your-api-key-id
KALSHI_PRIVATE_KEY_PATH=/absolute/path/to/kalshi.key
KALSHI_ENV=demo
KALSHI_DRY_RUN=true
```

Kalshi credentials have two parts: the API key ID UUID and a downloaded RSA private-key file. The UUID alone is not enough for authenticated requests.

## Commands

List open markets without credentials:

```bash
kalshi-bot markets --limit 5
```

Fetch your balance with signed authentication:

```bash
kalshi-bot balance
```

Run the sample strategy in dry-run mode:

```bash
kalshi-bot run --limit 20 --max-price-cents 1 --count 1
```

Run the combo-prediction strategy with a local prediction file:

```bash
kalshi-bot run --strategy combo-prediction --predictions-file predictions.json --max-price-cents 40 --min-combo-signals 2 --min-edge-cents 5
```

Example `predictions.json`:

```json
{
  "predictions": [
    {"ticker": "EXAMPLE-26", "probability": 0.66, "source": "model-a", "weight": 1.0},
    {"ticker": "EXAMPLE-26", "probability": "62%", "source": "model-b", "weight": 0.8}
  ]
}
```

The combo strategy converts each row into a YES-probability estimate, computes a weighted combo probability, then only picks YES or NO when enough sources agree and the predicted probability clears the configured confidence and edge thresholds.

Submit a live order only after you intentionally disable the environment safety and pass `--live`:

```bash
KALSHI_DRY_RUN=false kalshi-bot run --limit 20 --max-price-cents 1 --count 1 --live
```

## Leaderboard-informed copy trading

Kalshi's leaderboard is useful social/performance context, but a leaderboard row by itself is **not** a current trade to copy. The bot therefore separates two steps:

1. Load and filter leaderboard rows to identify traders worth watching.
2. Evaluate explicit public signals (for example, a saved post/export that includes `leader_handle`, `ticker`, `side`, and `price_cents`) against strict risk gates before any order can be placed.

Fetch/filter leaderboard rows from a local JSON export:

```bash
kalshi-bot leaderboard --file leaderboard.json --limit 10
```

Or opt into the third-party Apify scraper by setting `APIFY_API_TOKEN`, then run:

```bash
kalshi-bot leaderboard --metric projected_pnl --timeframe monthly --limit 10
```

Example `signals.json`:

```json
{
  "signals": [
    {
      "leader_handle": "example-trader",
      "ticker": "EXAMPLE-26",
      "side": "bid",
      "price_cents": 4,
      "count": 1,
      "reason": "public social post/export"
    }
  ]
}
```

Evaluate signals in dry-run mode:

```bash
kalshi-bot copy --signals-file signals.json --leaderboard-file leaderboard.json --max-price-cents 5
```

Submit approved copy orders only after paper-testing and after you intentionally disable both safety gates:

```bash
KALSHI_DRY_RUN=false kalshi-bot copy --signals-file signals.json --leaderboard-file leaderboard.json --max-price-cents 5 --live
```

The copy workflow refuses to infer private trades from leaderboard rank alone and only submits explicit, reviewed signals that pass the configured filters.

## Credential safety

The local `.env` file, `.key` files, and `.pem` files are ignored by git. Do not commit your Kalshi private key. If you rotate credentials, update your local `.env` and private-key path only.
