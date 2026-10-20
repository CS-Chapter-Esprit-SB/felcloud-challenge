from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Instance(Base):
    __tablename__ = "instances"

    id: Mapped[int] = mapped_column(primary_key=True)

    # OpenStack UUID; this is the stable identity of a VM.
    server_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True)
    classification: Mapped[str] = mapped_column(
        String(32),
        index=True,
    )

    ips: Mapped[list[str]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_inventory_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Last time traffic was observed for this VM.
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )


class ConsumerState(Base):
    __tablename__ = "consumer_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    consumer_name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
    )

    file_inode: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    file_offset: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    server_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    backend: Mapped[str] = mapped_column(String(255))
    server_name: Mapped[str] = mapped_column(String(255))
    http_status: Mapped[int] = mapped_column(Integer)

    # Store the raw line for troubleshooting, but cap its length.
    log_line: Mapped[str] = mapped_column(Text)


Index(
    "ix_activity_events_server_observed",
    ActivityEvent.server_id,
    ActivityEvent.observed_at,
)