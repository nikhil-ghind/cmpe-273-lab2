# CMPE 273 Lab 2 — Campus Food Ordering Workflow

**Team:** Nikhil Ghind, Richie Nguyen, Jahnavi Chenna, Cameron Ghaemmaghami

Three implementations of the same workflow — **User places order → Inventory reserved → User notified** — each demonstrating a different communication model.

---

## Parts Overview

| Part | Directory | Stack | Communication Model |
|------|-----------|-------|---------------------|
| A | [`sync-rest/`](../sync-rest/README.md) | Flask, requests | Synchronous REST — blocking HTTP calls |
| B | [`async-rabbitmq/`](../async-rabbitmq/README.md) | FastAPI, aio-pika | Asynchronous messaging — RabbitMQ queues |
| C | [`streaming-kafka/`](../streaming-kafka/README.md) | FastAPI, confluent-kafka | Event streaming — Kafka topics |

### Part A — Synchronous REST

Workflow is fully synchronous and blocking:

```
Client → POST /order → order_service (8080)
                         ├── POST /reserve → inventory_service (8081)
                         └── POST /send   → notification_service (8082)
                         ↓
                       200 OK / 500 Error
```

- Order service blocks on each downstream call before returning to the client
- Supports delay injection (`--delay-time`) and failure injection (`/set-fail-rate`) on inventory
- Demonstrates latency compounding in synchronous chains

### Part B — Async RabbitMQ

Workflow is event-driven via message queues:

```
POST /order → order_service → [orders-ex] → order.placed.q → inventory_service
                                                                    ↓
                                                             [inventory-ex]
                                                                    ↓
                                                         notification_service
```

- Order service returns `202 Accepted` immediately; processing happens asynchronously
- Durable queues retain messages when consumers are down (backlog recovery)
- Dead letter queue (`order.placed.dlq`) catches malformed/rejected messages
- Idempotent inventory consumer prevents double reservation on message redelivery

### Part C — Streaming Kafka

Workflow is event-log based with replayable history:

```
POST /produce → producer_order → [orders topic] → inventory_consumer → [inventory-events topic]
                                                                               ↓
                                                                       analytics_consumer
                                                                          GET /metrics
                                                                          POST /replay
```

- Events are durably stored in Kafka topics and can be replayed from any offset
- Analytics consumer tracks orders per minute, failure rate, and total reservations
- `POST /replay` resets offsets and recomputes all metrics from the beginning of the log

---

## Shared Utilities

### `common/ids.py`

Shared ID generation used across all parts:

```python
from common.ids import new_order_id, new_event_id, new_user_id, new_restaurant_id

new_order_id()            # o-3f2a1b4c
new_event_id()            # 550e8400-e29b-41d4-a716-446655440000
new_user_id()             # u-4a2f91
new_restaurant_id()       # r-7c3d02
new_sku()                 # sku-9f1a
new_load_test_order_id(42) # load-000042
```

---

## Setup and Run

Each part is self-contained with its own `docker-compose.yml`. Run them independently.

### Prerequisites

- Docker + Docker Compose installed
- If you see `permission denied` on Docker socket:
  ```bash
  sudo usermod -aG docker $USER
  newgrp docker
  ```

---

### Part A — Synchronous REST

```bash
cd sync-rest
docker compose up --build
```

Services start on:
- Order service: `http://localhost:8080`
- Inventory service: `http://localhost:8081`
- Notification service: `http://localhost:8082`

**Place an order:**
```bash
curl -s -X POST http://localhost:8080/order \
  -H "Content-Type: application/json" \
  -d '{"order": "test"}' | python3 -m json.tool
```

**Inject 2s delay into inventory:**
```bash
curl "http://localhost:8081/set-delay-time?delay-time=2"
```

**Inject 100% failure rate:**
```bash
curl "http://localhost:8081/set-fail-rate?fail-rate=1.0"
```

**Run latency test (10 requests):**
```bash
cd sync-rest/tests
python testprogram.py --requests 10
```

**Teardown:**
```bash
docker compose down
```

[Full Part A documentation →](../sync-rest/README.md)

---

### Part B — Async RabbitMQ

```bash
cd async-rabbitmq
docker compose up --build -d
```

Services start on:
- Order service: `http://localhost:8001`
- RabbitMQ management UI: `http://localhost:15672` (guest / guest)

**Place an order:**
```bash
curl -s -X POST http://localhost:8001/order \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "restaurant_id": "r1", "items": [{"sku": "burger", "qty": 1}]}' \
  | python3 -m json.tool
```

**View service logs:**
```bash
docker compose logs inventory_service
docker compose logs notification_service
```

**Kill and restart inventory to test backlog recovery:**
```bash
docker compose stop inventory_service
# ... publish orders while down ...
docker compose start inventory_service
```

**Teardown:**
```bash
docker compose down -v
```

[Full Part B documentation →](../async-rabbitmq/README.md)

---

### Part C — Streaming Kafka

```bash
cd streaming-kafka
docker compose up --build
```

Wait for `init-kafka` to finish creating topics before the producer becomes ready.

Services start on:
- Producer: `http://localhost:8000`
- Analytics: `http://localhost:8002`

**Health check:**
```bash
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:8002/health | python3 -m json.tool
```

**Produce a single order:**
```bash
curl -s -X POST http://localhost:8000/produce \
  -H "Content-Type: application/json" \
  -d '{"orderId": "o-123", "items": [{"sku": "burrito", "qty": 1}]}' \
  | python3 -m json.tool
```

**Load test (10,000 events):**
```bash
curl -s -X POST http://localhost:8000/load-test \
  -H "Content-Type: application/json" \
  -d '{"count": 10000}' | python3 -m json.tool
```

