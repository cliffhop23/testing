# Kalshi Trading Bot

A safety-first Python scaffold for a Kalshi event-contract trading bot. It uses Kalshi Trade API v2, signs authenticated requests with RSA-PSS, and defaults to dry-run mode so you can inspect decisions before any order is submitted.

> This project is engineering scaffolding, not financial advice. Replace the sample strategy before risking capital.

## What is included

- Public market browsing (`GET /markets`).
- Authenticated balance and order endpoints with `KALSHI-ACCESS-*` headers.
- RSA private-key request signing.
- A tiny starter strategy that selects open markets with displayed asks at or below a configurable maximum.
- Dry-run safeguards that require both `KALSHI_DRY_RUN=false` and `--live` before submitting an order.

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

Submit a live order only after you intentionally disable the environment safety and pass `--live`:

```bash
KALSHI_DRY_RUN=false kalshi-bot run --limit 20 --max-price-cents 1 --count 1 --live
```

## Credential safety

The local `.env` file, `.key` files, and `.pem` files are ignored by git. Do not commit your Kalshi private key. If you rotate credentials, update your local `.env` and private-key path only.
