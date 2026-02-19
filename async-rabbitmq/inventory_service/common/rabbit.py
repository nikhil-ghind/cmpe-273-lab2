import os
import aio_pika

AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/")

# ---- Orders side ----
ORDERS_EX = "orders-ex"
ORDER_PLACED_Q = "order.placed.q"
ORDER_PLACED_RK = "order.placed"

# ---- Inventory side ----
INVENTORY_EX = "inventory-ex"

INV_RESERVED_Q = "inventory.reserved.q"
INV_RESERVED_RK = "inventory.reserved"

# optional but recommended (helps testing + completeness)
INV_FAILED_Q = "inventory.failed.q"
INV_FAILED_RK = "inventory.failed"


async def setup_orders_topology(channel: aio_pika.abc.AbstractChannel):
    """Exchange + queue for OrderPlaced."""
    orders_ex = await channel.declare_exchange(
        ORDERS_EX, aio_pika.ExchangeType.DIRECT, durable=True
    )
    # Try to get existing queue passively first (avoids property conflicts)
    try:
        q = await channel.declare_queue(ORDER_PLACED_Q, durable=True, passive=True)
    except Exception:
        # Queue doesn't exist yet, create it (order service will create with DLQ, but if we're first, create without)
        q = await channel.declare_queue(ORDER_PLACED_Q, durable=True)
    
    # Ensure binding exists (idempotent)
    await q.bind(orders_ex, routing_key=ORDER_PLACED_RK)
    return orders_ex, q


async def setup_inventory_topology(channel: aio_pika.abc.AbstractChannel):
    """Exchange + queues for Inventory events."""
    inv_ex = await channel.declare_exchange(
        INVENTORY_EX, aio_pika.ExchangeType.DIRECT, durable=True
    )

    reserved_q = await channel.declare_queue(INV_RESERVED_Q, durable=True)
    await reserved_q.bind(inv_ex, routing_key=INV_RESERVED_RK)

    failed_q = await channel.declare_queue(INV_FAILED_Q, durable=True)
    await failed_q.bind(inv_ex, routing_key=INV_FAILED_RK)

    return inv_ex, reserved_q, failed_q
