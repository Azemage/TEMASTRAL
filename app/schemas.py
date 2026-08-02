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


class CharacterTraitSource(BaseModel):
    origin: str  # "sun"|"moon"|"ascendant"|"mercury"|"venus"|"mars"|"jupiter"|"saturn"|"dominant_element"|"dominant_modality"
    label: str
    house: int | None
    house_context: str | None
    traits: list[str]


class GenerationalPlacement(BaseModel):
    planet: str  # "Uranus" | "Neptune" | "Pluto"
    sign: str
    sign_fr: str
    house: int
    note: str


class CharacterTraits(BaseModel):
    keywords: list[str]
    dominant_traits: list[str] = Field(default_factory=list)
    sources: list[CharacterTraitSource]
    generational_placements: list[GenerationalPlacement] = Field(default_factory=list)


class LotAspectToNatal(BaseModel):
    planet: str
    type: str
    type_fr: str
    orb: float


class Lot(BaseModel):
    name: str
    name_en: str
    category: str
    signification: str
    formula_used: str
    sign: str
    sign_fr: str
    degree: float
    absolute_longitude: float
    house: int
    aspects_to_natal: list[LotAspectToNatal]


class DerivedHouseMappingEntry(BaseModel):
    derived_house_number: int
    represents_house: int
    keyword: str
    themes: list[str]
    planets: list[str]


class DerivedHouseSet(BaseModel):
    reference_house: int
    mapping: list[DerivedHouseMappingEntry]


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
    character_traits: CharacterTraits
    lots: list[Lot] = Field(default_factory=list)
    derived_houses: list[DerivedHouseSet] = Field(default_factory=list)
    unavailable_points: list[str] = Field(default_factory=list)


class TransitingPlanet(BaseModel):
    name: str
    sign: str
    sign_fr: str
    degree: float
    absolute_longitude: float
    retrograde: bool


class TransitAspect(BaseModel):
    transiting_planet: str
    natal_point: str
    type: str
    type_fr: str
    orb: float
    applying: bool
    favorability: str
    favorability_description: str


class ProfectionResult(BaseModel):
    as_of_date: date_type
    age: int
    profected_house: int
    profected_sign: str
    profected_sign_fr: str
    year_ruler: str
    profected_year_start: date_type
    profected_year_end: date_type


class TimingResponse(BaseModel):
    date: date_type
    transiting_planets: list[TransitingPlanet]
    aspects: list[TransitAspect]
    profection: ProfectionResult


class UpcomingTransitEvent(BaseModel):
    transiting_planet: str
    natal_point: str
    type: str
    type_fr: str
    peak_date: date_type
    peak_orb: float
    window_start: date_type
    window_end: date_type
    favorability: str
    favorability_description: str


class TransitForecastResponse(BaseModel):
    start_date: date_type
    end_date: date_type
    events: list[UpcomingTransitEvent]


class ZodiacalReleasingPeriod(BaseModel):
    level: int
    sign: str
    sign_fr: str
    start_date: date_type
    end_date: date_type
    duration_years: float
    parent_sign: str | None
    is_peak_period: bool
    is_loosing_of_the_bond: bool
    ruling_planet: str


class ZodiacalReleasingLotResult(BaseModel):
    lot_sign: str
    l1_periods: list[ZodiacalReleasingPeriod]
    current_l1: ZodiacalReleasingPeriod | None
    current_l1_l2_periods: list[ZodiacalReleasingPeriod]
    current_l2: ZodiacalReleasingPeriod | None


class ZodiacalReleasingResponse(BaseModel):
    as_of_date: date_type
    edge_case_same_sign_applied: bool
    fortune: ZodiacalReleasingLotResult
    spirit: ZodiacalReleasingLotResult


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
    reading_type: str = "global"  # 'global' | 'love' | 'career' | 'family' | 'lots' | 'derived_houses' | 'timing' | 'zodiacal_releasing'
    focus_areas: list[str] = Field(default_factory=lambda: ["general"])
    level: str = "débutant"
    tone: str = "accessible et bienveillant"
    language: str = "fr"
    reference_house: int | None = Field(default=None, ge=1, le=12)  # utilisé par 'derived_houses'
    as_of_date: date_type | None = None  # utilisé par 'timing'


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
