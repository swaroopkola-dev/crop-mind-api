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


def numeric_subscore(value: float, ideal: tuple[float, float], tolerable: tuple[float, float]) -> tuple[float, str]:
    ideal_low, ideal_high = ideal
    tol_low, tol_high = tolerable
    if tol_low > ideal_low or ideal_low > ideal_high or ideal_high > tol_high:
        raise ValueError("Invalid crop range configuration.")
    if ideal_low <= value <= ideal_high:
        return 1.0, "ideal_match"
    if tol_low <= value <= tol_high:
        return 0.5, "tolerable_match"
    return 0.0, "outside_tolerance"


def score_crop(inputs: dict[str, Any], crop: dict[str, Any]) -> dict[str, Any]:
    ranges = crop.get("ranges") or {}
    missing: list[str] = []
    factors: list[dict[str, Any]] = []
    known_weight = 0.0
    weighted_sum = 0.0

    for factor in ("soil_type", "season"):
        value = inputs.get(factor)
        if value is None:
            missing.append(factor)
            continue
        accepted = crop.get("soil_types", []) if factor == "soil_type" else crop.get("seasons", [])
        weight = FACTOR_WEIGHTS[factor]
        matched = value in accepted
        score = 1.0 if matched else 0.0
        factors.append({"factor": factor, "input_value": value, "accepted_values": accepted, "ideal_range": None, "tolerable_range": None, "sub_score": score, "weighted_contribution": None, "status": "match" if matched else "mismatch"})
        known_weight += weight
        weighted_sum += weight * score

    for factor in NUMERIC_FACTORS:
        value = inputs.get(factor)
        profile = ranges.get(factor)
        if value is None:
            missing.append(factor)
            continue
        if not profile or "ideal" not in profile or "tolerable" not in profile:
            missing.append(f"crop_profile.{factor}")
            continue
        score, status = numeric_subscore(float(value), tuple(profile["ideal"]), tuple(profile["tolerable"]))
        weight = FACTOR_WEIGHTS[factor]
        factors.append({"factor": factor, "input_value": value, "ideal_range": list(profile["ideal"]), "tolerable_range": list(profile["tolerable"]), "accepted_values": None, "sub_score": score, "weighted_contribution": None, "status": status})
        known_weight += weight
        weighted_sum += weight * score

    if known_weight <= 0:
        raise ValueError("Insufficient known inputs to compute a score.")

    # Reweight known factors back to a 100-point score. Missing factors reduce completeness only.
    for item in factors:
        weight = FACTOR_WEIGHTS[item["factor"]]
        item["weighted_contribution"] = round(100.0 * weight * item["sub_score"] / known_weight, 4)

    score = 100.0 * weighted_sum / known_weight
    completeness = 100.0 * known_weight / sum(FACTOR_WEIGHTS.values())
    category = "High" if score >= 75 else "Medium" if score >= 45 else "Low"
    completeness_label = "High input completeness" if completeness >= 95 else "Moderate input completeness" if completeness >= 80 else "Limited input completeness"
    strengths = [f["factor"] for f in factors if f["status"] in {"ideal_match", "match"}]
    weaknesses = [f["factor"] for f in factors if f["status"] in {"outside_tolerance", "mismatch"}]
    return {
        "crop_id": str(crop.get("_id", crop.get("id", ""))),
        "crop_name": crop.get("name", "Unknown crop"),
        "score": round(score, 4),
        "category": category,
        "confidence": {"completeness_pct": round(completeness, 2), "label": completeness_label, "missing_inputs": missing},
        "factor_breakdown": factors,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "assumptions": [crop.get("data_source_note", "Crop profile source is not documented.")],
        "dataset_version": crop.get("dataset_version", 1),
    }


def rank_crops(inputs: dict[str, Any], crops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = [score_crop(inputs, crop) for crop in crops if crop.get("active", True)]
    return sorted(results, key=lambda result: (-result["score"], result["crop_name"].casefold()))


def fallback_explanation(results: list[dict[str, Any]], missing_inputs: list[str]) -> str:
    if not results:
        return "No active crop profiles are available to compare. Please try again after the dataset is configured."
    top = results[0]
    strengths = ", ".join(top["strengths"][:4]) or "no ideal factor matches"
    weaknesses = ", ".join(top["weaknesses"][:4]) or "no known factor mismatches"
    missing = ", ".join(missing_inputs) if missing_inputs else "none"
    return (f"{top['crop_name'].title()} ranks first in this comparison with a suitability score of "
            f"{top['score']:.1f}/100 ({top['category'].lower()} category). Stronger matches: {strengths}. "
            f"Factors needing attention: {weaknesses}. Missing inputs: {missing}. These results use "
            "approximate crop profiles and are advisory, not a guarantee of yield or success.")
