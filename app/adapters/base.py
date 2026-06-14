"""BrokerAdapter seam.

Thin by design (Plan 2): adapters own flow *matching* and *account detection*.
Trade parsing stays in src/core/trade_handler.py — the parse shape is
TradingView's broker-panel REST API, shared across TV-panel brokers, so it is
not per-broker logic. A future non-TV broker can implement a richer parse_trade
on its own adapter without disturbing this one.
"""
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass
class AccountInfo:
    broker_url: str
    account_id: str


@runtime_checkable
class BrokerAdapter(Protocol):
    name: str

    def matches(self, flow) -> bool:
        """Return True if this flow belongs to our broker and is processable."""
        ...

    def detect_account(self, flow) -> Optional[AccountInfo]:
        """Extract broker_url/account_id from broker-panel traffic, or None."""
        ...
