from app.services.scoring import numeric_subscore, rank_crops, score_crop


def fake_crop(name="test-crop"):
    return {
        "_id": "abc123",
        "name": name,
        "active": True,
        "soil_types": ["loamy"],
        "seasons": ["Kharif"],
        "ranges": {
            "ph": {"ideal": [6, 7], "tolerable": [5, 8]},
            "nitrogen": {"ideal": [80, 120], "tolerable": [40, 160]},
            "phosphorus": {"ideal": [30, 60], "tolerable": [15, 90]},
            "potassium": {"ideal": [30, 60], "tolerable": [15, 90]},
            "rainfall_mm": {"ideal": [1000, 1800], "tolerable": [500, 2500]},
            "temperature_c": {"ideal": [20, 30], "tolerable": [10, 38]},
            "humidity_pct": {"ideal": [60, 85], "tolerable": [40, 95]},
        },
        "data_source_note": "Test-only synthetic range.",
    }


def inputs():
    return {
        "soil_type": "loamy",
        "season": "Kharif",
        "ph": 6.5,
        "nitrogen": 100,
        "phosphorus": 45,
        "potassium": 45,
        "rainfall_mm": 1400,
        "temperature_c": 25,
        "humidity_pct": 75,
    }


def test_numeric_subscore_ideal_tolerable_and_outside():
    assert numeric_subscore(6.5, (6, 7), (5, 8)) == (1.0, "ideal_match")
    assert numeric_subscore(5.5, (6, 7), (5, 8)) == (0.5, "tolerable_match")
    assert numeric_subscore(4.5, (6, 7), (5, 8)) == (0.0, "outside_tolerance")


def test_full_input_complete_score_and_contributions_sum_to_score():
    result = score_crop(inputs(), fake_crop())
    assert result["score"] == 100
    assert result["confidence"]["completeness_pct"] == 100
    assert sum(f["weighted_contribution"] for f in result["factor_breakdown"]) == 100


def test_missing_nutrients_reduce_completeness_not_score_as_failure():
    data = inputs()
    data["nitrogen"] = data["phosphorus"] = data["potassium"] = None
    result = score_crop(data, fake_crop())
    assert result["score"] == 100
    assert result["confidence"]["completeness_pct"] == 73
    assert set(result["confidence"]["missing_inputs"]) == {
        "nitrogen",
        "phosphorus",
        "potassium",
    }


def test_ranking_ties_are_deterministic_by_name():
    results = rank_crops(inputs(), [fake_crop("Zeta"), fake_crop("alpha")])
    assert [r["crop_name"] for r in results] == ["alpha", "Zeta"]
