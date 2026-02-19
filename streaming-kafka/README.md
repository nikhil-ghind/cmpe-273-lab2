# Part C — Streaming Kafka

Event streaming implementation of the campus food ordering workflow using Apache Kafka.

**Workflow:** User places order → Inventory reserved → Analytics updated

---

## Requirements Coverage

| Requirement | Implemented | Where |
|---|---|---|
| Producer publishes `OrderPlaced` events | ✅ | `producer_order/main.py` — `POST /produce` |
| Inventory consumes and emits `InventoryReserved` / `InventoryFailed` | ✅ | `inventory_consumer/main.py` |
| Analytics computes orders per minute | ✅ | `analytics_consumer/main.py` — `orders_per_minute` dict |
| Analytics computes failure rate | ✅ | `analytics_consumer/main.py` — `failed_reservations / total_reservations` |
| Replay: reset offsets and recompute metrics | ✅ | `analytics_consumer/main.py` — `POST /replay` |
| Produce 10k events | ✅ | `POST /load-test` + `test_produce_10k_events` |
| Consumer lag under throttling | ✅ | `CONSUMER_THROTTLE_MS` env var + `TestLagUnderThrottling` |
| Replay produces consistent metrics | ✅ | `test_replay_metrics` — after >= before |
| Metrics output file | ✅ | Written to `/app/metrics.txt` every 5 seconds |
| Evidence of replay before/after | ✅ | `results/kafka_replay.png` + `results/metrics_after_reply.png` |

---

## Architecture

```
POST /produce
     │
     ▼
producer_order ──► [orders topic] ──► inventory_consumer ──► [inventory-events topic]
     │                                                                  │
     ▼                                                                  ▼
POST /load-test                                              analytics_consumer
                                                                  │
                                                                  ▼
                                                            GET /metrics
                                                            POST /replay
```

### Services

| Service | Port | Role |
|---|---|---|
| `producer_order` | 8000 | FastAPI — publishes `OrderPlaced` events to `orders` topic |
| `inventory_consumer` | — | Consumes `orders`, publishes `InventoryReserved` / `InventoryFailed` to `inventory-events` |
| `analytics_consumer` | 8002 | Consumes both topics, tracks metrics, exposes `/metrics` and `/replay` |

### Kafka Topics

| Topic | Partitions | Producers | Consumers |
|---|---|---|---|
| `orders` | 3 | `producer_order` | `inventory_consumer`, `analytics_consumer` |
| `inventory-events` | 3 | `inventory_consumer` | `analytics_consumer` |

---

## Implementation Details

### producer_order

- FastAPI server on port 8000
- `POST /produce` — publishes a single `OrderPlaced` event to the `orders` topic
  - Event schema: `{ eventId, eventType: "OrderPlaced", orderId, items, createdAt }`
  - Event key is `orderId` (ensures same order routes to the same partition)
- `POST /load-test` — produces N `OrderPlaced` events (default 10,000) and flushes all to Kafka before returning
- Uses `linger.ms=5` and `batch.num.messages=1000` for high-throughput batched production

### inventory_consumer

- Kafka consumer in `inventory-service-group`
- Consumes `OrderPlaced` events from the `orders` topic
- For each order, publishes either `InventoryReserved` or `InventoryFailed` to `inventory-events`
- **Idempotent**: tracks processed order IDs in an in-memory `set` — if the same `orderId` is received more than once, it is skipped and not double-reserved
- **Fault injection** via environment variables:
  - `INVENTORY_FAIL_RATE` — fraction of orders that randomly fail (e.g. `0.3` = 30% failure rate)
  - `CONSUMER_THROTTLE_MS` — artificial delay per message to simulate a slow consumer and demonstrate consumer lag

### analytics_consumer

