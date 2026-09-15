from __future__ import annotations
from typing import Any, Dict, List, Tuple
import time
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, f1_score, precision_score,
    recall_score, accuracy_score, confusion_matrix
)
import xgboost as xgb

# ── Paths ──────────────────────────────────────────────────────────────────
MODEL_DIR = Path("data/models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

RF_PATH  = MODEL_DIR / "random_forest.pkl"
XGB_PATH = MODEL_DIR / "xgboost.pkl"
ENC_PATH = MODEL_DIR / "label_encoder.pkl"
META_PATH = MODEL_DIR / "baseline_meta.json"

# ── CICIDS2017 numeric features used for training ──────────────────────────
FLOW_FEATURES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Fwd Packet Length Max", "Fwd Packet Length Min", "Fwd Packet Length Mean",
    "Bwd Packet Length Max", "Bwd Packet Length Min", "Bwd Packet Length Mean",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std",
    "Fwd IAT Mean", "Fwd IAT Std", "Bwd IAT Mean", "Bwd IAT Std",
    "Fwd PSH Flags", "Bwd PSH Flags", "Fwd URG Flags", "Bwd URG Flags",
    "FIN Flag Count", "SYN Flag Count", "RST Flag Count",
    "PSH Flag Count", "ACK Flag Count", "URG Flag Count",
    "Down/Up Ratio", "Average Packet Size", "Avg Fwd Segment Size",
    "Avg Bwd Segment Size",
]


def _load_encoder():
    if ENC_PATH.exists():
        with open(ENC_PATH, "rb") as f:
            return pickle.load(f)
    return LabelEncoder()


def _save_encoder(enc):
    with open(ENC_PATH, "wb") as f:
        pickle.dump(enc, f)


