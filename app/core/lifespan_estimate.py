"""Technique hellénistique/médiévale du Hyleg et de l'Alcocoden (durée de vie) — couche
médiévale uniquement (table fixe d'années planétaires), pas la direction primaire par
ascension oblique. Voir app/reference_data/lifespan_technique.json pour les tables et
l'avertissement de source.

OUTIL DE RECHERCHE/BACKTEST, PAS une fonctionnalité de l'app web grand public (voir
scripts/backtest_lifespan.py) : cette technique produit un chiffre d'années de vie, ce que le
reste de l'app exclut systématiquement pour toute lecture destinée à un utilisateur quelconque
(risque réel qu'un chiffre à l'apparence mathématique soit pris pour une prédiction littérale,
pour soi ou pour le thème de quelqu'un d'autre). Son usage prévu ici est de comparer, pour des
personnages historiques dont la naissance ET la mort sont des faits publics déjà survenus,
l'estimation de la technique à l'âge réel atteint — exactement la démarche de validation que la
source documentaire elle-même illustre (exemple Charlie Chaplin)."""

from __future__ import annotations

from app.core import ephemeris
from app.core.aspects import BodyForAspect, compute_cross_aspects
from app.core.chart_calculator import find_house
from app.core.reference_data import dignities, lifespan_technique, ruler_map
from app.core.root_finding import scan_zero_crossings
from app.core.zodiac import sign_and_degree

# Les 7 planètes classiques au sens de cette technique (le Soleil à Saturne) — exclut les
# planètes modernes (Uranus/Neptune/Pluton), absentes de la table d'années planétaires et de
# toute source ancienne sur ce sujet.
TRADITIONAL_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]

_SYZYGY_SEARCH_WINDOW_DAYS = 40
_SYZYGY_SCAN_STEP_DAYS = 0.5

# Mêmes orbes par défaut que ChartSettings.aspect_orbs (app/schemas.py) : la sélection de
# l'Alcocoden utilise les orbes standards d'un thème natal, pas un orbe "exact" au degré près
# (ce niveau de précision est propre à la direction primaire de la phase 2, non implémentée ici).
_ASPECT_ORBS = {"conjunction": 8, "opposition": 8, "square": 7, "trine": 7, "sextile": 5}


def _longitude(jd_ut: float, planet_id: int) -> float:
    return ephemeris.calc_planet(jd_ut, planet_id).longitude % 360


def _prenatal_syzygy_longitude(birth_jd_ut: float) -> float:
    """Longitude de la Lune à la dernière Nouvelle/Pleine Lune avant la naissance (la
    'sizygie prénatale')."""
    sun_id = ephemeris.PLANET_IDS["Sun"]
    moon_id = ephemeris.PLANET_IDS["Moon"]

    def elongation(jd_ut: float) -> float:
        return (_longitude(jd_ut, moon_id) - _longitude(jd_ut, sun_id)) % 360

    start_jd = birth_jd_ut - _SYZYGY_SEARCH_WINDOW_DAYS
    crossings: list[float] = []
    for target_angle in (0.0, 180.0):

        def signed_offset(jd_ut: float, target=target_angle) -> float:
            return ((elongation(jd_ut) - target + 180) % 360) - 180

        crossings += scan_zero_crossings(signed_offset, start_jd, birth_jd_ut, step=_SYZYGY_SCAN_STEP_DAYS)

    last_syzygy_jd = max(jd for jd in crossings if jd <= birth_jd_ut)
    return _longitude(last_syzygy_jd, moon_id)


