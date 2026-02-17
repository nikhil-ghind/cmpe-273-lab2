import asyncio
import json
import aio_pika
from common.rabbit import AMQP_URL, setup_inventory_topology

async def connect_with_retry(amqp_url: str, retries: int = 60, delay: float = 1.0):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return await aio_pika.connect_robust(amqp_url)
        except Exception as e:
            last_exc = e
            print(f"[notify] RabbitMQ not ready (attempt {attempt}/{retries}): {e}")
            await asyncio.sleep(delay)
    raise last_exc

async def handle(msg: aio_pika.IncomingMessage):
    async with msg.process(requeue=False):
        body = json.loads(msg.body.decode())
        if body.get("event_type") == "InventoryReserved":
            print(f"[notify] Order confirmed: {body.get('order_id')}")
        else:
            print(f"[notify] unexpected event: {body}")

async def main():
    conn = await connect_with_retry(AMQP_URL)
    ch = await conn.channel()
    await ch.set_qos(prefetch_count=10)

    _, reserved_q, _ = await setup_inventory_topology(ch)

    await reserved_q.consume(handle)
    print("[notify] consuming inventory.reserved.q ...")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
