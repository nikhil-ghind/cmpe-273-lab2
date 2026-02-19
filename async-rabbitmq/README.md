# Part B — Async RabbitMQ

Asynchronous messaging implementation of the campus food ordering workflow using RabbitMQ.

**Workflow:** User places order → Inventory reserved/failed → Notification sent

---

## Requirements Coverage

| Requirement | Implemented | Where |
|---|---|---|
| OrderService writes order to local store | ✅ | `order_service/main.py` — `orders` dict |
| OrderService publishes `OrderPlaced` | ✅ | `order_service/main.py` — `POST /order` |
| InventoryService consumes `OrderPlaced` | ✅ | `inventory_service/main.py` |
| InventoryService publishes `InventoryReserved` or `InventoryFailed` | ✅ | `inventory_service/main.py` |
| NotificationService consumes `InventoryReserved` | ✅ | `notification_service/main.py` |
| Backlog drain after InventoryService restart | ✅ | Durable queues in RabbitMQ retain messages |
| Idempotency — no double reservation on duplicate delivery | ✅ | `processed_orders: set` in inventory_service |
| DLQ / poison message handling | ✅ | Malformed/invalid messages → `order.placed.dlq` via `orders-dlx` |

---

## Architecture

```
POST /order
     │
     ▼
order_service ──► [orders-ex] ──► order.placed.q ──► inventory_service
  (local store)       │                                      │
                      └──► orders-dlx ──► order.placed.dlq  │
                           (malformed/rejected messages)     │
                                                             ▼
                                                      [inventory-ex]
                                                      ┌──────┴──────┐
                                               inventory.reserved.q  inventory.failed.q
                                                      │
                                                      ▼
                                              notification_service
```

### Services

| Service | Port | Role |
|---|---|---|
| `order_service` | 8001 | FastAPI — stores orders locally, publishes `OrderPlaced` |
| `inventory_service` | — | Consumes `OrderPlaced`, publishes `InventoryReserved` or `InventoryFailed` |
| `notification_service` | — | Consumes `InventoryReserved`, logs order confirmation |
| `rabbitmq` | 5672 / 15672 | Message broker + management UI |

### Exchanges and Queues

| Exchange | Type | Purpose |
|---|---|---|
| `orders-ex` | direct | Receives `OrderPlaced` events from order_service |
| `orders-dlx` | direct | Dead letter exchange for rejected/malformed messages |
| `inventory-ex` | direct | Receives `InventoryReserved` / `InventoryFailed` from inventory_service |

| Queue | Bound Exchange | Routing Key | Purpose |
|---|---|---|---|
| `order.placed.q` | `orders-ex` | `order.placed` | Delivers orders to inventory_service |
| `order.placed.dlq` | `orders-dlx` | `order.placed.dlq` | Catches malformed/rejected messages |
| `inventory.reserved.q` | `inventory-ex` | `inventory.reserved` | Delivers successful reservations to notification_service |
| `inventory.failed.q` | `inventory-ex` | `inventory.failed` | Stores failed reservation events |

---

## Implementation Details

### order_service

- FastAPI server on port 8001 (mapped from internal 8000)
- `POST /order` — accepts an order, writes it to local in-memory store, publishes `OrderPlaced`, returns `202 Accepted`
  - Generates a UUID `order_id`
  - **Writes to local `orders` dict** before publishing: `{ order_id, status, data }`
  - Publishes a persistent `OrderPlaced` event to `orders-ex` with routing key `order.placed`
  - Event schema: `{ event_type, order_id, user_id, restaurant_id, items, ts }`
- `GET /order/{order_id}` — retrieves a single order from local store
- `GET /orders` — lists all orders in local store with count
- Connects to RabbitMQ on startup with retry logic (up to 60 attempts, 1s delay)
- Uses `aio_pika.connect_robust` for automatic reconnection

### inventory_service

- Pure async consumer (no HTTP server)
- Consumes `OrderPlaced` events from `order.placed.q` with `prefetch_count=5`
- **Failure rule**: any item with `qty > 5` triggers `InventoryFailed`; otherwise `InventoryReserved`
- **Idempotent**: tracks processed `order_id` values in an in-memory `set`
  - If the same `order_id` is received more than once, logs `[inventory] duplicate ignored: <order_id>` and skips processing
  - Prevents double reservation on at-least-once redelivery
- **DLQ handling**: malformed JSON or wrong `event_type` is rejected with `requeue=False`, routing the message to `order.placed.dlq` via `orders-dlx`
- Publishes `InventoryReserved` or `InventoryFailed` to `inventory-ex` as persistent messages

### notification_service

- Pure async consumer (no HTTP server)
- Consumes `InventoryReserved` events from `inventory.reserved.q` with `prefetch_count=10`
- Logs `[notify] Order confirmed: <order_id>` for each successful reservation
- Unexpected event types are logged and acknowledged (not rejected)

### common/rabbit.py

Shared topology setup used by all three services:
- `setup_orders_topology(channel)` — declares `orders-ex`, `orders-dlx`, `order.placed.q` (with DLX config), `order.placed.dlq` and all bindings
- `setup_inventory_topology(channel)` — declares `inventory-ex`, `inventory.reserved.q`, `inventory.failed.q` and all bindings
- All declarations are idempotent — any service can call setup without conflict

---

## Setup

### Start all services

```bash
cd async-rabbitmq
docker compose up --build -d
```

Verify all services are running:

```bash
docker compose ps
```

### RabbitMQ management UI

Open in browser: `http://localhost:15672`
- Username: `guest`
- Password: `guest`

### Teardown