def _dignity_score_at(planet_name: str, sign: str, degree_in_sign: float, is_day_chart: bool) -> int:
    """Score de dignité essentielle (0-15) d'une planète donnée EN UN POINT donné du zodiaque
    (pas à la position propre de la planète) — voir dignity_points dans
    lifespan_technique.json."""
    ref = lifespan_technique()
    points = ref["dignity_points"]
    score = 0

    if ruler_map("traditional").get(sign) == planet_name:
        score += points["domicile"]

    exaltation = next((d for d in dignities()["dignities"] if d["planet"] == planet_name), None)
    if exaltation and exaltation["exaltation"] == sign:
        score += points["exaltation"]

    element = ref["sign_elements"][sign]
    triplicity = ref["triplicity_rulers"][element]
    sect_key = "day" if is_day_chart else "night"
    if triplicity[sect_key] == planet_name or triplicity["participating"] == planet_name:
        score += points["triplicity"]

    degree_value = int(degree_in_sign)
    for term_ruler, start, end in ref["egyptian_terms"][sign]:
        if start <= degree_value < end and term_ruler == planet_name:
            score += points["term"]
            break

    decan_index = min(degree_value // 10, 2)
    if ref["decans"][sign][decan_index] == planet_name:
        score += points["decan"]

    return score


def find_hyleg(chart_data: dict, prenatal_syzygy_longitude: float) -> dict | None:
    """Détermine le Hyleg selon la hiérarchie à 4 niveaux (section 1.3 de la source) :
    luminaire de secte -> Part de Fortune -> sizygie prénatale -> Ascendant en dernier
    recours. Retourne {'name', 'longitude', 'sign', 'degree', 'house'} ou None si même
    l'Ascendant n'a pas de maison exploitable (ne devrait jamais arriver)."""
    ref = lifespan_technique()
    hylegiacal_houses = set(ref["hylegiacal_houses"])
    planets_by_name = {p["name"]: p for p in chart_data["planets"]}
    is_day_chart = chart_data["is_day_chart"]

    sect_luminary = "Sun" if is_day_chart else "Moon"
    luminary = planets_by_name.get(sect_luminary)
    if luminary and luminary["house"] in hylegiacal_houses:
        return {
            "name": sect_luminary,
            "longitude": luminary["absolute_longitude"],
            "sign": luminary["sign"],
            "degree": luminary["degree"],
            "house": luminary["house"],
        }

    fortune = next((lot for lot in chart_data.get("lots", []) if lot["name"] == "Fortune"), None)
    if fortune and fortune["house"] in hylegiacal_houses:
        return {
            "name": "Fortune",
            "longitude": fortune["absolute_longitude"],
            "sign": fortune["sign"],
            "degree": fortune["degree"],
            "house": fortune["house"],
        }

    cusps = [h["absolute_longitude"] for h in chart_data["houses"]]
    syzygy_house = find_house(prenatal_syzygy_longitude, cusps)
    if syzygy_house in hylegiacal_houses:
        sign, degree = sign_and_degree(prenatal_syzygy_longitude)
        return {
            "name": "prenatal_syzygy",
            "longitude": prenatal_syzygy_longitude,
            "sign": sign,
            "degree": round(degree, 2),
            "house": syzygy_house,
        }

    ascendant = chart_data["angles"]["ascendant"]
    return {
        "name": "Ascendant",
        "longitude": ascendant["absolute_longitude"],
        "sign": ascendant["sign"],
        "degree": ascendant["degree"],
        "house": 1,
    }


def find_alcocoden(hyleg: dict, chart_data: dict) -> dict | None:
    """Parmi les planètes classiques en aspect ptolémaïque avec le degré exact du Hyleg,
    retourne celle ayant la plus haute dignité essentielle EN CE DEGRÉ (pas à sa propre
    position) — voir section 2. `None` si aucune planète n'aspecte le Hyleg (résultat valide,
    pas une erreur : la source documente ce cas)."""
    ref = lifespan_technique()
    is_day_chart = chart_data["is_day_chart"]
    ptolemaic_types = set(ref["ptolemaic_aspects"])

    hyleg_body = BodyForAspect(name="hyleg", longitude=hyleg["longitude"])
    candidates = [
        BodyForAspect(name=p["name"], longitude=p["absolute_longitude"])
        for p in chart_data["planets"]
        if p["name"] in TRADITIONAL_PLANETS and p["name"] != hyleg["name"]
    ]
    aspects = compute_cross_aspects(
        [hyleg_body],
        candidates,
        orbs=_ASPECT_ORBS,
        include_minor=False,
        include_applying=False,
    )
    aspecting_planets = {a["body_b"] for a in aspects if a["type"] in ptolemaic_types}
    if not aspecting_planets:
        return None

    scored = [
        (planet, _dignity_score_at(planet, hyleg["sign"], hyleg["degree"], is_day_chart))
        for planet in aspecting_planets
    ]
    scored.sort(key=lambda item: (-item[1], TRADITIONAL_PLANETS.index(item[0])))
    best_planet, best_score = scored[0]
    return {"name": best_planet, "dignity_score_at_hyleg": best_score}


def _year_level(alcocoden_name: str, chart_data: dict) -> str:
    """Choix menores/medios/mayores selon l'angularité et la condition zodiacale de
    l'Alcocoden LUI-MÊME (sa propre position natale, pas le degré du Hyleg) — section 4."""
    planet = next(p for p in chart_data["planets"] if p["name"] == alcocoden_name)
    dignity_entry = next(d for d in dignities()["dignities"] if d["planet"] == alcocoden_name)
    in_good_condition = planet["sign"] not in dignity_entry["detriment"] and planet["sign"] != dignity_entry["fall"]

    angular = planet["house"] in (1, 4, 7, 10)
    succedent = planet["house"] in (2, 5, 8, 11)

    if angular and in_good_condition:
        return "major"
    if (angular or succedent) and not in_good_condition:
        return "medium"
    if not angular and not succedent and in_good_condition:  # cadent, bonne condition
        return "medium"
    return "minor"


def _adjust_for_aspects(base_years: float, alcocoden_name: str, chart_data: dict) -> tuple[float, list[dict]]:
    """Ajuste les années de base selon les planètes classiques en aspect ptolémaïque avec
    l'ALCOCODEN (sa position natale réelle, en réutilisant les aspects déjà calculés du thème
    — contrairement au Hyleg, l'Alcocoden est toujours une vraie planète). Simplification
    assumée par rapport à la source (voir docstring du module) : la magnitude ajoutée/
    retranchée est le nombre d'années MINEURES de la planète qui aspecte (jamais de
    fraction en mois/jours, dont la source donne une formule interne incohérente avec son
    propre exemple travaillé), mise à l'échelle par le score de dignité de cette planète à
    SA PROPRE position (0-15, normalisé sur 15)."""
    ref = lifespan_technique()
    is_day_chart = chart_data["is_day_chart"]
    ptolemaic_types = set(ref["ptolemaic_aspects"])
    benefics = set(ref["benefic_planets"])
    malefics = set(ref["malefic_planets"])
    planets_by_name = {p["name"]: p for p in chart_data["planets"]}

    total = base_years
    details = []
    for aspect in chart_data["aspects"]:
        if aspect["type"] not in ptolemaic_types:
            continue
        if alcocoden_name not in (aspect["planet1"], aspect["planet2"]):
            continue
        other = aspect["planet2"] if aspect["planet1"] == alcocoden_name else aspect["planet1"]
        if other not in TRADITIONAL_PLANETS or other == alcocoden_name:
            continue

        sign, degree = planets_by_name[other]["sign"], planets_by_name[other]["degree"]
        own_dignity = _dignity_score_at(other, sign, degree, is_day_chart)
        factor = own_dignity / 15
        minor_years = ref["planetary_years"][other]["minor"]

        delta = None
        if other in benefics:
            delta = minor_years * factor
        elif other in malefics:
            delta = -minor_years * factor

        if delta is not None:
            total += delta
            details.append({"planet": other, "aspect_type": aspect["type"], "delta_years": round(delta, 2)})

    return round(total, 2), details


def estimate_lifespan(chart_data: dict, birth_jd_ut: float) -> dict:
    """Point d'entrée principal : Hyleg -> Alcocoden -> niveau d'années -> ajustements.
    `chart_data` est le dict retourné par `calculate_natal_chart` (déjà calculé) ; `birth_jd_ut`
    est le jour julien UT de naissance (nécessaire pour rechercher la sizygie prénatale, pas
    stocké dans `chart_data`) — voir `ephemeris.local_datetime_to_jd_ut`."""
    ref = lifespan_technique()
    prenatal_syzygy_longitude = _prenatal_syzygy_longitude(birth_jd_ut)

    hyleg = find_hyleg(chart_data, prenatal_syzygy_longitude)
    alcocoden = find_alcocoden(hyleg, chart_data)
    if alcocoden is None:
        return {
            "available": False,
            "hyleg": hyleg,
            "note": "Aucune planète classique n'est en aspect ptolémaïque avec le degré du Hyleg : "
            "cette technique ne donne pas de résultat pour ce thème (résultat valide, voir Valens).",
            "warning": ref["warning"],
        }

    level = _year_level(alcocoden["name"], chart_data)
    base_years = ref["planetary_years"][alcocoden["name"]][level]
    total_years, adjustment_details = _adjust_for_aspects(base_years, alcocoden["name"], chart_data)

    return {
        "available": True,
        "hyleg": hyleg,
        "alcocoden": alcocoden,
        "year_level": level,
        "base_years": base_years,
        "adjustments": adjustment_details,
        "estimated_years": total_years,
        "warning": ref["warning"],
    }
