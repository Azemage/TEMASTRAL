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
    certainty: str | None = None  # lots classiques : fiabilité de l'attribution historique
    construction_logic: str | None = None  # lots modernes non-canoniques : analogie suivie
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
    intensity: int  # 1 à 4 flammes


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
    intensity: int  # 1 à 4 flammes


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
    lots: dict[str, ZodiacalReleasingLotResult]


class SignificatorMatch(BaseModel):
    weight: str  # "très fort" | "fort" | "moyen" | "faible" (libellés bruts de la table de référence)
    meaning: str


class SynastryInterAspect(BaseModel):
    planet_a: str
    planet_b: str
    type: str
    type_fr: str
    orb: float
    significator_matches: list[SignificatorMatch]


class SynastryHouseOverlayEntry(BaseModel):
    planet: str
    house: int
    key_meaning: str | None


class SynastryHouseOverlay(BaseModel):
    a_planets_in_b_houses: list[SynastryHouseOverlayEntry]
    b_planets_in_a_houses: list[SynastryHouseOverlayEntry]


class SynastryCompositePoint(BaseModel):
    sign: str
    sign_fr: str
    degree: float
    absolute_longitude: float


class SynastryCompositeChart(BaseModel):
    points: dict[str, SynastryCompositePoint]
    ascendant: SynastryCompositePoint
    method: str


class SynastryChartsTimeKnown(BaseModel):
    chart_a: bool
    chart_b: bool


class SynastryResponse(BaseModel):
    relationship_mode: str
    chart_a_id: str
    chart_b_id: str
    inter_aspects: list[SynastryInterAspect]
    house_overlay: SynastryHouseOverlay
    composite_chart: SynastryCompositeChart
    charts_time_known: SynastryChartsTimeKnown


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
    reading_type: str = "global"  # 'global' | 'love' | 'career' | 'family' | 'lots' | 'derived_houses' | 'timing' | 'zodiacal_releasing' | 'compatibility' | 'astrocartography' | 'astrocartography_forecast' | 'witchy_calendar' | 'witchy_day_detail' | 'weekly_weather' | 'weekly_weather_by_sign'
    focus_areas: list[str] = Field(default_factory=lambda: ["general"])
    level: str = "débutant"
    tone: str = "accessible et bienveillant"
    language: str = "fr"
    reference_house: int | None = Field(default=None, ge=1, le=12)  # utilisé par 'derived_houses' (repli si relation_key absent)
    relation_key: str | None = None  # utilisé par 'derived_houses' : clé de app/reference_data/derived_house_relations.json (ou 'custom:N1:N2')
    as_of_date: date_type | None = None  # utilisé par 'timing' et 'zodiacal_releasing'
    zr_selected_lots: list[str] = Field(default_factory=list)  # utilisé par 'zodiacal_releasing' ; vide = Fortune + Esprit
    zr_mode: str = "current"  # 'current' | 'predictive' (10 ans) ; utilisé par 'zodiacal_releasing'
    zr_axis_key: str | None = None  # utilisé par 'zodiacal_releasing' en mode 'predictive' : code d'axe de app/reference_data/axes_thematiques_lots.json
    chart_b_id: str | None = None  # utilisé par 'compatibility' : identifiant du second thème
    relationship_mode: str | None = None  # 'romantic' | 'friendship' | 'professional' ; utilisé par 'compatibility'
    timing_horizon: str = "year"  # 'week' | 'month' | 'year' ; utilisé par 'timing'
    astro_map_mode: str = "natal"  # 'natal' | 'transit' ; utilisé par 'astrocartography'
    astro_focus_latitude: float | None = None  # utilisé par 'astrocartography'/'astrocartography_forecast' ; défaut = lieu de naissance du thème
    astro_focus_longitude: float | None = None
    astro_focus_label: str | None = None  # nom du lieu analysé, pour la lecture (ex. "Lisbonne")
    forecast_start_date: date_type | None = None  # utilisé par 'astrocartography_forecast' ; défaut = aujourd'hui
    forecast_years: int = Field(default=10, ge=1, le=10)  # utilisé par 'astrocartography_forecast'
    forecast_threshold_km: float = 300.0  # utilisé par 'astrocartography_forecast'
    witchy_calendar_year: int | None = None  # utilisé par 'witchy_calendar' ; défaut = année en cours
    witchy_day_detail_date: date_type | None = None  # utilisé par 'witchy_day_detail' (mode_detail_journee) ; défaut = aujourd'hui
    weekly_weather_start_date: date_type | None = None  # utilisé par 'weekly_weather'/'weekly_weather_by_sign' ; défaut = aujourd'hui


