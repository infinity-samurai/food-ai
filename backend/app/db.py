from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal


JobStatus = Literal["queued", "in_progress", "done", "failed"]


@dataclass(frozen=True)
class JobRow:
    id: str
    status: JobStatus
    created_at: int
    updated_at: int
    image_key: str
    image_source: str  # "s3" | "local" | "url"
    error: str | None
    result_json: dict[str, Any] | None


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def connect(db_path: str) -> sqlite3.Connection:
    _ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          image_key TEXT NOT NULL,
          image_source TEXT NOT NULL,
          error TEXT,
          result_json TEXT
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_updated ON jobs(status, updated_at);")
    conn.commit()


def now_epoch() -> int:
    return int(time.time())


def create_job(conn: sqlite3.Connection, *, image_key: str, image_source: str) -> JobRow:
    job_id = str(uuid.uuid4())
    ts = now_epoch()
    conn.execute(
        "INSERT INTO jobs(id, status, created_at, updated_at, image_key, image_source) VALUES (?, ?, ?, ?, ?, ?)",
        (job_id, "queued", ts, ts, image_key, image_source),
    )
    conn.commit()
    return get_job(conn, job_id)


def get_job(conn: sqlite3.Connection, job_id: str) -> JobRow:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(job_id)

    result_json = None
    if row["result_json"]:
        result_json = json.loads(row["result_json"])

    return JobRow(
        id=row["id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        image_key=row["image_key"],
        image_source=row["image_source"],
        error=row["error"],
        result_json=result_json,
    )


def set_job_status(conn: sqlite3.Connection, job_id: str, status: JobStatus) -> None:
    conn.execute(
        "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
        (status, now_epoch(), job_id),
    )
    conn.commit()


def set_job_result(conn: sqlite3.Connection, job_id: str, result: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE jobs SET status = ?, updated_at = ?, result_json = ?, error = NULL WHERE id = ?",
        ("done", now_epoch(), json.dumps(result), job_id),
    )
    conn.commit()


def set_job_error(conn: sqlite3.Connection, job_id: str, error: str) -> None:
    conn.execute(
        "UPDATE jobs SET status = ?, updated_at = ?, error = ? WHERE id = ?",
        ("failed", now_epoch(), error[:2000], job_id),
    )
    conn.commit()


def claim_next_job(conn: sqlite3.Connection) -> JobRow | None:
    # Atomically claim one queued job.
    row = conn.execute(
        "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    job_id = row["id"]
    conn.execute(
        "UPDATE jobs SET status = 'in_progress', updated_at = ? WHERE id = ? AND status = 'queued'",
        (now_epoch(), job_id),
    )
    conn.commit()
    # If it was already claimed by another worker, update count would be 0; re-check.
    return get_job(conn, job_id) if get_job(conn, job_id).status == "in_progress" else None

