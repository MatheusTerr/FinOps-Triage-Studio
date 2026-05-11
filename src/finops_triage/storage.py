from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    channel TEXT NOT NULL,
    segment TEXT NOT NULL,
    product TEXT NOT NULL,
    request_type TEXT NOT NULL,
    description TEXT NOT NULL,
    value REAL NOT NULL,
    sentiment TEXT NOT NULL,
    sentiment_score REAL NOT NULL,
    reopened INTEGER NOT NULL,
    sla_hours INTEGER NOT NULL,
    resolution_hours REAL,
    sla_breached INTEGER NOT NULL,
    auto_service_candidate INTEGER NOT NULL,
    target_queue TEXT,
    priority_label TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    status TEXT NOT NULL,
    predicted_queue TEXT,
    confidence REAL,
    ai_summary TEXT
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def count_tickets(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS total FROM tickets").fetchone()
    return int(row["total"])


def replace_tickets(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM analyses")
    conn.execute("DELETE FROM tickets")
    insert_tickets(conn, rows)
    conn.commit()


def insert_tickets(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = [
        "ticket_id",
        "created_at",
        "channel",
        "segment",
        "product",
        "request_type",
        "description",
        "value",
        "sentiment",
        "sentiment_score",
        "reopened",
        "sla_hours",
        "resolution_hours",
        "sla_breached",
        "auto_service_candidate",
        "target_queue",
        "priority_label",
        "risk_score",
        "status",
        "predicted_queue",
        "confidence",
        "ai_summary",
    ]
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT OR REPLACE INTO tickets ({', '.join(columns)}) VALUES ({placeholders})"
    values = [tuple(_normalize(row.get(column)) for column in columns) for row in rows]
    conn.executemany(sql, values)
    conn.commit()


def list_tickets(conn: sqlite3.Connection, limit: int | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM tickets ORDER BY created_at DESC"
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    return [_row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


def training_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM tickets WHERE target_queue IS NOT NULL ORDER BY created_at"
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def save_analysis(
    conn: sqlite3.Connection,
    ticket: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    insert_tickets(conn, [ticket])
    conn.execute(
        "INSERT INTO analyses (ticket_id, created_at, payload_json) VALUES (?, ?, ?)",
        (ticket["ticket_id"], ticket["created_at"], json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()


def next_ticket_id(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT COUNT(*) AS total FROM tickets").fetchone()
    return f"FIN-{int(row['total']) + 1:05d}"


def _normalize(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    return value


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for key in ("reopened", "sla_breached", "auto_service_candidate"):
        data[key] = bool(data[key])
    return data

