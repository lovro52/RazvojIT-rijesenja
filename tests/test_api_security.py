from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import logs


@pytest.mark.parametrize("filename", ["../secret.csv", "/tmp/secret.csv", "nested/logs.csv"])
def test_upload_lookup_rejects_paths_outside_upload_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str
):
    monkeypatch.setattr(logs, "UPLOAD_DIR", tmp_path)

    with pytest.raises(HTTPException, match="Neispravan"):
        logs._resolve_upload(filename)


def test_upload_lookup_accepts_plain_filename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(logs, "UPLOAD_DIR", tmp_path)

    assert logs._resolve_upload("logs.csv") == tmp_path / "logs.csv"
