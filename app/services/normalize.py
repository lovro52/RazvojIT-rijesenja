from __future__ import annotations
from typing import Any, Dict, List, Optional
import pandas as pd


def _get_first(row: pd.Series, candidates: List[str]) -> Optional[Any]:
    """Return the first non-null value from `row` matching any of the candidate column names."""
    for col in candidates:
        if col in row.index:
            val = row[col]
            if pd.notna(val):
                return val
    return None


def normalize_dataframe(df: pd.DataFrame, max_rows: int = 5000) -> List[Dict[str, Any]]:
    """
    Convert a DataFrame with varying column names into a canonical record schema.
    Supports: custom sample CSVs and CICIDS2017 MachineLearningCSV format.
    The `message` field is used as the document text for embedding.

    max_rows: cap to avoid overloading ChromaDB on large datasets (default 5000).
    """
    # Strip whitespace from column names (CICIDS2017 has leading spaces)
    df = df.rename(columns={c: c.strip() for c in df.columns})

    # Cap rows for large datasets
    if len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=42).reset_index(drop=True)

    records: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        ts = _get_first(row, [
            "Timestamp", "timestamp", "time", "date", "datetime",
        ])
        src_ip = _get_first(row, [
            "Source IP", "src_ip", "source_ip", "src", "ip_src",
        ])
        dst_ip = _get_first(row, [
            "Destination IP", "dst_ip", "destination_ip", "dst", "ip_dst",
        ])
        src_port = _get_first(row, [
            "Source Port", "src_port", "sport", "source_port",
        ])
        dst_port = _get_first(row, [
            "Destination Port", "dst_port", "dport", "destination_port",
        ])
        protocol = _get_first(row, [
            "Protocol", "protocol", "proto",
        ])
        bytes_ = _get_first(row, [
            # CICIDS2017 uses these for traffic volume
            "Total Length of Fwd Packets", "Total Fwd Packets",
            "Flow Bytes/s", "Flow Packets/s",
            # Generic
            "bytes", "len", "size", "tot_bytes",
        ])
        action = _get_first(row, [
            # CICIDS2017 attack label
            "Label",
            # Generic
            "flag", "action", "event", "label",
        ])

        protocol = str(int(float(protocol))) if protocol is not None else "UNKNOWN"
        action   = str(action).strip()       if action   is not None else "UNKNOWN"

        # Map CICIDS2017 numeric protocol to name
        proto_map = {"6": "TCP", "17": "UDP", "1": "ICMP", "0": "HOPOPT"}
        protocol  = proto_map.get(protocol, protocol)

        message = (
            f"{protocol} {action} from {src_ip}:{src_port} "
            f"to {dst_ip}:{dst_port}, bytes={bytes_}"
        )

        try:
            src_port_int = int(float(src_port)) if src_port is not None else None
        except (ValueError, TypeError):
            src_port_int = None

        try:
            dst_port_int = int(float(dst_port)) if dst_port is not None else None
        except (ValueError, TypeError):
            dst_port_int = None

        try:
            bytes_int = int(float(bytes_)) if bytes_ is not None else None
        except (ValueError, TypeError):
            bytes_int = None

        records.append({
            "timestamp": str(ts)     if ts     is not None else None,
            "src_ip":    str(src_ip) if src_ip is not None else None,
            "dst_ip":    str(dst_ip) if dst_ip is not None else None,
            "src_port":  src_port_int,
            "dst_port":  dst_port_int,
            "protocol":  protocol,
            "bytes":     bytes_int,
            "action":    action,
            "message":   message,
            "tags":      ["network", "log"],
        })

    return records