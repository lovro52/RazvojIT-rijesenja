from experiments.prepare_dataset import (
    _drop_conflicting_fingerprints,
    grouped_stratified_split,
)


def _row(label, fingerprint, source_row):
    return {
        "label": label,
        "fingerprint": fingerprint,
        "source_file": "data.csv",
        "source_row": source_row,
        "features": {},
    }


def test_duplicate_groups_never_cross_splits():
    rows = []
    for label in ("BENIGN", "DOS"):
        for group in range(10):
            rows.extend(
                [
                    _row(label, f"{label}-{group}", group * 2),
                    _row(label, f"{label}-{group}", group * 2 + 1),
                ]
            )

    splits = grouped_stratified_split(rows, seed=42)
    location = {}
    for split_name, split_rows in splits.items():
        for row in split_rows:
            previous = location.setdefault(row["fingerprint"], split_name)
            assert previous == split_name
    assert all(splits.values())


def test_conflicting_labels_for_same_features_are_removed():
    rows = [_row("BENIGN", "same", 1), _row("DOS", "same", 2)]

    retained, conflicts = _drop_conflicting_fingerprints(rows)

    assert retained == []
    assert conflicts == {"same": ["BENIGN", "DOS"]}
