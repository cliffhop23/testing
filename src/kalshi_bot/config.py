"""Configuration loading for the Kalshi trading bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEMO_REST_URL = "https://external-api.demo.kalshi.co/trade-api/v2"
PRODUCTION_REST_URL = "https://external-api.kalshi.com/trade-api/v2"


@dataclass(frozen=True)
class Settings:
    """Runtime settings sourced from environment variables."""

    api_key_id: str | None
    private_key_path: Path | None
    base_url: str
    dry_run: bool
    default_order_count: int
    default_max_price_cents: int
    combo_min_signals: int
    combo_min_edge_cents: int
    combo_min_confidence_cents: int
    apify_api_token: str | None
    leaderboard_metric: str
    leaderboard_timeframe: str
    leaderboard_category: str
    copy_min_projected_pnl_cents: int
    copy_min_roi_percent: float | None
    copy_min_markets_traded: int
    copy_max_rank: int | None
    copy_min_market_volume: int
    copy_allowed_categories: frozenset[str]

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key_id and self.private_key_path)


def _bool_from_env(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_env_file(env_file: str | os.PathLike[str] | None) -> None:
    if not env_file:
        return
    path = Path(env_file)
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _optional_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def load_settings(env_file: str | os.PathLike[str] | None = ".env") -> Settings:
    """Load settings from ``env_file`` and process environment variables."""

    _load_env_file(env_file)

    private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
    environment = os.getenv("KALSHI_ENV", "demo").strip().lower()
    default_base_url = PRODUCTION_REST_URL if environment == "production" else DEMO_REST_URL

    return Settings(
        api_key_id=os.getenv("KALSHI_API_KEY_ID"),
        private_key_path=Path(private_key_path).expanduser() if private_key_path else None,
        base_url=os.getenv("KALSHI_BASE_URL", default_base_url).rstrip("/"),
        dry_run=_bool_from_env(os.getenv("KALSHI_DRY_RUN"), default=True),
        default_order_count=int(os.getenv("KALSHI_DEFAULT_ORDER_COUNT", "1")),
        default_max_price_cents=int(os.getenv("KALSHI_DEFAULT_MAX_PRICE_CENTS", "1")),
        combo_min_signals=int(os.getenv("KALSHI_COMBO_MIN_SIGNALS", "2")),
        combo_min_edge_cents=int(os.getenv("KALSHI_COMBO_MIN_EDGE_CENTS", "3")),
        combo_min_confidence_cents=int(os.getenv("KALSHI_COMBO_MIN_CONFIDENCE_CENTS", "55")),
        apify_api_token=os.getenv("APIFY_API_TOKEN"),
        leaderboard_metric=os.getenv("KALSHI_LEADERBOARD_METRIC", "projected_pnl"),
        leaderboard_timeframe=os.getenv("KALSHI_LEADERBOARD_TIMEFRAME", "monthly"),
        leaderboard_category=os.getenv("KALSHI_LEADERBOARD_CATEGORY", ""),
        copy_min_projected_pnl_cents=int(os.getenv("KALSHI_COPY_MIN_PROJECTED_PNL_CENTS", "10000")),
        copy_min_roi_percent=_optional_float(os.getenv("KALSHI_COPY_MIN_ROI_PERCENT")),
        copy_min_markets_traded=int(os.getenv("KALSHI_COPY_MIN_MARKETS_TRADED", "5")),
        copy_max_rank=_optional_int(os.getenv("KALSHI_COPY_MAX_RANK", "25")),
        copy_min_market_volume=int(os.getenv("KALSHI_COPY_MIN_MARKET_VOLUME", "0")),
        copy_allowed_categories=frozenset(
            item.strip() for item in os.getenv("KALSHI_COPY_ALLOWED_CATEGORIES", "").split(",") if item.strip()
        ),
    )