# ---------------------------------------------------------------------------
# Astrocartographie / Cyclocartographie
# ---------------------------------------------------------------------------
class AstrocartographyLinePoint(BaseModel):
    lat: float
    lon: float


class AstrocartographyLine(BaseModel):
    planet: str
    line_type: str  # 'ASC' | 'DC' | 'MC' | 'IC'
    line_points: list[AstrocartographyLinePoint]


class NatalAstrocartographyResponse(BaseModel):
    natal_chart_id: str
    lines: list[AstrocartographyLine]


class TransitAstrocartographyResponse(BaseModel):
    calculation_date: date_type
    lines: list[AstrocartographyLine]


class NearbyLineMatch(BaseModel):
    planet: str
    line_type: str
    distance_km: float


class NearbyLineCrossing(BaseModel):
    lat: float
    lon: float
    planet_a: str
    line_type_a: str
    planet_b: str
    line_type_b: str
    distance_km: float


class InterestingCity(BaseModel):
    name: str
    country: str
    latitude: float
    longitude: float
    score: float
    nearby_lines: list[NearbyLineMatch]
    nearby_crossings: list[NearbyLineCrossing]


class SavedLocationCreateRequest(BaseModel):
    label: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float
    longitude: float


class LocationForecastWindow(BaseModel):
    planet: str
    line_type: str
    start_date: date_type
    end_date: date_type
    peak_date: date_type
    peak_distance_km: float


class LocationForecastResponse(BaseModel):
    latitude: float
    longitude: float
    start_date: date_type
    end_date: date_type
    threshold_km: float
    windows: list[LocationForecastWindow]


class SavedLocationResponse(BaseModel):
    id: str
    natal_chart_id: str
    label: str | None
    city: str | None
    country: str | None
    latitude: float
    longitude: float
    nearby_lines_analysis: list[NearbyLineMatch] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RatingEntry(BaseModel):
    score: int = Field(ge=1, le=10)
    justification: str


class ReadingResponse(BaseModel):
    id: str
    natal_chart_id: str
    reading_type: str
    focus_areas: list[str]
    reading_text: str
    compatibility_ratings: dict[str, RatingEntry] | None = None
    timing_ratings: dict[str, RatingEntry] | None = None
    model_used: str | None
    tokens_used: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Calendrier ésotérique
# ---------------------------------------------------------------------------
class WitchyCalendarEvent(BaseModel):
    event_date: date_type
    event_type: str  # 'nouvelle_lune' | 'pleine_lune' | 'eclipse_solaire' | 'eclipse_lunaire' | 'station_retrograde' | 'station_directe' | 'ingres' | 'grande_conjonction'
    planet: str | None = None
    sign: str | None = None
    score_brut: float
    score: int = Field(ge=1, le=5)
    meaning_template: str | None = None
    event_longitude: float | None = None  # longitude écliptique exacte de l'événement (0-360°)
    # Champs propres à certains types d'événement uniquement (voir app/core/witchy_calendar.py)
    super_moon: bool | None = None  # lunaisons
    moon_distance_km: int | None = None  # lunaisons
    direction: str | None = None  # stations : 'retrograde' | 'direct'
    from_sign: str | None = None  # ingrès
    direct: bool | None = None  # ingrès : sens du franchissement (direct vs rétrograde)
    planet_b: str | None = None  # grandes conjonctions : seconde planète de la paire
    sign_b: str | None = None  # grandes conjonctions : signe occupé par planet_b
    aspect_type: str | None = None  # grandes conjonctions : 'conjunction' | 'square' | 'opposition'


