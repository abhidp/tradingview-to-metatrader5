"""FusionMarkets adapter: TradingView broker-panel traffic.

`matches` reproduces the gating that previously lived inline in
src/core/interceptor.py:should_log_request. `detect_account` (Task 7) learns the
broker target from live traffic. Trade parsing is unchanged and stays in
src/core/trade_handler.py.
"""
import logging
from typing import Optional

from app.storage.settings_store import SettingsStore

logger = logging.getLogger("FusionMarketsAdapter")


class FusionMarketsAdapter:
    name = "fusion_markets"

    def __init__(self, store: Optional[SettingsStore] = None) -> None:
        self.store = store if store is not None else SettingsStore()
        self._broker_url = self.store.get("tv.broker_url")
        self._account_id = self.store.get("tv.account_id")

    @property
    def base_path(self) -> Optional[str]:
        if not self._broker_url or not self._account_id:
            return None
        return f"{self._broker_url}/accounts/{self._account_id}"

    def matches(self, flow) -> bool:
        base = self.base_path
        if not base:
            return False
        url = flow.request.pretty_url
        if base not in url:
            return False
        if "/orders?locale=" in url and "requestId=" in url:
            return True
        if "/executions?locale=" in url and "instrument=" in url:
            return True
        if "/positions/" in url:
            return flow.request.method in ("DELETE", "PUT")
        if ".TP." in url or ".SL." in url:
            return flow.request.method == "DELETE"
        return False