def _prepare_features(df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    """Extract and clean numeric features from a CICIDS-style DataFrame."""
    df = df.rename(columns={c: c.strip() for c in df.columns})

    available = [f for f in FLOW_FEATURES if f in df.columns]
    X = df[available].copy()

    # Replace inf / NaN with 0
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(0, inplace=True)

    return X.values.astype(np.float32), available


def train_models(csv_path: str, sample_size: int = 20000) -> Dict[str, Any]:
    """
    Train Random Forest and XGBoost on a CICIDS-format CSV.
    Returns training metrics for both models.
    """
    df = pd.read_csv(csv_path)
    df = df.rename(columns={c: c.strip() for c in df.columns})

    if "Label" not in df.columns:
        return {"error": "CSV nema 'Label' stupac — nije CICIDS format"}

    # Sample to keep training fast
    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)

    X, features_used = _prepare_features(df)
    y_raw = df["Label"].astype(str).str.strip().values

    enc = _load_encoder()
    y   = enc.fit_transform(y_raw)  # type: ignore[arg-type]
    _save_encoder(enc)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    results = {}

    # ── Random Forest ──────────────────────────────────────────────────────
    t0 = time.perf_counter()
    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf_train_ms = round(float((time.perf_counter() - t0) * 1000), 1)

    t0 = time.perf_counter()
    y_pred_rf = rf.predict(X_test)
    rf_inf_ms = round(float((time.perf_counter() - t0) / len(X_test) * 1000), 4)

    with open(RF_PATH, "wb") as f:
        pickle.dump(rf, f)

    results["random_forest"] = {
        "name":         "Random Forest",
        "train_time_ms": rf_train_ms,
        "inference_ms_per_sample": rf_inf_ms,
        "accuracy":  round(float(accuracy_score(y_test, y_pred_rf)), 4),
        "f1_macro":  round(float(f1_score(y_test, y_pred_rf, average="macro",  zero_division=0)), 4),  # type: ignore[arg-type]
        "f1_weighted": round(float(f1_score(y_test, y_pred_rf, average="weighted", zero_division=0)), 4),  # type: ignore[arg-type]
        "precision": round(float(precision_score(y_test, y_pred_rf, average="weighted", zero_division=0)), 4),  # type: ignore[arg-type]
        "recall":    round(float(recall_score(y_test, y_pred_rf, average="weighted", zero_division=0)), 4),  # type: ignore[arg-type]
        "classes":   list(enc.classes_),
        "n_samples": len(X_train),
    }

    # ── XGBoost ───────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    xgb_model = xgb.XGBClassifier(
        n_estimators=100, max_depth=6, learning_rate=0.1,
        use_label_encoder=False, eval_metric="mlogloss",
        random_state=42, n_jobs=-1,
    )
    xgb_model.fit(X_train, y_train)
    xgb_train_ms = round(float((time.perf_counter() - t0) * 1000), 1)

    t0 = time.perf_counter()
    y_pred_xgb = xgb_model.predict(X_test)
    xgb_inf_ms = round(float((time.perf_counter() - t0) / len(X_test) * 1000), 4)

    with open(XGB_PATH, "wb") as f:
        pickle.dump(xgb_model, f)

    results["xgboost"] = {
        "name":         "XGBoost",
        "train_time_ms": xgb_train_ms,
        "inference_ms_per_sample": xgb_inf_ms,
        "accuracy":  round(float(accuracy_score(y_test, y_pred_xgb)), 4),
        "f1_macro":  round(float(f1_score(y_test, y_pred_xgb, average="macro",  zero_division=0)), 4),  # type: ignore[arg-type]
        "f1_weighted": round(float(f1_score(y_test, y_pred_xgb, average="weighted", zero_division=0)), 4),  # type: ignore[arg-type]
        "precision": round(float(precision_score(y_test, y_pred_xgb, average="weighted", zero_division=0)), 4),  # type: ignore[arg-type]
        "recall":    round(float(recall_score(y_test, y_pred_xgb, average="weighted", zero_division=0)), 4),  # type: ignore[arg-type]
        "classes":   list(enc.classes_),
        "n_samples": len(X_train),
    }

    # Save metadata
    meta = {
        "features_used": features_used,
        "trained_on":    csv_path,
        "sample_size":   len(df),
        "classes":       list(enc.classes_),
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f)

    return {
        "status":   "trained",
        "results":  results,
        "features": features_used,
        "classes":  list(enc.classes_),
        "n_samples": len(df),
    }


