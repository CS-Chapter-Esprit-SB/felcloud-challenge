from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from monitor_api.app.auth.dependencies import require_authenticated_user
from monitor_api.app.config import settings
from monitor_api.shared.database import SessionLocal
from monitor_api.shared.models import ActivityEvent, Instance


router = APIRouter(
    tags=["Monitoring"],
    dependencies=[Depends(require_authenticated_user)],
)


@router.get("/instances")
def list_instances() -> dict[str, Any]:
    with SessionLocal() as session:
        instances = session.scalars(
            select(Instance).order_by(Instance.name)
        ).all()

        return {
            "count": len(instances),
            "instances": [
                {
                    "id": instance.server_id,
                    "name": instance.name,
                    "status": instance.status,
                    "classification": instance.classification,
                    "ips": instance.ips,
                    "last_seen_at": (
                        instance.last_seen_at.isoformat()
                        if instance.last_seen_at
                        else None
                    ),
                    "last_inventory_at": (
                        instance.last_inventory_at.isoformat()
                        if instance.last_inventory_at
                        else None
                    ),
                }
                for instance in instances
            ],
        }


@router.get("/usage/report")
def usage_report() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(
        minutes=settings.IDLE_TIMEOUT_MINUTES
    )

    with SessionLocal() as session:
        instances = session.scalars(
            select(Instance).order_by(Instance.name)
        ).all()

        report = []

        for instance in instances:
            idle_minutes = None

            if instance.last_seen_at is not None:
                last_seen = instance.last_seen_at

                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)

                idle_minutes = max(
                    0,
                    int((now - last_seen).total_seconds() // 60),
                )

            is_candidate = (
                instance.classification == "sandbox"
                and instance.status == "ACTIVE"
                and instance.last_seen_at is not None
                and instance.last_seen_at < cutoff
            )

            report.append({
                "id": instance.server_id,
                "name": instance.name,
                "status": instance.status,
                "classification": instance.classification,
                "last_seen_at": (
                    instance.last_seen_at.isoformat()
                    if instance.last_seen_at
                    else None
                ),
                "idle_minutes": idle_minutes,
                "idle_candidate": is_candidate,
                "action": "review" if is_candidate else "none",
            })

        return {
            "idle_timeout_minutes": settings.IDLE_TIMEOUT_MINUTES,
            "automatic_stopping_enabled": settings.AUTO_STOP_ENABLED,
            "idle_candidate_count": sum(
                item["idle_candidate"] for item in report
            ),
            "instances": report,
        }


@router.get("/instances/{server_id}/activity")
def instance_activity(server_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        instance = session.scalar(
            select(Instance).where(
                Instance.server_id == server_id
            )
        )

        if instance is None:
            raise HTTPException(
                status_code=404,
                detail="Instance not found",
            )

        events = session.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.server_id == server_id)
            .order_by(ActivityEvent.observed_at.desc())
            .limit(100)
        ).all()

        return {
            "server_id": instance.server_id,
            "name": instance.name,
            "last_seen_at": (
                instance.last_seen_at.isoformat()
                if instance.last_seen_at
                else None
            ),
            "events": [
                {
                    "observed_at": event.observed_at.isoformat(),
                    "backend": event.backend,
                    "server_name": event.server_name,
                    "http_status": event.http_status,
                }
                for event in events
            ],
        }