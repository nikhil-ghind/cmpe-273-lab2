import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Consumer, Producer, KafkaError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inventory_consumer")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INVENTORY_FAIL_RATE = float(os.getenv("INVENTORY_FAIL_RATE", "0.0"))
CONSUMER_THROTTLE_MS = int(os.getenv("CONSUMER_THROTTLE_MS", "0"))

INPUT_TOPIC = "orders"
OUTPUT_TOPIC = "inventory-events"

# Idempotency: track processed order IDs
processed_orders: set[str] = set()

consumer_conf = {
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "group.id": "inventory-service-group",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
}

producer_conf = {
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "linger.ms": 5,
}


def delivery_report(err, msg):
    if err:
        logger.error("Delivery failed: %s", err)


def process_order(event: dict, producer: Producer):
    order_id = event.get("orderId")
    if not order_id:
        logger.warning("Event missing orderId, skipping: %s", event)
        return

    # Idempotency check
    if order_id in processed_orders:
        logger.info("Order %s already processed, skipping", order_id)
        return

    # Throttle injection for lag demonstration (C5)
    if CONSUMER_THROTTLE_MS > 0:
        time.sleep(CONSUMER_THROTTLE_MS / 1000.0)

    # Failure injection
    if INVENTORY_FAIL_RATE > 0 and random.random() < INVENTORY_FAIL_RATE:
        result_event = {
            "eventId": str(uuid.uuid4()),
            "eventType": "InventoryFailed",
            "orderId": order_id,
            "reason": "OUT_OF_STOCK",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Inventory FAILED for order %s (injected)", order_id)
    else:
        result_event = {
            "eventId": str(uuid.uuid4()),
            "eventType": "InventoryReserved",
            "orderId": order_id,
            "reservedAt": datetime.now(timezone.utc).isoformat(),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Inventory RESERVED for order %s", order_id)

    processed_orders.add(order_id)

    producer.produce(
        OUTPUT_TOPIC,
        key=order_id,
        value=json.dumps(result_event),
        callback=delivery_report,
    )
    producer.poll(0)


def main():
    consumer = Consumer(consumer_conf)
    producer = Producer(producer_conf)
    consumer.subscribe([INPUT_TOPIC])

    logger.info(
        "Inventory consumer started (fail_rate=%.2f, throttle_ms=%d)",
        INVENTORY_FAIL_RATE,
        CONSUMER_THROTTLE_MS,
    )

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("Consumer error: %s", msg.error())
                continue

            try:
                event = json.loads(msg.value().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error("Failed to decode message: %s", e)
                consumer.commit(message=msg)
                continue

            process_order(event, producer)
            consumer.commit(message=msg)

    except KeyboardInterrupt:
        logger.info("Shutting down inventory consumer")
    finally:
        producer.flush(timeout=10)
        consumer.close()


if __name__ == "__main__":
    main()
