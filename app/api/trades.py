"""Trade-history reads for the dashboard preview + the Trades tab (Plan 3b)."""
from typing import List, Optional, Tuple

from src.config.database import get_session_factory
from src.models.database import Trade


def _serialize(t) -> dict:
    created = getattr(t, "created_at", None)
    return {
        "trade_id": getattr(t, "trade_id", None),
        "instrument": getattr(t, "instrument", None),
        "side": getattr(t, "side", None),
        "quantity": str(getattr(t, "quantity", "")),
        "status": getattr(t, "status", None),
        "mt5_ticket": getattr(t, "mt5_ticket", None),
        "created_at": created.isoformat() if created else None,
    }


def query_trades(
    limit: int = 50, offset: int = 0, status: Optional[str] = None
) -> Tuple[List[dict], int]:
    """Return (rows, total) — trades newest-first, paged, optionally status-filtered."""
    Session = get_session_factory()
    session = Session()
    try:
        q = session.query(Trade)
        if status:
            q = q.filter(Trade.status == status)
        total = q.count()
        rows = (
            q.order_by(Trade.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_serialize(t) for t in rows], total
    finally:
        session.close()
