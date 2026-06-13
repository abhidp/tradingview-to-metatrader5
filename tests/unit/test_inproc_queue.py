import asyncio

from app.queue.inproc_queue import InProcQueue


async def test_push_then_consume_delivers_trade():
    queue = InProcQueue()
    received = []

    async def callback(msg_type, message):
        received.append((msg_type, message))

    queue.subscribe(callback)
    trade_id = await queue.async_push_trade({"trade_id": "T1", "instrument": "EURUSD"})

    # let the consumer task run
    await asyncio.sleep(0.05)

    assert trade_id == "T1"
    assert len(received) == 1
    msg_type, message = received[0]
    assert msg_type == "trade"
    assert message["data"]["instrument"] == "EURUSD"
    queue.cleanup()


async def test_push_generates_trade_id_when_missing():
    queue = InProcQueue()
    trade_id = await queue.async_push_trade({"instrument": "XAUUSD"})
    assert trade_id.startswith("trade_")
    queue.cleanup()


async def test_get_queue_status_reports_pending_count():
    queue = InProcQueue()
    await queue.async_push_trade({"trade_id": "T2"})
    status = queue.get_queue_status()
    assert status["pending"] == 1
    queue.cleanup()
