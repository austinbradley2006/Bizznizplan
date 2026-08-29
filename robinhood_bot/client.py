from __future__ import annotations

import logging
from dataclasses import dataclass

import pyhood
from pyhood.client import PyhoodClient
from pyhood.crypto import CryptoClient
from pyhood.exceptions import AuthError, DeviceApprovalRequiredError, TokenExpiredError
from pyhood.models import Mover, Watchlist

logger = logging.getLogger(__name__)


@dataclass
class AccountSnapshot:
    buying_power: float
    positions: list[dict]
    quotes: dict[str, float]


class RobinhoodService:
    """Thin wrapper around pyhood for bot operations."""

    def __init__(self) -> None:
        self._client: PyhoodClient | None = None
        self._crypto_client: CryptoClient | None = None
        self._crypto_checked = False

    def connect(self) -> None:
        try:
            session = pyhood.login()
        except (AuthError, TokenExpiredError, DeviceApprovalRequiredError) as exc:
            raise RuntimeError(
                "Robinhood session is missing or expired. Run `pyhood setup login` "
                "and approve the device in the Robinhood mobile app."
            ) from exc

        self._client = PyhoodClient(session)
        logger.info("Connected to Robinhood.")

    @property
    def client(self) -> PyhoodClient:
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._client

    def get_price(self, symbol: str) -> float:
        quote = self.client.get_quote(symbol)
        return float(quote.price)

    def get_quotes_batch(self, symbols: list[str]) -> dict:
        if not symbols:
            return {}
        return self.client.get_quotes(symbols)

    def get_fundamentals_batch(self, symbols: list[str]) -> dict[str, dict]:
        if not symbols:
            return {}
        return self.client.get_fundamentals_batch(symbols)

    def get_tag_symbols(self, tag: str) -> list[str]:
        return self.client.get_tags(tag)

    def get_movers(self, direction: str = "up") -> list[Mover]:
        return self.client.get_movers(direction)

    def get_watchlists(self) -> list[Watchlist]:
        return self.client.get_watchlists()

    def get_ratings(self, symbol: str):
        return self.client.get_ratings(symbol)

    @staticmethod
    def is_crypto_symbol(symbol: str) -> bool:
        return "-" in symbol.upper()

    def crypto_available(self) -> bool:
        if self._crypto_checked:
            return self._crypto_client is not None
        self._crypto_checked = True
        try:
            self._crypto_client = CryptoClient()
            self._crypto_client.get_account()
            return True
        except Exception:
            self._crypto_client = None
            return False

    def get_crypto_tradable_pairs(self) -> list[str]:
        if not self.crypto_available() or self._crypto_client is None:
            return []
        pairs = self._crypto_client.get_trading_pairs()
        return [
            pair.symbol
            for pair in pairs
            if pair.api_tradable and pair.quote_currency == "USD"
        ]

    def get_crypto_quote(self, symbol: str):
        if not self.crypto_available() or self._crypto_client is None:
            raise RuntimeError("Crypto API not configured")
        quotes = self._crypto_client.get_best_bid_ask(symbol.upper())
        return quotes[0] if quotes else None

    def get_crypto_closes(
        self,
        symbol: str,
        *,
        span: str = "week",
        interval: str = "hour",
    ) -> list[float]:
        if not self.crypto_available() or self._crypto_client is None:
            return []
        bars = self._crypto_client.get_historicals(symbol.upper(), interval=interval, span=span)
        return [float(bar.close_price) for bar in bars]

    def get_options_expirations(self, symbol: str) -> list[str]:
        return self.client.get_options_expirations(symbol)

    def get_options_chain(self, symbol: str, expiration: str):
        return self.client.get_options_chain(symbol, expiration)

    def get_closes(
        self,
        symbol: str,
        *,
        span: str = "month",
        interval: str = "day",
    ) -> list[float]:
        if self.is_crypto_symbol(symbol):
            crypto_span = "week" if span == "month" else span
            crypto_interval = "hour" if interval == "day" else interval
            return self.get_crypto_closes(symbol, span=crypto_span, interval=crypto_interval)
        bars = self.client.get_stock_historicals(symbol, interval=interval, span=span)
        return [float(bar.close_price) for bar in bars]

    def get_position_quantity(self, symbol: str) -> float:
        for position in self.client.get_positions():
            if position.symbol.upper() == symbol.upper():
                return float(position.quantity)
        return 0.0

    def account_snapshot(self, symbols: list[str]) -> AccountSnapshot:
        buying_power = float(self.client.get_buying_power())
        positions = [
            {
                "symbol": position.symbol,
                "quantity": float(position.quantity),
                "average_buy_price": float(position.average_buy_price),
            }
            for position in self.client.get_positions()
        ]
        quotes = {symbol: self.get_price(symbol) for symbol in symbols}
        return AccountSnapshot(
            buying_power=buying_power,
            positions=positions,
            quotes=quotes,
        )

    def buy_market(self, symbol: str, amount_usd: float, *, dry_run: bool) -> dict:
        price = self.get_price(symbol)
        quantity = round(amount_usd / price, 6)
        action = {
            "side": "buy",
            "symbol": symbol.upper(),
            "quantity": quantity,
            "estimated_price": price,
            "estimated_notional": round(quantity * price, 2),
            "order_type": "market",
        }
        if dry_run:
            logger.info("DRY RUN buy: %s", action)
            return {"dry_run": True, **action}

        order = self.client.buy_stock(symbol.upper(), quantity)
        logger.info("Placed buy order for %s: %s", symbol, order)
        return {"dry_run": False, "order": order, **action}

    def sell_market(self, symbol: str, quantity: float, *, dry_run: bool) -> dict:
        action = {
            "side": "sell",
            "symbol": symbol.upper(),
            "quantity": quantity,
            "order_type": "market",
        }
        if dry_run:
            logger.info("DRY RUN sell: %s", action)
            return {"dry_run": True, **action}

        order = self.client.sell_stock(symbol.upper(), quantity)
        logger.info("Placed sell order for %s: %s", symbol, order)
        return {"dry_run": False, "order": order, **action}
