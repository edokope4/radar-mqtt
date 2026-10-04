from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from radar_mqtt.storage import app_dir

STAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class InboxRow:
    id: int
    fecha_recepcion: str
    topico: str
    payload: str
    qos: int


def month_ago(moment: datetime) -> datetime:
    year = moment.year
    month = moment.month - 1
    if month == 0:
        month = 12
        year -= 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


class InboxStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (app_dir() / "inbox.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS INBOX (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_recepcion TEXT NOT NULL,
                topico TEXT NOT NULL,
                payload TEXT NOT NULL,
                qos INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_inbox_fecha ON INBOX (fecha_recepcion)"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record(
        self,
        topico: str,
        payload: str,
        qos: int,
        *,
        received_at: datetime | None = None,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now()
        moment = received_at or current
        stored_qos = max(0, min(2, int(qos)))
        self._conn.execute(
            "INSERT INTO INBOX (fecha_recepcion, topico, payload, qos) VALUES (?, ?, ?, ?)",
            (moment.strftime(STAMP_FORMAT), topico, payload, stored_qos),
        )
        self._purge(current)
        self._conn.commit()

    def list_messages(self, now: datetime | None = None) -> list[InboxRow]:
        current = now or datetime.now()
        self._purge(current)
        self._conn.commit()
        rows = self._conn.execute(
            """
            SELECT id, fecha_recepcion, topico, payload, qos
            FROM INBOX
            ORDER BY fecha_recepcion DESC, id DESC
            """
        ).fetchall()
        return [
            InboxRow(
                id=int(row["id"]),
                fecha_recepcion=str(row["fecha_recepcion"]),
                topico=str(row["topico"]),
                payload=str(row["payload"]),
                qos=int(row["qos"]),
            )
            for row in rows
        ]

    def _purge(self, now: datetime) -> None:
        cutoff = month_ago(now).strftime(STAMP_FORMAT)
        self._conn.execute("DELETE FROM INBOX WHERE fecha_recepcion < ?", (cutoff,))
