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


def normalize_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert a DataFrame with varying column names into a canonical record schema.
    The `message` field is used as the document text for embedding.
    """
    # Strip whitespace from column names
    df = df.rename(columns={c: c.strip() for c in df.columns})

    records: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        ts       = _get_first(row, ["timestamp", "time", "date", "datetime"])
        src_ip   = _get_first(row, ["src_ip", "source_ip", "src", "ip_src"])
        dst_ip   = _get_first(row, ["dst_ip", "destination_ip", "dst", "ip_dst"])
        src_port = _get_first(row, ["src_port", "sport", "source_port"])
        dst_port = _get_first(row, ["dst_port", "dport", "destination_port"])
        protocol = _get_first(row, ["protocol", "proto"])
        bytes_   = _get_first(row, ["bytes", "len", "size", "tot_bytes"])
        action   = _get_first(row, ["flag", "action", "event", "label"])

        protocol = str(protocol) if protocol is not None else "UNKNOWN"
        action   = str(action)   if action   is not None else "UNKNOWN"

        message = (
            f"{protocol} {action} from {src_ip}:{src_port} "
            f"to {dst_ip}:{dst_port}, bytes={bytes_}"
        )

        records.append({
            "timestamp": str(ts)        if ts        is not None else None,
            "src_ip":    str(src_ip)    if src_ip    is not None else None,
            "dst_ip":    str(dst_ip)    if dst_ip    is not None else None,
            "src_port":  int(src_port)  if src_port  is not None else None,
            "dst_port":  int(dst_port)  if dst_port  is not None else None,
            "protocol":  protocol,
            "bytes":     int(bytes_)    if bytes_    is not None else None,
            "action":    action,
            "message":   message,
            "tags":      ["network", "log"],
        })

    return records
