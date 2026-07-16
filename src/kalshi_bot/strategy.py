"""Simple, conservative trading strategy helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TradeCandidate:
    ticker: str
    title: str
    side: str
    price_cents: int
    reason: str
    outcome: str | None = None
    predicted_probability_cents: int | None = None
    edge_cents: int | None = None
    combo_signal_count: int = 0
    combo_sources: tuple[str, ...] = ()

    @property
    def price_dollars(self) -> str:
        return f"{self.price_cents / 100:.4f}"


@dataclass(frozen=True)
class PredictionSignal:
    """One prediction input for a market, normalized to a YES probability."""

    ticker: str
    probability_cents: int
    source: str
    weight: float = 1.0


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
        # Prefer the documented dollar fields (yes_ask_dollars / no_ask_dollars),
        # falling back to the older yes_ask / no_ask for backwards compatibility.
        if market.get("yes_ask_dollars") is not None:
            yes_ask = _coerce_dollars_to_cents(market.get("yes_ask_dollars"))
        else:
            yes_ask = _coerce_cents(market.get("yes_ask"))

        if market.get("no_ask_dollars") is not None:
            no_ask = _coerce_dollars_to_cents(market.get("no_ask_dollars"))
        else:
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


def load_prediction_signals(path: str | Path) -> dict[str, list[PredictionSignal]]:
    """Load combo prediction inputs from JSON.

    Accepted shapes are ``[{...}]``, ``{"predictions": [{...}]}``, or a mapping
    of ticker to one or more probability entries. Probabilities may be expressed
    as cents/percentage points (``62`` or ``"62%"``) or decimals (``0.62``).
    """

    payload = json.loads(Path(path).read_text())
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict) and "predictions" in payload:
        raw_rows = payload["predictions"]
        if not isinstance(raw_rows, list):
            raise ValueError("predictions must be a list")
        rows = [row for row in raw_rows if isinstance(row, dict)]
    elif isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        for ticker, value in payload.items():
            entries = value if isinstance(value, list) else [value]
            for index, entry in enumerate(entries):
                if isinstance(entry, dict):
                    rows.append({"ticker": ticker, **entry})
                else:
                    rows.append({"ticker": ticker, "probability_cents": entry, "source": f"{ticker}:{index}"})
    else:
        raise ValueError("Prediction JSON must be a list, mapping, or object with a 'predictions' list.")

    grouped: dict[str, list[PredictionSignal]] = {}
    for row in rows:
        ticker = str(row.get("ticker", "")).strip()
        if not ticker:
            continue
        probability = _prediction_probability(row)
        if probability is None:
            continue
        source = str(row.get("source") or row.get("model") or row.get("name") or "prediction")
        weight = _coerce_float(row.get("weight"), default=1.0)
        if weight <= 0:
            continue
        signal = PredictionSignal(ticker=ticker, probability_cents=probability, source=source, weight=weight)
        grouped.setdefault(ticker, []).append(signal)
    return grouped


def choose_combo_prediction_candidates(
    markets: list[dict],
    prediction_signals: dict[str, list[PredictionSignal]],
    *,
    max_price_cents: int,
    min_edge_cents: int,
    min_confidence_cents: int,
    min_combo_signals: int,
    side: str = "bid",
) -> list[TradeCandidate]:
    """Pick trades when a combination of prediction signals implies enough edge.

    The strategy treats each signal as a YES-probability estimate, combines the
    configured signals with a weighted average, and only considers a market when
    at least ``min_combo_signals`` independent inputs agree. It then compares the
    combo-implied YES/NO probability to the current displayed ask and keeps the
    side with enough confidence and edge.
    """

    candidates: list[TradeCandidate] = []
    for market in markets:
        ticker = str(market.get("ticker", ""))
        title = str(market.get("title", ticker))
        if not ticker:
            continue
        signals = prediction_signals.get(ticker, [])
        if len(signals) < min_combo_signals:
            continue
        yes_probability = _weighted_probability(signals)
        yes_ask = _coerce_cents(market.get("yes_ask"))
        no_ask = _coerce_cents(market.get("no_ask"))
        market_candidates: list[TradeCandidate] = []

        if yes_ask is not None and yes_ask <= max_price_cents:
            yes_edge = yes_probability - yes_ask
            if yes_probability >= min_confidence_cents and yes_edge >= min_edge_cents:
                market_candidates.append(
                    _combo_candidate(
                        ticker=ticker,
                        title=title,
                        side=side,
                        outcome="yes",
                        price_cents=yes_ask,
                        probability_cents=yes_probability,
                        edge_cents=yes_edge,
                        signals=signals,
                        min_edge_cents=min_edge_cents,
                    )
                )

        no_probability = 100 - yes_probability
        if no_ask is not None and no_ask <= max_price_cents:
            no_edge = no_probability - no_ask
            if no_probability >= min_confidence_cents and no_edge >= min_edge_cents:
                market_candidates.append(
                    _combo_candidate(
                        ticker=ticker,
                        title=title,
                        side=side,
                        outcome="no",
                        price_cents=no_ask,
                        probability_cents=no_probability,
                        edge_cents=no_edge,
                        signals=signals,
                        min_edge_cents=min_edge_cents,
                    )
                )

        if market_candidates:
            candidates.append(max(market_candidates, key=lambda candidate: candidate.edge_cents or 0))

    return sorted(candidates, key=lambda candidate: (-(candidate.edge_cents or 0), candidate.price_cents, candidate.ticker))


def _combo_candidate(
    *,
    ticker: str,
    title: str,
    side: str,
    outcome: str,
    price_cents: int,
    probability_cents: int,
    edge_cents: int,
    signals: list[PredictionSignal],
    min_edge_cents: int,
) -> TradeCandidate:
    sources = tuple(signal.source for signal in signals)
    return TradeCandidate(
        ticker=ticker,
        title=title,
        side=side,
        price_cents=price_cents,
        outcome=outcome,
        predicted_probability_cents=probability_cents,
        edge_cents=edge_cents,
        combo_signal_count=len(signals),
        combo_sources=sources,
        reason=(
            f"{len(signals)} prediction signals imply {probability_cents}¢ {outcome.upper()} probability; "
            f"ask is {price_cents}¢ for {edge_cents}¢ edge >= min {min_edge_cents}¢"
        ),
    )


def _prediction_probability(row: dict[str, Any]) -> int | None:
    for key in (
        "yes_probability_cents",
        "probability_cents",
        "yes_probability",
        "probability",
        "projected_probability",
        "model_probability",
    ):
        if key in row:
            return _coerce_probability_cents(row[key])
    return None


def _weighted_probability(signals: list[PredictionSignal]) -> int:
    total_weight = sum(signal.weight for signal in signals)
    return round(sum(signal.probability_cents * signal.weight for signal in signals) / total_weight)


def _coerce_probability_cents(value: object) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace("%", "")
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if 0 <= number <= 1:
        number *= 100
    if not 0 <= number <= 100:
        return None
    return round(number)


def _coerce_cents(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_dollars_to_cents(value: object) -> int | None:
    """Convert a dollar value (string or number) to integer cents.

    Examples:
      "3.50" -> 350
      3.5 -> 350
    Rounds to the nearest cent and handles malformed inputs gracefully by
    returning None.
    """
    if value in (None, ""):
        return None
    try:
        cents = round(float(value) * 100)
        return int(cents)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object, *, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
