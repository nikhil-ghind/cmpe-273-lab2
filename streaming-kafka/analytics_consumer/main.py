import json
import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime

from confluent_kafka import Consumer, KafkaError, TopicPartition
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analytics_consumer")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

ORDERS_TOPIC = "orders"
INVENTORY_TOPIC = "inventory-events"
GROUP_ID = "analytics-group"
METRICS_FILE = "/app/metrics.txt"

# Metrics state
orders_per_minute: dict[str, int] = defaultdict(int)  # minute_bucket -> count
total_reservations = 0
failed_reservations = 0
total_orders = 0
metrics_lock = threading.Lock()

# Signal for replay
replay_requested = threading.Event()

app = FastAPI()


def get_minute_bucket(created_at: str) -> str:
    """Extract minute bucket from ISO timestamp (event time bucketing)."""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M")
    except (ValueError, AttributeError):
        return "unknown"


def reset_metrics():
    global total_reservations, failed_reservations, total_orders
    with metrics_lock:
        orders_per_minute.clear()
        total_reservations = 0
        failed_reservations = 0
        total_orders = 0


def _get_failure_rate():
    return (
        failed_reservations / total_reservations
        if total_reservations > 0
        else 0.0
    )

def write_metrics():
    with metrics_lock:
        failure_rate = _get_failure_rate()
        lines = [
            "=== Analytics Metrics ===",
            f"Total orders seen: {total_orders}",
            f"Total reservations: {total_reservations}",
            f"Failed reservations: {failed_reservations}",
            f"Failure rate: {failure_rate:.4f}",
            "",
            "Orders per minute:",
        ]
        for bucket in sorted(orders_per_minute.keys()):
            lines.append(f"  {bucket}: {orders_per_minute[bucket]}")

        report = "\n".join(lines)

    logger.info("\n%s", report)
    try:
        with open(METRICS_FILE, "w") as f:
            f.write(report + "\n")
    except OSError as e:
        logger.warning("Could not write metrics file: %s", e)

    return report


def process_message(event: dict):
    global total_reservations, failed_reservations, total_orders

    event_type = event.get("eventType", "")

    with metrics_lock:
        if event_type == "OrderPlaced":
            total_orders += 1
            created_at = event.get("createdAt", "")
            bucket = get_minute_bucket(created_at)
            orders_per_minute[bucket] += 1

        elif event_type == "InventoryReserved":
            total_reservations += 1

        elif event_type == "InventoryFailed":
            total_reservations += 1
            failed_reservations += 1


def consumer_loop():
    """Main consumer loop running in a background thread."""
    while True:
        consumer = Consumer({
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })
        consumer.subscribe([ORDERS_TOPIC, INVENTORY_TOPIC])
        logger.info("Analytics consumer started (group=%s)", GROUP_ID)

        last_metrics_time = time.time()
        idle_count = 0

        try:
            while not replay_requested.is_set():
                msg = consumer.poll(1.0)
                if msg is None:
                    idle_count += 1
                    # Write metrics periodically (every 5s of idle)
                    if time.time() - last_metrics_time > 5:
                        write_metrics()
                        last_metrics_time = time.time()
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        idle_count += 1
                        continue
                    logger.error("Consumer error: %s", msg.error())
                    continue

                idle_count = 0
                try:
                    event = json.loads(msg.value().decode("utf-8"))
                    process_message(event)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.error("Failed to decode message: %s", e)

                consumer.commit(message=msg)

                # Periodic metrics write
                if time.time() - last_metrics_time > 5:
                    write_metrics()
                    last_metrics_time = time.time()

        except Exception as e:
            logger.error("Consumer loop error: %s", e)
        finally:
            consumer.close()

        # If replay was requested, reset and restart
        if replay_requested.is_set():
            logger.info("Replay requested — resetting metrics and offsets")
            reset_metrics()
            replay_requested.clear()

            # Reset offsets by committing offset 0 for all partitions
            from confluent_kafka.admin import AdminClient
            admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})

            # Build list of all topic-partitions to reset
            reset_offsets = []
            for topic in [ORDERS_TOPIC, INVENTORY_TOPIC]:
                metadata = admin.list_topics(topic, timeout=10)
                topic_meta = metadata.topics.get(topic)
                if topic_meta:
                    for pid in topic_meta.partitions:
                        reset_offsets.append(TopicPartition(topic, pid, 0))

            if reset_offsets:
                # Use a temporary consumer to commit offset 0
                tmp_consumer = Consumer({
                    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                    "group.id": GROUP_ID,
                })
                tmp_consumer.commit(offsets=reset_offsets, asynchronous=False)
                tmp_consumer.close()
                logger.info("Offsets reset for %d partitions", len(reset_offsets))

            logger.info("Replay: restarting consumer from beginning")
            # Loop will restart with fresh consumer


@app.post("/replay")
def replay():
    """Trigger a replay — reset offsets and recompute metrics."""
    before_metrics = write_metrics()
    replay_requested.set()
    return {"status": "replay_triggered", "before_metrics": before_metrics}


@app.get("/metrics")
def get_metrics():
    with metrics_lock:
        failure_rate = _get_failure_rate()
        return {
            "total_orders": total_orders,
            "total_reservations": total_reservations,
            "failed_reservations": failed_reservations,
            "failure_rate": round(failure_rate, 4),
            "orders_per_minute": dict(orders_per_minute),
        }


@app.get("/health")
def health():
    return {"status": "ok"}


def start_api():
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")


if __name__ == "__main__":
    # Start consumer loop in background thread
    consumer_thread = threading.Thread(target=consumer_loop, daemon=True)
    consumer_thread.start()

    # Run FastAPI in main thread
    start_api()
