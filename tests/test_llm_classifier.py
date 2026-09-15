import json

from app.services.llm_classifier import _parse_classification


def test_classifier_accepts_only_known_schema_values():
    result = _parse_classification(json.dumps({"attack_type": "PORT_SCAN", "risk_level": "HIGH"}))
    assert result.attack_type == "PORT_SCAN"
