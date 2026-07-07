import pytest

from kalshi_bot.client import KalshiClient, MissingCredentialsError


def test_auth_headers_require_credentials():
    client = KalshiClient(base_url="https://external-api.demo.kalshi.co/trade-api/v2")

    with pytest.raises(MissingCredentialsError):
        client._auth_headers("GET", "/portfolio/balance")


def test_v2_event_order_payload(monkeypatch):
    client = KalshiClient(base_url="https://external-api.demo.kalshi.co/trade-api/v2")
    captured = {}

    def fake_request(method, path, *, params=None, json=None, auth=False):
        captured.update(method=method, path=path, json=json, auth=auth)
        return {"order": {"client_order_id": json["client_order_id"]}}

    monkeypatch.setattr(client, "request", fake_request)

    response = client.place_event_order(
        ticker="TEST-MARKET",
        side="bid",
        count=1,
        price_dollars="0.0100",
        client_order_id="client-1",
    )

    assert response["order"]["client_order_id"] == "client-1"
    assert captured == {
        "method": "POST",
        "path": "/portfolio/events/orders",
        "json": {
            "ticker": "TEST-MARKET",
            "side": "bid",
            "count": "1.00",
            "price": "0.0100",
            "time_in_force": "good_till_canceled",
            "self_trade_prevention_type": "taker_at_cross",
            "client_order_id": "client-1",
        },
        "auth": True,
    }
<<<<<<< HEAD
=======


def test_get_market_uses_public_market_endpoint(monkeypatch):
    client = KalshiClient(base_url="https://external-api.demo.kalshi.co/trade-api/v2")
    captured = {}

    def fake_request(method, path, *, params=None, json=None, auth=False):
        captured.update(method=method, path=path, auth=auth)
        return {"market": {"ticker": "TEST"}}

    monkeypatch.setattr(client, "request", fake_request)

    assert client.get_market("TEST") == {"market": {"ticker": "TEST"}}
    assert captured == {"method": "GET", "path": "/markets/TEST", "auth": False}
>>>>>>> origin/main
