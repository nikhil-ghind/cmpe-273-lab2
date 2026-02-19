# CMPE 273 Lab 2 — Campus Food Ordering Workflow

**Team:** Nikhil Ghind, Richie Nguyen, Jahnavi Chenna, Cameron Ghaemmaghami

Three implementations of the same workflow — **User places order → Inventory reserved → User notified** — each demonstrating a different communication model.

For full documentation, setup steps, API reference, and test results, see:

**[common/README.md](common/README.md)**

---

## Quick Reference

| Part | Directory | Stack | Model |
|------|-----------|-------|-------|
| A | [`sync-rest/`](sync-rest/README.md) | Flask, requests | Synchronous REST |
| B | [`async-rabbitmq/`](async-rabbitmq/README.md) | FastAPI, aio-pika | Async Messaging (RabbitMQ) |
| C | [`streaming-kafka/`](streaming-kafka/README.md) | FastAPI, confluent-kafka | Event Streaming (Kafka) |

---

## Run Any Part

```bash
# Part A
cd sync-rest && docker compose up --build

# Part B
cd async-rabbitmq && docker compose up --build -d

# Part C
cd streaming-kafka && docker compose up --build
```

Each part is self-contained. See [common/README.md](common/README.md) for full setup instructions, curl commands, test steps, and test result screenshots for all three parts.
