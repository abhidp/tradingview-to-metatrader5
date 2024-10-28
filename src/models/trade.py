from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
from src.config.constants import REQUIRED_TRADE_FIELDS

@dataclass
class Trade:
    """Data class for representing a trade."""
    timestamp: datetime
    request_data: Dict[str, Any]
    response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary format."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'request_data': self.request_data,
            'response': self.response
        }

    @classmethod
    def from_flow(cls, flow, response_data: Optional[Dict] = None):
        """Create Trade instance from mitmproxy flow."""
        return cls(
            timestamp=datetime.now(),
            request_data=dict(flow.request.urlencoded_form),
            response=response_data
        )

    def is_valid(self) -> bool:
        """Check if trade has all required fields."""
        return all(field in self.request_data for field in REQUIRED_TRADE_FIELDS)