from __future__ import annotations
from typing import Any, Dict, List, Optional
import json
import time
import ollama

from app.core.config import OLLAMA_MODEL

SYSTEM_PROMPT = """
Ti si cybersecurity analitičar koji analizira mrežne logove.

Tvoj zadatak je:
1. procijeniti razinu rizika (LOW, MEDIUM, HIGH),
2. kratko objasniti što logovi sugeriraju,
3. navesti glavne indikatore sumnjivog ponašanja,
4. preporučiti sljedeće korake.

Vrati ISKLJUČIVO JSON u ovom formatu (bez markdowna, bez ``` blokova):

{
  "risk_level": "LOW|MEDIUM|HIGH",
  "summary": "kratko objašnjenje",
  "key_indicators": ["indikator 1", "indikator 2"],
  "recommended_actions": ["akcija 1", "akcija 2"],
  "evidence_highlights": [
    {
      "id": "id loga",
      "reason": "zašto je bitan"
    }
  ]
}

Ne vraćaj ništa osim JSON-a.
"""


def generate_local_security_report(
    query:    str,
    evidence: List[Dict[str, Any]],
    model:    Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a security report using the specified model.
    Returns the report dict plus inference_ms timing.
    """
    selected_model = model or OLLAMA_MODEL

    compact = [
        {
            "id":       e.get("id"),
            "distance": e.get("distance"),
            "document": e.get("document"),
            "metadata": e.get("metadata"),
        }
        for e in evidence
    ]

    t0 = time.perf_counter()

    response = ollama.chat(
        model=selected_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": json.dumps(
                {"query": query, "evidence": compact}, ensure_ascii=False
            )},
        ],
        options={"temperature": 0.2},
    )

    inference_ms = round((time.perf_counter() - t0) * 1000, 1)

    raw = response["message"]["content"].strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        report = json.loads(raw)
    except Exception:
        report = {"error": "Model nije vratio valjan JSON", "raw": raw}

    report["inference_ms"]   = inference_ms
    report["model_used"]     = selected_model

    return report


SYSTEM_PROMPT_TEXT = """
Ti si cybersecurity analitičar specijaliziran za analizu WEB napada u HTTP logovima.

Fokusiraj se na:
- SQL Injection pokušaje (UNION, SELECT, DROP, WHERE u URL parametrima)
- XSS napade (script, alert, onclick u zahtjevima)
- Command injection (;, |, && u parametrima)
- Anomalne HTTP zahtjeve i neobične user-agente

Vrati ISKLJUČIVO JSON (bez markdowna):
{
  "risk_level": "LOW|MEDIUM|HIGH",
  "summary": "kratko objašnjenje",
  "key_indicators": ["indikator 1", "indikator 2"],
  "recommended_actions": ["akcija 1", "akcija 2"],
  "evidence_highlights": [{"id": "id loga", "reason": "zašto je bitan"}],
  "detection_mode": "text"
}
"""

SYSTEM_PROMPT_FLOW = """
Ti si cybersecurity analitičar specijaliziran za analizu MREŽNOG PROMETA.

Fokusiraj se na:
- DDoS i DoS napade (visoki broj paketa, kratki tokovi)
- Port scan aktivnosti (veze na mnogo portova s iste IP adrese)
- Brute force napade (ponavljajuće veze na isti port)
- Botnet komunikaciju (periodički promet, C&C obrasci)

Analiziraj numeričke karakteristike toka: Flow Duration, Total Fwd Packets,
Flow Bytes/s, SYN Flag Count, broj veza itd.

Vrati ISKLJUČIVO JSON (bez markdowna):
{
  "risk_level": "LOW|MEDIUM|HIGH",
  "summary": "kratko objašnjenje",
  "key_indicators": ["indikator 1", "indikator 2"],
  "recommended_actions": ["akcija 1", "akcija 2"],
  "evidence_highlights": [{"id": "id loga", "reason": "zašto je bitan"}],
  "detection_mode": "flow"
}
"""

WEB_KEYWORDS = [
    "sql", "injection", "xss", "script", "http", "url", "web",
    "request", "payload", "cross-site", "command", "injection",
    "get", "post", "header", "cookie", "union", "select",
]

FLOW_KEYWORDS = [
    "ddos", "dos", "flood", "port scan", "portscan", "botnet",
    "brute force", "ssh", "ftp", "syn", "packet", "flow",
    "bandwidth", "traffic", "connection", "slowloris", "hulk",
]


def _detect_mode(query: str) -> str:
    """Auto-detect whether query is about text/web or network-flow attacks."""
    q_lower = query.lower()
    text_score = sum(1 for kw in WEB_KEYWORDS  if kw in q_lower)
    flow_score = sum(1 for kw in FLOW_KEYWORDS if kw in q_lower)
    if text_score > flow_score:
        return "text"
    if flow_score > text_score:
        return "flow"
    return "flow"  # default to flow for network logs


def generate_local_security_report_mode(
    query:    str,
    evidence: List[Dict[str, Any]],
    model:    Optional[str] = None,
    mode:     str = "auto",
) -> Dict[str, Any]:
    """Generate a security report with detection mode awareness."""
    selected_model = model or OLLAMA_MODEL

    if mode == "auto":
        mode = _detect_mode(query)

    prompt = SYSTEM_PROMPT_TEXT if mode == "text" else SYSTEM_PROMPT_FLOW

    compact = [
        {
            "id":       e.get("id"),
            "distance": e.get("distance"),
            "document": e.get("document"),
            "metadata": e.get("metadata"),
        }
        for e in evidence
    ]

    t0 = time.perf_counter()

    response = ollama.chat(
        model=selected_model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user",   "content": json.dumps(
                {"query": query, "evidence": compact}, ensure_ascii=False
            )},
        ],
        options={"temperature": 0.2},
    )

    inference_ms = round((time.perf_counter() - t0) * 1000, 1)

    raw = response["message"]["content"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        report = json.loads(raw)
    except Exception:
        report = {"error": "Model nije vratio valjan JSON", "raw": raw}

    report["inference_ms"]    = inference_ms
    report["model_used"]      = selected_model
    report["detection_mode"]  = mode

    return report