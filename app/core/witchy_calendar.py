"""Calendrier ésotérique annuel : détection déterministe des événements astrologiques
collectifs (lunaisons, éclipses, stations rétrogrades, ingrès de planètes lentes, grandes
conjonctions) sur une année civile — voir app/reference_data/witchy_calendar_events.json pour
les poids et gabarits de sens utilisés ensuite par la lecture LLM.

Ce calendrier ne dépend d'AUCUN thème natal : c'est le même pour tout le monde une année
donnée (voir witchy_calendar_service.py pour le cache partagé, même principe que les lignes
de transit de l'astrocartographie). La personnalisation par croisement avec le thème natal
(V2 du document source) est une couche séparée, voir witchy_calendar_personalization.py —
appliquée seulement à la lecture LLM, jamais au calendrier collectif lui-même.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import swisseph as swe

from app.core.day_chart import compute_day_chart
from app.core.ephemeris import CALC_FLAGS, PLANET_IDS
from app.core.reference_data import witchy_calendar_events
from app.core.zodiac import SIGNS, sign_and_degree

# Planètes concernées par les stations rétrogrades et les ingrès (voir le document source :
# le Soleil et la Lune ne sont jamais rétrogrades en géocentrique, donc exclus des stations ;
# seules les planètes "lentes" Jupiter->Pluton comptent pour les ingrès).
STATION_PLANETS = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
SLOW_PLANETS = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

# Seuil de distance Terre-Lune (km) en-deçà duquel une lunaison est considérée "super" —
# heuristique courante (popularisée par R. Nolle) : Nouvelle/Pleine Lune dans les ~10% du
# périgée moyen (~363 300 km), pas une définition astronomique unique et figée.
SUPER_MOON_DISTANCE_KM_THRESHOLD = 360_000
_AU_TO_KM = 149_597_870.7

# Pas d'échantillonnage (jours) pour le balayage préliminaire de chaque type d'événement,
# très inférieur à l'espacement minimal réel entre deux occurrences du même type (~29,5 jours
# pour les lunaisons, plusieurs mois pour les stations/ingrès) : aucune occurrence n'est donc
# manquée entre deux échantillons.
_SCAN_STEP_DAYS = 1.0
_BISECTION_ITERATIONS = 30


def _longitude(jd_ut: float, planet_id: int) -> float:
    (lon, _lat, _dist, _slon, _slat, _sdist), _flag = swe.calc_ut(jd_ut, planet_id, CALC_FLAGS)
    return lon % 360


def _speed_longitude(jd_ut: float, planet_id: int) -> float:
    (_lon, _lat, _dist, slon, _slat, _sdist), _flag = swe.calc_ut(jd_ut, planet_id, CALC_FLAGS)
    return slon


def _distance_km(jd_ut: float, planet_id: int) -> float:
    (_lon, _lat, dist, _slon, _slat, _sdist), _flag = swe.calc_ut(jd_ut, planet_id, CALC_FLAGS)
    return dist * _AU_TO_KM


def _bisect(f, lo: float, hi: float) -> float:
    """Racine de `f` (changement de signe) entre `lo` et `hi`, par bissection."""
    f_lo_negative = f(lo) < 0
    for _ in range(_BISECTION_ITERATIONS):
        mid = (lo + hi) / 2
        if (f(mid) < 0) == f_lo_negative:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _scan_zero_crossings(f, start_jd: float, end_jd: float, step: float = _SCAN_STEP_DAYS) -> list[float]:
    """Jours juliens où `f` change de signe dans [start_jd, end_jd], affinés par bissection."""
    results: list[float] = []
    jd = start_jd
    prev = f(jd)
    while jd < end_jd:
        next_jd = min(jd + step, end_jd)
        curr = f(next_jd)
        if prev == 0:
            results.append(jd)
        elif (prev < 0) != (curr < 0) and abs(curr - prev) < 180:
            # Le "< 180" exclut les discontinuités de rebouclage (ex. offset qui saute de
            # +179° à -180° à l'opposé exact de la cible, pour une fonction construite avec un
            # modulo centré comme les lunaisons) : une vraie racine ne change que d'un pas de
            # jour, jamais de ~360° d'un coup.
            results.append(_bisect(f, jd, next_jd))
        jd = next_jd
        prev = curr
    return results


def _score_from_raw(score_brut: float) -> int:
    """Conversion en note 1-5, voir scoring_formula.conversion_echelle_5 du document source."""
    if score_brut >= 10:
        return 5
    if score_brut >= 8:
        return 4
    if score_brut >= 5:
        return 3
    return 2


@dataclass
class CalendarEvent:
    event_date: str  # ISO YYYY-MM-DD
    event_type: str
    planet: str | None
    sign: str | None
    score_brut: float
    score: int
    details: dict

    def to_dict(self) -> dict:
        return {
            "event_date": self.event_date,
            "event_type": self.event_type,
            "planet": self.planet,
            "sign": self.sign,
            "score_brut": self.score_brut,
            "score": self.score,
            **self.details,
        }


def _jd_to_iso_date(jd_ut: float) -> str:
    year, month, day, _hour = swe.revjul(jd_ut)
    return f"{year:04d}-{month:02d}-{day:02d}"


# ---------------------------------------------------------------------------
# Lunaisons (Nouvelle Lune / Pleine Lune) + super lunes
# ---------------------------------------------------------------------------
def _elongation(jd_ut: float) -> float:
    """Écart angulaire Lune - Soleil, dans [0, 360) : 0 = Nouvelle Lune, 180 = Pleine Lune."""
    return (_longitude(jd_ut, PLANET_IDS["Moon"]) - _longitude(jd_ut, PLANET_IDS["Sun"])) % 360


def _find_lunations(start_jd: float, end_jd: float, target_angle: float) -> list[float]:
    def signed_offset(jd_ut: float) -> float:
        return ((_elongation(jd_ut) - target_angle + 180) % 360) - 180

    return _scan_zero_crossings(signed_offset, start_jd, end_jd)


def compute_lunation_events(start_jd: float, end_jd: float) -> list[dict]:
    catalog = witchy_calendar_events()["event_catalog"]["lunaisons"]
    events: list[dict] = []
    for target_angle, event_type in ((0.0, "nouvelle_lune"), (180.0, "pleine_lune")):
        for jd in _find_lunations(start_jd, end_jd, target_angle):
            moon_lon = _longitude(jd, PLANET_IDS["Moon"])
            sign, _degree = sign_and_degree(moon_lon)
            moon_distance_km = _distance_km(jd, PLANET_IDS["Moon"])
            is_super = moon_distance_km <= SUPER_MOON_DISTANCE_KM_THRESHOLD
            score_brut = catalog["poids_base"] + (2 if is_super else 0)
            events.append(
                CalendarEvent(
                    event_date=_jd_to_iso_date(jd),
                    event_type=event_type,
                    planet="Moon",
                    sign=sign,
                    score_brut=score_brut,
                    score=_score_from_raw(score_brut),
                    details={
                        "meaning_template": catalog["sous_types"][event_type]["meaning_template"],
                        "super_moon": is_super,
                        "moon_distance_km": round(moon_distance_km),
                        "event_longitude": round(moon_lon, 3),
                    },
                ).to_dict()
            )
    return events


# ---------------------------------------------------------------------------
# Éclipses (solaires et lunaires) — fonctions dédiées de swisseph, plus fiables et précises
# qu'une détection manuelle par proximité aux nœuds lunaires.
# ---------------------------------------------------------------------------
def compute_eclipse_events(start_jd: float, end_jd: float) -> list[dict]:
    catalog = witchy_calendar_events()["event_catalog"]["eclipses"]
    events: list[dict] = []

    jd = start_jd
    while jd < end_jd:
        try:
            _flag, tret = swe.sol_eclipse_when_glob(jd, CALC_FLAGS, 0, False)
        except swe.Error:
            break
        eclipse_jd = tret[0]
        if eclipse_jd >= end_jd:
            break
        sun_lon = _longitude(eclipse_jd, PLANET_IDS["Sun"])
        sign, _degree = sign_and_degree(sun_lon)
        score_brut = catalog["poids_base"] + 1  # solaire : +1 par rapport à lunaire (voir catalogue)
        events.append(
            CalendarEvent(
                event_date=_jd_to_iso_date(eclipse_jd),
                event_type="eclipse_solaire",
                planet="Sun",
                sign=sign,
                score_brut=score_brut,
                score=_score_from_raw(score_brut),
                details={
                    "meaning_template": catalog["sous_types"]["eclipse_solaire"]["meaning"],
                    "event_longitude": round(sun_lon, 3),
                },
            ).to_dict()
        )
        jd = eclipse_jd + 1  # reprend la recherche après cette éclipse

    jd = start_jd
    while jd < end_jd:
        try:
            _flag, tret = swe.lun_eclipse_when(jd, CALC_FLAGS, 0, False)
        except swe.Error:
            break
        eclipse_jd = tret[0]
        if eclipse_jd >= end_jd:
            break
        moon_lon = _longitude(eclipse_jd, PLANET_IDS["Moon"])
        sign, _degree = sign_and_degree(moon_lon)
        score_brut = catalog["poids_base"]
        events.append(
            CalendarEvent(
                event_date=_jd_to_iso_date(eclipse_jd),
                event_type="eclipse_lunaire",
                planet="Moon",
                sign=sign,
                score_brut=score_brut,
                score=_score_from_raw(score_brut),
                details={
                    "meaning_template": catalog["sous_types"]["eclipse_lunaire"]["meaning"],
                    "event_longitude": round(moon_lon, 3),
                },
            ).to_dict()
        )
        jd = eclipse_jd + 1

    return events


# ---------------------------------------------------------------------------
# Stations rétrogrades/directes (vitesse apparente = 0)
# ---------------------------------------------------------------------------
_STATION_MODIFIERS = {"Venus": 1, "Mars": 1}  # voir poids_modificateur_par_planete du catalogue


def compute_station_events(start_jd: float, end_jd: float) -> list[dict]:
    catalog = witchy_calendar_events()["event_catalog"]["stations_retrogrades"]
    events: list[dict] = []
    for planet in STATION_PLANETS:
        planet_id = PLANET_IDS[planet]
        for jd in _scan_zero_crossings(lambda t, pid=planet_id: _speed_longitude(t, pid), start_jd, end_jd):
            station_lon = _longitude(jd, planet_id)
            sign, _degree = sign_and_degree(station_lon)
            # Sens de la station : vitesse négative juste après -> devient rétrograde.
            direction = "retrograde" if _speed_longitude(jd + 0.5, planet_id) < 0 else "direct"
            score_brut = catalog["poids_base"] + _STATION_MODIFIERS.get(planet, 0)
            events.append(
                CalendarEvent(
                    event_date=_jd_to_iso_date(jd),
                    event_type="station_retrograde" if direction == "retrograde" else "station_directe",
                    planet=planet,
                    sign=sign,
                    score_brut=score_brut,
                    score=_score_from_raw(score_brut),
                    details={
                        "meaning_template": catalog["meaning_template"],
                        "direction": direction,
                        "event_longitude": round(station_lon, 3),
                    },
                ).to_dict()
            )
    return events


# ---------------------------------------------------------------------------
# Ingrès de planètes lentes (changement de signe, Jupiter -> Pluton)
# ---------------------------------------------------------------------------
_INGRESS_MODIFIERS = {"Saturn": 1, "Uranus": 2, "Neptune": 2, "Pluto": 2}  # voir poids_modificateur du catalogue


def compute_ingress_events(start_jd: float, end_jd: float) -> list[dict]:
    catalog = witchy_calendar_events()["event_catalog"]["ingres_planetes_lentes"]
    events: list[dict] = []
    for planet in SLOW_PLANETS:
        planet_id = PLANET_IDS[planet]
        jd = start_jd
        prev_lon = _longitude(jd, planet_id)
        while jd < end_jd:
            next_jd = min(jd + _SCAN_STEP_DAYS, end_jd)
            curr_lon = _longitude(next_jd, planet_id)
            prev_index = int(prev_lon // 30)
            curr_index = int(curr_lon // 30)
            if prev_index != curr_index:
                # Détermine la frontière (multiple de 30°) franchie, en tenant compte du sens
                # (direct : on entre dans le signe suivant ; rétrograde : on ressort vers le
                # signe précédent) et du passage 360°->0° (Poissons -> Bélier).
                entering_next = curr_index == (prev_index + 1) % 12
                boundary = ((prev_index + 1) % 12) * 30 if entering_next else prev_index * 30

                def f(t, pid=planet_id, b=boundary):
                    return ((_longitude(t, pid) - b + 180) % 360) - 180

                exact_jd = _bisect(f, jd, next_jd)
                event_lon = _longitude(exact_jd, planet_id)
                from_sign, to_sign = SIGNS[prev_index], SIGNS[curr_index]
                score_brut = catalog["poids_base"] + _INGRESS_MODIFIERS.get(planet, 0)
                events.append(
                    CalendarEvent(
                        event_date=_jd_to_iso_date(exact_jd),
                        event_type="ingres",
                        planet=planet,
                        sign=to_sign,
                        score_brut=score_brut,
                        score=_score_from_raw(score_brut),
                        details={
                            "meaning_template": catalog["meaning_template"],
                            "from_sign": from_sign,
                            "direct": entering_next,
                            "event_longitude": round(event_lon, 3),
                        },
                    ).to_dict()
                )
            jd = next_jd
            prev_lon = curr_lon
    return events


# ---------------------------------------------------------------------------
# Grandes conjonctions : aspect majeur exact (conjonction/carré/opposition) entre deux
# planètes lentes — calcul dynamique (pas une liste figée), les dates réelles variant sur des
# décennies selon la paire de planètes.
# ---------------------------------------------------------------------------
SLOW_PLANET_PAIRS = list(combinations(SLOW_PLANETS, 2))
# conjonction = écart de 0° ; opposition = 180° ; carré = 90° OU 270° (montant/descendant),
# les deux comptent comme des carrés à part entière.
_GRAND_CONJUNCTION_TARGETS = {"conjunction": [0.0], "square": [90.0, 270.0], "opposition": [180.0]}


def compute_grand_conjunction_events(start_jd: float, end_jd: float) -> list[dict]:
    catalog = witchy_calendar_events()["event_catalog"]["grandes_conjonctions"]
    events: list[dict] = []
    for planet_a, planet_b in SLOW_PLANET_PAIRS:
        id_a, id_b = PLANET_IDS[planet_a], PLANET_IDS[planet_b]

        def directed_diff(t: float) -> float:
            return (_longitude(t, id_b) - _longitude(t, id_a)) % 360

        for aspect_type, targets in _GRAND_CONJUNCTION_TARGETS.items():
            for target in targets:

                def f(t, tgt=target):
                    return ((directed_diff(t) - tgt + 180) % 360) - 180

                for jd in _scan_zero_crossings(f, start_jd, end_jd):
                    lon_a = _longitude(jd, id_a)
                    lon_b = _longitude(jd, id_b)
                    sign_a, _ = sign_and_degree(lon_a)
                    sign_b, _ = sign_and_degree(lon_b)
                    score_brut = catalog["poids_base"]
                    events.append(
                        CalendarEvent(
                            event_date=_jd_to_iso_date(jd),
                            event_type="grande_conjonction",
                            planet=planet_a,
                            sign=sign_a,
                            score_brut=score_brut,
                            score=_score_from_raw(score_brut),
                            details={
                                "meaning_template": catalog["meaning_template"],
                                "planet_b": planet_b,
                                "sign_b": sign_b,
                                "aspect_type": aspect_type,
                                "event_longitude": round(lon_a, 3),
                            },
                        ).to_dict()
                    )
    return events


def compute_witchy_calendar(year: int) -> list[dict]:
    """Tous les événements du calendrier ésotérique pour l'année civile donnée (1er janvier
    00h UT au 1er janvier suivant), triés chronologiquement. Calcul purement déterministe et
    indépendant de tout thème natal (voir docstring du module) : le même résultat pour tout
    le monde une année donnée."""
    start_jd = swe.julday(year, 1, 1, 0)
    end_jd = swe.julday(year + 1, 1, 1, 0)

    events = (
        compute_lunation_events(start_jd, end_jd)
        + compute_eclipse_events(start_jd, end_jd)
        + compute_station_events(start_jd, end_jd)
        + compute_ingress_events(start_jd, end_jd)
        + compute_grand_conjunction_events(start_jd, end_jd)
    )
    events.sort(key=lambda e: e["event_date"])
    return events


# ---------------------------------------------------------------------------
# location_context : visibilité locale des éclipses — voir note_dependance_geographique du
# document source. Information contextuelle affichée à la lecture (dépend du lieu de
# l'utilisateur), jamais mise en cache dans le calendrier collectif partagé ci-dessus.
# ---------------------------------------------------------------------------
def _eclipse_jd_for_date(event_type: str, event_date: str) -> float | None:
    """Retrouve l'instant exact (jour julien UT) de l'éclipse déjà détectée à `event_date` en
    relançant la même recherche swisseph que compute_eclipse_events, à partir de la veille —
    aucun nouveau moteur, seule l'heure précise (non conservée dans le CalendarEvent) manque."""
    year, month, day = (int(part) for part in event_date.split("-"))
    start_jd = swe.julday(year, month, day, 0) - 1
    try:
        if event_type == "eclipse_solaire":
            _flag, tret = swe.sol_eclipse_when_glob(start_jd, CALC_FLAGS, 0, False)
        elif event_type == "eclipse_lunaire":
            _flag, tret = swe.lun_eclipse_when(start_jd, CALC_FLAGS, 0, False)
        else:
            return None
    except swe.Error:
        return None
    eclipse_jd = tret[0]
    return eclipse_jd if _jd_to_iso_date(eclipse_jd) == event_date else None


