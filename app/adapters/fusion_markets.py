"""FusionMarkets adapter: TradingView broker-panel traffic.

`matches` reproduces the gating that previously lived inline in
src/core/interceptor.py:should_log_request. `detect_account` (Task 7) learns the
broker target from live traffic. Trade parsing is unchanged and stays in
src/core/trade_handler.py.
"""
import logging
import re
from typing import Optional

from app.adapters.base import AccountInfo
from app.storage.settings_store import SettingsStore

logger = logging.getLogger("FusionMarketsAdapter")

# https://{host}/accounts/{digits}/...  (TradingView broker-panel REST shape)
_ACCOUNT_RE = re.compile(r"https?://(?P<host>[^/]+)/accounts/(?P<acct>\d+)/")


def _is_tradingview(flow) -> bool:
    """True if the flow looks TradingView-originated.

    Gates broker-target auto-detection only (not authentication), so a loose
    substring check on referer/origin is an acceptable trade-off; spoofing it
    at worst mis-detects an endpoint, never grants trust.
    """
    headers = getattr(flow.request, "headers", {}) or {}
    referer = headers.get("referer", "") or ""
    origin = headers.get("origin", "") or ""
    return "tradingview.com" in (referer + origin)


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

    @property
    def broker_url(self) -> Optional[str]:
        return self._broker_url

    @property
    def account_id(self) -> Optional[str]:
        return self._account_id

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

    def detect_account(self, flow) -> Optional[AccountInfo]:
        """Learn broker_url/account_id from TradingView-originated traffic."""
        if not _is_tradingview(flow):
            return None
        match = _ACCOUNT_RE.search(flow.request.pretty_url)
        if not match:
            return None
        return AccountInfo(broker_url=match.group("host"),
                           account_id=match.group("acct"))

    def persist_account(self, info: AccountInfo) -> bool:
        """Persist a detected target if it differs from the current one.

        Returns True if the stored target changed (so callers can refresh
        derived state like base_path).
        """
        if (info.broker_url, info.account_id) == (self._broker_url, self._account_id):
            return False
        self.store.set("tv.broker_url", info.broker_url)
        self.store.set("tv.account_id", info.account_id)
        self._broker_url = info.broker_url
        self._account_id = info.account_id
        logger.info("Detected TradingView target %s (%s)",
                    info.account_id, info.broker_url)
        return True
