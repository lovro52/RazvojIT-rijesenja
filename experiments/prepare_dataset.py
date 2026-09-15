from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.feature_schema import (  # noqa: E402
    LLM_FLOW_FEATURES,
    SCHEMA_VERSION,
    canonical_feature_values,
    classifier_messages,
    normalize_attack_label,
    target_response,
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(features: dict[str, float]) -> str:
    normalized = {key: round(float(value), 8) for key, value in features.items()}
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reservoir_rows(
    files: Iterable[Path], max_per_class: int, seed: int, chunksize: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    randomizer = random.Random(seed)
    reservoirs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: Counter[str] = Counter()
    unsupported: Counter[str] = Counter()
    sources = []

    for path in files:
        sources.append(
            {"file": path.name, "size_bytes": path.stat().st_size, "sha256": _file_sha256(path)}
        )
        offset = 0
        for chunk in pd.read_csv(path, chunksize=chunksize, low_memory=False):
            chunk = chunk.rename(columns={str(c): str(c).strip() for c in chunk.columns})
            if "Label" not in chunk.columns:
                raise ValueError(f"{path.name} nema stupac Label.")
            missing = [feature for feature in LLM_FLOW_FEATURES if feature not in chunk.columns]
            if missing:
                raise ValueError(f"{path.name} nema potrebne značajke: {', '.join(missing)}")

            for local_index, raw in chunk.iterrows():
                original_label = str(raw["Label"]).strip()
                label = normalize_attack_label(original_label)
                if label is None:
                    unsupported[original_label] += 1
                    continue
                seen[label] += 1
                features = canonical_feature_values(raw.to_dict())
                row = {
                    "source_file": path.name,
                    "source_row": offset + int(local_index - chunk.index[0]),
                    "label": label,
                    "features": features,
                    "fingerprint": _fingerprint(features),
                }
                reservoir = reservoirs[label]
                if len(reservoir) < max_per_class:
                    reservoir.append(row)
                else:
                    replacement = randomizer.randrange(seen[label])
                    if replacement < max_per_class:
                        reservoir[replacement] = row
            offset += len(chunk)

    rows = [row for label in sorted(reservoirs) for row in reservoirs[label]]
    return rows, {
        "sources": sources,
        "seen_class_counts": dict(sorted(seen.items())),
        "sampled_class_counts": dict(sorted(Counter(row["label"] for row in rows).items())),
        "unsupported_original_labels": dict(unsupported.most_common()),
    }


def _drop_conflicting_fingerprints(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    labels_by_fingerprint: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        labels_by_fingerprint[row["fingerprint"]].add(row["label"])
    conflicts = {
        fingerprint: sorted(labels)
        for fingerprint, labels in labels_by_fingerprint.items()
        if len(labels) > 1
    }
    return [row for row in rows if row["fingerprint"] not in conflicts], conflicts


def grouped_stratified_split(
    rows: list[dict[str, Any]], seed: int = 42
) -> dict[str, list[dict[str, Any]]]:
    """Keep exact feature duplicates in one split while preserving class coverage."""
    randomizer = random.Random(seed)
    by_label: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_label[row["label"]][row["fingerprint"]].append(row)

    splits = {"train": [], "validation": [], "test": []}
    ratios = {"train": 0.8, "validation": 0.1, "test": 0.1}
    for label, grouped in sorted(by_label.items()):
        groups = list(grouped.values())
        randomizer.shuffle(groups)
        assigned = {name: 0 for name in splits}
        if len(groups) >= 3:
            for split_name, group in zip(("train", "validation", "test"), groups[:3], strict=True):
                splits[split_name].extend(group)
                assigned[split_name] += len(group)
            groups = groups[3:]
        for group in groups:
            total = max(sum(assigned.values()) + len(group), 1)
            split_name = max(
                ratios,
                key=lambda name: ratios[name] - assigned[name] / total,
            )
            splits[split_name].extend(group)
            assigned[split_name] += len(group)
        if len(grouped) < 3:
            print(
                f"WARNING: class {label} has only {len(grouped)} unique groups; "
                "it cannot be represented in every split.",
                file=sys.stderr,
            )
    return splits


def _training_record(row: dict[str, Any]) -> dict[str, Any]:
    messages = classifier_messages(row["features"])
    messages.append({"role": "assistant", "content": target_response(row["label"])})
    return {
        "messages": messages,
        "label": row["label"],
        "group_id": row["fingerprint"],
        "source_file": row["source_file"],
        "source_row": row["source_row"],
        "schema_version": SCHEMA_VERSION,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_training_record(row), ensure_ascii=False) + "\n")


def prepare(
    input_dir: Path,
    output_dir: Path,
    pattern: str,
    max_per_class: int,
    seed: int,
    chunksize: int,
    external_dir: Path | None = None,
) -> dict[str, Any]:
    files = sorted(input_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Nema datoteka za uzorak {pattern!r} u {input_dir}.")
    output_dir.mkdir(parents=True, exist_ok=True)

    rows, source_report = _reservoir_rows(files, max_per_class, seed, chunksize)
    sampled_before_conflict_filter = len(rows)
    rows, conflicts = _drop_conflicting_fingerprints(rows)
    splits = grouped_stratified_split(rows, seed)
    for name, split_rows in splits.items():
        _write_jsonl(output_dir / f"{name}.jsonl", split_rows)

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "split_protocol": "label-stratified duplicate-group split 80/10/10",
        "features": LLM_FLOW_FEATURES,
        "max_per_class": max_per_class,
        **source_report,
        "dropped_conflicting_fingerprint_count": len(conflicts),
        "dropped_conflicting_row_count": sampled_before_conflict_filter - len(rows),
        "split_counts": {
            name: dict(sorted(Counter(row["label"] for row in split_rows).items()))
            for name, split_rows in splits.items()
        },
    }

    if external_dir:
        external_files = sorted(external_dir.glob(pattern))
        external_rows, external_report = _reservoir_rows(
            external_files, max_per_class, seed, chunksize
        )
        external_rows, external_conflicts = _drop_conflicting_fingerprints(external_rows)
        _write_jsonl(output_dir / "external_test.jsonl", external_rows)
        report["external_test"] = {
            **external_report,
            "rows": len(external_rows),
            "dropped_conflicting_fingerprint_count": len(external_conflicts),
        }

    (output_dir / "dataset_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/experiments"))
    parser.add_argument("--external-dir", type=Path)
    parser.add_argument("--pattern", default="*.csv")
    parser.add_argument("--max-per-class", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--chunksize", type=int, default=100_000)
    arguments = parser.parse_args()
    result = prepare(**vars(arguments))
    print(json.dumps(result["split_counts"], indent=2))


if __name__ == "__main__":
    main()
