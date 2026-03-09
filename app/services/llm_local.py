from __future__ import annotations
from typing import Any, Dict, List
import json

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
    query: str,
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    compact = [
        {
            "id":       e.get("id"),
            "distance": e.get("distance"),
            "document": e.get("document"),
            "metadata": e.get("metadata"),
        }
        for e in evidence
    ]

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": json.dumps({"query": query, "evidence": compact}, ensure_ascii=False)},
        ],
        options={"temperature": 0.2},
    )

    raw = response["message"]["content"].strip()

    # Strip accidental markdown fences the model might add
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        return {"error": "Model nije vratio valjan JSON", "raw": raw}
