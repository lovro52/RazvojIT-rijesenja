from __future__ import annotations

import json
import pickle
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from app.core.config import MODEL_DIR

MODEL_DIR.mkdir(parents=True, exist_ok=True)
RF_PATH = MODEL_DIR / "random_forest.pkl"
XGB_PATH = MODEL_DIR / "xgboost.pkl"
ENC_PATH = MODEL_DIR / "label_encoder.pkl"
META_PATH = MODEL_DIR / "baseline_meta.json"

FLOW_FEATURES = [
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Total Length of Fwd Packets",
    "Total Length of Bwd Packets",
    "Fwd Packet Length Max",
    "Fwd Packet Length Min",
    "Fwd Packet Length Mean",
    "Bwd Packet Length Max",
    "Bwd Packet Length Min",
    "Bwd Packet Length Mean",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Flow IAT Mean",
    "Flow IAT Std",
    "Fwd IAT Mean",
    "Fwd IAT Std",
    "Bwd IAT Mean",
    "Bwd IAT Std",
    "Fwd PSH Flags",
    "Bwd PSH Flags",
    "Fwd URG Flags",
    "Bwd URG Flags",
    "FIN Flag Count",
    "SYN Flag Count",
    "RST Flag Count",
    "PSH Flag Count",
    "ACK Flag Count",
    "URG Flag Count",
    "Down/Up Ratio",
    "Average Packet Size",
    "Avg Fwd Segment Size",
    "Avg Bwd Segment Size",
]


def _read_pickle(path: Path):
    # Model artifacts are local and must never be accepted through the upload API.
    with path.open("rb") as handle:
        return pickle.load(handle)


def _write_pickle(path: Path, value: Any) -> None:
    with path.open("wb") as handle:
        pickle.dump(value, handle)


def _prepare_features(
    dataframe: pd.DataFrame,
    required_features: list[str] | None = None,
    strict: bool = False,
) -> tuple[np.ndarray, list[str], list[str]]:
    """Return numeric model input in a stable, explicitly defined order."""
    clean = dataframe.rename(columns={str(c): str(c).strip() for c in dataframe.columns})
    features = required_features or [name for name in FLOW_FEATURES if name in clean.columns]
    missing = [name for name in features if name not in clean.columns]
    if strict and missing:
        raise ValueError("Dataset nema značajke korištene pri treniranju: " + ", ".join(missing))
    if not features:
        raise ValueError("Dataset ne sadrži podržane numeričke flow značajke.")

    values = clean.reindex(columns=features, fill_value=0).apply(pd.to_numeric, errors="coerce")
    values.replace([np.inf, -np.inf], np.nan, inplace=True)
    values.fillna(0, inplace=True)
    return values.to_numpy(dtype=np.float32), features, missing


def _metrics(
    truth: np.ndarray,
    prediction: np.ndarray,
    classes: list[str],
    inference_ms: float,
) -> dict[str, Any]:
    labels = list(range(len(classes)))
    report = classification_report(
        truth,
        prediction,
        labels=labels,
        target_names=classes,
        output_dict=True,
        zero_division=0,
    )
    per_class = {
        name: {
            "precision": round(float(report[name]["precision"]), 4),
            "recall": round(float(report[name]["recall"]), 4),
            "f1": round(float(report[name]["f1-score"]), 4),
            "support": int(report[name]["support"]),
        }
        for name in classes
        if name in report
    }
    return {
        "accuracy": round(float(accuracy_score(truth, prediction)), 4),
        "f1_macro": round(float(f1_score(truth, prediction, average="macro", zero_division=0)), 4),
        "f1_weighted": round(
            float(f1_score(truth, prediction, average="weighted", zero_division=0)), 4
        ),
        "precision_macro": round(
            float(precision_score(truth, prediction, average="macro", zero_division=0)), 4
        ),
        "recall_macro": round(
            float(recall_score(truth, prediction, average="macro", zero_division=0)), 4
        ),
        "precision_weighted": round(
            float(precision_score(truth, prediction, average="weighted", zero_division=0)), 4
        ),
        "recall_weighted": round(
            float(recall_score(truth, prediction, average="weighted", zero_division=0)), 4
        ),
        "inference_ms_per_sample": inference_ms,
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(truth, prediction, labels=labels).tolist(),
        "confusion_matrix_labels": classes,
        "n_samples": int(len(truth)),
    }


