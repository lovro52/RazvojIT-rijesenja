from __future__ import annotations

import time
from typing import Any

import ollama
from pydantic import BaseModel

from app.core.feature_schema import ATTACK_TYPES, classifier_messages


class FlowClassification(BaseModel):
    attack_type: str
    risk_level: str


def _parse_classification(raw: str) -> FlowClassification:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model nije vratio JSON objekt.")
    result = FlowClassification.model_validate_json(raw[start : end + 1])
    if result.attack_type not in ATTACK_TYPES:
        raise ValueError(f"Nepoznata klasa modela: {result.attack_type}")
    if result.risk_level not in {"LOW", "MEDIUM", "HIGH"}:
        raise ValueError(f"Nepoznata razina rizika: {result.risk_level}")
    return result


def classify_flow(record: dict[str, Any], model: str) -> dict[str, Any]:
    messages = classifier_messages(record)
    started = time.perf_counter()
    response = ollama.chat(
        model=model,
        messages=messages,
        format="json",
        options={"temperature": 0, "seed": 42, "num_predict": 64},
    )
    inference_ms = round((time.perf_counter() - started) * 1000, 2)
    raw = str(response["message"]["content"])
    try:
        classification = _parse_classification(raw).model_dump()
        error = None
    except ValueError as exc:
        classification = None
        error = str(exc)
    return {
        "model": model,
        "classification": classification,
        "inference_ms": inference_ms,
        "valid_json": classification is not None,
        "error": error,
        "raw_output": raw if classification is None else None,
    }
