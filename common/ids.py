"""
common/ids.py

Shared ID generation utilities for the campus food ordering project.
Used across Part A (sync-rest), Part B (async-rabbitmq), and Part C (streaming-kafka).

Usage:
    from common.ids import new_order_id, new_event_id, new_user_id, new_restaurant_id
"""

import uuid


def new_order_id() -> str:
    """Generate a unique order ID.
    Format: o-<8 hex chars>  e.g. o-3f2a1b4c
    Used in: Part B (async-rabbitmq), Part C (streaming-kafka)
    """
    return f"o-{uuid.uuid4().hex[:8]}"


def new_event_id() -> str:
    """Generate a unique event ID.
    Format: full UUID  e.g. 550e8400-e29b-41d4-a716-446655440000
    Used in: Part C (streaming-kafka) — OrderPlaced, InventoryReserved, InventoryFailed events
    """
    return str(uuid.uuid4())


def new_user_id() -> str:
    """Generate a unique user ID.
    Format: u-<6 hex chars>  e.g. u-4a2f91
    Used in: Part B (async-rabbitmq) order payloads
    """
    return f"u-{uuid.uuid4().hex[:6]}"


def new_restaurant_id() -> str:
    """Generate a unique restaurant ID.
    Format: r-<6 hex chars>  e.g. r-7c3d02
    Used in: Part B (async-rabbitmq) order payloads
    """
    return f"r-{uuid.uuid4().hex[:6]}"


def new_sku() -> str:
    """Generate a random SKU for a menu item.
    Format: sku-<4 hex chars>  e.g. sku-9f1a
    Used in: order item payloads across all parts
    """
    return f"sku-{uuid.uuid4().hex[:4]}"


def new_load_test_order_id(index: int) -> str:
    """Generate a deterministic order ID for load testing by index.
    Format: load-<6 zero-padded index>  e.g. load-000042
    Used in: Part C (streaming-kafka) /load-test endpoint
    """
    return f"load-{index:06d}"