**Get analytics metrics:**
```bash
curl -s http://localhost:8002/metrics | python3 -m json.tool
```

**Replay all events from beginning:**
```bash
curl -s -X POST http://localhost:8002/replay | python3 -m json.tool
```

**Run tests:**
```bash
cd streaming-kafka/tests
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest -v
```

**Fault injection:**
```bash
# 30% inventory failure rate
INVENTORY_FAIL_RATE=0.3 docker compose up --build

# Slow consumer (100ms per message) to observe lag
CONSUMER_THROTTLE_MS=100 docker compose up --build
```

**Teardown:**
```bash
docker compose down -v
```

[Full Part C documentation →](../streaming-kafka/README.md)

---

## Test Results

### Part A — Synchronous REST

Results in [`sync-rest/tests/imagesManual/`](../sync-rest/tests/imagesManual/):

| Test | Screenshot |
|------|------------|
| Baseline latency (10 requests) | [syncBaselineTest.png](../sync-rest/tests/imagesManual/syncBaselineTest.png) |
| Order service log (baseline) | [syncBaseOrderService.png](../sync-rest/tests/imagesManual/syncBaseOrderService.png) |
| Inventory log (baseline) | [syncBaselineInventory.png](../sync-rest/tests/imagesManual/syncBaselineInventory.png) |
| Notification log (baseline) | [syncBaselineNotification.png](../sync-rest/tests/imagesManual/syncBaselineNotification.png) |
| 2s delay test | [syncDelayTest.png](../sync-rest/tests/imagesManual/syncDelayTest.png) |
| Failure injection test | [syncFailTest.png](../sync-rest/tests/imagesManual/syncFailTest.png) |
| Order service on failure | [syncFailOrderService.png](../sync-rest/tests/imagesManual/syncFailOrderService.png) |
| Timeout test | [syncTimeoutTest.png](../sync-rest/tests/imagesManual/syncTimeoutTest.png) |
| Order service on timeout | [syncTimeoutOrderService.png](../sync-rest/tests/imagesManual/syncTimeoutOrderService.png) |

### Part B — Async RabbitMQ

Results in [`async-rabbitmq/tests_screenshots/`](../async-rabbitmq/tests_screenshots/):

| Test | Screenshot |
|------|------------|
| Basic flow — inventory log | [TC1_Inventorylog.png](../async-rabbitmq/tests_screenshots/TC1_Inventorylog.png) |
| Basic flow — notification log | [TC1_Notifylog.png](../async-rabbitmq/tests_screenshots/TC1_Notifylog.png) |
| Backlog (30 messages queued) | [TC2_Backup.png](../async-rabbitmq/tests_screenshots/TC2_Backup.png) |
| Recovery (queue drained) | [TC2_Recovery.png](../async-rabbitmq/tests_screenshots/TC2_Recovery.png) |
| Idempotency — duplicate ignored | [TC3_dempotency.png](../async-rabbitmq/tests_screenshots/TC3_dempotency.png) |
| Idempotency — inventory log | [TC3_Inventorylog.png](../async-rabbitmq/tests_screenshots/TC3_Inventorylog.png) |
| Trigger DLQ with malformed message | [Trigger DLQ with malformed message.png](<../async-rabbitmq/tests_screenshots/Trigger DLQ with malformed message.png>) |
| DLQ — inventory rejection log | [TC4_Inventorylog.png](../async-rabbitmq/tests_screenshots/TC4_Inventorylog.png) |
| DLQ — message queued | [TC4_DLQ.png](../async-rabbitmq/tests_screenshots/TC4_DLQ.png) |

### Part C — Streaming Kafka

Results in [`streaming-kafka/results/`](../streaming-kafka/results/):

| Test | Screenshot |
|------|------------|
| Health check | [health_check.png](../streaming-kafka/results/health_check.png) |
| Single order produced | [produce_1.png](../streaming-kafka/results/produce_1.png) |
| Load test 100 events | [load_100_test.png](../streaming-kafka/results/load_100_test.png) |
| Load test 10k events | [produce_10k_test.png](../streaming-kafka/results/produce_10k_test.png) |
| Analytics metrics | [metrics.png](../streaming-kafka/results/metrics.png) |
| Replay trigger | [kafka_replay.png](../streaming-kafka/results/kafka_replay.png) |
| Metrics after replay | [metrics_after_reply.png](../streaming-kafka/results/metrics_after_reply.png) |
| Failure rate 30% | [fail_rate_30.png](../streaming-kafka/results/fail_rate_30.png) |
| Metrics after fail rate | [check_metrics_after_fail_rate.png](../streaming-kafka/results/check_metrics_after_fail_rate.png) |
| Load test with throttle | [load_test_with_throttle.png](../streaming-kafka/results/load_test_with_throttle.png) |
| Consumer throttle lag | [consumer__throttle.png](../streaming-kafka/results/consumer__throttle.png) |
| Consumer groups query | [check_for_consumer_grps.png](../streaming-kafka/results/check_for_consumer_grps.png) |
| Produce with lag | [produce_with_lag.png](../streaming-kafka/results/produce_with_lag.png) |
| Test — inventory processes all | [test_inventory_all.png](../streaming-kafka/results/test_inventory_all.png) |
| Test — analytics volume | [test_analytics_volume.png](../streaming-kafka/results/test_analytics_volume.png) |
| Test — consumer group query | [test_can_query_consumer.png](../streaming-kafka/results/test_can_query_consumer.png) |
| Test — replay metrics | [test_replay_metrics.png](../streaming-kafka/results/test_replay_metrics.png) |
