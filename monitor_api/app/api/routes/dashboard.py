from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi import Request, Response
import socket
from sqlalchemy import select

from monitor_api.app.auth.dependencies import require_authenticated_user
from monitor_api.shared.database import SessionLocal
from monitor_api.shared.models import ActivityEvent
from monitor_api.shared.openstack_client import get_connection
from monitor_api.app.lifecycle import LifecycleError, change_instance_state  # adjust path
from monitor_api.app.auth.client import auth0_client

STATIC = Path(__file__).resolve().parents[2] / "static" / "dashboard.html"

router = APIRouter(
    tags=["Dashboard"],
    dependencies=[Depends(require_authenticated_user)],
)

page_router = APIRouter(include_in_schema=False)

@page_router.get("/dashboard", include_in_schema=False)
async def dashboard_page(request: Request, response: Response):
    user = await auth0_client.client.get_user(
        store_options={"request": request, "response": response}
    )
    if not user:
        return RedirectResponse("/auth/login")
    return FileResponse(STATIC)


# ---------------------------------------------------------------- traffic
@router.get("/traffic/logs")
def traffic_logs(limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    with SessionLocal() as s:
        events = s.scalars(
            select(ActivityEvent)
            .order_by(ActivityEvent.observed_at.desc())
            .limit(limit)
        ).all()
        return {
            "logs": [
                {
                    "observed_at": e.observed_at.isoformat(),
                    "backend": e.backend,
                    "server_name": e.server_name,
                    "server_id": e.server_id,
                    "http_status": e.http_status,
                }
                for e in events
            ]
        }


@router.get("/subdomains")
def subdomains() -> dict[str, Any]:
    """Latest backend -> server mapping, derived from observed traffic.
    Replace with your real routing table (HAProxy/Nginx map) if you have one."""
    with SessionLocal() as s:
        events = s.scalars(
            select(ActivityEvent).order_by(ActivityEvent.observed_at.desc()).limit(1000)
        ).all()
        seen: dict[str, dict[str, Any]] = {}
        for e in events:
            m = seen.setdefault(
                e.backend,
                {"subdomain": e.backend, "server_id": e.server_id,
                 "server_name": e.server_name, "hits": 0,
                 "last_hit": e.observed_at.isoformat()},
            )
            m["hits"] += 1
        return {"mappings": list(seen.values())}


# ---------------------------------------------------------------- lifecycle
def _lifecycle(server_id: str, action: str) -> dict[str, str]:
    try:
        return change_instance_state(server_id, action)
    except LifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/instances/{server_id}/start")
def spin_up(server_id: str) -> dict[str, str]:
    return _lifecycle(server_id, "start")


@router.post("/instances/{server_id}/stop")
def tear_down(server_id: str) -> dict[str, str]:
    return _lifecycle(server_id, "stop")


# ---------------------------------------------------------------- gateways
# Gateway VMs are real OpenStack servers, looked up by name.
GATEWAY_SERVICES = {
    "haproxy": {"master": "vm-haproxy-master", "backup": "vm-haproxy-backup", "port": 80},
    "squid": {"master": "vm-squid-master", "backup": "vm-squid-backup", "port": 3128},
}


def _ips(server: Any) -> list[str]:
    return [a["addr"] for addrs in (server.addresses or {}).values() for a in addrs]


def _probe(ip: str | None, port: int) -> bool | None:
    """Best-effort TCP check; None if the API host can't reach the network."""
    if not ip:
        return None
    try:
        with socket.create_connection((ip, port), timeout=1.5):
            return True
    except OSError:
        return False


def _gateway_servers(service: str) -> tuple[Any, Any, Any]:
    cfg = GATEWAY_SERVICES.get(service)
    if cfg is None:
        raise HTTPException(404, "Unknown gateway service.")
    conn = get_connection()
    by_name = {s.name: s for s in conn.compute.servers()}
    master, backup = by_name.get(cfg["master"]), by_name.get(cfg["backup"])  # pyright: ignore[reportArgumentType]
    if master is None or backup is None:
        raise HTTPException(404, "Gateway instances not found in OpenStack.")
    return conn, master, backup


@router.get("/gateways")
def gateways() -> dict[str, Any]:
    by_name = {s.name: s for s in get_connection().compute.servers()}
    groups = []
    for service, cfg in GATEWAY_SERVICES.items():
        master, backup = by_name.get(cfg["master"]), by_name.get(cfg["backup"]) # pyright: ignore[reportArgumentType]
        master_up = master is not None and master.status == "ACTIVE"
        nodes = []
        for configured, srv in (("master", master), ("backup", backup)):
            if srv is None:
                nodes.append({"name": cfg[configured], "configured_role": configured,
                              "status": "MISSING", "ips": [], "role": "standby",
                              "healthy": False, "reachable": None})
                continue
            ips = _ips(srv)
            serving = srv.status == "ACTIVE" and (configured == "master" or not master_up)
            nodes.append({
                "id": srv.id, "name": srv.name, "configured_role": configured,
                "status": srv.status, "ips": ips,
                "role": "primary" if serving else "standby",
                "healthy": srv.status == "ACTIVE",
                "reachable": _probe(ips[0] if ips else None, cfg["port"]), # pyright: ignore[reportArgumentType]
            })
        groups.append({"service": service, "nodes": nodes})
    return {"groups": groups}


@router.post("/gateways/{service}/failover")
def failover(service: str) -> dict[str, str]:
    """Manual failover: stop the master VM so VRRP/keepalived promotes the backup."""
    conn, master, backup = _gateway_servers(service)
    if backup.status != "ACTIVE":
        raise HTTPException(409, f"Standby {backup.name} is {backup.status}; failover refused.")
    if master.status != "ACTIVE":
        raise HTTPException(409, f"{master.name} is already {master.status}; nothing to fail over.")
    conn.compute.stop_server(master)
    return {"message": f"Stopping {master.name}; {backup.name} will take over."}


@router.post("/gateways/{service}/restore")
def restore(service: str) -> dict[str, str]:
    """Bring the master back after a failover."""
    conn, master, _ = _gateway_servers(service)
    if master.status != "SHUTOFF":
        raise HTTPException(409, f"{master.name} is {master.status}; cannot restore.")
    conn.compute.start_server(master)
    return {"message": f"Starting {master.name}."}