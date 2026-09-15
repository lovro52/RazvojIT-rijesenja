import pandas as pd
import pytest

from app.services.baseline import _prepare_features


def test_feature_order_follows_training_metadata():
    dataframe = pd.DataFrame([{"SYN Flag Count": 3, "Flow Duration": 10, "unrelated": 999}])
    values, features, missing = _prepare_features(
        dataframe,
        required_features=["Flow Duration", "SYN Flag Count"],
        strict=True,
    )

    assert features == ["Flow Duration", "SYN Flag Count"]
    assert missing == []
    assert values.tolist() == [[10.0, 3.0]]


def test_missing_trained_feature_is_rejected():
    with pytest.raises(ValueError, match="SYN Flag Count"):
        _prepare_features(
            pd.DataFrame([{"Flow Duration": 10}]),
            required_features=["Flow Duration", "SYN Flag Count"],
            strict=True,
        )
