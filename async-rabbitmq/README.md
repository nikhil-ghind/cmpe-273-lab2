Async Communication Model – RabbitMQ (Part B)

Overview
This implementation models a Campus Food Ordering system using asynchronous messaging with RabbitMQ.
It demonstrates:
Event-driven architecture
Decoupled services
Backlog handling and recovery
Idempotent consumer design
Dead Letter Queue (DLQ) handling

Services:

1. Order Service
POST /order
Publishes OrderPlaced
Returns 202 Accepted immediately

2.Inventory Service
Consumes OrderPlaced
Publishes InventoryReserved or InventoryFailed
Implements idempotency using processed_orders set
Rejects malformed messages → sent to DLQ

3.Notification Service
Consumes InventoryReserved
Logs order confirmation

4.RabbitMQ
Handles exchanges and queues
Stores messages when services are down
Messaging Components

Exchanges
orders-ex
orders-dlx
inventory-ex

Queues
order.placed.q
order.placed.dlq
inventory.reserved.q
inventory.failed.q

How to Run
From inside async-rabbitmq/:

docker compose down -v
docker compose up --build -d
docker compose ps

Testing
1. Basic Flow
curl -X POST http://localhost:8001/order \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","restaurant_id":"r1","items":[{"sku":"burger","qty":1}]}'

Expected:
Inventory logs reservation
Notification logs:
[notify] Order confirmed: <order_id>

2. Backlog + Recovery
Stop Inventory:
docker compose stop inventory_service
Publish 30 orders:
for i in {1..30}; do
  curl -s -X POST http://localhost:8001/order \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"u$i\",\"restaurant_id\":\"r1\",\"items\":[{\"sku\":\"burger\",\"qty\":1}]}" > /dev/null
done

Check backlog:
docker compose exec rabbitmq rabbitmqctl list_queues name messages
Restart Inventory:
docker compose start inventory_service
Expected:
order.placed.q drains to 0
Orders are processed and confirmed

3️. Idempotency Test
Publish the same OrderPlaced message twice.
Expected Inventory log:
[inventory] duplicate ignored: <order_id>

4️. DLQ / Poison Message Test
Publish malformed message to orders-ex with routing key order.placed.
Verify DLQ:
docker compose exec rabbitmq rabbitmqctl list_queues name messages
Expected:
order.placed.dlq    1
Idempotency Strategy
InventoryService tracks processed order_id values in memory.
Duplicate messages are ignored to prevent double reservation.


Concepts Demonstrated
Asynchronous communication
Loose coupling via message broker
At-least-once delivery
Idempotent consumer
Dead Letter Queue handling
Backlog recovery