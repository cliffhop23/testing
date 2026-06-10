from kalshi_bot.strategy import choose_low_price_candidates


def test_choose_low_price_candidates_picks_affordable_markets():
    markets = [
        {"ticker": "HIGH", "title": "Too expensive", "yes_ask": 12, "no_ask": 15},
        {"ticker": "LOW", "title": "Affordable", "yes_ask": 3, "no_ask": 7},
    ]

    candidates = choose_low_price_candidates(markets, max_price_cents=3)

    assert len(candidates) == 1
    assert candidates[0].ticker == "LOW"
    assert candidates[0].price_dollars == "0.0300"


def test_choose_low_price_candidates_skips_missing_prices():
    assert choose_low_price_candidates([{"ticker": "EMPTY"}], max_price_cents=1) == []
