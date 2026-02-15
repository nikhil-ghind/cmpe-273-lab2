import json
import logging
import os
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("producer_order")

app = FastAPI()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = "orders"

producer_conf = {
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "linger.ms": 5,
    "batch.num.messages": 1000,
}
producer = Producer(producer_conf)


def delivery_report(err, msg):
    if err:
        logger.error("Delivery failed for %s: %s", msg.key(), err)


def build_event(order_id: str, items: list) -> dict:
    return {
        "eventId": str(uuid.uuid4()),
        "eventType": "OrderPlaced",
        "orderId": order_id,
        "items": items,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/produce")
def produce_order(payload: dict):
    order_id = payload.get("orderId", f"o-{uuid.uuid4().hex[:8]}")
    items = payload.get("items", [{"sku": "burrito", "qty": 1}])

    event = build_event(order_id, items)
    producer.produce(
        TOPIC,
        key=order_id,
        value=json.dumps(event),
        callback=delivery_report,
    )
    producer.poll(0)

    logger.info("Produced OrderPlaced for %s", order_id)
    return {"orderId": order_id, "status": "PRODUCED", "event": event}


@app.post("/load-test")
def load_test(payload: dict | None = None):
    count = 10000
    if payload and "count" in payload:
        count = int(payload["count"])

    items = [{"sku": "burrito", "qty": 1}]
    produced = 0

    for i in range(count):
        order_id = f"load-{i:06d}"
        event = build_event(order_id, items)
        producer.produce(
            TOPIC,
            key=order_id,
            value=json.dumps(event),
            callback=delivery_report,
        )
        # Poll periodically to trigger delivery reports and avoid buffer full
        if (i + 1) % 500 == 0:
            producer.poll(0)
        produced += 1

    # Flush all remaining messages
    remaining = producer.flush(timeout=30)
    logger.info("Load test: produced %d events, %d still in queue", produced, remaining)

    return {"produced": produced, "remaining_in_queue": remaining}


@app.get("/health")
def health():
    return {"status": "ok"}
