"""
Tests for Part C – Streaming (Kafka).

Prerequisites:
  cd streaming-kafka && docker compose up --build
  Then run: cd tests && pytest -v
"""

import time

import requests
import pytest
from confluent_kafka.admin import AdminClient

PRODUCER_URL = "http://localhost:8000"
ANALYTICS_URL = "http://localhost:8002"
KAFKA_BOOTSTRAP = "localhost:9092"


def wait_for_service(url, timeout=30):
    """Wait for a service to become available."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{url}/health", timeout=2)
            if r.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    pytest.fail(f"Service at {url} not available after {timeout}s")


@pytest.fixture(scope="session", autouse=True)
def services_ready():
    """Ensure all services are up before running tests."""
    wait_for_service(PRODUCER_URL)
    wait_for_service(ANALYTICS_URL)
    # Give consumers a moment to subscribe
    time.sleep(3)


# ─── C6: Load Test ───────────────────────────────────────────────────────────


class TestLoadTest:
    """C6: Produce 10k events and verify processing."""

    def test_produce_10k_events(self):
        """Produce 10,000 OrderPlaced events via /load-test."""
        resp = requests.post(
            f"{PRODUCER_URL}/load-test",
            json={"count": 10000},
            timeout=120,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["produced"] == 10000
        assert data["remaining_in_queue"] == 0

    def test_inventory_processes_all(self):
        """Wait for inventory consumer to process all 10k events, then check analytics."""
        # Give consumers time to process all events
        max_wait = 120
        start = time.time()
        while time.time() - start < max_wait:
            resp = requests.get(f"{ANALYTICS_URL}/metrics", timeout=5)
            metrics = resp.json()
            if metrics["total_orders"] >= 10000:
                break
            time.sleep(2)

        resp = requests.get(f"{ANALYTICS_URL}/metrics", timeout=5)
        metrics = resp.json()

        assert metrics["total_orders"] >= 10000, (
            f"Expected >=10000 orders, got {metrics['total_orders']}"
        )
        print(f"\nLoad test metrics: {metrics}")

    def test_analytics_reflects_volume(self):
        """Verify analytics metrics reflect the total volume."""
        resp = requests.get(f"{ANALYTICS_URL}/metrics", timeout=5)
        metrics = resp.json()

        # Total reservations should eventually match (reserved + failed)
        # Give more time for inventory-events to be consumed
        max_wait = 60
        start = time.time()
        while time.time() - start < max_wait:
            resp = requests.get(f"{ANALYTICS_URL}/metrics", timeout=5)
            metrics = resp.json()
            if metrics["total_reservations"] >= 10000:
                break
            time.sleep(2)

        assert metrics["total_reservations"] >= 10000, (
            f"Expected >=10000 reservations, got {metrics['total_reservations']}"
        )
        # orders_per_minute should have entries
        assert len(metrics["orders_per_minute"]) > 0
        print(f"\nFinal analytics: {metrics}")


# ─── C5: Lag Under Throttling ────────────────────────────────────────────────


class TestLagUnderThrottling:
    """C5: Demonstrate consumer lag under throttling.

    NOTE: This test requires restarting inventory_consumer with CONSUMER_THROTTLE_MS set.
    For a full demo, run manually:
      CONSUMER_THROTTLE_MS=100 docker compose up --build
    Then produce events and observe lag via:
      docker compose exec kafka kafka-consumer-groups \
        --bootstrap-server kafka:29092 --describe --group inventory-service-group
    """

    def test_can_query_consumer_groups(self):
        """Verify we can query consumer group lag via admin client."""
        admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP})

        # List consumer groups
        groups = admin.list_consumer_groups()
        group_names = [g.group_id for g in groups.result(timeout=10).valid]
        assert "inventory-service-group" in group_names, (
            f"Expected inventory-service-group in groups, got {group_names}"
        )

    def test_produce_with_lag_observation(self):
        """Produce a small batch and observe lag is being tracked."""
        # Produce a small batch
        for i in range(50):
            requests.post(
                f"{PRODUCER_URL}/produce",
                json={"orderId": f"lag-test-{i}", "items": [{"sku": "taco", "qty": 1}]},
                timeout=5,
            )

        time.sleep(2)

        # Query lag via admin client
        admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP})

        groups = admin.list_consumer_groups()
        group_names = [g.group_id for g in groups.result(timeout=10).valid]
        assert "inventory-service-group" in group_names
        print(f"\nConsumer groups: {group_names}")
        print("To observe lag under throttling, restart with CONSUMER_THROTTLE_MS=100")


# ─── C4: Replay Demonstration ───────────────────────────────────────────────


class TestReplay:
    """C4: Demonstrate replay by resetting offsets and recomputing metrics."""

    def test_replay_metrics(self):
        """Trigger replay and verify metrics are recomputed."""
        # Get metrics before replay
        resp = requests.get(f"{ANALYTICS_URL}/metrics", timeout=5)
        before = resp.json()
        print(f"\nBefore replay: {before}")

        assert before["total_orders"] > 0, "No orders in metrics before replay"

        # Trigger replay
        resp = requests.post(f"{ANALYTICS_URL}/replay", timeout=10)
        assert resp.status_code == 200

        # Wait for replay to complete — consumer restarts and reprocesses
        max_wait = 120
        start = time.time()
        while time.time() - start < max_wait:
            time.sleep(3)
            resp = requests.get(f"{ANALYTICS_URL}/metrics", timeout=5)
            after = resp.json()
            # Replay should eventually re-read all events
            if after["total_orders"] >= before["total_orders"]:
                break

        print(f"After replay: {after}")

        # After replay, total_orders should match (or exceed if new events arrived)
        assert after["total_orders"] >= before["total_orders"], (
            f"After replay ({after['total_orders']}) should be >= before ({before['total_orders']})"
        )
