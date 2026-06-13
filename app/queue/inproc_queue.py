"""In-process asyncio queue that mirrors the RedisQueue public API.

RedisQueue delivered messages to a callback as (msg_type, message) where, for
trades, message == {"id", "data": <trade_data>, "timestamp"}. InProcQueue keeps
that exact shape so TradeHandler and MT5Worker need no changes beyond which
queue object they are handed.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional, Union

logger = logging.getLogger('InProcQueue')


class InProcQueue:
    def __init__(self) -> None:
        self.logger = logging.getLogger('InProcQueue')
        self._queue: asyncio.Queue = asyncio.Queue()
        self._callback: Optional[Union[Callable, Awaitable]] = None
        self._consumer_task: Optional[asyncio.Task] = None

    async def async_push_trade(self, trade_data: Dict[str, Any]) -> str:
        """Enqueue a trade for the worker. Returns the trade id."""
        trade_id = trade_data.get('trade_id') or f"trade_{datetime.now().timestamp()}"
        if isinstance(trade_data, dict) and 'trade_id' not in trade_data:
            trade_data['trade_id'] = trade_id
        message = {
            'id': trade_id,
            'data': trade_data,
            'timestamp': datetime.now().isoformat(),
        }
        await self._queue.put(('trade', message))
        self.logger.info(f"Trade {trade_id} enqueued")
        return trade_id

    def push_trade(self, trade_data: Dict[str, Any]) -> str:
        """Synchronous enqueue helper (schedules onto the running loop)."""
        trade_id = trade_data.get('trade_id') or f"trade_{datetime.now().timestamp()}"
        if isinstance(trade_data, dict) and 'trade_id' not in trade_data:
            trade_data['trade_id'] = trade_id
        message = {
            'id': trade_id,
            'data': trade_data,
            'timestamp': datetime.now().isoformat(),
        }
        self._queue.put_nowait(('trade', message))
        return trade_id

    def subscribe(self, callback: Union[Callable, Awaitable]) -> None:
        """Register the message handler and start the consumer task."""
        self._callback = callback
        self._consumer_task = asyncio.ensure_future(self._consume())
        self._consumer_task.add_done_callback(self._on_consumer_done)

    def _on_consumer_done(self, task: asyncio.Task) -> None:
        """Log if the consumer task died unexpectedly (not via cancel)."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            self.logger.error(f"Consumer task died unexpectedly: {exc}")

    async def _consume(self) -> None:
        while True:
            msg_type, message = await self._queue.get()
            try:
                if self._callback is None:
                    continue
                if asyncio.iscoroutinefunction(self._callback):
                    await self._callback(msg_type, message)
                else:
                    self._callback(msg_type, message)
            except Exception as e:
                self.logger.error(f"Error handling {msg_type} message: {e}")
            finally:
                self._queue.task_done()

    # --- API-compatibility shims (RedisQueue had these) ---

    def publish_status(self, message: str) -> None:
        self.logger.info(f"Status: {message.strip()}")

    async def async_publish_status(self, message: str) -> None:
        self.publish_status(message)

    def get_queue_status(self) -> Dict[str, int]:
        return {'pending': self._queue.qsize()}

    async def async_get_queue_status(self) -> Dict[str, int]:
        return self.get_queue_status()

    def cleanup(self) -> None:
        """Cancel the consumer task."""
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            self._consumer_task = None
        self.logger.info("InProcQueue cleaned up")
