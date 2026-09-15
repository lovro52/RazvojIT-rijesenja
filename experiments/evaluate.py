from __future__ import annotations

import argparse
import json
import random
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


def _load_jsonl(path: Path, limit: int | None) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
                if limit and len(rows) >= limit:
                    break
    if not rows:
        raise ValueError(f"Nema evaluacijskih primjera u {path}.")
    return rows


def _extract_prediction(text: str, allowed: set[str]) -> str | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
        value = str(payload["attack_type"])
        risk = str(payload["risk_level"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return value if value in allowed and risk in {"LOW", "MEDIUM", "HIGH"} else None


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = round((len(ordered) - 1) * percentile)
    return round(ordered[position], 3)


def _bootstrap_macro_f1(
    truth: list[str], prediction: list[str], labels: list[str], seed: int
) -> list[float]:
    import numpy as np
    from sklearn.metrics import f1_score

    randomizer = np.random.default_rng(seed)
    indices = np.arange(len(truth))
    scores = []
    for _ in range(1000):
        sample = randomizer.choice(indices, size=len(indices), replace=True)
        scores.append(
            float(
                f1_score(
                    np.asarray(truth)[sample],
                    np.asarray(prediction)[sample],
                    labels=labels,
                    average="macro",
                    zero_division=0,
                )
            )
        )
    return [
        round(float(np.percentile(scores, 2.5)), 4),
        round(float(np.percentile(scores, 97.5)), 4),
    ]


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    import numpy as np
    import torch
    from peft import AutoPeftModelForCausalLM
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
    )
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        set_seed,
    )

    registry = json.loads(arguments.models_file.read_text(encoding="utf-8"))
    specification = registry[arguments.model]
    model_id = specification["model_id"]
    rows = _load_jsonl(arguments.dataset, arguments.max_samples or None)
    labels = ATTACK_TYPES
    allowed = set(ATTACK_TYPES)
    random.seed(arguments.seed)
    np.random.seed(arguments.seed)
    set_seed(arguments.seed)
    if not torch.cuda.is_available():
        raise RuntimeError("4-bit base/fine-tuned evaluacija zahtijeva CUDA GPU.")

    dtype = (
        torch.bfloat16
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        else torch.float16
    )
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=dtype,
    )
    common = {
        "device_map": "auto",
        "quantization_config": quantization,
        "torch_dtype": dtype,
        "trust_remote_code": bool(specification.get("trust_remote_code", False)),
    }
    if arguments.variant == "fine_tuned":
        if not arguments.adapter:
            raise ValueError("--adapter je obvezan za fine_tuned evaluaciju.")
        model = AutoPeftModelForCausalLM.from_pretrained(arguments.adapter, **common)
        tokenizer_source = arguments.adapter
    else:
        model = AutoModelForCausalLM.from_pretrained(model_id, **common)
        tokenizer_source = model_id
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_source,
        trust_remote_code=bool(specification.get("trust_remote_code", False)),
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.eval()

    def generate(row: dict[str, Any]) -> tuple[str, float, int]:
        messages = row["messages"][:-1]
        template_arguments = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        if arguments.model.startswith("qwen"):
            template_arguments["enable_thinking"] = False
        try:
            prompt = tokenizer.apply_chat_template(messages, **template_arguments)
        except TypeError:
            template_arguments.pop("enable_thinking", None)
            prompt = tokenizer.apply_chat_template(messages, **template_arguments)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=arguments.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        latency = (time.perf_counter() - started) * 1000
        generated = output[0, inputs["input_ids"].shape[1] :]
        return tokenizer.decode(generated, skip_special_tokens=True), latency, len(generated)

    for _ in range(arguments.warmup_runs):
        generate(rows[0])
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    truth: list[str] = []
    prediction_for_metrics: list[str] = []
    latencies: list[float] = []
    generated_tokens = 0
    invalid = 0
    predictions = []
    for row in rows:
        raw, latency, token_count = generate(row)
        predicted = _extract_prediction(raw, allowed)
        actual = str(row["label"])
        truth.append(actual)
        prediction_for_metrics.append(predicted or "INVALID_OUTPUT")
        latencies.append(latency)
        generated_tokens += token_count
        invalid += int(predicted is None)
        predictions.append(
            {
                "source_file": row.get("source_file"),
                "source_row": row.get("source_row"),
                "actual": actual,
                "predicted": predicted,
                "latency_ms": round(latency, 3),
                "raw_output": raw,
            }
        )

    metric_labels = ATTACK_TYPES + ["INVALID_OUTPUT"]
    report = classification_report(
        truth,
        prediction_for_metrics,
        labels=metric_labels,
        output_dict=True,
        zero_division=0,
    )
    total_seconds = sum(latencies) / 1000
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "model_key": arguments.model,
        "model_id": model_id,
        "variant": arguments.variant,
        "adapter": str(arguments.adapter) if arguments.adapter else None,
        "dataset": str(arguments.dataset),
        "seed": arguments.seed,
        "deterministic_decoding": True,
        "warmup_runs": arguments.warmup_runs,
        "n_samples": len(rows),
        "accuracy": round(float(accuracy_score(truth, prediction_for_metrics)), 4),
        "f1_macro": round(
            float(
                f1_score(
                    truth, prediction_for_metrics, labels=labels, average="macro", zero_division=0
                )
            ),
            4,
        ),
        "f1_macro_95pct_bootstrap_ci": _bootstrap_macro_f1(
            truth, prediction_for_metrics, labels, arguments.seed
        ),
        "invalid_output_rate": round(invalid / len(rows), 4),
        "per_class": {name: report[name] for name in ATTACK_TYPES},
        "confusion_matrix_labels": metric_labels,
        "confusion_matrix": confusion_matrix(
            truth, prediction_for_metrics, labels=metric_labels
        ).tolist(),
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 3),
            "median": round(statistics.median(latencies), 3),
            "p95": _percentile(latencies, 0.95),
        },
        "throughput_samples_per_second": round(len(rows) / max(total_seconds, 1e-9), 4),
        "generated_tokens_per_second": round(generated_tokens / max(total_seconds, 1e-9), 3),
        "peak_gpu_memory_mb": (
            round(torch.cuda.max_memory_allocated() / 1024**2, 2)
            if torch.cuda.is_available()
            else None
        ),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    predictions_path = arguments.output.with_name(arguments.output.stem + "_predictions.jsonl")
    with predictions_path.open("w", encoding="utf-8") as handle:
        for prediction in predictions:
            handle.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--variant", choices=("base", "fine_tuned"), required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models-file", type=Path, default=Path(__file__).with_name("models.json"))
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--warmup-runs", type=int, default=3)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(evaluate(parse_args()), indent=2))
