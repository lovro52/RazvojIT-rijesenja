"""
Klasifikacija pojedinačnog mrežnog toka fine-tunanim modelom.

Odvojeno od `llm_local.py` jer su to dva različita zadatka:

  llm_local.py       RAG sloj — prima korisnički upit i više dohvaćenih
                     dokaza, generira sigurnosni izvještaj. Koristi opći
                     model (llama3.1:8b).

  llm_classifier.py  Klasifikacijski sloj — prima jedan tok, vraća tip
                     napada i razinu rizika. Koristi fine-tunani model
                     (v3) i prompt identičan onome iz treninga.

Miješanje to dvoje bio bi propust: fine-tunani model nikad nije vidio
RAG prompt s poljima `query` i `evidence`, pa bi na njemu radio lošije
nego bazni model.
"""
from __future__ import annotations

import json
import time
from typing import Any

import ollama

from app.core.flow_schema import (
    ATTACK_TYPES,
    RISK_LEVELS,
    SCHEMA_VERSION,
    build_classification_prompt,
)


class ClassifierError(RuntimeError):
    """Model nije dostupan ili nije vratio upotrebljiv odgovor."""


def _extract_json(text: str) -> str | None:
    """
    Izvlači prvi potpuni JSON objekt iz generiranog teksta.

    Modeli nastavljaju generirati i nakon zatvorene vitičaste zagrade
    (npr. novi `### Input:` blok), pa `json.loads` na cijelom izlazu puca.
    """
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 1:
            text = parts[1][4:] if parts[1].startswith("json") else parts[1]
            text = text.strip()

    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                return text[start:i + 1]
    return None


def classify_flow(
    flow_features: dict[str, Any],
    protocol: Any = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Klasificira jedan mrežni tok.

    Vraća:
        attack_type, risk_level, summary, key_indicators,
        recommended_actions, inference_ms, model_used, schema_version

    Ako model vrati neispravan JSON ili nepoznatu klasu, polje `warnings`
    to bilježi, a `attack_type` postaje "UNKNOWN". Tiho prihvaćanje
    neispravnog izlaza bilo bi gore od vidljive greške.
    """
    from app.core.config import CLASSIFIER_MODEL

    selected = model or CLASSIFIER_MODEL
    prompt   = build_classification_prompt(flow_features, protocol)

    t0 = time.perf_counter()
    try:
        response = ollama.generate(
            model=selected,
            prompt=prompt,
            # raw=True zaobilazi Modelfile TEMPLATE. Prompt je već potpun —
            # gradi ga `build_classification_prompt` iz zajedničke sheme.
            # Bez ovoga Ollama omota prompt još jednom i model dobije
            # ulaz kakav u treningu nikad nije vidio.
            raw=True,
            options={
                "temperature": 0.1,
                "num_predict": 220,
                # Model je treniran na blokovima; bez ovoga nastavlja
                # generirati sljedeći primjer nakon odgovora.
                "stop": ["### Instruction:", "### Input:", "### Response:"],
            },
        )
    except Exception as exc:
        raise ClassifierError(
            f"Model '{selected}' nije dostupan u Ollami: {exc}"
        ) from exc

    inference_ms = round((time.perf_counter() - t0) * 1000, 1)
    raw = response.get("response", "")

    warnings: list[str] = []
    payload: dict[str, Any] = {}

    extracted = _extract_json(raw)
    if extracted is None:
        warnings.append("Model nije vratio JSON objekt.")
    else:
        try:
            payload = json.loads(extracted)
        except json.JSONDecodeError as exc:
            warnings.append(f"Neispravan JSON: {exc}")

    attack = str(payload.get("attack_type", "")).strip()
    risk   = str(payload.get("risk_level", "")).strip().upper()

    if attack not in ATTACK_TYPES:
        if attack:
            warnings.append(f"Nepoznat tip napada: {attack!r}")
        attack = "UNKNOWN"
    if risk not in RISK_LEVELS:
        if risk:
            warnings.append(f"Nepoznata razina rizika: {risk!r}")
        risk = "UNKNOWN"

    return {
        "attack_type":         attack,
        "risk_level":          risk,
        "summary":             str(payload.get("summary", "")).strip(),
        "key_indicators":      list(payload.get("key_indicators", []))[:10],
        "recommended_actions": list(payload.get("recommended_actions", []))[:10],
        "inference_ms":        inference_ms,
        "model_used":          selected,
        "schema_version":      SCHEMA_VERSION,
        "warnings":            warnings,
        "raw":                 raw if warnings else None,
    }


def classify_batch(
    records: list[dict[str, Any]],
    model: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Klasificira više tokova i vraća zbirnu statistiku.

    `limit` postoji jer je inferenca po toku reda veličine sekundi —
    pedeset tokova je već minuta do nekoliko minuta, ovisno o modelu.
    """
    from collections import Counter

    subset  = records[:limit]
    results: list[dict[str, Any]] = []
    total_ms = 0.0
    failed   = 0

    for rec in subset:
        features = rec.get("flow_features") or {}
        if not features:
            failed += 1
            continue
        try:
            out = classify_flow(features, rec.get("protocol"), model)
        except ClassifierError:
            failed += 1
            continue

        total_ms += out["inference_ms"]
        results.append({
            "message":      rec.get("message"),
            "src_ip":       rec.get("src_ip"),
            "dst_ip":       rec.get("dst_ip"),
            "dst_port":     rec.get("dst_port"),
            "attack_type":  out["attack_type"],
            "risk_level":   out["risk_level"],
            "summary":      out["summary"],
            "inference_ms": out["inference_ms"],
            # Istinita oznaka, ako postoji — služi za usporedbu, ne ulazi
            # u prompt koji model vidi.
            "ground_truth": rec.get("ground_truth"),
        })

    correct = comparable = 0
    for r in results:
        gt = r.get("ground_truth")
        if not gt:
            continue
        comparable += 1
        if _labels_match(gt, r["attack_type"]):
            correct += 1

    n = len(results)
    return {
        "results":       results,
        "classified":    n,
        "failed":        failed,
        "model_used":    model,
        "avg_inference_ms": round(total_ms / n, 1) if n else None,
        "attack_distribution": dict(Counter(r["attack_type"] for r in results)),
        "risk_distribution":   dict(Counter(r["risk_level"]  for r in results)),
        "accuracy_vs_ground_truth": (
            round(correct / comparable * 100, 1) if comparable else None
        ),
        "comparable_records": comparable,
    }


def _labels_match(ground_truth: str, predicted: str) -> bool:
    """
    Uspoređuje CICIDS oznaku s predikcijom modela.

    CICIDS koristi granularnije oznake nego model: "DoS Hulk",
    "DoS GoldenEye" i "DoS slowloris" model svodi na "DoS".
    """
    gt = str(ground_truth).strip().lower()
    pr = str(predicted).strip().lower()

    if gt == pr:
        return True
    if gt.startswith("dos") or gt == "heartbleed":
        return pr == "dos"
    if gt == "ddos":
        return pr == "ddos"
    if "web attack" in gt:
        return pr == "webattack"
    if gt == "portscan":
        return pr == "portscan"
    if gt == "bot":
        return pr == "botnet"
    return gt.replace("-", "") == pr.replace("-", "")