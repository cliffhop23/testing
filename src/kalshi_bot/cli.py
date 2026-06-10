"""Command-line interface for the Kalshi trading bot."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict

from .client import KalshiClient, KalshiClientError
from .config import Settings, load_settings
from .copy_trading import evaluate_copy_signals, load_copy_signals
from .social import LeaderboardError, fetch_apify_leaderboard, load_leaderboard_file, rank_traders_for_copying
from .strategy import choose_low_price_candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a safety-first Kalshi trading bot.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("balance", help="Fetch portfolio balance using signed Kalshi API auth.")

    markets = subparsers.add_parser("markets", help="List currently open markets.")
    markets.add_argument("--limit", type=int, default=10)

    leaderboard = subparsers.add_parser("leaderboard", help="Fetch/filter the Kalshi social leaderboard.")
    leaderboard.add_argument("--file", help="Read leaderboard rows from a local JSON export instead of Apify.")
    leaderboard.add_argument("--metric", help="Leaderboard metric, e.g. projected_pnl, volume, num_markets_traded.")
    leaderboard.add_argument("--timeframe", help="Leaderboard timeframe, e.g. daily, weekly, monthly, yearly, all_time.")
    leaderboard.add_argument("--category", help="Optional leaderboard category filter.")
    leaderboard.add_argument("--limit", type=int, default=10, help="Rows to print after copy filters.")

    copy = subparsers.add_parser("copy", help="Evaluate explicit social copy-trading signals with safety gates.")
    copy.add_argument("--signals-file", required=True, help="JSON file containing explicit leader/ticker/side/price signals.")
    copy.add_argument("--leaderboard-file", help="Local leaderboard JSON export. Omit to use Apify.")
    copy.add_argument("--max-price-cents", type=int, help="Maximum signal price to copy.")
    copy.add_argument("--count", type=int, help="Override signal counts with this contract count.")
    copy.add_argument("--live", action="store_true", help="Actually submit approved orders. Omit for dry-run only.")

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

        if args.command == "leaderboard":
            return leaderboard_command(args, settings)

        if args.command == "copy":
            return copy_command(args, settings, client)

        if args.command == "run":
            return run_bot(args, settings, client)
    except (KalshiClientError, LeaderboardError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 2


def leaderboard_command(args: argparse.Namespace, settings: Settings) -> int:
    traders = _load_leaderboard(args.file, settings, metric=args.metric, timeframe=args.timeframe, category=args.category)
    qualified = rank_traders_for_copying(
        traders,
        min_projected_pnl_cents=settings.copy_min_projected_pnl_cents,
        min_roi_percent=settings.copy_min_roi_percent,
        min_markets_traded=settings.copy_min_markets_traded,
        max_rank=settings.copy_max_rank,
    )
    print(
        json.dumps(
            {
                "source_rows": len(traders),
                "qualified_rows": len(qualified),
                "copy_filters": _copy_filter_summary(settings),
                "traders": [asdict(trader) for trader in qualified[: args.limit]],
                "note": "Leaderboard rows are performance context only; use explicit public signals for copy trades.",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def copy_command(args: argparse.Namespace, settings: Settings, client: KalshiClient) -> int:
    max_price_cents = args.max_price_cents or settings.default_max_price_cents
    signals = load_copy_signals(args.signals_file)
    if args.count is not None:
        signals = [signal.__class__(**{**asdict(signal), "count": args.count}) for signal in signals]
    leaderboard = _load_leaderboard(args.leaderboard_file, settings, metric=None, timeframe=None, category=None)
    market_lookup = _fetch_signal_markets(client, signals)
    decisions = evaluate_copy_signals(
        signals,
        leaderboard,
        market_lookup,
        min_projected_pnl_cents=settings.copy_min_projected_pnl_cents,
        min_roi_percent=settings.copy_min_roi_percent,
        min_markets_traded=settings.copy_min_markets_traded,
        max_rank=settings.copy_max_rank,
        max_price_cents=max_price_cents,
        min_volume=settings.copy_min_market_volume,
        allowed_categories=set(settings.copy_allowed_categories) or None,
    )
    dry_run = settings.dry_run or not args.live
    print(
        json.dumps(
            {
                "dry_run": dry_run,
                "copy_filters": {**_copy_filter_summary(settings), "max_price_cents": max_price_cents},
                "decisions": [
                    {"signal": asdict(decision.signal), "approved": decision.approved, "reasons": decision.reasons}
                    for decision in decisions
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    approved = [decision for decision in decisions if decision.approved]
    if dry_run:
        print("Dry run only. Re-run with --live and KALSHI_DRY_RUN=false to submit approved copy orders.")
        return 0
    for decision in approved:
        signal = decision.signal
        response = client.place_event_order(
            ticker=signal.ticker,
            side=signal.side,
            count=signal.count,
            price_dollars=signal.price_dollars,
            client_order_id=str(uuid.uuid4()),
        )
        print(json.dumps(response, indent=2, sort_keys=True))
    return 0


def run_bot(args: argparse.Namespace, settings: Settings, client: KalshiClient) -> int:
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


def _load_leaderboard(
    path: str | None,
    settings: Settings,
    *,
    metric: str | None,
    timeframe: str | None,
    category: str | None,
):
    if path:
        return load_leaderboard_file(path)
    if not settings.apify_api_token:
        raise LeaderboardError("Provide --leaderboard-file/--file or set APIFY_API_TOKEN for the optional Apify scraper.")
    return fetch_apify_leaderboard(
        api_token=settings.apify_api_token,
        metric=metric or settings.leaderboard_metric,
        timeframe=timeframe or settings.leaderboard_timeframe,
        category=category if category is not None else settings.leaderboard_category,
    )


def _fetch_signal_markets(client: KalshiClient, signals) -> dict[str, dict]:
    market_lookup: dict[str, dict] = {}
    for ticker in sorted({signal.ticker for signal in signals}):
        payload = client.get_market(ticker)
        market_lookup[ticker] = payload.get("market", payload)
    return market_lookup


def _copy_filter_summary(settings: Settings) -> dict:
    return {
        "min_projected_pnl_cents": settings.copy_min_projected_pnl_cents,
        "min_roi_percent": settings.copy_min_roi_percent,
        "min_markets_traded": settings.copy_min_markets_traded,
        "max_rank": settings.copy_max_rank,
        "min_market_volume": settings.copy_min_market_volume,
        "allowed_categories": sorted(settings.copy_allowed_categories),
    }


if __name__ == "__main__":
    raise SystemExit(main())
