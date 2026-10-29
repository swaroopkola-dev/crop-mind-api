import pytest
from pydantic import ValidationError

from app.schemas.recommendation import CropCreate, RangeSpec, RecommendationInput


def valid_inputs():
    return {
        "soil_type": "loamy",
        "ph": 6.5,
        "rainfall_mm": 900,
        "temperature_c": 25,
        "humidity_pct": 70,
        "season": "Kharif",
    }


def test_recommendation_allows_missing_npk_as_null():
    payload = RecommendationInput(**valid_inputs())
    assert payload.nitrogen is None
    assert payload.phosphorus is None
    assert payload.potassium is None


def test_recommendation_rejects_out_of_range_ph():
    data = valid_inputs()
    data["ph"] = 15
    with pytest.raises(ValidationError):
        RecommendationInput(**data)


def test_range_validation_rejects_nested_tolerable_range():
    with pytest.raises(ValidationError):
        RangeSpec(ideal=(5, 8), tolerable=(6, 7))


def test_crop_requires_all_numeric_ranges():
    with pytest.raises(ValidationError):
        CropCreate(
            name="test",
            ranges={"ph": {"ideal": [6, 7], "tolerable": [5, 8]}},
            soil_types=["loamy"],
            seasons=["Kharif"],
            data_source_note="test data note",
        )
