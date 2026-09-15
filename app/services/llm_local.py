from __future__ import annotations

import json
import time
from enum import StrEnum
from typing import Any

import ollama
from pydantic import BaseModel, Field, ValidationError

from app.core.config import OLLAMA_MODEL

PROMPT_VERSION = "flow-incident-v2"


class DetectionMode(StrEnum):
    AUTO = "auto"
    FLOW = "flow"
    TEXT = "text"


class RiskLevel(StrEnum):
    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvidenceHighlight(BaseModel):
    id: str
    reason: str = Field(min_length=1, max_length=500)


class SecurityReport(BaseModel):
    risk_level: RiskLevel
    summary: str = Field(min_length=1, max_length=2000)
    key_indicators: list[str] = Field(default_factory=list, max_length=10)
    recommended_actions: list[str] = Field(default_factory=list, max_length=10)
    evidence_highlights: list[EvidenceHighlight] = Field(default_factory=list, max_length=20)


SYSTEM_PROMPT_FLOW = """
Ti si pomoćnik analitičaru kibernetičke sigurnosti. Analiziraš samo dostavljene
agregirane vremenske prozore mrežnih tokova. Ne proglašavaj napad na temelju
jednog porta ili jedne TCP zastavice. Port scan, brute-force i DoS/DDoS zahtijevaju
ponavljajući ili agregirani obrazac. Ne koristi znanje koje nije vidljivo u dokazima.

Ako dokazi nisu dovoljni, vrati risk_level UNKNOWN i jasno navedi koje informacije
nedostaju. Svaki evidence_highlights.id mora biti identičan jednom dostavljenom ID-u.
Vrati samo valjan JSON sa sljedećim poljima:
{
  "risk_level": "UNKNOWN|LOW|MEDIUM|HIGH",
  "summary": "sažetak utemeljen na dokazima",
  "key_indicators": ["opaženi mjerljivi indikator"],
  "recommended_actions": ["razmjerna sljedeća radnja"],
  "evidence_highlights": [{"id": "dostavljeni ID", "reason": "obrazloženje"}]
}
""".strip()


class UnsupportedDetectionModeError(ValueError):
    pass


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model nije vratio JSON objekt.")
    return json.loads(text[start : end + 1])


def _validated_report(raw: str, evidence_ids: set[str]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    try:
        report = SecurityReport.model_validate(_extract_json(raw))
    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        return (
            SecurityReport(
                risk_level=RiskLevel.UNKNOWN,
                summary="Lokalni model nije vratio izvještaj koji odgovara propisanoj JSON shemi.",
                recommended_actions=["Pregledaj sirovi izlaz i ponovi analizu."],
            ).model_dump(mode="json"),
            [f"Nevaljan izlaz modela: {exc}"],
        )

    valid_highlights = []
    for highlight in report.evidence_highlights:
        if highlight.id in evidence_ids:
            valid_highlights.append(highlight)
        else:
            warnings.append(f"Odbačen je nepostojeći ID dokaza: {highlight.id}")
    report.evidence_highlights = valid_highlights
    return report.model_dump(mode="json"), warnings


def _insufficient_evidence(model: str, mode: str) -> dict[str, Any]:
    report = SecurityReport(
        risk_level=RiskLevel.UNKNOWN,
        summary="Nema dovoljno relevantnih indeksiranih dokaza za pouzdan zaključak.",
        recommended_actions=[
            "Odaberi indeksiranu datoteku ili proširi skup relevantnih vremenskih prozora."
        ],
    ).model_dump(mode="json")
    report.update(
        {
            "inference_ms": 0.0,
            "model_used": model,
            "detection_mode": mode,
            "prompt_version": PROMPT_VERSION,
            "evidence_count": 0,
            "validation_warnings": [],
        }
    )
    return report


def generate_local_security_report_mode(
    query: str,
    evidence: list[dict[str, Any]],
    model: str | None = None,
    mode: str = "auto",
) -> dict[str, Any]:
    selected_model = model or OLLAMA_MODEL
    detection_mode = DetectionMode(mode)
    if detection_mode is DetectionMode.TEXT:
        raise UnsupportedDetectionModeError(
            "Web/text analiza je onemogućena jer mrežni flow dataset nema HTTP URL, "
            "zaglavlja ni payload potreban za valjanu detekciju SQLi/XSS napada."
        )
    detection_mode = DetectionMode.FLOW

    if not evidence:
        return _insufficient_evidence(selected_model, detection_mode.value)

    compact = [
        {
            "id": item.get("id"),
            "similarity": item.get("similarity"),
            "incident": item.get("document"),
            "metadata": item.get("metadata"),
        }
        for item in evidence
    ]
    evidence_ids = {str(item["id"]) for item in compact if item.get("id")}

    started = time.perf_counter()
    response = ollama.chat(
        model=selected_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_FLOW},
            {
                "role": "user",
                "content": json.dumps(
                    {"question": query, "incident_evidence": compact},
                    ensure_ascii=False,
                ),
            },
        ],
        format="json",
        options={"temperature": 0, "seed": 42},
    )
    inference_ms = round((time.perf_counter() - started) * 1000, 1)
    raw = str(response["message"]["content"])
    report, warnings = _validated_report(raw, evidence_ids)
    report.update(
        {
            "inference_ms": inference_ms,
            "model_used": selected_model,
            "detection_mode": detection_mode.value,
            "prompt_version": PROMPT_VERSION,
            "evidence_count": len(evidence),
            "validation_warnings": warnings,
        }
    )
    return report


def generate_local_security_report(
    query: str,
    evidence: list[dict[str, Any]],
    model: str | None = None,
) -> dict[str, Any]:
    return generate_local_security_report_mode(query, evidence, model, "flow")
