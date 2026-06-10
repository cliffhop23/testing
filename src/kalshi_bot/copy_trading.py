"""Safety checks for leaderboard-informed copy-trading signals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .social import LeaderboardTrader, rank_traders_for_copying


@dataclass(frozen=True)
class CopySignal:
    """A proposed trade from a public/social signal source."""

    leader_handle: str
    ticker: str
    side: str
    price_cents: int
    count: int
    reason: str

    @property
    def price_dollars(self) -> str:
        return f"{self.price_cents / 100:.4f}"


@dataclass(frozen=True)
class CopyDecision:
    """The result of evaluating a potential copy trade."""

    signal: CopySignal
    approved: bool
    reasons: tuple[str, ...]


def load_copy_signals(path: str | Path) -> list[CopySignal]:
    """Load copy-trading signals from a JSON file.

    Expected shape: either a list of objects or ``{"signals": [...]}``. This makes
    copy trading explicit; the bot will not infer hidden/private trades from a
    leaderboard row alone.
    """

    payload = json.loads(Path(path).read_text())
    rows = payload.get("signals", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Signals JSON must be a list or an object with a 'signals' list.")
    signals: list[CopySignal] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        signals.append(
            CopySignal(
                leader_handle=str(row["leader_handle"]),
                ticker=str(row["ticker"]),
                side=str(row.get("side", "bid")),
                price_cents=_cents(row["price_cents"]),
                count=int(row.get("count", 1)),
                reason=str(row.get("reason", "external copy-trading signal")),
            )
        )
    return signals


def evaluate_copy_signals(
    signals: list[CopySignal],
    leaderboard: list[LeaderboardTrader],
    market_lookup: dict[str, dict[str, Any]],
    *,
    min_projected_pnl_cents: int,
    min_roi_percent: float | None,
    min_markets_traded: int,
    max_rank: int | None,
    max_price_cents: int,
    min_volume: int,
    allowed_categories: set[str] | None,
) -> list[CopyDecision]:
    """Approve only signals that pass leaderboard, price, liquidity, and category gates."""

    qualified = {
        trader.handle.lower(): trader
        for trader in rank_traders_for_copying(
            leaderboard,
            min_projected_pnl_cents=min_projected_pnl_cents,
            min_roi_percent=min_roi_percent,
            min_markets_traded=min_markets_traded,
            max_rank=max_rank,
        )
    }
    decisions: list[CopyDecision] = []
    for signal in signals:
        reasons: list[str] = []
        trader = qualified.get(signal.leader_handle.lower())
        market = market_lookup.get(signal.ticker, {})

        if trader is None:
            reasons.append("leader does not meet configured leaderboard performance filters")
        if signal.price_cents > max_price_cents:
            reasons.append(f"signal price {signal.price_cents}¢ exceeds max {max_price_cents}¢")
        if signal.count <= 0:
            reasons.append("signal count must be positive")

        volume = _market_int(market, "volume", "volume_24h", "notional_volume")
        if volume is not None and volume < min_volume:
            reasons.append(f"market volume {volume} is below min {min_volume}")

        category = _market_text(market, "category", "event_category", "series_ticker")
        if allowed_categories and (category or "").lower() not in {item.lower() for item in allowed_categories}:
            reasons.append(f"market category {category or 'unknown'} is not allowed")

        if not reasons:
            reasons.append("leaderboard, price, liquidity, and category filters passed")
        decisions.append(CopyDecision(signal=signal, approved=len(reasons) == 1 and reasons[0].endswith("passed"), reasons=tuple(reasons)))
    return decisions


def _cents(value: object) -> int:
    return int(float(str(value).replace("¢", "").replace("$", "")))


def _market_int(market: dict[str, Any], *names: str) -> int | None:
    for name in names:
        value = market.get(name)
        if value not in (None, ""):
            try:
                return int(float(str(value).replace(",", "")))
            except ValueError:
                return None
    return None


def _market_text(market: dict[str, Any], *names: str) -> str | None:
    for name in names:
        value = market.get(name)
        if value not in (None, ""):
            return str(value)
    return None
