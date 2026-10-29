"""Deterministic, explainable crop suitability scoring."""
from __future__ import annotations

from typing import Any

FACTOR_WEIGHTS: dict[str, float] = {
    "soil_type": 0.05,
    "season": 0.05,
    "ph": 0.135,
    "nitrogen": 0.09,
    "phosphorus": 0.09,
    "potassium": 0.09,
    "rainfall_mm": 0.18,
    "temperature_c": 0.18,
    "humidity_pct": 0.135,
}
NUMERIC_FACTORS = ("ph", "nitrogen", "phosphorus", "potassium", "rainfall_mm", "temperature_c", "humidity_pct")


def numeric_subscore(value: float, ideal: list[float] | tuple[float, float], tolerable: list[float] | tuple[float, float]) -> tuple[float, str]:
    """Return the 1.0 / 0.5 / 0.0 factor score and a readable status."""
    low, high = ideal
    tol_low, tol_high = tolerable
    if not (tol_low <= low <= high <= tol_high):
        raise ValueError("Expected tolerable range to contain ideal range")
    if low <= value <= high:
        return 1.0, "ideal_match"
    if tol_low <= value <= tol_high:
        return 0.5, "tolerable_match"
    return 0.0, "outside_tolerance"


def score_crop(inputs: dict[str, Any], crop: dict[str, Any]) -> dict[str, Any]:
    """Score one crop and transparently expose missing inputs and factor details."""
    ranges = crop.get("ranges", {})
    known_weight = 0.0
    earned_weight = 0.0
    breakdown = []
    missing = []
    for factor, weight in FACTOR_WEIGHTS.items():
        value = inputs.get(factor)
        if factor in ("soil_type", "season"):
            if value is None:
                missing.append(factor)
                continue
            accepted = crop.get("soil_types" if factor == "soil_type" else "seasons", [])
            subscore = 1.0 if value in accepted else 0.0
            status = "categorical_match" if subscore else "categorical_mismatch"
            breakdown.append({"factor": factor, "input_value": value, "sub_score": subscore, "weighted_contribution": round(weight * subscore * 100, 3), "status": status})
        else:
            if value is None:
                missing.append(factor)
                continue
            profile = ranges.get(factor)
            if not profile:
                missing.append(factor)
                continue
            subscore, status = numeric_subscore(float(value), profile["ideal"], profile["tolerable"])
            breakdown.append({"factor": factor, "input_value": value, "ideal_range": profile["ideal"], "tolerable_range": profile["tolerable"], "sub_score": subscore, "weighted_contribution": round(weight * subscore * 100, 3), "status": status})
        known_weight += weight
        earned_weight += weight * subscore
    score = 0.0 if known_weight == 0 else (earned_weight / known_weight) * 100
    completeness = known_weight * 100
    category = "High" if score >= 75 else "Medium" if score >= 45 else "Low"
    return {
        "crop_name": crop.get("name", "unknown"),
        "score": round(score, 2),
        "category": category,
        "confidence": {
            "completeness_pct": round(completeness, 2),
            "label": "Full input coverage" if completeness >= 99.9 else "Limited input completeness",
            "missing_inputs": missing,
        },
        "factor_breakdown": breakdown,
        "assumptions": list(dict.fromkeys([
            crop.get("data_source_note", "Crop profile data may be approximate."),
            *([f"Missing inputs: {', '.join(missing)}."] if missing else []),
            "Suitability score is a rules-based match, not a probability of yield or success.",
        ])),
    }


def rank_crops(inputs: dict[str, Any], crops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank crops deterministically; crop name resolves score ties."""
    scored = [score_crop(inputs, crop) for crop in crops if crop.get("active", True)]
    return sorted(scored, key=lambda item: (-item["score"], item["crop_name"].casefold()))
