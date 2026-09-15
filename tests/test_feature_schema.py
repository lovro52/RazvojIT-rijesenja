import json

from app.core.feature_schema import (
    classifier_messages,
    normalize_attack_label,
    target_response,
)
from experiments.evaluate import _extract_prediction


def test_attack_family_mapping_keeps_heartbleed_separate_from_dos():
    assert normalize_attack_label("Heartbleed") == "HEARTBLEED"
    assert normalize_attack_label("DDoS") == "DDOS"
    assert normalize_attack_label("DoS Hulk") == "DOS"
    assert normalize_attack_label("FTP-Patator") == "BRUTE_FORCE"
    assert normalize_attack_label("Web Attack – XSS") == "WEB_ATTACK"
    assert normalize_attack_label("Brute Force -Web") == "WEB_ATTACK"
    assert normalize_attack_label("DDOS attack-HOIC") == "DDOS"


def test_classifier_prompt_does_not_contain_target_label():
    messages = classifier_messages({"Destination Port": 443})
    user_payload = json.loads(messages[1]["content"])
    assert user_payload["features"]["Destination Port"] == 443
    assert "label" not in user_payload
    assert json.loads(target_response("BENIGN")) == {
        "attack_type": "BENIGN",
        "risk_level": "LOW",
    }


def test_evaluation_rejects_incomplete_json_schema():
    assert _extract_prediction('{"attack_type":"DOS"}', {"DOS"}) is None
    assert _extract_prediction('{"attack_type":"DOS","risk_level":"HIGH"}', {"DOS"}) == "DOS"
