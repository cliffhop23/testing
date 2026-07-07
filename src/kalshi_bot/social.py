"""Kalshi social leaderboard ingestion helpers.

Kalshi's public Trade API does not expose trader identities or a native copy-trading
feed. This module keeps leaderboard lookup explicit and pluggable: use a local
JSON export for tests/manual review, or an Apify actor token if you choose to use
that third-party scraper.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LeaderboardError(RuntimeError):
    """Raised when leaderboard data cannot be loaded or normalized."""


@dataclass(frozen=True)
class LeaderboardTrader:
    """A normalized trader row from a Kalshi social leaderboard source."""

    handle: str
    rank: int | None
    projected_pnl_cents: int | None
    roi_percent: float | None
    volume_cents: int | None
    markets_traded: int | None
    category: str | None
    timeframe: str | None
    source: str

    @property
    def projected_pnl_dollars(self) -> float | None:
        if self.projected_pnl_cents is None:
            return None
        return self.projected_pnl_cents / 100


def load_leaderboard_file(path: str | Path) -> list[LeaderboardTrader]:
    """Load leaderboard rows from a JSON file exported by a scraper or manually saved."""

    payload = json.loads(Path(path).read_text())
    rows = payload.get("items", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise LeaderboardError("Leaderboard JSON must be a list or an object with an 'items' list.")
    return normalize_leaderboard_rows(rows, source=str(path))


def fetch_apify_leaderboard(
    *,
    api_token: str,
    metric: str,
    timeframe: str,
    category: str = "",
    timeout_seconds: float = 120.0,
) -> list[LeaderboardTrader]:
    """Fetch Kalshi leaderboard rows via the optional Apify community actor.

    The actor is third-party infrastructure, so callers must provide their own
    Apify token and should review the actor's terms/pricing before use.
    """

    import requests

    response = requests.post(
        "https://api.apify.com/v2/acts/saswave~kalshi-leaderboard-scraper/run-sync-get-dataset-items",
        params={"token": api_token},
        json={"name": metric, "time": timeframe, "category": category},
        timeout=timeout_seconds,
    )
    if response.status_code >= 400:
        raise LeaderboardError(f"Apify leaderboard fetch failed {response.status_code}: {response.text}")
    payload = response.json()
    if not isinstance(payload, list):
        raise LeaderboardError("Apify leaderboard response was not a list of rows.")
    return normalize_leaderboard_rows(payload, source="apify:saswave/kalshi-leaderboard-scraper")


def normalize_leaderboard_rows(rows: list[dict[str, Any]], *, source: str) -> list[LeaderboardTrader]:
    """Normalize likely leaderboard field names into ``LeaderboardTrader`` objects."""

    traders: list[LeaderboardTrader] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        handle = _first_text(row, "handle", "username", "user", "name", "trader", "display_name")
        if not handle:
            continue
        traders.append(
            LeaderboardTrader(
                handle=handle,
                rank=_first_int(row, "rank", "position", "place"),
                projected_pnl_cents=_money_to_cents(
                    _first_value(row, "projected_pnl", "pnl", "profit", "net_profit", "projectedPnl")
                ),
                roi_percent=_percent_to_float(_first_value(row, "roi", "roi_percent", "return", "return_percent")),
                volume_cents=_money_to_cents(_first_value(row, "volume", "total_volume", "volume_traded")),
                markets_traded=_first_int(row, "num_markets_traded", "markets_traded", "markets", "market_count"),
                category=_first_text(row, "category", "section"),
                timeframe=_first_text(row, "timeframe", "time", "date_range"),
                source=source,
            )
        )
    return traders


def rank_traders_for_copying(
    traders: list[LeaderboardTrader],
    *,
    min_projected_pnl_cents: int,
    min_roi_percent: float | None = None,
    min_markets_traded: int = 0,
    max_rank: int | None = None,
) -> list[LeaderboardTrader]:
    """Filter leaderboard rows to traders with enough public performance history."""

    qualified: list[LeaderboardTrader] = []
    for trader in traders:
        if trader.projected_pnl_cents is None or trader.projected_pnl_cents < min_projected_pnl_cents:
            continue
        if min_roi_percent is not None and (trader.roi_percent is None or trader.roi_percent < min_roi_percent):
            continue
        if trader.markets_traded is not None and trader.markets_traded < min_markets_traded:
            continue
        if max_rank is not None and trader.rank is not None and trader.rank > max_rank:
            continue
        qualified.append(trader)
    return sorted(qualified, key=lambda item: (item.rank is None, item.rank or 999_999, -(item.projected_pnl_cents or 0)))


def _first_value(row: dict[str, Any], *names: str) -> Any:
    lowered = {key.lower(): value for key, value in row.items()}
    for name in names:
        if name in row:
            return row[name]
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _first_text(row: dict[str, Any], *names: str) -> str | None:
    value = _first_value(row, *names)
    if value in (None, ""):
        return None
    return str(value).strip()


def _first_int(row: dict[str, Any], *names: str) -> int | None:
    value = _first_value(row, *names)
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except ValueError:
        return None


def _money_to_cents(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int | float):
        return round(float(value) * 100)
    text = str(value).strip().replace(",", "")
    multiplier = 1.0
    if text.endswith("K") or text.endswith("k"):
        multiplier = 1_000.0
        text = text[:-1]
    elif text.endswith("M") or text.endswith("m"):
        multiplier = 1_000_000.0
        text = text[:-1]
    text = text.replace("$", "").replace("¢", "")
    try:
        return round(float(text) * multiplier * 100)
    except ValueError:
        return None


def _percent_to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None