def train_models(csv_path: str, sample_size: int = 20000) -> dict[str, Any]:
    """Train quick RF/XGBoost baselines for the application demo.

    The thesis experiments use the separate grouped-split pipeline under
    ``experiments/``; this endpoint is intentionally labelled as a demo baseline.
    """
    dataframe = pd.read_csv(csv_path)
    dataframe = dataframe.rename(columns={str(c): str(c).strip() for c in dataframe.columns})
    if "Label" not in dataframe.columns:
        return {"error": "CSV nema stupac 'Label' — nije podržani CICIDS format."}
    if len(dataframe) > sample_size:
        dataframe = dataframe.sample(n=sample_size, random_state=42).reset_index(drop=True)

    try:
        features, features_used, _ = _prepare_features(dataframe)
    except ValueError as exc:
        return {"error": str(exc)}
    raw_labels = dataframe["Label"].astype(str).str.strip().to_numpy()
    counts = pd.Series(raw_labels).value_counts()
    if len(counts) < 2 or int(counts.min()) < 2:
        return {"error": "Potrebne su najmanje dvije klase i dva primjera po klasi."}

    encoder = LabelEncoder()
    labels = encoder.fit_transform(raw_labels)
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )
    classes = [str(value) for value in encoder.classes_]
    models = {
        "random_forest": RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1),
        "xgboost": xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=-1,
        ),
    }
    paths = {"random_forest": RF_PATH, "xgboost": XGB_PATH}
    results: dict[str, Any] = {}
    for name, model in models.items():
        started = time.perf_counter()
        model.fit(x_train, y_train)
        training_ms = round((time.perf_counter() - started) * 1000, 1)
        started = time.perf_counter()
        prediction = model.predict(x_test)
        inference_ms = round((time.perf_counter() - started) * 1000 / max(len(x_test), 1), 4)
        result = _metrics(y_test, prediction, classes, inference_ms)
        result.update(
            {
                "name": "Random Forest" if name == "random_forest" else "XGBoost",
                "train_time_ms": training_ms,
                "training_samples": int(len(x_train)),
            }
        )
        results[name] = result
        _write_pickle(paths[name], model)

    _write_pickle(ENC_PATH, encoder)
    metadata = {
        "schema_version": "cicids-flow-v2",
        "features_used": features_used,
        "trained_on": Path(csv_path).name,
        "sample_size": int(len(dataframe)),
        "classes": classes,
        "random_seed": 42,
        "split_strategy": "stratified_random_80_20_demo_only",
        "missing_value_imputation": "zero",
    }
    META_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {
        "status": "trained",
        "purpose": "application_demo_baseline",
        "results": results,
        "features": features_used,
        "classes": classes,
        "n_samples": int(len(dataframe)),
    }


def _load_artifacts() -> tuple[Any, Any, LabelEncoder, dict[str, Any]]:
    required = (RF_PATH, XGB_PATH, ENC_PATH, META_PATH)
    if not all(path.exists() for path in required):
        raise FileNotFoundError("Modeli nisu trenirani. Najprije pokreni /baseline/train.")
    return (
        _read_pickle(RF_PATH),
        _read_pickle(XGB_PATH),
        _read_pickle(ENC_PATH),
        json.loads(META_PATH.read_text(encoding="utf-8")),
    )


def predict_record(record: dict[str, Any]) -> dict[str, Any]:
    try:
        random_forest, xgboost_model, encoder, metadata = _load_artifacts()
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    features = list(metadata["features_used"])
    row = []
    for feature in features:
        try:
            value = float(record.get(feature, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        row.append(value if np.isfinite(value) else 0.0)
    matrix = np.asarray([row], dtype=np.float32)

    results = {}
    for name, model in (("random_forest", random_forest), ("xgboost", xgboost_model)):
        started = time.perf_counter()
        encoded = int(model.predict(matrix)[0])
        probabilities = model.predict_proba(matrix)[0]
        results[name] = {
            "prediction": str(encoder.inverse_transform([encoded])[0]),
            "confidence": round(float(probabilities.max()), 4),
            "inference_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    return {"results": results, "features_used": features}


def get_baseline_status() -> dict[str, Any]:
    try:
        _, _, _, metadata = _load_artifacts()
    except FileNotFoundError:
        return {"trained": False}
    return {"trained": True, "meta": metadata}


def evaluate_on_file(csv_path: str, sample_size: int = 10000) -> dict[str, Any]:
    try:
        random_forest, xgboost_model, encoder, metadata = _load_artifacts()
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    dataframe = pd.read_csv(csv_path)
    dataframe = dataframe.rename(columns={str(c): str(c).strip() for c in dataframe.columns})
    if "Label" not in dataframe.columns:
        return {"error": "CSV nema stupac 'Label'."}
    if len(dataframe) > sample_size:
        dataframe = dataframe.sample(n=sample_size, random_state=42).reset_index(drop=True)

    required_features = list(metadata.get("features_used", []))
    try:
        features, features_used, missing = _prepare_features(
            dataframe, required_features=required_features, strict=True
        )
    except ValueError as exc:
        return {"error": str(exc), "required_features": required_features}

    raw_labels = dataframe["Label"].astype(str).str.strip().to_numpy()
    known_classes = set(str(value) for value in encoder.classes_)
    mask = np.asarray([label in known_classes for label in raw_labels])
    if int(mask.sum()) == 0:
        return {"error": "Nijedna klasa iz datoteke nije poznata modelu."}
    features = features[mask]
    raw_labels = raw_labels[mask]
    labels = encoder.transform(raw_labels)
    classes = [str(value) for value in encoder.classes_]

    results = {}
    for name, model in (("random_forest", random_forest), ("xgboost", xgboost_model)):
        started = time.perf_counter()
        prediction = model.predict(features)
        inference_ms = round((time.perf_counter() - started) * 1000 / max(len(features), 1), 4)
        results[name] = _metrics(labels, prediction, classes, inference_ms)

    unique, counts = np.unique(raw_labels, return_counts=True)
    return {
        "file": Path(csv_path).name,
        "n_samples": int(len(labels)),
        "ignored_unseen_labels": int((~mask).sum()),
        "distribution": {str(key): int(value) for key, value in zip(unique, counts, strict=True)},
        "results": results,
        "features": features_used,
        "missing_features": missing,
    }
