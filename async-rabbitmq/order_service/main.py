# async-rabbitmq/order_service/main.py
import os
import json
import uuid
import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel
import aio_pika

from common.rabbit import AMQP_URL, setup_orders_topology, ORDERS_EX, ORDER_PLACED_RK

app = FastAPI()
app.state.conn = None

# Local in-memory order store
orders: dict = {}

class Item(BaseModel):
    sku: str
    qty: int

class OrderIn(BaseModel):
    user_id: str
    restaurant_id: str
    items: list[Item]

async def connect_with_retry(amqp_url: str, retries: int = 30, delay: float = 1.0):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            conn = await aio_pika.connect_robust(amqp_url)
            return conn
        except Exception as e:
            last_exc = e
            print(f"[order] RabbitMQ not ready (attempt {attempt}/{retries}): {e}")
            await asyncio.sleep(delay)
    raise last_exc

@app.on_event("startup")
async def startup():
    # connect to rabbit with retries so service doesn't crash on early start
    app.state.conn = await connect_with_retry(AMQP_URL, retries=60, delay=1.0)
    app.state.channel = await app.state.conn.channel()
    await app.state.channel.set_qos(prefetch_count=10)

    # Ensure exchange/queue exist (idempotent)
    app.state.exchange, _ = await setup_orders_topology(app.state.channel)
    print("[order] connected to RabbitMQ and topology declared")

@app.on_event("shutdown")
async def shutdown():
    if app.state.conn:
        await app.state.conn.close()
        print("[order] RabbitMQ connection closed")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/order", status_code=202)
async def create_order(order: OrderIn):
    order_id = str(uuid.uuid4())
    event = {
        "event_type": "OrderPlaced",
        "order_id": order_id,
        "user_id": order.user_id,
        "restaurant_id": order.restaurant_id,
        "items": [i.model_dump() for i in order.items],
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    # Write to local store before publishing
    orders[order_id] = {"order_id": order_id, "status": "PLACED", "data": event}

    msg = aio_pika.Message(
        body=json.dumps(event).encode(),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )

    await app.state.exchange.publish(msg, routing_key=ORDER_PLACED_RK)
    print(f"[order] published OrderPlaced {order_id}")
    return {"order_id": order_id, "status": "PLACED"}

@app.get("/order/{order_id}")
def get_order(order_id: str):
    if order_id not in orders:
        return {"error": "not found"}, 404
    return orders[order_id]

@app.get("/orders")
def list_orders():
    return {"count": len(orders), "orders": list(orders.values())}
