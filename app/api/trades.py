"""Recent-trades read for the Dashboard preview (full history is Plan 3b)."""
from typing import List

from src.config.database import get_session_factory
from src.models.database import Trade


def recent_trades(limit: int = 10) -> List[dict]:
    """Most recent trades, newest first, as JSON-friendly dicts."""
    Session = get_session_factory()
    session = Session()
    try:
        rows = (
            session.query(Trade)
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .all()
        )
        out = []
        for t in rows:
            created = getattr(t, "created_at", None)
            out.append({
                "trade_id": getattr(t, "trade_id", None),
                "instrument": getattr(t, "instrument", None),
                "side": getattr(t, "side", None),
                "quantity": str(getattr(t, "quantity", "")),
                "status": getattr(t, "status", None),
                "created_at": created.isoformat() if created else None,
            })
        return out
    finally:
        session.close()
