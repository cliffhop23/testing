from kalshi_bot.copy_trading import CopySignal, evaluate_copy_signals
from kalshi_bot.social import normalize_leaderboard_rows


def test_evaluate_copy_signals_requires_leader_and_market_filters():
    leaderboard = normalize_leaderboard_rows(
        [{"username": "sharp", "rank": 1, "projected_pnl": "$750", "roi": "20%", "markets": 12}],
        source="fixture",
    )
    signals = [
        CopySignal("sharp", "GOOD", "bid", 4, 1, "public post"),
        CopySignal("unknown", "GOOD", "bid", 4, 1, "public post"),
        CopySignal("sharp", "PRICEY", "bid", 20, 1, "public post"),
    ]

    decisions = evaluate_copy_signals(
        signals,
        leaderboard,
        {"GOOD": {"volume": 1000, "category": "Politics"}, "PRICEY": {"volume": 1000, "category": "Politics"}},
        min_projected_pnl_cents=50_000,
        min_roi_percent=10,
        min_markets_traded=5,
        max_rank=10,
        max_price_cents=5,
        min_volume=100,
        allowed_categories={"Politics"},
    )

    assert decisions[0].approved is True
    assert decisions[1].approved is False
    assert "leader does not meet" in decisions[1].reasons[0]
    assert decisions[2].approved is False
    assert "exceeds max" in decisions[2].reasons[0]
