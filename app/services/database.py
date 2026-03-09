from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("data/logs.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                filename    TEXT    NOT NULL UNIQUE,
                uploaded_at TEXT    NOT NULL,
                rows        INTEGER NOT NULL,
                indexed     INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS log_records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT    NOT NULL,
                timestamp   TEXT,
                src_ip      TEXT,
                dst_ip      TEXT,
                src_port    INTEGER,
                dst_port    INTEGER,
                protocol    TEXT,
                bytes       INTEGER,
                action      TEXT,
                message     TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_log_src_ip    ON log_records(src_ip);
            CREATE INDEX IF NOT EXISTS idx_log_dst_ip    ON log_records(dst_ip);
            CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log_records(timestamp);
            CREATE INDEX IF NOT EXISTS idx_log_source    ON log_records(source_file);
        """)


def save_uploaded_file(filename: str, uploaded_at: str, rows: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO uploaded_files (filename, uploaded_at, rows, indexed)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(filename) DO UPDATE SET rows=excluded.rows
            """,
            (filename, uploaded_at, rows),
        )


def mark_file_indexed(filename: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE uploaded_files SET indexed = 1 WHERE filename = ?",
            (filename,),
        )


def save_log_records(records: List[Dict[str, Any]], source_file: str) -> None:
    """Insert normalised records into SQLite (replace existing for same source)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM log_records WHERE source_file = ?", (source_file,))
        conn.executemany(
            """
            INSERT INTO log_records
                (source_file, timestamp, src_ip, dst_ip, src_port, dst_port,
                 protocol, bytes, action, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    source_file,
                    r.get("timestamp"),
                    r.get("src_ip"),
                    r.get("dst_ip"),
                    r.get("src_port"),
                    r.get("dst_port"),
                    r.get("protocol"),
                    r.get("bytes"),
                    r.get("action"),
                    r.get("message"),
                )
                for r in records
            ],
        )


def list_uploaded_files() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM uploaded_files ORDER BY uploaded_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def filter_logs(
    src_ip:     Optional[str] = None,
    dst_ip:     Optional[str] = None,
    hours:      Optional[int] = None,
    protocol:   Optional[str] = None,
    action:     Optional[str] = None,
    source_file: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Filter log records from SQLite.
    `hours` filters records where timestamp >= now - hours.
    All other filters are exact/partial matches.
    """
    clauses: List[str] = []
    params:  List[Any] = []

    if src_ip:
        clauses.append("src_ip LIKE ?")
        params.append(f"%{src_ip}%")
    if dst_ip:
        clauses.append("dst_ip LIKE ?")
        params.append(f"%{dst_ip}%")
    if protocol:
        clauses.append("protocol = ?")
        params.append(protocol.upper())
    if action:
        clauses.append("action = ?")
        params.append(action.upper())
    if source_file:
        clauses.append("source_file = ?")
        params.append(source_file)
    if hours:
        clauses.append(
            "timestamp >= datetime('now', ? || ' hours')"
        )
        params.append(f"-{hours}")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql   = f"SELECT * FROM log_records {where} ORDER BY timestamp DESC LIMIT 500"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(r) for r in rows]