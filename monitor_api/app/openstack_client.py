from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import openstack
from openstack.connection import Connection
from dotenv import load_dotenv

load_dotenv()

INFRASTRUCTURE_NAMES = {
    name.strip()
    for name in os.getenv("INFRASTRUCTURE_INSTANCES", "").split(",")
    if name.strip()
}

INFRASTRUCTURE_IDS = {
    server_id.strip()
    for server_id in os.getenv("INFRASTRUCTURE_IDS", "").split(",")
    if server_id.strip()
}


def get_connection() -> Connection:
    return openstack.connect(
        cloud=os.getenv("OS_CLOUD", "default")
    )


def classify_instance(server: Any) -> str:
    metadata = server.metadata or {}

    if (
        server.id in INFRASTRUCTURE_IDS
        or server.name in INFRASTRUCTURE_NAMES
        or metadata.get("role") == "infrastructure"
    ):
        return "infrastructure"

    if metadata.get("managed_by") == "sandbox-manager":
        return "sandbox"

    return "unknown"


def fetch_instances() -> list[dict[str, Any]]:
    connection = get_connection()
    instances: list[dict[str, Any]] = []

    for server in connection.compute.servers(details=True):
        addresses = server.addresses or {}

        ips = sorted({
            address["addr"]
            for network_addresses in addresses.values()
            for address in network_addresses
            if address.get("addr")
        })

        created_at = server.created_at

        if isinstance(created_at, datetime):
            created_at = created_at

        instances.append({
            "server_id": server.id,
            "name": server.name,
            "status": server.status,
            "classification": classify_instance(server),
            "ips": ips,
            "created_at": created_at,
        })

    return instances