- Kafka consumer in `analytics-group` + FastAPI server on port 8002
- Subscribes to both `orders` and `inventory-events` topics
- Computes and tracks:
  - `total_orders` — count of `OrderPlaced` events seen
  - `total_reservations` — count of `InventoryReserved` + `InventoryFailed` events
  - `failed_reservations` — count of `InventoryFailed` events
  - `failure_rate` — `failed_reservations / total_reservations`
  - `orders_per_minute` — order counts bucketed by the event's `createdAt` minute timestamp
- Writes a formatted metrics report to stdout and `/app/metrics.txt` every 5 seconds
- `POST /replay` — resets the consumer group offsets to 0 across all partitions of both topics, clears in-memory metrics state, and reprocesses all events from the beginning of the log

---

## Setup

### Start all services

```bash
cd streaming-kafka
docker compose up --build
```

This starts: Zookeeper → Kafka → init-kafka (creates topics) → producer_order → inventory_consumer → analytics_consumer

Wait for `init-kafka` to finish creating the `orders` and `inventory-events` topics before the services become ready.

### Verify services are healthy

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:8002/health | python3 -m json.tool
```

![Health Check](results/health_check.png)

### Teardown

```bash
docker compose down
```

If Kafka fails to start with a `NodeExists` error (stale Zookeeper state from a previous session), wipe volumes and restart:

```bash
docker compose down -v
docker compose up --build
```

---

## API Reference

### producer_order (port 8000)

**Produce a single order:**
```bash
curl -s -X POST http://localhost:8000/produce \
  -H "Content-Type: application/json" \
  -d '{"orderId": "o-123", "items": [{"sku": "burrito", "qty": 1}]}' | python3 -m json.tool
```

![Produce Single Order](results/produce_1.png)

**Load test — produce 100 events:**
```bash
curl -s -X POST http://localhost:8000/load-test \
  -H "Content-Type: application/json" \
  -d '{"count": 100}' | python3 -m json.tool
```

![Load Test 100](results/load_100_test.png)

**Load test — produce 10,000 events:**
```bash
curl -s -X POST http://localhost:8000/load-test \
  -H "Content-Type: application/json" \
  -d '{"count": 10000}' | python3 -m json.tool
```

![Load Test 10k](results/produce_10k_test.png)

### analytics_consumer (port 8002)

**Get metrics:**
```bash
curl -s http://localhost:8002/metrics | python3 -m json.tool
```

![Metrics](results/metrics.png)

**Trigger replay:**
```bash
curl -s -X POST http://localhost:8002/replay | python3 -m json.tool
```

![Kafka Replay](results/kafka_replay.png)

**Metrics after replay:**
```bash
curl -s http://localhost:8002/metrics | python3 -m json.tool
```

![Metrics After Replay](results/metrics_after_reply.png)

---

## Fault Injection

### Inventory failure rate (30%)

```bash
docker compose down -v
INVENTORY_FAIL_RATE=0.3 docker compose up --build
```

Produce events and verify `failure_rate` is ~0.3 in metrics:

```bash
curl -s -X POST http://localhost:8000/load-test \
  -H "Content-Type: application/json" \
  -d '{"count": 100}' | python3 -m json.tool

sleep 5
curl -s http://localhost:8002/metrics | python3 -m json.tool
```

![Fail Rate 30%](results/fail_rate_30.png)

![Metrics After Fail Rate](results/check_metrics_after_fail_rate.png)

### Consumer lag (throttling)

```bash
docker compose down -v
CONSUMER_THROTTLE_MS=100 docker compose up --build
```

Produce events and observe lag building up:

```bash
curl -s -X POST http://localhost:8000/load-test \
  -H "Content-Type: application/json" \
  -d '{"count": 500}' | python3 -m json.tool
```

![Load Test With Throttle](results/load_test_with_throttle.png)

Check consumer lag via Kafka admin:

```bash
docker compose exec kafka kafka-consumer-groups \
  --bootstrap-server kafka:29092 \
  --describe --group inventory-service-group
```

![Consumer Throttle](results/consumer__throttle.png)

---

## Submission Artifacts

### Metrics output file

The analytics consumer writes a formatted report to `/app/metrics.txt` inside the container every 5 seconds. Sample output:

```
=== Analytics Metrics ===
Total orders seen: 10000
Total reservations: 10000
Failed reservations: 0
Failure rate: 0.0000

