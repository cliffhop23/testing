"""Simple, conservative trading strategy helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeCandidate:
    ticker: str
    title: str
    side: str
    price_cents: int
    reason: str

    @property
    def price_dollars(self) -> str:
        return f"{self.price_cents / 100:.4f}"


def choose_low_price_candidates(
    markets: list[dict],
    *,
    max_price_cents: int,
    side: str = "bid",
) -> list[TradeCandidate]:
    """Pick open markets with a displayed yes/no ask no higher than ``max_price_cents``.

    This is intentionally not financial advice or a profitable strategy. It is a
    transparent starter rule that lets the bot run safely in dry-run mode while
    you replace it with your own model.
    """

    candidates: list[TradeCandidate] = []
    for market in markets:
        ticker = str(market.get("ticker", ""))
        title = str(market.get("title", ticker))
        yes_ask = _coerce_cents(market.get("yes_ask"))
        no_ask = _coerce_cents(market.get("no_ask"))
        ask_prices = [price for price in (yes_ask, no_ask) if price is not None]
        if not ticker or not ask_prices:
            continue
        best_price = min(ask_prices)
        if best_price <= max_price_cents:
            candidates.append(
                TradeCandidate(
                    ticker=ticker,
                    title=title,
                    side=side,
                    price_cents=best_price,
                    reason=f"lowest displayed ask ({best_price}¢) is <= max ({max_price_cents}¢)",
                )
            )
    return candidates


def _coerce_cents(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
