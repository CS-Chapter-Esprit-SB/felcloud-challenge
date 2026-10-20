from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import ActivityEvent, Instance

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sandbox Lifecycle Manager",
    version="0.2.0",
)

IDLE_TIMEOUT_MINUTES = int(
    os.getenv("SANDBOX_IDLE_TIMEOUT_MINUTES", "30")
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/instances")
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


@app.get("/usage/report")
def usage_report() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=IDLE_TIMEOUT_MINUTES)

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
            "idle_timeout_minutes": IDLE_TIMEOUT_MINUTES,
            "automatic_stopping_enabled": (
                os.getenv("SANDBOX_AUTO_STOP_ENABLED", "false").lower()
                == "true"
            ),
            "idle_candidate_count": sum(
                item["idle_candidate"] for item in report
            ),
            "instances": report,
        }


@app.get("/instances/{server_id}/activity")
def instance_activity(server_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        instance = session.scalar(
            select(Instance).where(Instance.server_id == server_id)
        )

        if instance is None:
            raise HTTPException(status_code=404, detail="Instance not found")

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