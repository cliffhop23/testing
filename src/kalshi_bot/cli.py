"""Command-line interface for the Kalshi trading bot."""

from __future__ import annotations

import argparse
import json
import sys
import uuid

from .client import KalshiClient, KalshiClientError
from .config import load_settings
from .strategy import choose_low_price_candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a safety-first Kalshi trading bot.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("balance", help="Fetch portfolio balance using signed Kalshi API auth.")

    markets = subparsers.add_parser("markets", help="List currently open markets.")
    markets.add_argument("--limit", type=int, default=10)

    run = subparsers.add_parser("run", help="Scan markets and optionally place one conservative order.")
    run.add_argument("--limit", type=int, default=10, help="Number of open markets to scan.")
    run.add_argument("--max-price-cents", type=int, help="Maximum displayed ask price to consider.")
    run.add_argument("--count", type=int, help="Contract count to submit if live trading is enabled.")
    run.add_argument("--live", action="store_true", help="Actually submit an order. Omit for dry-run only.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    client = KalshiClient(
        base_url=settings.base_url,
        api_key_id=settings.api_key_id,
        private_key_path=settings.private_key_path,
    )

    try:
        if args.command == "balance":
            print(json.dumps(client.get_balance(), indent=2, sort_keys=True))
            return 0

        if args.command == "markets":
            payload = client.get_markets(limit=args.limit)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        if args.command == "run":
            return run_bot(args, settings, client)
    except KalshiClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 2


def run_bot(args: argparse.Namespace, settings, client: KalshiClient) -> int:
    max_price_cents = args.max_price_cents or settings.default_max_price_cents
    count = args.count or settings.default_order_count
    markets_payload = client.get_markets(limit=args.limit, status="open")
    markets = markets_payload.get("markets", [])
    candidates = choose_low_price_candidates(markets, max_price_cents=max_price_cents)

    if not candidates:
        print(f"No candidates found at or below {max_price_cents}¢.")
        return 0

    candidate = candidates[0]
    print(
        json.dumps(
            {
                "selected": candidate.__dict__,
                "count": count,
                "dry_run": settings.dry_run or not args.live,
            },
            indent=2,
            sort_keys=True,
        )
    )

    if settings.dry_run or not args.live:
        print("Dry run only. Re-run with --live and KALSHI_DRY_RUN=false to submit an order.")
        return 0

    response = client.place_event_order(
        ticker=candidate.ticker,
        side=candidate.side,
        count=count,
        price_dollars=candidate.price_dollars,
        client_order_id=str(uuid.uuid4()),
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
