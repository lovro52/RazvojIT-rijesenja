from app.services.llm_local import _validated_report


def test_report_discards_hallucinated_evidence_ids():
    raw = """```json
    {
      "risk_level": "HIGH",
      "summary": "Povećan broj tokova.",
      "key_indicators": ["flow_count=100"],
      "recommended_actions": ["Provjeri izvor."],
      "evidence_highlights": [
        {"id": "known:1", "reason": "Postoji."},
        {"id": "invented:9", "reason": "Ne postoji."}
      ]
    }
    ```"""

    report, warnings = _validated_report(raw, {"known:1"})

    assert [item["id"] for item in report["evidence_highlights"]] == ["known:1"]
    assert warnings == ["Odbačen je nepostojeći ID dokaza: invented:9"]


def test_invalid_json_becomes_unknown_instead_of_unstructured_output():
    report, warnings = _validated_report("not json", {"known:1"})
    assert report["risk_level"] == "UNKNOWN"
    assert warnings