class WitchyCalendarResponse(BaseModel):
    year: int
    events: list[WitchyCalendarEvent]


# ---------------------------------------------------------------------------
# Météo de la semaine
# ---------------------------------------------------------------------------
class WeeklyWeatherPlanetPosition(BaseModel):
    name: str
    sign: str
    sign_fr: str
    degree: float
    absolute_longitude: float
    retrograde: bool
    date: str | None = None  # présent uniquement pour moon_path (un par jour de la semaine)


class WeeklyWeatherFastPlanet(BaseModel):
    name: str
    sign_start: str
    degree_start: float
    retrograde_start: bool
    sign_end: str
    degree_end: float
    retrograde_end: bool
    ingress: dict | None = None  # {"date","from_sign","to_sign"} si un changement de signe a lieu dans la semaine


class WeeklyWeatherAspect(BaseModel):
    date: str
    planet_a: str
    planet_b: str
    aspect_type: str
    aspect_type_fr: str
    score: int


class WeeklyWeatherHighlight(BaseModel):
    date: str
    kind: str  # 'ingres_lune' | 'ingres_rapide' | 'station' | 'aspect_exact' | 'aspect_generational' | un event_type du calendrier witchy
    planet: str | None = None
    planet_b: str | None = None
    sign: str | None = None
    from_sign: str | None = None
    aspect_type: str | None = None
    aspect_type_fr: str | None = None
    direction: str | None = None
    meaning_template: str | None = None
    score: int


class WeeklyWeatherMainEvent(BaseModel):
    kind: str
    planet: str | None = None
    sign: str


class WeeklyWeatherCombinationLine(BaseModel):
    kind: str  # 'combinaison_editoriale' | 'aspect_rapide_lente' | 'aspect_rapide_rapide' | 'degre_remarquable' | 'position_signe'
    text: str
    date: str | None = None
    planet: str | None = None
    planet_b: str | None = None
    sign: str | None = None
    aspect_type: str | None = None
    aspect_type_fr: str | None = None
    degree_type: str | None = None
    id: str | None = None
    score: int | None = None


class WeeklyWeatherResponse(BaseModel):
    period_start: date_type
    period_end: date_type
    moon_path: list[WeeklyWeatherPlanetPosition]
    moon_ingresses: list[dict]
    fast_planets: list[WeeklyWeatherFastPlanet]
    stations: list[dict]
    witchy_events: list[dict]
    transit_transit_aspects: list[WeeklyWeatherAspect]
    generational_aspects: list[WeeklyWeatherAspect] = []  # rapide (Mercure/Vénus/Mars) -> générationnelle (Jupiter à Pluton, Chiron, axe des Nœuds)
    moon_generational_aspects: list[WeeklyWeatherAspect] = []  # idem, mais Lune -> générationnelle (voir _compute_moon_generational_aspects)
    combination_lines: list[WeeklyWeatherCombinationLine] = []  # bibliothèque de combinaisons hebdomadaires (voir weekly_weather_combinations.py)
    highlights: list[WeeklyWeatherHighlight]
    main_event: WeeklyWeatherMainEvent


class WeeklyWeatherBySignEntry(BaseModel):
    sign: str
    sign_fr: str
    generic_house: int
    house_keyword: str
    house_themes: list[str]
    is_main_event_sign: bool
    score: int = Field(ge=1, le=5)


class WeeklyWeatherBySignResponse(BaseModel):
    main_event_sign: str
    by_sign: list[WeeklyWeatherBySignEntry]


class WeeklyWeatherDomainScore(BaseModel):
    note: int = Field(ge=1, le=5)
    label: str
    top_positive_signal: str | None = None
    top_negative_signal: str | None = None


class WeeklyWeatherDomainScoresResponse(BaseModel):
    period_start: date_type
    period_end: date_type
    scores: dict[str, WeeklyWeatherDomainScore]  # clé = code de life_areas (amour/argent/sante/travail_quotidien)
