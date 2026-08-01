from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from datetime import time as time_type

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Entrée : données de naissance (cf. cahier des charges, section 4.1)
# ---------------------------------------------------------------------------
class Location(BaseModel):
    city: str | None = None
    country: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class BirthData(BaseModel):
    date: date_type
    time: str | None = None  # "HH:MM:SS", requis si time_known=True
    time_known: bool = True
    timezone: str
    location: Location


class AspectOrbs(BaseModel):
    conjunction: float = 8
    opposition: float = 8
    square: float = 7
    trine: float = 7
    sextile: float = 5
    semi_sextile: float = 2
    semi_square: float = 2
    sesquiquadrate: float = 2
    quincunx: float = 3
    quintile: float = 2


class ChartSettings(BaseModel):
    house_system: str = "placidus"
    zodiac_type: str = "tropical"
    rulership_system: str = "both"
    aspect_orbs: AspectOrbs = Field(default_factory=AspectOrbs)
    include_minor_aspects: bool = True
    optional_points: list[str] = Field(default_factory=lambda: ["north_node", "south_node"])


class ChartCreateRequest(BaseModel):
    birth_data: BirthData
    settings: ChartSettings = Field(default_factory=ChartSettings)
    subject_name: str | None = None
    relationship_to_user: str = "self"


# ---------------------------------------------------------------------------
# Sortie : thème natal calculé (cf. cahier des charges, section 4.2-4.3)
# ---------------------------------------------------------------------------
class PlanetPosition(BaseModel):
    name: str
    sign: str
    sign_fr: str
    degree: float
    absolute_longitude: float
    house: int
    retrograde: bool


class AnglePosition(BaseModel):
    sign: str
    sign_fr: str
    degree: float
    absolute_longitude: float


class Angles(BaseModel):
    ascendant: AnglePosition
    midheaven: AnglePosition
    descendant: AnglePosition
    imum_coeli: AnglePosition


class HouseCusp(BaseModel):
    number: int
    sign: str
    sign_fr: str
    degree: float
    absolute_longitude: float


class Aspect(BaseModel):
    planet1: str
    planet2: str
    type: str
    type_fr: str
    angle: float
    orb: float
    applying: bool


class ElementsBalance(BaseModel):
    fire: int
    earth: int
    air: int
    water: int


class ModalityBalance(BaseModel):
    cardinal: int
    fixed: int
    mutable: int


class Dispositor(BaseModel):
    planet: str
    sign_occupied: str
    rulers: dict[str, str]
    self_disposed: bool


class DispositorChain(BaseModel):
    chain: list[str]
    final_dispositor: str | None
    type: str  # "linear" | "loop"


class MutualReception(BaseModel):
    planets: list[str]
    signs: list[str]
    system: str


class DispositorConvergence(BaseModel):
    final_dispositor_counts: dict[str, int]
    dominant_dispositor: str | None
    dominant_count: int
    total_chains: int
    convergence_ratio: float
    level: str  # "forte" | "notable" | "aucune"


class DispositorsAnalysis(BaseModel):
    dispositors: list[Dispositor]
    dispositor_chains: list[DispositorChain]
    mutual_receptions: list[MutualReception]
    convergence: DispositorConvergence


class NatalChartComputed(BaseModel):
    schema_version: int = 1
    time_known: bool = True
    is_day_chart: bool
    planets: list[PlanetPosition]
    angles: Angles
    houses: list[HouseCusp]
    aspects: list[Aspect]
    elements_balance: ElementsBalance
    modality_balance: ModalityBalance
    dispositors_traditional: DispositorsAnalysis | None = None
    dispositors_modern: DispositorsAnalysis | None = None
    unavailable_points: list[str] = Field(default_factory=list)


class NatalChartResponse(BaseModel):
    id: str
    subject_name: str | None
    relationship_to_user: str
    birth_date: date_type
    birth_time: time_type | None
    birth_time_known: bool
    birth_timezone: str
    birth_city: str | None
    birth_country: str | None
    birth_latitude: float
    birth_longitude: float
    house_system: str
    zodiac_type: str
    rulership_system: str
    computed_chart_data: NatalChartComputed
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Interprétation LLM (cf. cahier des charges, section 4.7)
# ---------------------------------------------------------------------------
class ReadingRequest(BaseModel):
    reading_type: str = "global"  # 'global' | 'love' | 'career' | 'timing' | ...
    focus_areas: list[str] = Field(default_factory=lambda: ["general"])
    level: str = "débutant"
    tone: str = "accessible et bienveillant"
    language: str = "fr"


class ReadingResponse(BaseModel):
    id: str
    natal_chart_id: str
    reading_type: str
    focus_areas: list[str]
    reading_text: str
    model_used: str | None
    tokens_used: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
