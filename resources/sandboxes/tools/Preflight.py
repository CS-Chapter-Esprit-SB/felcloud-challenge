"""
Preflight: ask OpenStack whether this batch can succeed BEFORE `pulumi up`.

  python -m tools.preflight --sandbox-dir sandboxes --flavor m1.small

Credentials come from the usual places (clouds.yaml + OS_CLOUD, or OS_* env vars).
Exit code: 0 = OK (warnings allowed), 1 = would fail, 2 = bad YAML / bad usage.
"""
from __future__ import annotations

import argparse
import sys
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Any

from resources.sandboxes.validate import (

    estimate_needs,
    validate_directory,
)
from resources.sandboxes.loader import LoadedSandbox
from resources.sandboxes.models import Needs, BatchValidationError

# YAML subnet key -> real Neutron subnet name. Override with --subnet key=name.
DEFAULT_SUBNET_NAMES = {
    "inbound_subnet": "inbound-subnet",
    "outbound_subnet": "outbound-subnet",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _get(obj: Any, name: str) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
    """Read a field from an SDK object or a dict."""
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)  # pyright: ignore[reportUnknownMemberType, reportAny, reportUnknownVariableType]


def _check(label: str, limit: int | None, in_use: int, needed: int, errors: list[str]) -> None:
    """limit None or -1 means unlimited."""
    unlimited = limit is None or limit < 0
    free = "unlimited" if unlimited else str(limit - in_use)
    status = "ok"
    if not unlimited and in_use + needed > limit:
        status = "TOO FEW"
        errors.append(f"quota: {label}: need {needed}, only {limit - in_use} free (limit {limit}, used {in_use})")
    print(f"  {label:<24} need {needed:>4}   free {free:>9}   {status}")


# --------------------------------------------------------------------------- #
# quotas
# --------------------------------------------------------------------------- #
def check_quotas(conn: Any, needs: Needs, flavor_name: str | None) -> list[str]:
    errors: list[str] = []
    print("Quotas:")

    absolute = conn.compute.get_limits().absolute
    _check("instances", absolute.instances, absolute.instances_used, needs.instances, errors)

    if flavor_name:
        flavor = conn.compute.find_flavor(flavor_name)
        if flavor is None:
            errors.append(f"flavor {flavor_name!r} not found")
        else:
            _check("cores", absolute.total_cores, absolute.total_cores_used,
                   needs.instances * flavor.vcpus, errors)
            _check("ram (MB)", absolute.total_ram, absolute.total_ram_used,
                   needs.instances * flavor.ram, errors)

    quota = conn.network.get_quota(conn.current_project_id, details=True)
    for attr, needed in (
        ("ports", needs.ports),
        ("security_groups", needs.security_groups),
        # peak = permanent rules + the default rules that exist for a moment
        ("security_group_rules", needs.security_group_rules + needs.transient_rules),
    ):
        entry = _get(quota, attr)
        if entry is None:
            print(f"  {attr:<24} (not reported by this cloud, skipped)")
            continue
        used = (_get(entry, "used") or 0) + (_get(entry, "reserved") or 0)
        _check(attr, _get(entry, "limit"), used, needed, errors)

    return errors


# --------------------------------------------------------------------------- #
# static IPs
# --------------------------------------------------------------------------- #
def check_ips(
    conn: Any, items: list[LoadedSandbox], subnet_names: dict[str, str]
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    print("Static IPs:")

    wanted = [(p, s) for p, s in items if s.ip is not None]
    if not wanted:
        print("  none requested (Neutron will allocate every address)")
        return errors, warnings

    cache: dict[str, tuple[Any, set[str]]] = {}
    for path, sb in wanted:
        key = sb.subnet
        if key not in cache:
            subnet = conn.network.find_subnet(subnet_names[key])
            if subnet is None:
                errors.append(f"subnet {subnet_names[key]!r} (for {key}) not found in OpenStack")
                cache[key] = (None, set())
                continue
            used: set[str] = set()
            for port in conn.network.ports(network_id=subnet.network_id):
                for fixed in port.fixed_ips or []:
                    used.add(fixed["ip_address"])
            cache[key] = (subnet, used)

        subnet, used = cache[key]
        if subnet is None:
            continue

        ip = IPv4Address(str(sb.ip))
        if ip not in IPv4Network(subnet.cidr):
            errors.append(f"{path.name}: {ip} is outside real subnet {subnet.name} ({subnet.cidr})")
        elif str(ip) in used:
            errors.append(f"{path.name}: {ip} is already assigned to a port on {subnet.name}")
        elif subnet.gateway_ip and str(ip) == subnet.gateway_ip:
            errors.append(f"{path.name}: {ip} is the gateway of {subnet.name}")
        else:
            in_pool = any(
                IPv4Address(p["start"]) <= ip <= IPv4Address(p["end"])
                for p in (subnet.allocation_pools or [])
            )
            if in_pool:
                warnings.append(
                    f"{path.name}: {ip} is inside the DHCP allocation pool of {subnet.name}. "
                    "Ports created in parallel with an automatic address can grab it first (race). "
                    "Use a static IP outside the pool, or drop the static IP."
                )
        print(f"  {path.name:<18} {ip}")

    return errors, warnings


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def run_preflight(
    conn: Any,
    items: list[LoadedSandbox],
    *,
    subnet_names: dict[str, str],
    flavor_name: str | None,
    n_allowed_ingress: int,
    n_shared_services: int,
) -> tuple[list[str], list[str]]:
    needs = estimate_needs(
        [s for _, s in items],
        n_allowed_ingress=n_allowed_ingress,
        n_shared_services=n_shared_services,
    )
    errors = check_quotas(conn, needs, flavor_name)
    ip_errors, warnings = check_ips(conn, items, subnet_names)
    return errors + ip_errors, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sandbox-dir", type=Path, default=Path("sandboxes"))
    ap.add_argument("--flavor", help="flavor name, enables the cores/RAM quota check")
    ap.add_argument("--subnet", action="append", default=[], metavar="KEY=NAME",
                    help="map a YAML subnet key to its real Neutron name, e.g. inbound_subnet=inbound-subnet")
    ap.add_argument("--allowed-ingress", type=int, default=1,
                    help="number of allowed_ingress entries given to SandboxManager (default 1)")
    ap.add_argument("--shared-services", type=int, default=2,
                    help="number of SharedService entries given to SandboxManager (default 2)")
    args = ap.parse_args(argv)

    subnet_names = dict(DEFAULT_SUBNET_NAMES)
    for pair in args.subnet:
        key, _, name = pair.partition("=")
        subnet_names[key] = name

    try:
        items = validate_directory(Directory=args.sandbox_dir)
    except BatchValidationError as exc:
        print("YAML validation failed:\n  " + "\n  ".join(exc.errors), file=sys.stderr)
        return 2

    import openstack  # imported late so the offline tests don't need credentials

    conn = openstack.connect()
    errors, warnings = run_preflight(
        conn, items,
        subnet_names=subnet_names,
        flavor_name=args.flavor,
        n_allowed_ingress=args.allowed_ingress,
        n_shared_services=args.shared_services,
    )

    for w in warnings:
        print(f"WARNING: {w}")
    if errors:
        print("\nPreflight FAILED:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    print(f"\nPreflight OK for {len(items)} sandbox(es).")
    return 0


if __name__ == "__main__":
    sys.exit(main())