from __future__ import annotations

import argparse
import importlib.metadata
import json
import random
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _render_prompt(tokenizer: Any, messages: list[dict[str, str]], qwen: bool) -> str:
    kwargs = {"tokenize": False, "add_generation_prompt": True}
    if qwen:
        kwargs["enable_thinking"] = False
    try:
        return tokenizer.apply_chat_template(messages, **kwargs)
    except TypeError:
        kwargs.pop("enable_thinking", None)
        return tokenizer.apply_chat_template(messages, **kwargs)


def train(arguments: argparse.Namespace) -> dict[str, Any]:
    import numpy as np
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        set_seed,
    )
    from trl import SFTConfig, SFTTrainer

    model_registry = json.loads(arguments.models_file.read_text(encoding="utf-8"))
    if arguments.model not in model_registry:
        raise ValueError(f"Nepoznat model. Dostupno: {', '.join(model_registry)}")
    model_spec = model_registry[arguments.model]
    model_id = model_spec["model_id"]
    output_dir = arguments.output_dir / arguments.model
    output_dir.mkdir(parents=True, exist_ok=True)

    random.seed(arguments.seed)
    np.random.seed(arguments.seed)
    set_seed(arguments.seed)
    if not torch.cuda.is_available():
        raise RuntimeError("QLoRA trening zahtijeva CUDA GPU.")
    torch.cuda.manual_seed_all(arguments.seed)
    compute_dtype = (
        torch.bfloat16
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        else torch.float16
    )
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        token=arguments.hf_token,
        trust_remote_code=bool(model_spec.get("trust_remote_code", False)),
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        token=arguments.hf_token,
        trust_remote_code=bool(model_spec.get("trust_remote_code", False)),
        quantization_config=quantization,
        device_map="auto",
        torch_dtype=compute_dtype,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)

    files = {
        "train": str(arguments.data_dir / "train.jsonl"),
        "validation": str(arguments.data_dir / "validation.jsonl"),
    }
    dataset = load_dataset("json", data_files=files)
    is_qwen = arguments.model.startswith("qwen")
    dataset = dataset.map(
        lambda row: {
            "prompt": _render_prompt(tokenizer, row["messages"][:-1], is_qwen),
            "completion": row["messages"][-1]["content"] + tokenizer.eos_token,
        },
        remove_columns=dataset["train"].column_names,
    )

    lora = LoraConfig(
        r=arguments.lora_rank,
        lora_alpha=arguments.lora_alpha,
        lora_dropout=arguments.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        # Portable across Qwen, SmolLM and Phi projection naming schemes.
        target_modules="all-linear",
    )
    training_config = SFTConfig(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=arguments.epochs,
        per_device_train_batch_size=arguments.batch_size,
        per_device_eval_batch_size=arguments.batch_size,
        gradient_accumulation_steps=arguments.gradient_accumulation_steps,
        learning_rate=arguments.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.01,
        max_grad_norm=1.0,
        max_length=arguments.max_seq_length,
        completion_only_loss=True,
        packing=False,
        gradient_checkpointing=True,
        fp16=compute_dtype == torch.float16,
        bf16=compute_dtype == torch.bfloat16,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=arguments.seed,
        data_seed=arguments.seed,
        report_to="none",
    )
    trainer = SFTTrainer(
        model=model,
        args=training_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        peft_config=lora,
        processing_class=tokenizer,
    )
    result = trainer.train(resume_from_checkpoint=arguments.resume)
    adapter_dir = output_dir / "adapter"
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    metrics = {key: float(value) for key, value in result.metrics.items()}
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "model_key": arguments.model,
        "model_id": model_id,
        "license": model_spec["license"],
        "quantization_during_training": "QLoRA NF4 4-bit double quantization",
        "seed": arguments.seed,
        "hyperparameters": {
            "epochs": arguments.epochs,
            "batch_size": arguments.batch_size,
            "gradient_accumulation_steps": arguments.gradient_accumulation_steps,
            "learning_rate": arguments.learning_rate,
            "max_seq_length": arguments.max_seq_length,
            "lora_rank": arguments.lora_rank,
            "lora_alpha": arguments.lora_alpha,
            "lora_dropout": arguments.lora_dropout,
        },
        "hardware": {
            "cuda_available": torch.cuda.is_available(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "compute_dtype": str(compute_dtype),
        },
        "package_versions": {
            name: _version(name)
            for name in ("torch", "transformers", "datasets", "peft", "trl", "bitsandbytes")
        },
        "metrics": metrics,
    }
    (output_dir / "training_report.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--models-file",
        type=Path,
        default=Path(__file__).with_name("models.json"),
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data/experiments"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--hf-token", default=None)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-seq-length", type=int, default=768)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(train(parse_args()), indent=2))
