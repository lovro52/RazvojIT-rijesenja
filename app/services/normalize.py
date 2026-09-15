from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from ipaddress import ip_address
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import MAX_NORMALIZED_ROWS

COLUMN_ALIASES = {
    "timestamp": ["Timestamp", "timestamp", "time", "date", "datetime"],
    "src_ip": ["Source IP", "src_ip", "source_ip", "src", "ip_src"],
    "dst_ip": ["Destination IP", "dst_ip", "destination_ip", "dst", "ip_dst"],
    "src_port": ["Source Port", "src_port", "sport", "source_port"],
    "dst_port": ["Destination Port", "dst_port", "dport", "destination_port"],
    "protocol": ["Protocol", "protocol", "proto"],
    "bytes": [
        "Total Length of Fwd Packets",
        "bytes",
        "len",
        "size",
        "tot_bytes",
    ],
    "action": ["flag", "action", "event"],
    "ground_truth": ["Label", "label"],
}

FLOW_FIELDS = {
    "flow_duration": "Flow Duration",
    "fwd_packets": "Total Fwd Packets",
    "bwd_packets": "Total Backward Packets",
    "fwd_bytes": "Total Length of Fwd Packets",
    "bwd_bytes": "Total Length of Bwd Packets",
    "bytes_per_second": "Flow Bytes/s",
    "packets_per_second": "Flow Packets/s",
    "syn_flag_count": "SYN Flag Count",
    "psh_flag_count": "PSH Flag Count",
    "ack_flag_count": "ACK Flag Count",
}

PROTOCOL_MAP = {0: "HOPOPT", 1: "ICMP", 6: "TCP", 17: "UDP"}
_SAFE_PROTOCOL = re.compile(r"[A-Z0-9_.-]{1,20}")


def _first(row: pd.Series, candidates: list[str]) -> Any | None:
    for column in candidates:
        if column in row.index and pd.notna(row[column]):
            return row[column]
    return None


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    number = _finite_float(value)
    if number is None:
        return None
    return int(number)


def _timestamp(value: Any) -> str | None:
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    if getattr(parsed, "tzinfo", None) is not None:
        parsed = parsed.tz_convert("UTC").tz_localize(None)
    return parsed.isoformat(timespec="seconds")


def _protocol(value: Any) -> str:
    number = _integer(value)
    if number is not None:
        return PROTOCOL_MAP.get(number, f"IP-{number}")
    text = str(value).strip().upper() if value is not None else ""
    return text if _SAFE_PROTOCOL.fullmatch(text) else "UNKNOWN"


