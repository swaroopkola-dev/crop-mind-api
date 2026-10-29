from enum import Enum
from pydantic import Field, field_validator, model_validator

from app.schemas.common import APIModel


class SoilType(str, Enum):
    sandy = "sandy"
    loamy = "loamy"
    clay = "clay"
    silt = "silt"
    black = "black"
    red = "red"
    alluvial = "alluvial"


class Season(str, Enum):
    kharif = "Kharif"
    rabi = "Rabi"
    zaid = "Zaid"


class RecommendationInput(APIModel):
    soil_type: SoilType
    ph: float = Field(ge=0, le=14)
    nitrogen: float | None = Field(default=None, ge=0, le=500)
    phosphorus: float | None = Field(default=None, ge=0, le=300)
    potassium: float | None = Field(default=None, ge=0, le=500)
    rainfall_mm: float = Field(ge=0, le=5000)
    temperature_c: float = Field(ge=-10, le=60)
    humidity_pct: float = Field(ge=0, le=100)
    season: Season

    @field_validator("ph", "nitrogen", "phosphorus", "potassium", "rainfall_mm", "temperature_c", "humidity_pct")
    @classmethod
    def finite_measurements(cls, value):
        if value is not None and (value != value or value in (float("inf"), float("-inf"))):
            raise ValueError("Measurements must be finite numbers.")
        return value


class RangeSpec(APIModel):
    ideal: tuple[float, float]
    tolerable: tuple[float, float]

    @model_validator(mode="after")
    def validate_order(self):
        low, high = self.tolerable
        ideal_low, ideal_high = self.ideal
        if low > ideal_low or ideal_low > ideal_high or ideal_high > high:
            raise ValueError("Expected tolerable low <= ideal low <= ideal high <= tolerable high.")
        return self


class CropCreate(APIModel):
    name: str = Field(min_length=2, max_length=80)
    ranges: dict[str, RangeSpec]
    soil_types: list[SoilType] = Field(min_length=1)
    seasons: list[Season] = Field(min_length=1)
    data_source_note: str = Field(min_length=10, max_length=1000)
    active: bool = True
    dataset_version: int = Field(default=1, ge=1)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.lower().split())

    @model_validator(mode="after")
    def required_ranges(self):
        required = {"ph", "nitrogen", "phosphorus", "potassium", "rainfall_mm", "temperature_c", "humidity_pct"}
        missing = required.difference(self.ranges)
        if missing:
            raise ValueError(f"Missing crop ranges: {', '.join(sorted(missing))}")
        return self


class ComparisonInput(APIModel):
    inputs: RecommendationInput
    crop_ids: list[str] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def unique_crop_ids(self):
        if len(set(self.crop_ids)) != len(self.crop_ids):
            raise ValueError("crop_ids must be unique.")
        return self
