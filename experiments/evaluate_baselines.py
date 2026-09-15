from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from app.core.feature_schema import ATTACK_TYPES, LLM_FLOW_FEATURES
from experiments.evaluate import _bootstrap_macro_f1


def _load(path: Path) -> tuple[np.ndarray, list[str]]:
    features: list[list[float]] = []
    labels: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            values = row["messages"][1]["content"]
            payload = json.loads(values)
            features.append(
                [float(payload["features"].get(name, 0.0)) for name in LLM_FLOW_FEATURES]
            )
            labels.append(str(row["label"]))
    if not features:
        raise ValueError(f"Skup {path} je prazan.")
    matrix = np.nan_to_num(np.asarray(features, dtype=np.float64))
    return matrix, labels


def _models(seed: int) -> dict[str, Any]:
    return {
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=None,
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=-1,
        ),
        "xgboost": XGBClassifier(
            n_estimators=300,
            max_depth=8,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="multi:softprob",
            eval_metric="mlogloss",
            tree_method="hist",
            random_state=seed,
            n_jobs=-1,
        ),
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * fraction), len(ordered) - 1)
    return round(ordered[index], 4)


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    x_train, y_train_text = _load(arguments.train)
    x_test, y_test = _load(arguments.test)
    encoder = LabelEncoder().fit(y_train_text)
    y_train = encoder.transform(y_train_text)
    requested = list(_models(arguments.seed)) if arguments.model == "all" else [arguments.model]
    results: dict[str, Any] = {}

    for name in requested:
        model = _models(arguments.seed)[name]
        started = time.perf_counter()
        fit_kwargs = {}
        if name == "xgboost":
            fit_kwargs["sample_weight"] = compute_sample_weight("balanced", y_train)
        model.fit(x_train, y_train, **fit_kwargs)
        training_seconds = time.perf_counter() - started

        model.predict(x_test[:1])
        latencies: list[float] = []
        predicted_encoded = []
        for row in x_test:
            started = time.perf_counter()
            predicted_encoded.append(int(model.predict(row.reshape(1, -1))[0]))
            latencies.append((time.perf_counter() - started) * 1000)
        predictions = encoder.inverse_transform(predicted_encoded).tolist()
        class_report = classification_report(
            y_test,
            predictions,
            labels=ATTACK_TYPES,
            output_dict=True,
            zero_division=0,
        )
        results[name] = {
            "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
            "f1_macro": round(
                float(
                    f1_score(
                        y_test,
                        predictions,
                        labels=ATTACK_TYPES,
                        average="macro",
                        zero_division=0,
                    )
                ),
                4,
            ),
            "f1_macro_95pct_bootstrap_ci": _bootstrap_macro_f1(
                y_test, predictions, ATTACK_TYPES, arguments.seed
            ),
            "per_class": {label: class_report[label] for label in ATTACK_TYPES},
            "confusion_matrix_labels": ATTACK_TYPES,
            "confusion_matrix": confusion_matrix(y_test, predictions, labels=ATTACK_TYPES).tolist(),
            "training_seconds": round(training_seconds, 3),
            "latency_ms": {
                "mean": round(statistics.mean(latencies), 4),
                "median": round(statistics.median(latencies), 4),
                "p95": _percentile(latencies, 0.95),
            },
            "throughput_samples_per_second": round(
                len(latencies) / max(sum(latencies) / 1000, 1e-9), 3
            ),
        }

    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "train": str(arguments.train),
        "test": str(arguments.test),
        "seed": arguments.seed,
        "feature_schema": LLM_FLOW_FEATURES,
        "train_rows": len(y_train_text),
        "test_rows": len(y_test),
        "trained_classes": encoder.classes_.tolist(),
        "results": results,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--model", choices=("all", "random_forest", "xgboost"), default="all")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(evaluate(parse_args()), indent=2))
