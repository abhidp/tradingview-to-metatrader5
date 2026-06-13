"""Single-process supervisor: embeds mitmproxy + the MT5 worker on one loop."""
import asyncio
import logging

from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster

logger = logging.getLogger('Engine')


def build_master(addon, listen_host: str = "127.0.0.1", listen_port: int = 8080) -> DumpMaster:
    """Build an embedded mitmproxy DumpMaster with our interceptor addon.

    Returns the configured master without running it, so it is unit-testable.
    MUST be called from within a running asyncio event loop: mitmproxy 11's
    Master.__init__ calls asyncio.get_running_loop() at construction. Task 11's
    run_engine() satisfies this; the unit test is async for the same reason.
    """
    opts = Options(
        listen_host=listen_host,
        listen_port=listen_port,
        ssl_insecure=True,
        mode=["regular"],
    )
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    master.addons.add(addon)
    return master


async def run_engine(listen_host: str = "127.0.0.1", listen_port: int = 8080) -> None:
    """Wire SQLite + queue + worker + interceptor onto one loop and run.

    This is the single-process replacement for the old two-terminal
    (start_proxy.py + start_worker.py) setup. No Docker, Redis, or Postgres.
    """
    # Local imports so unit tests can import build_master without these deps.
    from src.models.database import init_db
    from src.utils.database_handler import DatabaseHandler
    from src.core.trade_handler import TradeHandler
    from src.core.interceptor import TradingViewInterceptor
    from src.workers.mt5_worker import MT5Worker
    from app.queue.inproc_queue import InProcQueue

    init_db()

    loop = asyncio.get_event_loop()
    queue = InProcQueue()
    db = DatabaseHandler()

    # Shared trade handler used by the interceptor; pushes onto the queue.
    trade_handler = TradeHandler(queue=queue, db=db)

    # Worker consumes from the same queue on the same loop.
    worker = MT5Worker()
    worker.init_inproc(loop=loop, queue=queue, db=db)
    queue.subscribe(worker.handle_message)

    # Interceptor addon shares the trade handler.
    TradingViewInterceptor._instance = None
    TradingViewInterceptor._initialized = False
    interceptor = TradingViewInterceptor(trade_handler=trade_handler)

    master = build_master(interceptor, listen_host=listen_host, listen_port=listen_port)

    # Worker's MT5 position-monitor loop + the proxy run concurrently.
    worker_task = asyncio.create_task(worker.run_async())
    try:
        logger.info("Engine starting: proxy on %s:%s", listen_host, listen_port)
        await master.run()
    finally:
        worker.running = False
        worker_task.cancel()
        queue.cleanup()
        db.cleanup()
        logger.info("Engine stopped")
