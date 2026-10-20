from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

LOG_FILE = Path(
    os.getenv("HAPROXY_LOG_FILE", "/var/log/remote-haproxy.log")
)

try:
    TARGET_MAP: dict[str, str] = json.loads(
        os.getenv("HAPROXY_TARGET_MAP", "{}")
    )
except json.JSONDecodeError as exc:
    raise ValueError("HAPROXY_TARGET_MAP must contain valid JSON") from exc


# Standard HAProxy HTTP log structure:
# [date] frontend backend/server timings status bytes ...
HTTP_LOG_PATTERN = re.compile(
    r"\[(?P<date>[^\]]+)\]\s+"+
    r"(?P<frontend>\S+)\s+"+
    r"(?P<backend_server>\S+)\s+"+
    r"(?P<timings>\S+)\s+"+
    r"(?P<status>\d{3})\s+"+
    r"(?P<bytes>\d+)"
)


def parse_haproxy_logs(max_lines: int = 100_000) -> dict[str, Any]:
    """Parse recent HAProxy HTTP logs and count requests by backend."""
    if not LOG_FILE.exists():
        raise FileNotFoundError(f"HAProxy log file not found: {LOG_FILE}")

    requests: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    parsed_lines = 0
    unmatched_lines = 0

    # Read only a bounded number of recent lines.
    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as log:
        lines = log.readlines()[-max_lines:]

    for line in lines:
        match = HTTP_LOG_PATTERN.search(line)

        if not match:
            unmatched_lines += 1
            continue

        record = match.groupdict()
        backend_server = record["backend_server"]

        # HAProxy represents a backend/server as backend_name/server_name.
        backend, separator, server_name = backend_server.partition("/")

        if not separator or server_name == "<NOSRV>":
            target_ip = None
        else:
            # Server names must be mapped to their actual OpenStack IPs.
            target_ip = TARGET_MAP.get(server_name)

        target_key = target_ip or (
            server_name if separator else backend_server
        )

        requests[target_key] += 1
        statuses[record["status"]] += 1
        parsed_lines += 1

    return {
        "log_file": str(LOG_FILE),
        "parsed_lines": parsed_lines,
        "unmatched_lines": unmatched_lines,
        "requests_by_target": dict(requests),
        "responses_by_status": dict(statuses),
    }