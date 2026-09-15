from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def merge_adapter(adapter: Path, merged_dir: Path) -> None:
    import torch
    from peft import AutoPeftModelForCausalLM
    from transformers import AutoTokenizer

    dtype = (
        torch.bfloat16
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        else torch.float16
    )
    model = AutoPeftModelForCausalLM.from_pretrained(
        adapter,
        device_map="auto",
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
    )
    merged = model.merge_and_unload()
    merged.save_pretrained(merged_dir, safe_serialization=True, max_shard_size="2GB")
    AutoTokenizer.from_pretrained(adapter).save_pretrained(merged_dir)


def convert_and_quantize(
    merged_dir: Path, llama_cpp_dir: Path, output: Path, quantization: str
) -> None:
    converter = llama_cpp_dir / "convert_hf_to_gguf.py"
    quantizer_candidates = [
        llama_cpp_dir / "build" / "bin" / "llama-quantize",
        llama_cpp_dir / "llama-quantize",
        llama_cpp_dir / "quantize",
    ]
    quantizer = next((path for path in quantizer_candidates if path.is_file()), None)
    if not converter.is_file() or quantizer is None:
        raise FileNotFoundError(
            "Nije pronađen llama.cpp converter ili llama-quantize. Izgradi llama.cpp "
            "i proslijedi njegov direktorij kroz --llama-cpp-dir."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    fp16_output = output.with_name(output.stem + "-f16.gguf")
    subprocess.run(
        [
            "python",
            str(converter),
            str(merged_dir),
            "--outfile",
            str(fp16_output),
            "--outtype",
            "f16",
        ],
        check=True,
    )
    subprocess.run([str(quantizer), str(fp16_output), str(output), quantization], check=True)


def create_ollama_model(output: Path, tag: str) -> None:
    model_file = output.with_name(output.stem + ".Modelfile")
    model_file.write_text(
        "\n".join(
            [
                f"FROM {output.resolve()}",
                "PARAMETER temperature 0",
                "PARAMETER seed 42",
                "PARAMETER num_predict 64",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["ollama", "create", tag, "-f", str(model_file)], check=True)


def run(arguments: argparse.Namespace) -> dict[str, Any]:
    arguments.merged_dir.mkdir(parents=True, exist_ok=True)
    if not arguments.skip_merge:
        merge_adapter(arguments.adapter, arguments.merged_dir)
    convert_and_quantize(
        arguments.merged_dir,
        arguments.llama_cpp_dir,
        arguments.output,
        arguments.quantization,
    )
    if arguments.ollama_tag:
        create_ollama_model(arguments.output, arguments.ollama_tag)
    report = {
        "adapter": str(arguments.adapter),
        "merged_dir": str(arguments.merged_dir),
        "output": str(arguments.output),
        "quantization": arguments.quantization,
        "size_bytes": arguments.output.stat().st_size,
        "sha256": _sha256(arguments.output),
        "ollama_tag": arguments.ollama_tag,
    }
    report_path = arguments.output.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--merged-dir", type=Path, required=True)
    parser.add_argument("--llama-cpp-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quantization", default="Q4_K_M")
    parser.add_argument("--ollama-tag")
    parser.add_argument("--skip-merge", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))