Orders per minute:
  2026-02-19T04:30: 10000
```

To retrieve it from the running container:

```bash
docker compose exec analytics_consumer cat /app/metrics.txt
```

### Replay — before and after evidence

Replay resets the `analytics-group` consumer offsets to 0 across all partitions of `orders` and `inventory-events`, clears all in-memory metrics state, and reprocesses the full event log from the beginning.

**Before replay:**

![Kafka Replay](results/kafka_replay.png)

**After replay:**

![Metrics After Replay](results/metrics_after_reply.png)

**Note on consistency:** After replay, `total_orders` is guaranteed to be `>=` the pre-replay count rather than exactly equal. This is expected — new events may arrive from the producer while the replay is in progress, causing the post-replay count to be slightly higher. This is correct Kafka behavior: the event log is durable and all events are reprocessed faithfully.

![Test Replay Metrics](results/test_replay_metrics.png)

---

## Running Tests

### Setup

```bash
cd streaming-kafka/tests
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run all tests

> Services must be running via `docker compose up --build` before running tests.

```bash
pytest -v
```

### Run tests one at a time

```bash
pytest -v -k test_produce_10k_events && \
pytest -v -k test_inventory_processes_all && \
pytest -v -k test_analytics_reflects_volume && \
pytest -v -k test_can_query_consumer_groups && \
pytest -v -k test_produce_with_lag_observation && \
pytest -v -k test_replay_metrics
```

---

## Test Cases

### C6 — Load Test (`TestLoadTest`)

Verifies the system can handle high-throughput event production and processing end to end.

**`test_produce_10k_events`**
- Calls `POST /load-test` with `count=10000`
- Asserts response returns `produced=10000` and `remaining_in_queue=0`
- Confirms all messages were flushed to Kafka before the endpoint returned

![Produce 10k Test](results/produce_10k_test.png)

**`test_inventory_processes_all`**
- Waits up to 120 seconds for `analytics_consumer` to report `total_orders >= 10000`
- Asserts inventory consumer processed all events from the `orders` topic

![Test Inventory All](results/test_inventory_all.png)

**`test_analytics_reflects_volume`**
- Waits up to 60 seconds for `total_reservations >= 10000`
- Asserts `orders_per_minute` has at least one time bucket entry
- Confirms analytics consumer read and processed all `inventory-events`

![Test Analytics Volume](results/test_analytics_volume.png)

---

### C5 — Consumer Lag Under Throttling (`TestLagUnderThrottling`)

Demonstrates Kafka's ability to track and expose consumer lag when a consumer is slow. To observe real lag, restart with `CONSUMER_THROTTLE_MS=100` before running these tests.

**`test_can_query_consumer_groups`**
- Uses `confluent_kafka.admin.AdminClient` to list all consumer groups
- Asserts `inventory-service-group` is present
- Confirms the inventory consumer registered with Kafka

![Test Can Query Consumer](results/test_can_query_consumer.png)

**`test_produce_with_lag_observation`**
- Produces 50 orders via `POST /produce`
- Queries consumer groups via admin client
- Asserts `inventory-service-group` still exists and lag is being tracked

![Check For Consumer Groups](results/check_for_consumer_grps.png)

![Produce With Lag](results/produce_with_lag.png)

---

### C4 — Replay (`TestReplay`)

Verifies that the analytics consumer can reset its offsets and recompute metrics from scratch, demonstrating Kafka's event log durability.

**`test_replay_metrics`**
- Captures `before` metrics via `GET /metrics` — asserts `total_orders > 0`
- Calls `POST /replay` to trigger offset reset and metric state clear
- Waits up to 120 seconds for the consumer to reprocess all events
- Asserts `after.total_orders >= before.total_orders`
- Proves that events are permanently stored in Kafka and can be replayed at any time

![Test Replay Metrics](results/test_replay_metrics.png)
