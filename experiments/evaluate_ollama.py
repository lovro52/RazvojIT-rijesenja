from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.feature_schema import ATTACK_TYPES  # noqa: E402
from app.services.llm_classifier import _parse_classification  # noqa: E402
from experiments.evaluate import _bootstrap_macro_f1  # noqa: E402


def _rows(path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
                if limit and len(rows) >= limit:
                    break
    if not rows:
        raise ValueError("Evaluacijski skup je prazan.")
    return rows


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = min(round((len(ordered) - 1) * fraction), len(ordered) - 1)
    return round(ordered[position], 3)


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    import ollama
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

    rows = _rows(arguments.dataset, arguments.max_samples)

    def infer(row: dict[str, Any]) -> tuple[str | None, float, str]:
        started = time.perf_counter()
        response = ollama.chat(
            model=arguments.model,
            messages=row["messages"][:-1],
            format="json",
            options={"temperature": 0, "seed": arguments.seed, "num_predict": 64},
        )
        latency = (time.perf_counter() - started) * 1000
        raw = str(response["message"]["content"])
        try:
            return _parse_classification(raw).attack_type, latency, raw
        except ValueError:
            return None, latency, raw

    for _ in range(arguments.warmup_runs):
        infer(rows[0])

    truth: list[str] = []
    predicted: list[str] = []
    latencies: list[float] = []
    details: list[dict[str, Any]] = []
    for row in rows:
        prediction, latency, raw = infer(row)
        actual = str(row["label"])
        truth.append(actual)
        predicted.append(prediction or "INVALID_OUTPUT")
        latencies.append(latency)
        details.append(
            {
                "source_file": row.get("source_file"),
                "source_row": row.get("source_row"),
                "actual": actual,
                "predicted": prediction,
                "latency_ms": round(latency, 3),
                "raw_output": raw,
            }
        )

    labels = ATTACK_TYPES + ["INVALID_OUTPUT"]
    class_report = classification_report(
        truth, predicted, labels=labels, output_dict=True, zero_division=0
    )
    elapsed = sum(latencies) / 1000
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "runtime": "ollama",
        "model": arguments.model,
        "dataset": str(arguments.dataset),
        "seed": arguments.seed,
        "warmup_runs": arguments.warmup_runs,
        "n_samples": len(rows),
        "accuracy": round(float(accuracy_score(truth, predicted)), 4),
        "f1_macro": round(
            float(
                f1_score(truth, predicted, labels=ATTACK_TYPES, average="macro", zero_division=0)
            ),
            4,
        ),
        "f1_macro_95pct_bootstrap_ci": _bootstrap_macro_f1(
            truth, predicted, ATTACK_TYPES, arguments.seed
        ),
        "invalid_output_rate": round(predicted.count("INVALID_OUTPUT") / len(rows), 4),
        "per_class": {label: class_report[label] for label in ATTACK_TYPES},
        "confusion_matrix_labels": labels,
        "confusion_matrix": confusion_matrix(truth, predicted, labels=labels).tolist(),
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 3),
            "median": round(statistics.median(latencies), 3),
            "p95": _percentile(latencies, 0.95),
        },
        "throughput_samples_per_second": round(len(rows) / max(elapsed, 1e-9), 4),
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    detail_path = arguments.output.with_name(arguments.output.stem + "_predictions.jsonl")
    with detail_path.open("w", encoding="utf-8") as handle:
        for detail in details:
            handle.write(json.dumps(detail, ensure_ascii=False) + "\n")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Ollama tag, npr. netlog-qwen3:q4_k_m")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--warmup-runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(evaluate(parse_args()), indent=2))
