"""
Zajednička shema između fine-tuninga i aplikacije.

Fine-tunani modeli (v3) trenirani su na točno ovom popisu značajki, u ovom
redoslijedu, i na točno ovom obliku prompta. Ako se ovdje bilo što promijeni,
modeli treba ponovo trenirati — inače im aplikacija šalje ulaz kakav nikad
nisu vidjeli i fine-tuning se gubi.

Izvor: NetlogRAG_FineTuning_v2.ipynb, ćelija 5 (`build_instruction`).
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "netlog-flow-v3"

# Redoslijed je bitan — određuje redoslijed u promptu.
TRAINING_FLOW_FEATURES: list[str] = [
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
    "PSH Flag Count",
    "ACK Flag Count",
    "Down/Up Ratio",
    "Average Packet Size",
]

# Odredišni port NIJE među značajkama — namjerno. U v1 je bio prvi podatak
# u ulazu, pa je model naučio mapirati port 21 → FTP-Patator i port 22 →
# SSH-Patator umjesto analizirati promet. Vidi poglavlje o evaluaciji.
EXCLUDED_FEATURES: list[str] = ["Destination Port"]

ATTACK_TYPES: list[str] = [
    "BENIGN", "DDoS", "DoS", "FTP-Patator",
    "PortScan", "SSH-Patator", "WebAttack",
]

RISK_LEVELS: list[str] = ["LOW", "MEDIUM", "HIGH"]

INSTRUCTION = (
    "Analiziraj karakteristike ovog mrežnog toka, odredi tip napada "
    "i procijeni razinu rizika. Vrati ISKLJUČIVO JSON."
)

PROTO_MAP = {6: "TCP", 17: "UDP", 1: "ICMP", 0: "HOPOPT"}

# Kratice kolona — moraju se poklapati s onima iz treninga
_SHORT = {
    col: (col.replace("Total ", "").replace("Length of ", "Len")
             .replace("Packet", "Pkt").replace("Backward", "Bwd")
             .replace("Forward", "Fwd").replace(" ", ""))
    for col in TRAINING_FLOW_FEATURES
}


def _safe_float(value: Any) -> float | None:
    """None za NaN, Infinity i neparsabilne vrijednosti."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def build_flow_input(
    flow_features: dict[str, Any],
    protocol: Any = None,
) -> str:
    """
    Sastavlja ulazni tekst identičan onome iz treninga.

    Primjer izlaza:
        "TCP tok. FlowDuration=1200.0, FwdPkts=8.0, BwdPkts=6.0, ..."
    """
    parts: list[str] = []
    for col in TRAINING_FLOW_FEATURES:
        v = _safe_float(flow_features.get(col))
        if v is None:
            continue
        parts.append(f"{_SHORT[col]}={v:.1f}")

    proto = "TCP"
    if isinstance(protocol, str) and protocol.strip().upper() in {
        "TCP", "UDP", "ICMP", "HOPOPT", "OTHER"
    }:
        proto = protocol.strip().upper()
    else:
        pv = _safe_float(protocol)
        if pv is not None:
            proto = PROTO_MAP.get(int(pv), "OTHER")

    return f"{proto} tok. " + ", ".join(parts)


def build_classification_prompt(
    flow_features: dict[str, Any],
    protocol: Any = None,
) -> str:
    """Puni prompt u formatu na kojem su v3 modeli trenirani."""
    return (
        f"### Instruction:\n{INSTRUCTION}\n\n"
        f"### Input:\n{build_flow_input(flow_features, protocol)}\n\n"
        f"### Response:\n"
    )