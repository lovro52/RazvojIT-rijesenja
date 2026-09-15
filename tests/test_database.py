from app.services import database


def test_file_upsert_resets_index_state(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "logs.db")
    database.init_db()
    database.save_uploaded_file("logs.csv", "2026-01-01T00:00:00+00:00", 2)
    database.mark_file_indexed("logs.csv")
    database.save_uploaded_file("logs.csv", "2026-01-02T00:00:00+00:00", 3)

    file_record = database.list_uploaded_files()[0]
    assert file_record["rows"] == 3
    assert file_record["indexed"] == 0
    assert file_record["uploaded_at"] == "2026-01-02T00:00:00+00:00"


def test_query_history_keeps_audit_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "logs.db")
    database.init_db()
    database.save_query(
        "question",
        5,
        {"risk_level": "LOW", "summary": "summary"},
        1,
        "2026-01-01T00:00:00+00:00",
        "llama",
        "flow",
        "logs.csv",
        ["logs.csv:incident:0"],
        "flow-incident-v2",
    )

    item = database.get_query_history()[0]
    assert item["model_used"] == "llama"
    assert item["source_file"] == "logs.csv"
    assert item["evidence_ids"] == ["logs.csv:incident:0"]


def test_keyword_search_is_source_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "logs.db")
    database.init_db()
    record = {
        "message": "repeated scan",
        "src_ip": "10.0.0.1",
        "protocol": "TCP",
    }
    database.save_log_records([record], "first.csv")
    database.save_log_records([record], "second.csv")

    results = database.keyword_search("scan", source_file="second.csv")

    assert [item["source_file"] for item in results] == ["second.csv"]
