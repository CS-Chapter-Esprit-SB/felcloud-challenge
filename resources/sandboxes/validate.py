"""
Batch-level validation for sandbox YAML files.

The Pydantic `Sandbox` model validates ONE file. This module validates a whole
BATCH: it reports every broken file, then checks things no single file can know
(duplicate names/IPs/hostnames, IPs outside the subnet, ...).

Everything here is offline: no OpenStack calls, no Pulumi. Checks that need the
real cloud (IP already taken, quotas) live in tools/preflight.py.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from .loader import load_sandboxes, LoadedSandbox,CLIENTS_NEW

from .models import Sandbox,Needs,BatchValidationError

# YAML subnet key -> CIDR. Must match what your network module creates.
DEFAULT_SUBNET_CIDRS: dict[str, str] = {
    "inbound_subnet": "10.0.1.0/24",
    "outbound_subnet": "10.0.2.0/24",
}



def resource_name(raw: str) -> str:
    """Same sanitising as SandboxManager._resource_name (a test keeps them in sync)."""
    return re.sub(r"[^a-zA-Z0-9-]", "-", raw).strip("-").lower()


# --------------------------------------------------------------------------- #
# 1. Loading: collect every broken file instead of dying on the first one
# --------------------------------------------------------------------------- #



# --------------------------------------------------------------------------- #
# 2. Cross-file checks
# --------------------------------------------------------------------------- #
def check_batch(
    items: Iterable[LoadedSandbox],
    subnet_cidrs: Mapping[str, str]  = DEFAULT_SUBNET_CIDRS,
    reserved_ips: Iterable[str] = (),
) -> list[str]:
    """Return a list of problems (empty list == batch is consistent)."""
    items = list(items)

    cidrs = {k: IPv4Network(v) for k, v in subnet_cidrs.items()}
    reserved = {IPv4Address(ip) for ip in reserved_ips}
    errors: list[str] = []

    by_name: dict[str, list[str]] = defaultdict(list)
    by_ip: dict[IPv4Address, list[str]] = defaultdict(list)
    by_host: dict[str, list[str]] = defaultdict(list)

    for path, sb in items:
        f = path.name
        rname = resource_name(sb.name)
        if not rname:
            errors.append(f"{f}: name {sb.name!r} is empty after sanitising")
        by_name[rname].append(f)

        if sb.url.host:
            by_host[sb.url.host.lower()].append(f)

        if sb.ip is not None:
            by_ip[sb.ip].append(f)
            net = cidrs.get(sb.subnet)
            if net is not None:
                if sb.ip not in net:
                    errors.append(f"{f}: ip {sb.ip} is outside {sb.subnet} ({net})")
                elif sb.ip in (net.network_address, net.broadcast_address):
                    errors.append(f"{f}: ip {sb.ip} is the network/broadcast address of {net}")
            if sb.ip in reserved:
                errors.append(f"{f}: ip {sb.ip} is reserved for shared infrastructure")

        # The model only accepts IPv4 prefixes, so an IPv6 rule can never be valid.
        for direction, rules in (("ingress", sb.security_group.ingress), ("egress", sb.security_group.egress)):
            for i, rule in enumerate(rules):
                if rule.ethertype == "IPv6" and rule.remote_ip_prefix is not None:
                    errors.append(
                        f"{f}: security_group.{direction}[{i}]: ethertype IPv6 " +
                        f"with IPv4 remote_ip_prefix {rule.remote_ip_prefix}"
                    )

    for label, groups in (("name", by_name), ("ip", by_ip), ("hostname", by_host)):
        for value, files in groups.items():
            if len(files) > 1:
                errors.append(f"duplicate {label} {str(value)!r} in: {', '.join(sorted(files))}")

    return errors



def validate_directory(
    subnet_cidrs: Mapping[str, str] = DEFAULT_SUBNET_CIDRS,
    reserved_ips: Iterable[str] = (),
    Directory: Path = CLIENTS_NEW,
) -> list[LoadedSandbox]:
    """Load + cross-check. Raises BatchValidationError listing ALL problems."""
    loaded, errors = load_sandboxes()
    errors += check_batch(loaded, subnet_cidrs, reserved_ips)
    if not loaded and not errors:
        errors.append(f"no sandbox YAML files found in {Directory.resolve()}")
    if errors:
        raise BatchValidationError(errors)
    return loaded

# --------------------------------------------------------------------------- #
# 3. Resource estimate (used by preflight quota check and cross-checked by a test)
# --------------------------------------------------------------------------- #



def estimate_needs(
    sandboxes: Sequence[Sandbox],
    *,
    n_allowed_ingress: int = 0,
    n_shared_services: int = 0,
) -> Needs:
    """
    Per sandbox: 1 instance, 1 port, 1 security group, and
      YAML ingress + YAML egress + allowed_ingress + 2 per shared service
    rules (the shared-service pair is an egress rule on the sandbox group plus an
    ingress rule on the service's group; both count against the project quota).
    """
    n = len(sandboxes)
    rules = sum(
        len(s.security_group.ingress) + len(s.security_group.egress) for s in sandboxes
    ) + n * (n_allowed_ingress + 2 * n_shared_services)
    return Needs(
        instances=n,
        ports=n,
        security_groups=n,
        security_group_rules=rules,
        transient_rules=2 * n,
    )