"""Minimal Kalshi REST client with RSA-PSS request signing."""

from __future__ import annotations

import base64
import datetime as dt
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


HttpMethod = str


class KalshiClientError(RuntimeError):
    """Raised when Kalshi returns an unsuccessful response."""


class MissingCredentialsError(KalshiClientError):
    """Raised when an authenticated endpoint is called without credentials."""


class KalshiClient:
    """Small REST client for Kalshi's Trade API v2."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key_id: str | None = None,
        private_key_path: str | Path | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_id = api_key_id
        self.private_key_path = Path(private_key_path).expanduser() if private_key_path else None
        self.timeout_seconds = timeout_seconds
        self._private_key: Any | None = None

    def get_markets(self, *, limit: int = 10, status: str = "open") -> dict[str, Any]:
        return self.request("GET", "/markets", params={"limit": limit, "status": status}, auth=False)

    def get_market(self, ticker: str) -> dict[str, Any]:
        return self.request("GET", f"/markets/{ticker}", auth=False)

    def get_orderbook(self, ticker: str) -> dict[str, Any]:
        return self.request("GET", f"/markets/{ticker}/orderbook", auth=False)

    def get_balance(self) -> dict[str, Any]:
        return self.request("GET", "/portfolio/balance", auth=True)

    def list_orders(self, *, limit: int = 50) -> dict[str, Any]:
        return self.request("GET", "/portfolio/orders", params={"limit": limit}, auth=True)

    def place_event_order(
        self,
        *,
        ticker: str,
        side: str,
        count: int,
        price_dollars: str,
        client_order_id: str,
    ) -> dict[str, Any]:
        """Submit an event-market order with Kalshi's V2 order shape."""

        payload = {
            "ticker": ticker,
            "side": side,
            "count": f"{count:.2f}",
            "price": price_dollars,
            "time_in_force": "good_till_canceled",
            "self_trade_prevention_type": "taker_at_cross",
            "client_order_id": client_order_id,
        }
        return self.request("POST", "/portfolio/events/orders", json=payload, auth=True)

    def request(
        self,
        method: HttpMethod,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        auth: bool,
    ) -> dict[str, Any]:
        import requests

        url = f"{self.base_url}{path}"
        headers = self._auth_headers(method, path) if auth else {}
        response = requests.request(
            method,
            url,
            params=params,
            json=json,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise KalshiClientError(f"Kalshi API error {response.status_code}: {response.text}")
        return response.json()

    def _auth_headers(self, method: HttpMethod, path: str) -> dict[str, str]:
        if not self.api_key_id or not self.private_key_path:
            raise MissingCredentialsError(
                "KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH are required for authenticated requests."
            )

        timestamp = str(int(dt.datetime.now(tz=dt.UTC).timestamp() * 1000))
        sign_path = urlparse(f"{self.base_url}{path}").path
        signature = self.sign_request(timestamp, method.upper(), sign_path)
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
        }

    def sign_request(self, timestamp: str, method: HttpMethod, path: str) -> str:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        path_without_query = path.split("?", 1)[0]
        message = f"{timestamp}{method.upper()}{path_without_query}".encode("utf-8")
        signature = self._load_private_key().sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _load_private_key(self) -> Any:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        if self._private_key is not None:
            return self._private_key
        if self.private_key_path is None:
            raise MissingCredentialsError("KALSHI_PRIVATE_KEY_PATH is required for request signing.")
        with self.private_key_path.open("rb") as key_file:
            key = serialization.load_pem_private_key(key_file.read(), password=None, backend=default_backend())
        if not isinstance(key, rsa.RSAPrivateKey):
            raise KalshiClientError("Kalshi private key must be an RSA private key.")
        self._private_key = key
        return key