def compute_eclipse_local_visibility(event: dict, latitude: float, longitude: float) -> bool | None:
    """Éclipse visible (au moins partiellement) depuis (latitude, longitude) au moment exact de
    l'événement, via les fonctions de circonstances locales de swisseph (sol_eclipse_how /
    lun_eclipse_how : bit de retour à 0 si rien n'est visible depuis cette position). None si
    `event` n'est pas une éclipse ou si l'instant exact n'a pas pu être retrouvé."""
    eclipse_jd = _eclipse_jd_for_date(event["event_type"], event["event_date"])
    if eclipse_jd is None:
        return None
    geopos = (longitude, latitude, 0.0)
    if event["event_type"] == "eclipse_solaire":
        retflags, _attr = swe.sol_eclipse_how(eclipse_jd, geopos, CALC_FLAGS)
    else:
        retflags, _attr = swe.lun_eclipse_how(eclipse_jd, geopos, CALC_FLAGS)
    return retflags != 0


def compute_hemisphere(latitude: float) -> str:
    return "nord" if latitude >= 0 else "sud"


def compute_location_context(event: dict, latitude: float, longitude: float) -> dict | None:
    """`location_context` de l'output_schema du document source, pour un événement et un lieu
    utilisateur donnés — None pour tout événement autre qu'une éclipse (non applicable)."""
    if event["event_type"] not in ("eclipse_solaire", "eclipse_lunaire"):
        return None
    return {
        "hemisphere": compute_hemisphere(latitude),
        "eclipse_visible_locally": compute_eclipse_local_visibility(event, latitude, longitude),
    }


