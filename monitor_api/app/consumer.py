from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .database import Base, SessionLocal, engine
from .models import ActivityEvent, ConsumerState, Instance
from .openstack_client import fetch_instances

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("sandbox-consumer")

LOG_FILE = Path(
    os.getenv("HAPROXY_LOG_FILE", "/var/log/remote-haproxy.log")
)

POLL_INTERVAL = int(
    os.getenv("CONSUMER_INTERVAL_SECONDS", "15")
)

CONSUMER_NAME = "haproxy-log-consumer"

try:
    TARGET_MAP: dict[str, str] = json.loads(
        os.getenv("HAPROXY_TARGET_MAP", "{}")
    )
except json.JSONDecodeError as exc:
    raise ValueError("HAPROXY_TARGET_MAP must be valid JSON") from exc


# Standard HAProxy HTTP log fields.
HTTP_LOG_PATTERN = re.compile(
    r"\[(?P<date>[^\]]+)\]\s+"+
    r"(?P<frontend>\S+)\s+"+
    r"(?P<backend_server>\S+)\s+"+
    r"(?P<timings>\S+)\s+"+
    r"(?P<status>\d{3})\s+"+
    r"(?P<bytes>\d+)"
)


def parse_log_line(line: str) -> dict[str, object] | None:
    """Extract the HAProxy backend/server and HTTP status."""

    match = HTTP_LOG_PATTERN.search(line)

    if not match:
        return None

    record = match.groupdict()
    backend_server = record["backend_server"]

    backend, separator, server_name = backend_server.partition("/")

    if not separator or server_name == "<NOSRV>":
        return None

    target_ip = TARGET_MAP.get(server_name)

    return {
        "backend": backend,
        "server_name": server_name,
        "target_ip": target_ip,
        "http_status": int(record["status"]),
    }


def sync_inventory() -> None:
    """Refresh inventory without overwriting activity timestamps."""

    now = datetime.now(timezone.utc)
    servers = fetch_instances()

    with SessionLocal.begin() as session:
        for server in servers:
            instance = session.scalar(
                select(Instance).where(
                    Instance.server_id == server["server_id"]
                )
            )

            if instance is None:
                instance = Instance(
                    server_id=server["server_id"],
                    name=server["name"],
                    status=server["status"],
                    classification=server["classification"],
                    ips=server["ips"],
                    created_at=server["created_at"],
                    last_inventory_at=now,
                )
                session.add(instance)
            else:
                instance.name = server["name"]
                instance.status = server["status"]
                instance.classification = server["classification"]
                instance.ips = server["ips"]
                instance.created_at = server["created_at"]
                instance.last_inventory_at = now

    logger.info("Refreshed OpenStack inventory: %d servers", len(servers))


def read_new_lines(
    path: Path,
    inode: int | None,
    offset: int,
) -> tuple[int, int, list[tuple[int, str]]]:
    """
    Return current inode, next byte offset and new complete log lines.

    Incomplete final lines remain unread until the next poll.
    """

    stat = path.stat()
    current_inode = stat.st_ino

    if inode != current_inode or stat.st_size < offset:
        offset = 0

    lines: list[tuple[int, str]] = []

    with path.open("rb") as file:
        file.seek(offset)

        while True:
            line_start = file.tell()
            raw_line = file.readline()

            if not raw_line:
                break

            # Don't consume an incomplete final line.
            if not raw_line.endswith(b"\n"):
                break

            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            lines.append((line_start, line))

        next_offset = file.tell()

    return current_inode, next_offset, lines


def consume_logs() -> None:
    """Process new log records and persist events and checkpoint atomically."""

    if not LOG_FILE.exists():
        logger.warning("Log file does not exist: %s", LOG_FILE)
        return

    with SessionLocal.begin() as session:
        state = session.scalar(
            select(ConsumerState)
            .where(ConsumerState.consumer_name == CONSUMER_NAME)
            .with_for_update()
        )

        if state is None:
            state = ConsumerState(
                consumer_name=CONSUMER_NAME,
                file_inode=None,
                file_offset=0,
            )
            session.add(state)
            session.flush()

        inode, offset, lines = read_new_lines(
            LOG_FILE,
            state.file_inode,
            state.file_offset,
        )

        if not lines:
            state.file_inode = inode
            state.file_offset = offset
            return

        # Build lookup tables from the current inventory.
        instances = session.scalars(select(Instance)).all()

        by_ip: dict[str, Instance] = {}
        by_name: dict[str, Instance] = {}

        for instance in instances:
            by_name[instance.name] = instance

            for ip in instance.ips or []:
                by_ip[ip] = instance

        now = datetime.now(timezone.utc)
        parsed_count = 0
        unmatched_count = 0

        for _, line in lines:
            record = parse_log_line(line)

            if record is None:
                unmatched_count += 1
                continue

            server_name = str(record["server_name"])
            target_ip = record["target_ip"]

            instance = (
                by_ip.get(str(target_ip))
                if target_ip
                else by_name.get(server_name)
            )

            if instance is None:
                unmatched_count += 1
                continue

            # Record usage for managed sandboxes only.
            # Unknown and infrastructure VMs are never lifecycle candidates.
            if instance.classification != "sandbox":
                continue

            instance.last_seen_at = now

            session.add(
                ActivityEvent(
                    server_id=instance.server_id,
                    observed_at=now,
                    backend=str(record["backend"]),
                    server_name=server_name,
                    http_status=int(record["http_status"]),  # pyright: ignore[reportArgumentType]
                    log_line=line[:4000],
                )
            )

            parsed_count += 1

        # Checkpoint and events commit in the same transaction.
        # If the transaction fails, the previous offset remains.
        state.file_inode = inode
        state.file_offset = offset

    logger.info(
        "Processed %d lines: %d sandbox events, %d unmatched/unusable lines",
        len(lines),
        parsed_count,
        unmatched_count,
    )


def run() -> None:
    Base.metadata.create_all(bind=engine)

    logger.info("Starting sandbox monitoring consumer")

    while True:
        try:
            sync_inventory()
            consume_logs()
        except Exception:
            logger.exception("Monitoring iteration failed")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()