def predict_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Predict attack type for a single log record using both trained models.
    record should have numeric flow features (CICIDS format).
    """
    if not RF_PATH.exists() or not XGB_PATH.exists():
        return {"error": "Modeli nisu trenirani. Najprije pokreni /baseline/train."}

    with open(RF_PATH,  "rb") as f: rf  = pickle.load(f)
    with open(XGB_PATH, "rb") as f: xgb_model = pickle.load(f)
    with open(ENC_PATH, "rb") as f: enc = pickle.load(f)
    with open(META_PATH)       as f: meta = json.load(f)

    features = meta["features_used"]
    row = [float(record.get(feat, 0) or 0) for feat in features]
    X   = np.array([row], dtype=np.float32)

    results = {}

    t0 = time.perf_counter()
    pred_rf  = rf.predict(X)[0]
    prob_rf  = rf.predict_proba(X)[0]
    rf_ms    = round((time.perf_counter() - t0) * 1000, 2)
    results["random_forest"] = {
        "prediction":   enc.inverse_transform([pred_rf])[0],
        "confidence":   round(float(prob_rf.max()), 4),
        "inference_ms": rf_ms,
    }

    t0 = time.perf_counter()
    pred_xgb = xgb_model.predict(X)[0]
    prob_xgb = xgb_model.predict_proba(X)[0]
    xgb_ms   = round((time.perf_counter() - t0) * 1000, 2)
    results["xgboost"] = {
        "prediction":   enc.inverse_transform([pred_xgb])[0],
        "confidence":   round(float(prob_xgb.max()), 4),
        "inference_ms": xgb_ms,
    }

    return {"results": results, "features_used": features}


def get_baseline_status() -> Dict[str, Any]:
    """Return whether models are trained and their metadata."""
    trained = RF_PATH.exists() and XGB_PATH.exists()
    if not trained:
        return {"trained": False}

    meta = {}
    if META_PATH.exists():
        with open(META_PATH) as f:
            meta = json.load(f)

    return {"trained": True, "meta": meta}


def evaluate_on_file(csv_path: str, sample_size: int = 10000) -> Dict[str, Any]:
    """
    Evaluate trained models on a new CSV file (without retraining).
    Returns per-class and overall metrics for both models.
    """
    if not RF_PATH.exists() or not XGB_PATH.exists():
        return {"error": "Modeli nisu trenirani. Najprije pokreni /baseline/train."}

    with open(RF_PATH,  "rb") as f: rf        = pickle.load(f)
    with open(XGB_PATH, "rb") as f: xgb_model = pickle.load(f)
    with open(ENC_PATH, "rb") as f: enc       = pickle.load(f)

    df = pd.read_csv(csv_path)
    df = df.rename(columns={c: c.strip() for c in df.columns})

    if "Label" not in df.columns:
        return {"error": "CSV nema 'Label' stupac"}

    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)

    X, features_used = _prepare_features(df)
    y_raw = df["Label"].astype(str).str.strip().values

    # Handle unseen labels
    known = set(enc.classes_)
    mask  = np.array([y in known for y in y_raw])
    if mask.sum() == 0:
        return {"error": "Niti jedna klasa u ovom fajlu nije poznata modelu"}

    X     = X[mask]
    y_raw = y_raw[mask]
    y     = enc.transform(y_raw)  # type: ignore[arg-type]

    results = {}
    classes = list(enc.classes_)

    for name, model in [("random_forest", rf), ("xgboost", xgb_model)]:
        t0     = time.perf_counter()
        y_pred = model.predict(X)
        inf_ms = round(float((time.perf_counter() - t0) / max(len(X), 1) * 1000), 4)

        report = classification_report(
            y, y_pred,
            labels=list(range(len(classes))),
            target_names=classes,
            output_dict=True,
            zero_division=0,
        )

        per_class = {}
        for cls in classes:
            if cls in report:
                cls_data = report[cls]  # type: ignore[index]
                per_class[cls] = {
                    "precision": round(float(cls_data["precision"]), 4),  # type: ignore[index]
                    "recall":    round(float(cls_data["recall"]),    4),  # type: ignore[index]
                    "f1":        round(float(cls_data["f1-score"]),  4),  # type: ignore[index]
                    "support":   int(cls_data["support"]),                # type: ignore[index]
                }

        results[name] = {
            "accuracy":    round(float(accuracy_score(y, y_pred)), 4),
            "f1_weighted": round(float(f1_score(y, y_pred, average="weighted", zero_division=0)), 4),  # type: ignore[arg-type]
            "f1_macro":    round(float(f1_score(y, y_pred, average="macro",    zero_division=0)), 4),  # type: ignore[arg-type]
            "precision":   round(float(precision_score(y, y_pred, average="weighted", zero_division=0)), 4),  # type: ignore[arg-type]
            "recall":      round(float(recall_score(y, y_pred, average="weighted",    zero_division=0)), 4),  # type: ignore[arg-type]
            "inference_ms_per_sample": inf_ms,
            "per_class":   per_class,
            "n_samples":   int(len(y)),
        }

    # Attack type distribution
    unique, counts = np.unique(y_raw, return_counts=True)  # type: ignore[call-overload]
    distribution   = {str(k): int(v) for k, v in zip(unique, counts)}

    return {
        "file":         csv_path.split("\\")[-1].split("/")[-1],
        "n_samples":    int(len(y)),
        "distribution": distribution,
        "results":      results,
        "features":     features_used,
    }