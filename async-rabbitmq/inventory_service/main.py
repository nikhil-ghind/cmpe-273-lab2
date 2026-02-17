import asyncio
import json
from datetime import datetime, timezone

import aio_pika

from common.rabbit import (
    AMQP_URL,
    setup_orders_topology,
    setup_inventory_topology,
    INV_RESERVED_RK,
    INV_FAILED_RK,
)

# In-memory idempotency for lab (prevents double reserve on duplicate delivery)
processed_orders: set[str] = set()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

async def connect_with_retry(amqp_url: str, retries: int = 60, delay: float = 1.0):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return await aio_pika.connect_robust(amqp_url)
        except Exception as e:
            last_exc = e
            print(f"[inventory] RabbitMQ not ready (attempt {attempt}/{retries}): {e}")
            await asyncio.sleep(delay)
    raise last_exc

async def main():
    # Connect + channel
    conn = await connect_with_retry(AMQP_URL)
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=5)

    # Ensure topology exists
    _, order_queue = await setup_orders_topology(channel)
    inventory_exchange, _, _ = await setup_inventory_topology(channel)


    async def handle_message(message: aio_pika.IncomingMessage):
        async with message.process(requeue=False):
            # Parse JSON
            try:
                payload = json.loads(message.body.decode())
            except Exception as e:
                print(f"[inventory] malformed JSON -> reject: {e}")
                await message.reject(requeue=False)
                return

            # Validate basic schema
            if payload.get("event_type") != "OrderPlaced" or "order_id" not in payload:
                print(f"[inventory] invalid schema -> reject: {payload}")
                await message.reject(requeue=False)
                return

            order_id = payload["order_id"]

            # Idempotency: ignore duplicate order_id
            if order_id in processed_orders:
                print(f"[inventory] duplicate ignored: {order_id}")
                return
            processed_orders.add(order_id)

            # ---- Fake reservation logic (replace later if needed) ----
            items = payload.get("items", [])
            fail = any((item.get("qty", 0) > 5) for item in items)  # example fail rule

            if fail:
                event = {
                    "event_type": "InventoryFailed",
                    "order_id": order_id,
                    "reason": "qty_too_high",
                    "ts": now_iso(),
                }
                rk = INV_FAILED_RK
                print(f"[inventory] reservation FAILED for {order_id}")
            else:
                event = {
                    "event_type": "InventoryReserved",
                    "order_id": order_id,
                    "ts": now_iso(),
                }
                rk = INV_RESERVED_RK
                print(f"[inventory] reservation OK for {order_id}")

            # Publish Inventory event
            out_msg = aio_pika.Message(
                body=json.dumps(event).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await inventory_exchange.publish(out_msg, routing_key=rk)
            print(f"[inventory] published {event['event_type']} for {order_id}")

    # Start consuming
    await order_queue.consume(handle_message)
    print("[inventory] consuming OrderPlaced...")

    # Keep alive
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
