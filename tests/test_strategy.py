<<<<<<< HEAD
from kalshi_bot.strategy import choose_low_price_candidates
=======
from kalshi_bot.strategy import (
    PredictionSignal,
    choose_combo_prediction_candidates,
    choose_low_price_candidates,
    load_prediction_signals,
)
>>>>>>> origin/main


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
<<<<<<< HEAD
=======


def test_load_prediction_signals_accepts_prediction_list(tmp_path):
    predictions_file = tmp_path / "predictions.json"
    predictions_file.write_text(
        '{"predictions": ['
        '{"ticker": "TEST", "probability": 0.62, "source": "model-a"},'
        '{"ticker": "TEST", "probability": "66%", "source": "model-b", "weight": 2}'
        ']}\n'
    )

    signals = load_prediction_signals(predictions_file)

    assert [signal.probability_cents for signal in signals["TEST"]] == [62, 66]
    assert signals["TEST"][1].weight == 2


def test_choose_combo_prediction_candidates_requires_multiple_signals_and_edge():
    markets = [
        {"ticker": "YES-EDGE", "title": "Yes edge", "yes_ask": 55, "no_ask": 48},
        {"ticker": "NO-EDGE", "title": "No edge", "yes_ask": 45, "no_ask": 30},
        {"ticker": "ONE-SIGNAL", "title": "Too few signals", "yes_ask": 20, "no_ask": 80},
    ]
    signals = {
        "YES-EDGE": [PredictionSignal("YES-EDGE", 70, "model-a"), PredictionSignal("YES-EDGE", 74, "model-b")],
        "NO-EDGE": [PredictionSignal("NO-EDGE", 20, "model-a"), PredictionSignal("NO-EDGE", 24, "model-b")],
        "ONE-SIGNAL": [PredictionSignal("ONE-SIGNAL", 90, "model-a")],
    }

    candidates = choose_combo_prediction_candidates(
        markets,
        signals,
        max_price_cents=60,
        min_edge_cents=10,
        min_confidence_cents=60,
        min_combo_signals=2,
    )

    assert [candidate.ticker for candidate in candidates] == ["NO-EDGE", "YES-EDGE"]
    assert candidates[0].outcome == "no"
    assert candidates[0].predicted_probability_cents == 78
    assert candidates[0].edge_cents == 48
    assert candidates[0].combo_signal_count == 2
    assert candidates[1].outcome == "yes"
>>>>>>> origin/main
