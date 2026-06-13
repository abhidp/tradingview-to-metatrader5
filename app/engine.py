"""Single-process supervisor: embeds mitmproxy + the MT5 worker on one loop."""
import asyncio
import logging

from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster

logger = logging.getLogger('Engine')


def quiet_proxy_noise() -> None:
    """Silence benign, high-volume proxy chatter so real events stay readable.

    - asyncio (proactor) logs a ConnectionResetError [WinError 10054] traceback
      every time a client drops a connection — pure noise on Windows.
    - mitmproxy logs every 'client connect'/'server connect'/'client disconnect'
      at INFO. We keep WARNING+ (genuine problems) but drop the per-connection spam.
    This mirrors the old two-terminal setup's `--quiet console_output_level=error`.
    """
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    logging.getLogger("mitmproxy").setLevel(logging.WARNING)


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

    quiet_proxy_noise()
    init_db()

    loop = asyncio.get_running_loop()
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
    # sync_instruments=False: at cold start there is no auth token yet, so the
    # network instrument-sync can't run anyway; avoid the confusing startup error
    # and any risk of a blocking request stalling the loop before the proxy listens.
    interceptor = TradingViewInterceptor(trade_handler=trade_handler, sync_instruments=False)

    master = build_master(interceptor, listen_host=listen_host, listen_port=listen_port)

    # Worker's MT5 position-monitor loop + the proxy run concurrently.
    worker_task = asyncio.create_task(worker.run_async())
    try:
        logger.info("Engine starting: proxy on %s:%s", listen_host, listen_port)
        await master.run()
    finally:
        worker.running = False
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)
        queue.cleanup()
        db.cleanup()
        logger.info("Engine stopped")
