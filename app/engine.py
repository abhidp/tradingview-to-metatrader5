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