def _ip(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(ip_address(str(value).strip()))
    except ValueError:
        return None


def _representative_sample(df: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    """Deterministically retain coverage across labels and the whole file."""
    if max_rows <= 0 or len(df) <= max_rows:
        return df

    label_column = next((c for c in ("Label", "label") if c in df.columns), None)
    if label_column is None:
        positions = np.linspace(0, len(df) - 1, max_rows, dtype=int)
        return df.iloc[positions]

    labels = df[label_column].astype(str).str.strip()
    groups = list(df.assign(__label=labels).groupby("__label", sort=True))
    minimum = min(25, max(1, max_rows // max(len(groups), 1)))
    chosen: set[int] = set()

    for _, group in groups:
        quota = max(minimum, round(max_rows * len(group) / len(df)))
        quota = min(quota, len(group))
        positions = np.linspace(0, len(group) - 1, quota, dtype=int)
        chosen.update(int(index) for index in group.iloc[positions].index)

    if len(chosen) > max_rows:
        ordered = sorted(chosen)
        keep = np.linspace(0, len(ordered) - 1, max_rows, dtype=int)
        chosen = {ordered[i] for i in keep}
    elif len(chosen) < max_rows:
        remaining = [int(i) for i in df.index if int(i) not in chosen]
        required = min(max_rows - len(chosen), len(remaining))
        if required:
            keep = np.linspace(0, len(remaining) - 1, required, dtype=int)
            chosen.update(remaining[i] for i in keep)

    return df.loc[sorted(chosen)]


def normalize_dataframe(
    df: pd.DataFrame, max_rows: int = MAX_NORMALIZED_ROWS
) -> list[dict[str, Any]]:
    """Convert supported CSV schemas to canonical, model-safe flow records."""
    clean = df.rename(columns={str(c): str(c).strip() for c in df.columns}).copy()
    clean["__original_row_index"] = np.arange(len(clean), dtype=int)
    clean = _representative_sample(clean, max_rows)

    records: list[dict[str, Any]] = []
    for _, row in clean.iterrows():
        values = {name: _first(row, aliases) for name, aliases in COLUMN_ALIASES.items()}
        timestamp = _timestamp(values["timestamp"])
        src_port = _integer(values["src_port"])
        dst_port = _integer(values["dst_port"])
        byte_count = _integer(values["bytes"])
        protocol = _protocol(values["protocol"])
        action = (
            str(values["action"]).strip().upper() if values["action"] is not None else "UNKNOWN"
        )
        ground_truth = (
            str(values["ground_truth"]).strip() if values["ground_truth"] is not None else None
        )
        src_ip = _ip(values["src_ip"])
        dst_ip = _ip(values["dst_ip"])

        features = {
            canonical: _finite_float(_first(row, [source]))
            for canonical, source in FLOW_FIELDS.items()
        }
        feature_text = ", ".join(
            f"{name}={value:.4g}" for name, value in features.items() if value is not None
        )
        message = (
            f"network_flow timestamp={timestamp or 'unknown'} protocol={protocol} "
            f"action={action} src={src_ip or 'unknown'}:{src_port} "
            f"dst={dst_ip or 'unknown'}:{dst_port} bytes={byte_count}"
        )
        if feature_text:
            message = f"{message}, {feature_text}"

        records.append(
            {
                "original_row_index": int(row["__original_row_index"]),
                "timestamp": timestamp,
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
                "protocol": protocol,
                "bytes": byte_count,
                "action": action,
                **features,
                "message": message,
                # Never include this value in message or retrieval metadata.
                "ground_truth": ground_truth,
                "record_type": "flow",
                "tags": ["network", "flow"],
            }
        )

    return records


def build_flow_incidents(
    records: list[dict[str, Any]], window_minutes: int = 5
) -> list[dict[str, Any]]:
    """Aggregate flows into evidence windows suitable for RAG analysis."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for position, record in enumerate(records):
        src_ip = record.get("src_ip") or "unknown"
        timestamp = record.get("timestamp")
        if timestamp:
            parsed = datetime.fromisoformat(timestamp)
            minute = parsed.minute - (parsed.minute % window_minutes)
            bucket = parsed.replace(minute=minute, second=0, microsecond=0).isoformat()
        else:
            bucket = f"sequence-{position // 50:05d}"
        groups.setdefault((src_ip, bucket), []).append(record)

    incidents: list[dict[str, Any]] = []
    for incident_index, ((src_ip, bucket), flows) in enumerate(sorted(groups.items())):
        destinations = {f["dst_ip"] for f in flows if f.get("dst_ip")}
        destination_ports = {f["dst_port"] for f in flows if f.get("dst_port") is not None}
        protocols = sorted({f["protocol"] for f in flows if f.get("protocol")})

        def total(field: str, current_flows: list[dict[str, Any]] = flows) -> float:
            return float(sum(f.get(field) or 0 for f in current_flows))

        def mean(field: str, current_flows: list[dict[str, Any]] = flows) -> float:
            values = [float(f[field]) for f in current_flows if f.get(field) is not None]
            return float(sum(values) / len(values)) if values else 0.0

        labels = [str(f["ground_truth"]) for f in flows if f.get("ground_truth")]
        label = Counter(labels).most_common(1)[0][0] if labels else None
        row_ids = [int(f["original_row_index"]) for f in flows]
        metrics = {
            "flow_count": len(flows),
            "unique_destination_ips": len(destinations),
            "unique_destination_ports": len(destination_ports),
            "total_bytes": int(total("bytes")),
            "total_forward_packets": int(total("fwd_packets")),
            "total_backward_packets": int(total("bwd_packets")),
            "total_syn_flags": int(total("syn_flag_count")),
            "mean_bytes_per_second": round(mean("bytes_per_second"), 3),
            "mean_packets_per_second": round(mean("packets_per_second"), 3),
        }
        metric_text = " ".join(f"{key}={value}" for key, value in metrics.items())
        message = (
            f"network_incident window={bucket} source={src_ip} "
            f"protocols={','.join(protocols) or 'unknown'} {metric_text}"
        )
        incidents.append(
            {
                "incident_index": incident_index,
                "timestamp": None if bucket.startswith("sequence-") else bucket,
                "src_ip": src_ip,
                "protocol": ",".join(protocols),
                "message": message,
                "record_type": "incident",
                "source_row_start": min(row_ids),
                "source_row_end": max(row_ids),
                "ground_truth": label,
                **metrics,
            }
        )
    return incidents