# ---------------------------------------------------------------------------
# enrichissement_contextuel_mode_apercu : 1-2 signaux contextuels forts par événement, calculés
# à partir des inter-aspects transit-transit (pas transit-natal) du jour de l'événement.
# ---------------------------------------------------------------------------
_EVENT_MAIN_ACTORS = {
    "nouvelle_lune": lambda e: {"Sun", "Moon"},
    "pleine_lune": lambda e: {"Sun", "Moon"},
    "eclipse_solaire": lambda e: {"Sun", "Moon"},
    "eclipse_lunaire": lambda e: {"Sun", "Moon"},
    "station_retrograde": lambda e: {e["planet"]},
    "station_directe": lambda e: {e["planet"]},
    "ingres": lambda e: {e["planet"]},
    "grande_conjonction": lambda e: {e["planet"], e["planet_b"]},
}
MAJOR_ASPECT_TYPES = {"conjunction", "sextile", "square", "trine", "opposition"}
CONTEXTUAL_SIGNAL_ORB_THRESHOLD = 2.0
CONTEXTUAL_SIGNAL_MAX_SIGNALS = 2


def compute_contextual_signals(event: dict, day_aspects: list[dict]) -> list[dict]:
    """Signaux contextuels forts du mode aperçu (voir enrichissement_contextuel_mode_apercu du
    document source) : parmi `day_aspects` (déjà calculés pour le jour de l'événement — voir
    app.core.day_chart.compute_day_chart, AUCUN nouveau calcul ici), ne garder que les aspects
    majeurs à orbe serré impliquant un acteur principal de l'événement, en excluant l'aspect
    ENTRE les acteurs principaux eux-mêmes (qui EST l'événement, pas un signal supplémentaire),
    puis ne renvoyer que le(s) plus serré(s) — jamais une liste exhaustive."""
    actors_fn = _EVENT_MAIN_ACTORS.get(event["event_type"])
    if actors_fn is None:
        return []
    actors = actors_fn(event)
    candidates = []
    for aspect in day_aspects:
        if aspect["type"] not in MAJOR_ASPECT_TYPES or aspect["orb"] >= CONTEXTUAL_SIGNAL_ORB_THRESHOLD:
            continue
        p1, p2 = aspect["planet1"], aspect["planet2"]
        involves_actor = p1 in actors or p2 in actors
        both_are_actors = p1 in actors and p2 in actors
        if not involves_actor or both_are_actors:
            continue
        candidates.append(aspect)
    candidates.sort(key=lambda a: a["orb"])
    return candidates[:CONTEXTUAL_SIGNAL_MAX_SIGNALS]


def enrich_events_with_contextual_signals(events: list[dict]) -> list[dict]:
    """Attache `contextual_signals` à chaque événement (mode aperçu). Un seul day_chart calculé
    par date distincte, plusieurs événements pouvant partager la même date (ex. éclipse +
    lunaison, ou deux stations le même jour)."""
    day_aspects_cache: dict[str, list[dict]] = {}
    enriched = []
    for event in events:
        date = event["event_date"]
        if date not in day_aspects_cache:
            day_aspects_cache[date] = compute_day_chart(date)["aspects"]
        signals = compute_contextual_signals(event, day_aspects_cache[date])
        enriched.append({**event, "contextual_signals": signals})
    return enriched
