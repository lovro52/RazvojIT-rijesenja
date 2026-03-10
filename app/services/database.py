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

            CREATE TABLE IF NOT EXISTS query_history (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                queried_at     TEXT    NOT NULL,
                query          TEXT    NOT NULL,
                top_k          INTEGER NOT NULL,
                risk_level     TEXT,
                summary        TEXT,
                key_indicators TEXT,
                recommended_actions TEXT,
                evidence_count INTEGER
            );
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


def get_dashboard_stats() -> Dict[str, Any]:
    """Return aggregated stats for the dashboard."""
    with get_conn() as conn:
        total_records = conn.execute("SELECT COUNT(*) FROM log_records").fetchone()[0]
        total_files   = conn.execute("SELECT COUNT(*) FROM uploaded_files").fetchone()[0]
        indexed_files = conn.execute("SELECT COUNT(*) FROM uploaded_files WHERE indexed = 1").fetchone()[0]

        protocol_dist = conn.execute(
            "SELECT protocol, COUNT(*) as count FROM log_records GROUP BY protocol ORDER BY count DESC"
        ).fetchall()

        action_dist = conn.execute(
            "SELECT action, COUNT(*) as count FROM log_records GROUP BY action ORDER BY count DESC"
        ).fetchall()

        top_src_ips = conn.execute(
            "SELECT src_ip, COUNT(*) as count FROM log_records WHERE src_ip IS NOT NULL GROUP BY src_ip ORDER BY count DESC LIMIT 10"
        ).fetchall()

        top_dst_ports = conn.execute(
            "SELECT dst_port, COUNT(*) as count FROM log_records WHERE dst_port IS NOT NULL GROUP BY dst_port ORDER BY count DESC LIMIT 10"
        ).fetchall()

        recent_files = conn.execute(
            "SELECT filename, uploaded_at, rows, indexed FROM uploaded_files ORDER BY uploaded_at DESC LIMIT 5"
        ).fetchall()

    return {
        "total_records":   total_records,
        "total_files":     total_files,
        "indexed_files":   indexed_files,
        "protocol_dist":   [dict(r) for r in protocol_dist],
        "action_dist":     [dict(r) for r in action_dist],
        "top_src_ips":     [dict(r) for r in top_src_ips],
        "top_dst_ports":   [dict(r) for r in top_dst_ports],
        "recent_files":    [dict(r) for r in recent_files],
    }


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

def save_query(
    query: str,
    top_k: int,
    report: Dict[str, Any],
    evidence_count: int,
    queried_at: str,
) -> None:
    import json
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO query_history
                (queried_at, query, top_k, risk_level, summary, key_indicators,
                 recommended_actions, evidence_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                queried_at,
                query,
                top_k,
                report.get("risk_level"),
                report.get("summary"),
                json.dumps(report.get("key_indicators", []), ensure_ascii=False),
                json.dumps(report.get("recommended_actions", []), ensure_ascii=False),
                evidence_count,
            ),
        )


def get_query_history(limit: int = 50) -> List[Dict[str, Any]]:
    import json
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM query_history ORDER BY queried_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["key_indicators"]      = json.loads(d["key_indicators"] or "[]")
        d["recommended_actions"] = json.loads(d["recommended_actions"] or "[]")
        result.append(d)
    return result


def get_dashboard_stats_with_history(recent_queries: int = 5) -> Dict[str, Any]:
    """Extend dashboard stats with recent query count."""
    stats = get_dashboard_stats()
    with get_conn() as conn:
        total_queries = conn.execute("SELECT COUNT(*) FROM query_history").fetchone()[0]
    stats["total_queries"] = total_queries
    return stats


def get_ip_stats(ip: str) -> Dict[str, Any]:
    """Return detailed statistics for a specific IP address."""
    with get_conn() as conn:
        # Total appearances as source
        as_src = conn.execute(
            "SELECT COUNT(*) FROM log_records WHERE src_ip = ?", (ip,)
        ).fetchone()[0]

        # Total appearances as destination
        as_dst = conn.execute(
            "SELECT COUNT(*) FROM log_records WHERE dst_ip = ?", (ip,)
        ).fetchone()[0]

        # Actions breakdown when this IP is the source
        actions = conn.execute(
            """SELECT action, COUNT(*) as count FROM log_records
               WHERE src_ip = ? GROUP BY action ORDER BY count DESC""",
            (ip,)
        ).fetchall()

        # Target ports this IP connected to
        dst_ports = conn.execute(
            """SELECT dst_port, COUNT(*) as count FROM log_records
               WHERE src_ip = ? AND dst_port IS NOT NULL
               GROUP BY dst_port ORDER BY count DESC LIMIT 10""",
            (ip,)
        ).fetchall()

        # Source ports used
        src_ports = conn.execute(
            """SELECT src_port, COUNT(*) as count FROM log_records
               WHERE src_ip = ? AND src_port IS NOT NULL
               GROUP BY src_port ORDER BY count DESC LIMIT 10""",
            (ip,)
        ).fetchall()

        # IPs this IP talked to
        contacted_ips = conn.execute(
            """SELECT dst_ip, COUNT(*) as count FROM log_records
               WHERE src_ip = ? AND dst_ip IS NOT NULL
               GROUP BY dst_ip ORDER BY count DESC LIMIT 10""",
            (ip,)
        ).fetchall()

        # All log records involving this IP
        records = conn.execute(
            """SELECT * FROM log_records
               WHERE src_ip = ? OR dst_ip = ?
               ORDER BY timestamp DESC LIMIT 100""",
            (ip, ip)
        ).fetchall()

        # Total bytes sent
        total_bytes = conn.execute(
            "SELECT SUM(bytes) FROM log_records WHERE src_ip = ?", (ip,)
        ).fetchone()[0]

    return {
        "ip":            ip,
        "as_source":     as_src,
        "as_destination": as_dst,
        "total_bytes":   total_bytes or 0,
        "actions":       [dict(r) for r in actions],
        "dst_ports":     [dict(r) for r in dst_ports],
        "src_ports":     [dict(r) for r in src_ports],
        "contacted_ips": [dict(r) for r in contacted_ips],
        "records":       [dict(r) for r in records],
    }


def list_all_ips() -> List[Dict[str, Any]]:
    """Return all unique IPs with their appearance count."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT src_ip as ip, COUNT(*) as count
               FROM log_records WHERE src_ip IS NOT NULL
               GROUP BY src_ip
               ORDER BY count DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def keyword_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Simple keyword search across log messages and IP fields."""
    terms = query.strip().split()
    if not terms:
        return []

    clauses = []
    params  = []
    for term in terms:
        clauses.append(
            "(message LIKE ? OR src_ip LIKE ? OR dst_ip LIKE ? OR action LIKE ? OR protocol LIKE ?)"
        )
        like = f"%{term}%"
        params.extend([like, like, like, like, like])

    where = " AND ".join(clauses)
    sql   = f"SELECT * FROM log_records WHERE {where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(r) for r in rows]