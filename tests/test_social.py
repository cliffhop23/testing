from kalshi_bot.social import normalize_leaderboard_rows, rank_traders_for_copying


def test_normalize_leaderboard_rows_accepts_common_fields():
    traders = normalize_leaderboard_rows(
        [
            {
                "username": "sharp-one",
                "rank": "1",
                "projected_pnl": "$1,234.50",
                "roi": "18.5%",
                "volume": "$10K",
                "num_markets_traded": "42",
                "category": "Politics",
            }
        ],
        source="fixture",
    )

    assert traders[0].handle == "sharp-one"
    assert traders[0].projected_pnl_cents == 123450
    assert traders[0].roi_percent == 18.5
    assert traders[0].volume_cents == 1_000_000
    assert traders[0].markets_traded == 42


def test_rank_traders_for_copying_filters_profit_roi_and_history():
    traders = normalize_leaderboard_rows(
        [
            {"username": "good", "rank": 2, "projected_pnl": "$500", "roi": "15%", "markets": 10},
            {"username": "lucky", "rank": 1, "projected_pnl": "$900", "roi": "30%", "markets": 1},
            {"username": "low-roi", "rank": 3, "projected_pnl": "$700", "roi": "2%", "markets": 20},
        ],
        source="fixture",
    )

    ranked = rank_traders_for_copying(
        traders,
        min_projected_pnl_cents=50_000,
        min_roi_percent=10,
        min_markets_traded=5,
    )

    assert [trader.handle for trader in ranked] == ["good"]
