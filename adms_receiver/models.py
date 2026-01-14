from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OutboxStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class AdmsAttlogRaw(Base):
    __tablename__ = "adms_attlog_raw"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    sn: Mapped[str] = mapped_column(String(64), nullable=False)
    pin: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    status_code: Mapped[str] = mapped_column(String(32), nullable=False)
    verify_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workcode: Mapped[str | None] = mapped_column(String(32), nullable=True)

    raw_line: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    outbox: Mapped["AdmsAttlogOutbox"] = relationship(back_populates="raw", uselist=False)

    __table_args__ = (
        UniqueConstraint("sn", "pin", "event_time", "status_code", name="uq_adms_attlog_dedupe"),
    )


class AdmsAttlogOutbox(Base):
    __tablename__ = "adms_attlog_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_id: Mapped[str] = mapped_column(String(36), ForeignKey("adms_attlog_raw.id", ondelete="CASCADE"), unique=True)

    status: Mapped[OutboxStatus] = mapped_column(Enum(OutboxStatus), nullable=False, default=OutboxStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    raw: Mapped[AdmsAttlogRaw] = relationship(back_populates="outbox")


class DeviceCmdStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKED = "ACKED"
    FAILED = "FAILED"


class AdmsDeviceCmd(Base):
    """Server -> device command queue (delivered via GET /iclock/getrequest).

    Evidence-backed wire-format (see archived admsjs source):
    - Receiver returns one line per command:
      C:<ID>:<COMMAND_TEXT>
    - For USER provisioning, <COMMAND_TEXT> is typically:
      DATA UPDATE USERINFO <TAB separated key=value pairs>

    We store COMMAND_TEXT only; the API adds the `C:<ID>:` prefix at send time.
    """

    __tablename__ = "adms_device_cmd"

    # admsjs evidence uses numeric command IDs in the `C:<ID>:` prefix.
    # Use an auto-increment integer so devices can echo back `ID=<ID>` reliably.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    sn: Mapped[str] = mapped_column(String(64), nullable=False)
    command_text: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[DeviceCmdStatus] = mapped_column(Enum(DeviceCmdStatus), nullable=False, default=DeviceCmdStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class AdmsDeviceCmdCallback(Base):
    """Device -> server response to commands (POST /devicecmd).

    We store raw payloads for debugging / evidence. We also attempt to link callbacks
    to queued commands when the callback includes `ID=<id>`.
    """

    __tablename__ = "adms_device_cmd_callback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # SN may not be present in the callback payload; keep it nullable for safety.
    sn: Mapped[str | None] = mapped_column(String(64), nullable=True)

    payload_text: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