```bash
docker compose down -v
```

The `-v` flag removes volumes, clearing all queued messages and RabbitMQ state.

---

## API Reference

### order_service (port 8001)

**Place an order:**
```bash
curl -s -X POST http://localhost:8001/order \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "restaurant_id": "r1", "items": [{"sku": "burger", "qty": 1}]}' \
  | python3 -m json.tool
```

Expected response (`202 Accepted`):
```json
{
    "order_id": "<uuid>",
    "status": "PLACED"
}
```

**Get a specific order from local store:**
```bash
curl -s http://localhost:8001/order/<order_id> | python3 -m json.tool
```

**List all orders in local store:**
```bash
curl -s http://localhost:8001/orders | python3 -m json.tool
```

**Health check:**
```bash
curl -s http://localhost:8001/health | python3 -m json.tool
```

---

## Testing

### 1. Basic flow

Place an order and verify the full pipeline runs:

```bash
curl -s -X POST http://localhost:8001/order \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "restaurant_id": "r1", "items": [{"sku": "burger", "qty": 1}]}' \
  | python3 -m json.tool
```

Check service logs:
```bash
docker compose logs inventory_service
docker compose logs notification_service
```

Expected inventory log:
```
[inventory] reservation OK for <order_id>
[inventory] published InventoryReserved for <order_id>
```

Expected notification log:
```
[notify] Order confirmed: <order_id>
```

### 2. Backlog and recovery (60-second kill test)

Kill inventory_service, publish 30 orders, then restart and verify the backlog drains:

```bash
# Stop inventory
docker compose stop inventory_service

# Publish 30 orders while inventory is down
for i in {1..30}; do
  curl -s -X POST http://localhost:8001/order \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"u$i\",\"restaurant_id\":\"r1\",\"items\":[{\"sku\":\"burger\",\"qty\":1}]}" > /dev/null
done

# Check backlog — should show 30 messages queued in order.placed.q
docker compose exec rabbitmq rabbitmqctl list_queues name messages

# Wait ~60 seconds, then restart inventory
sleep 60
docker compose start inventory_service

# Watch backlog drain to 0
docker compose exec rabbitmq rabbitmqctl list_queues name messages

# Confirm all 30 orders were processed
docker compose logs inventory_service
docker compose logs notification_service
```

Expected: `order.placed.q` drains to 0 and all 30 orders appear as confirmed in notification logs. Messages are retained durably by RabbitMQ while the consumer is down.

### 3. Idempotency test

The inventory_service tracks processed `order_id` values in an in-memory `set`. If the same `OrderPlaced` message is delivered twice, the second delivery is detected and skipped — no double reservation occurs.

**Strategy:** On receiving a message, inventory_service checks `if order_id in processed_orders`. If found, it logs `[inventory] duplicate ignored: <order_id>` and returns without publishing any event. Only after this check passes does it add the `order_id` to the set and proceed with reservation.

To demonstrate, place an order and note the `order_id`, then use the RabbitMQ management UI (`http://localhost:15672`) to manually re-publish the same message body to `orders-ex` with routing key `order.placed`:

```bash
# Place an order
curl -s -X POST http://localhost:8001/order \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "restaurant_id": "r1", "items": [{"sku": "burger", "qty": 1}]}' \
  | python3 -m json.tool
```

After re-publishing the duplicate, check inventory logs:
```
[inventory] duplicate ignored: <order_id>
```

Only one `InventoryReserved` event is published — no double reservation.

### 4. DLQ / poison message test

**Trigger via high qty (InventoryFailed path):**
```bash
curl -s -X POST http://localhost:8001/order \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "restaurant_id": "r1", "items": [{"sku": "burger", "qty": 10}]}' \
  | python3 -m json.tool
```

Expected inventory log:
```
[inventory] reservation FAILED for <order_id>
[inventory] published InventoryFailed for <order_id>
```

**Trigger DLQ with malformed message:**

Use the RabbitMQ management UI (`http://localhost:15672`) → Exchanges → `orders-ex` → Publish Message, and send invalid JSON or a message missing `order_id`. The inventory_service will reject it with `requeue=False`, routing it to `order.placed.dlq`.

Verify the DLQ received the message:
```bash
docker compose exec rabbitmq rabbitmqctl list_queues name messages
```

Expected:
```
order.placed.dlq    1
```

---

## Idempotency Strategy

The inventory_service maintains a module-level `processed_orders: set[str]` in memory. Before processing any `OrderPlaced` event:

1. The `order_id` is extracted from the message payload
2. If `order_id in processed_orders` → log duplicate, acknowledge message, return immediately
3. Otherwise → add `order_id` to the set, proceed with reservation

This prevents double reservation when RabbitMQ redelivers a message (e.g. after a consumer crash before acknowledgement). The tradeoff is that the set is lost on restart — in production this would be backed by a database.

---

## Concepts Demonstrated

| Concept | Implementation |
|---|---|
| Local order store | `orders` dict in order_service — written before publishing |
| Asynchronous communication | `POST /order` returns `202` immediately; processing happens async |
| Loose coupling | Services communicate only through RabbitMQ — no direct HTTP calls |
| At-least-once delivery | Persistent messages + manual ack (`prefetch_count` limits in-flight) |
| Idempotent consumer | `processed_orders: set` in inventory_service prevents double reservation |
| Dead Letter Queue | Malformed/rejected messages route to `order.placed.dlq` via `orders-dlx` |
| Backlog recovery | RabbitMQ durably stores messages while inventory_service is down |
| Reconnection resilience | All services use `connect_with_retry` (60 attempts) + `connect_robust` |
