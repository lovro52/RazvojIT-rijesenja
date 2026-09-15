from __future__ import annotations

import math
from typing import Any

SCHEMA_VERSION = "netlog-flow-classification-v1"

LLM_FLOW_FEATURES = [
    "Destination Port",
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Total Length of Fwd Packets",
    "Total Length of Bwd Packets",
    "Fwd Packet Length Mean",
    "Bwd Packet Length Mean",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Flow IAT Mean",
    "Flow IAT Std",
    "SYN Flag Count",
    "RST Flag Count",
    "PSH Flag Count",
    "ACK Flag Count",
    "Average Packet Size",
]

ATTACK_TYPES = [
    "BENIGN",
    "BOTNET",
    "BRUTE_FORCE",
    "DDOS",
    "DOS",
    "HEARTBLEED",
    "INFILTRATION",
    "PORT_SCAN",
    "WEB_ATTACK",
]


def normalize_attack_label(label: Any) -> str | None:
    value = str(label).strip().lower().replace("�", "-")
    compact = " ".join(value.replace("_", " ").replace("-", " ").split())
    if value in {"benign", "normal"}:
        return "BENIGN"
    if "heartbleed" in compact:
        return "HEARTBLEED"
    if "infiltration" in compact:
        return "INFILTRATION"
    if "portscan" in value or "port scan" in compact:
        return "PORT_SCAN"
    if "web attack" in compact or any(
        marker in compact for marker in ("sql injection", "xss", "brute force web")
    ):
        return "WEB_ATTACK"
    if "ddos" in compact:
        return "DDOS"
    if "dos" in compact or any(
        marker in compact for marker in ("hulk", "slowhttptest", "slowloris", "goldeneye")
    ):
        return "DOS"
    if "bot" in compact:
        return "BOTNET"
    if any(marker in compact for marker in ("patator", "brute force", "bruteforce")):
        return "BRUTE_FORCE"
    return None


def canonical_feature_values(record: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for feature in LLM_FLOW_FEATURES:
        try:
            value = float(record.get(feature, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        result[feature] = value if math.isfinite(value) else 0.0
    return result


def classifier_messages(record: dict[str, Any]) -> list[dict[str, str]]:
    import json

    system = (
        "Classify one network-flow record. Return only JSON with attack_type and "
        "risk_level. attack_type must be one of: "
        + ", ".join(ATTACK_TYPES)
        + ". risk_level must be LOW, MEDIUM, or HIGH. Do not invent missing features."
    )
    user = json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "task": "classify_network_flow",
            "features": canonical_feature_values(record),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def target_response(attack_type: str) -> str:
    import json

    risk = "LOW" if attack_type == "BENIGN" else "HIGH"
    return json.dumps(
        {"attack_type": attack_type, "risk_level": risk},
        separators=(",", ":"),
        sort_keys=True,
    )
