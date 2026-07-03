from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QueueItem:
    id: int
    operation: str
    payload: dict[str, Any]
    retry_count: int
    last_error: str | None


class MemoryQueue:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists memory_queue (
                    id integer primary key autoincrement,
                    operation text not null,
                    payload_json text not null,
                    status text not null default 'pending',
                    retry_count integer not null default 0,
                    last_error text,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                "create index if not exists idx_memory_queue_status on memory_queue(status, id)"
            )

    def enqueue(self, operation: str, payload: dict[str, Any]) -> int:
        now = utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                insert into memory_queue (operation, payload_json, status, created_at, updated_at)
                values (?, ?, 'pending', ?, ?)
                """,
                (operation, json.dumps(payload, ensure_ascii=False), now, now),
            )
            return int(cur.lastrowid)

    def pending(self, limit: int = 20) -> list[QueueItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select id, operation, payload_json, retry_count, last_error
                from memory_queue
                where status = 'pending'
                order by id
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [
            QueueItem(
                id=int(row["id"]),
                operation=str(row["operation"]),
                payload=json.loads(str(row["payload_json"])),
                retry_count=int(row["retry_count"]),
                last_error=row["last_error"],
            )
            for row in rows
        ]

    def mark_done(self, item_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "update memory_queue set status = 'done', updated_at = ? where id = ?",
                (utc_now(), item_id),
            )

    def mark_failed(self, item_id: int, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                update memory_queue
                set retry_count = retry_count + 1, last_error = ?, updated_at = ?
                where id = ?
                """,
                (error[:1000], utc_now(), item_id),
            )

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "select status, count(*) as count from memory_queue group by status"
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}
