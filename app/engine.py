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


class MitmEngineRunner:
    """The proxy + MT5 worker wiring as a start/stoppable unit.

    serve() blocks until shutdown() is called (it awaits mitmproxy's master).
    This is the production runner injected into EngineController; tests inject a fake.
    """

    def __init__(self, listen_host: str = "127.0.0.1", listen_port: int = 8080) -> None:
        self.listen_host = listen_host
        self.listen_port = listen_port
        self._master = None
        self._worker = None
        self._worker_task = None
        self._queue = None
        self._db = None

    async def serve(self) -> None:
        from src.models.database import init_db
        from src.utils.database_handler import DatabaseHandler
        from src.core.trade_handler import TradeHandler
        from src.core.interceptor import TradingViewInterceptor
        from src.workers.mt5_worker import MT5Worker
        from app.queue.inproc_queue import InProcQueue
        from app.storage.settings_store import SettingsStore
        from app.adapters.fusion_markets import FusionMarketsAdapter

        quiet_proxy_noise()
        init_db()

        store = SettingsStore()
        store.seed_from_env_once()

        loop = asyncio.get_running_loop()
        self._queue = InProcQueue()
        self._db = DatabaseHandler()

        trade_handler = TradeHandler(queue=self._queue, db=self._db)

        self._worker = MT5Worker()
        self._worker.init_inproc(loop=loop, queue=self._queue, db=self._db)
        self._queue.subscribe(self._worker.handle_message)

        adapter = FusionMarketsAdapter(store=store)

        TradingViewInterceptor._instance = None
        TradingViewInterceptor._initialized = False
        interceptor = TradingViewInterceptor(
            trade_handler=trade_handler, adapter=adapter, sync_instruments=False
        )

        self._master = build_master(
            interceptor, listen_host=self.listen_host, listen_port=self.listen_port
        )

        self._worker_task = asyncio.create_task(self._worker.run_async())
        try:
            logger.info("Engine starting: proxy on %s:%s", self.listen_host, self.listen_port)
            await self._master.run()
        finally:
            self._worker.running = False
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)
            self._queue.cleanup()
            self._db.cleanup()
            logger.info("Engine stopped")

    def shutdown(self) -> None:
        if self._master is not None:
            self._master.shutdown()

    def mt5_connected(self) -> bool:
        return bool(self._worker is not None and getattr(self._worker, "mt5", None) is not None
                    and getattr(self._worker.mt5, "connected", False))

    def tv_connected(self) -> bool:
        from src.utils.token_manager import GLOBAL_TOKEN_MANAGER
        try:
            return bool(GLOBAL_TOKEN_MANAGER.get_token())
        except Exception:
            return False


async def run_engine(listen_host: str = "127.0.0.1", listen_port: int = 8080) -> None:
    """Wire SQLite + settings store + queue + worker + broker adapter + interceptor onto one loop and run.

    This is the single-process replacement for the old two-terminal
    (start_proxy.py + start_worker.py) setup. No Docker, Redis, or Postgres.
    """
    runner = MitmEngineRunner(listen_host=listen_host, listen_port=listen_port)
    await runner.serve()
