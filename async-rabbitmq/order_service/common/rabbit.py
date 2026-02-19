import os
import aio_pika

AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/")

# ---- Orders ----
ORDERS_EX = "orders-ex"
ORDER_PLACED_Q = "order.placed.q"
ORDER_PLACED_RK = "order.placed"

# ---- DLQ for Orders ----
ORDERS_DLX = "orders-dlx"
ORDER_PLACED_DLQ = "order.placed.dlq"
ORDER_PLACED_DLQ_RK = "order.placed.dlq"

# ---- Inventory ----
INVENTORY_EX = "inventory-ex"
INV_RESERVED_Q = "inventory.reserved.q"
INV_RESERVED_RK = "inventory.reserved"
INV_FAILED_Q = "inventory.failed.q"
INV_FAILED_RK = "inventory.failed"


async def setup_orders_topology(channel):
    # main exchange
    orders_ex = await channel.declare_exchange(
        ORDERS_EX, aio_pika.ExchangeType.DIRECT, durable=True
    )

    # DLX + DLQ
    dlx = await channel.declare_exchange(
        ORDERS_DLX, aio_pika.ExchangeType.DIRECT, durable=True
    )
    dlq = await channel.declare_queue(ORDER_PLACED_DLQ, durable=True)
    await dlq.bind(dlx, routing_key=ORDER_PLACED_DLQ_RK)

    # Delete existing queue if it exists (to handle property mismatches)
    try:
        await channel.queue_delete(ORDER_PLACED_Q)
    except Exception:
        # Queue doesn't exist or already deleted, which is fine
        pass

    # main queue with DLQ config
    q = await channel.declare_queue(
        ORDER_PLACED_Q,
        durable=True,
        arguments={
            "x-dead-letter-exchange": ORDERS_DLX,
            "x-dead-letter-routing-key": ORDER_PLACED_DLQ_RK,
        },
    )
    await q.bind(orders_ex, routing_key=ORDER_PLACED_RK)

    return orders_ex, q


async def setup_inventory_topology(channel):
    inv_ex = await channel.declare_exchange(
        INVENTORY_EX, aio_pika.ExchangeType.DIRECT, durable=True
    )

    reserved_q = await channel.declare_queue(INV_RESERVED_Q, durable=True)
    await reserved_q.bind(inv_ex, routing_key=INV_RESERVED_RK)

    failed_q = await channel.declare_queue(INV_FAILED_Q, durable=True)
    await failed_q.bind(inv_ex, routing_key=INV_FAILED_RK)

    return inv_ex, reserved_q, failed_q
