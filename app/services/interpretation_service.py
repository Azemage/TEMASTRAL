"""Génère la lecture rédigée d'un thème via l'API Anthropic, à partir du JSON calculé.

Principe directeur du cahier des charges : le calcul astrologique est déterministe et
codé en dur (jamais délégué au modèle) ; seule la mise en mots — nuancée, pédagogique,
non déterministe — est confiée au LLM. Le modèle reçoit uniquement les données déjà
calculées et ne doit jamais recalculer ou inventer de positions.

Les lectures "basiques" (global/love/career/family) ne reçoivent que le thème natal de
base (planètes, maisons, aspects, dispositeurs, traits). Les lectures spécialisées
(lots, maisons dérivées, timing) reçoivent uniquement les données de leur technique,
avec un système de prompt dédié à cette technique — pas de mélange des deux.
"""

from __future__ import annotations

import json
import re
from datetime import date as date_type
from datetime import timedelta

from anthropic import AsyncAnthropic

from app import models, schemas
from app.config import get_settings
from app.core import ephemeris
from app.core.astrocartography import analyze_nearby_lines
from app.core.astrocartography_personalization import personalize_nearby_lines
from app.core.derived_houses import resolve_relation
from app.core.profections import compute_profection
from app.core.reference_data import astrocartography_significations, houses_meanings, rulerships
from app.core.witchy_calendar import compute_witchy_calendar
from app.core.zodiacal_releasing import FORTUNE_LOT_NAME, SPIRIT_LOT_NAME
from app.services import astrocartography_service, timing_service
from app.services.synastry_service import compute_synastry_for_charts
from app.services.zodiacal_releasing_service import compute_zodiacal_releasing_for_chart

BASIC_READING_TYPES = {"global", "love", "career", "family"}

FOCUS_AREA_GUIDANCE = {
    "general": "vue d'ensemble de la personnalité (Soleil, Lune, Ascendant) et dynamiques dominantes du thème",
    "love": "vie affective et amoureuse (Vénus, Mars, maison VII, aspects vers ces points)",
    "career": "vocation et carrière (Midciel, maison X, Saturne, dispositeur du Midciel)",
    "family": "famille, foyer, racines (Lune, maison IV, maison X selon la tradition retenue)",
}

READING_TYPE_MAX_TOKENS = {
    "global": 4000,
    "love": 2200,
    "career": 2200,
    "family": 2200,
    "lots": 3000,
    "derived_houses": 2400,
    "compatibility": 4500,
}

COMPATIBILITY_MODE_LABELS_FR = {
    "romantic": "relation amoureuse/romantique",
    "friendship": "amitié",
    "professional": "relation professionnelle (collègue, associé, employeur)",
}

# Axes de notation (1 à 10) par mode de relation, affichés comme jauges dans le frontend.
# Choisis pour être spécifiques au mode plutôt qu'un score générique de "compatibilité en %"
# (cf. la mise en garde du document de référence sur la synastrie) : chaque axe cible un
# sous-thème concret que l'utilisateur peut vouloir comparer d'une paire à l'autre.
COMPATIBILITY_RATING_AXES = {
    "romantic": [
        {
            "key": "passion_alchimie",
            "label": "Passion & alchimie",
            "hint": "attraction physique, désir, magnétisme (Vénus-Mars notamment)",
        },
        {
            "key": "complicite_emotionnelle",
            "label": "Complicité émotionnelle",
            "hint": "confort au quotidien, facilité à se comprendre (Lune-Lune, Soleil-Lune)",
        },
        {
            "key": "engagement_duree",
            "label": "Engagement & durabilité",
            "hint": "capacité à construire dans la durée (Saturne-planètes personnelles)",
        },
        {
            "key": "valeurs_partagees",
            "label": "Valeurs partagées",
            "hint": "goûts et vision de vie communs (Vénus-Vénus, Soleil-Soleil)",
        },
    ],
    "friendship": [
        {"key": "complicite_humour", "label": "Complicité & humour", "hint": "communication et humour (Mercure-Mercure)"},
        {"key": "confort_relationnel", "label": "Confort relationnel", "hint": "sentiment de confort général (Soleil-Lune)"},
        {
            "key": "plaisir_partage",
            "label": "Plaisir partagé",
            "hint": "enthousiasme, sentiment d'expansion mutuelle (Jupiter-planètes personnelles)",
        },
        {
            "key": "stimulation_intellectuelle",
            "label": "Stimulation intellectuelle",
            "hint": "ce qui sort de l'ordinaire (Uranus-planètes personnelles)",
        },
    ],
    "professional": [
        {
            "key": "communication_pro",
            "label": "Communication professionnelle",
            "hint": "compréhension mutuelle des idées (Mercure-Mercure)",
        },
        {
            "key": "rigueur_fiabilite",
            "label": "Rigueur & fiabilité partagées",
            "hint": "approche du travail et des responsabilités (Saturne-Saturne)",
        },
        {"key": "rythme_travail", "label": "Rythme de travail", "hint": "cadence, gestion des désaccords (Mars-Mars)"},
        {
            "key": "reconnaissance_croissance",
            "label": "Reconnaissance & croissance mutuelle",
            "hint": "dynamique d'autorité et potentiel de collaboration (Soleil-Saturne, Jupiter-Soleil)",
        },
    ],
}

_RATINGS_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _compatibility_ratings_prompt_section(mode: str) -> str:
    axes = COMPATIBILITY_RATING_AXES.get(mode, [])
    axes_desc = "\n".join(f'- "{axis["key"]}" ({axis["label"]}) : {axis["hint"]}' for axis in axes)
    keys_example = ", ".join(f'"{axis["key"]}": {{"score": <1-10>, "justification": "..."}}' for axis in axes)

    return f"""Termine IMPÉRATIVEMENT ta réponse par un bloc de notation chiffrée, dans ce \
format exact et rien d'autre après ce bloc :

```json
{{"compatibility_ratings": {{{keys_example}}}}}
```

Les axes à noter, un score ENTIER de 1 (très faible) à 10 (très fort) pour chacun :
{axes_desc}

Chaque `justification` est une phrase courte (15-25 mots), concrète, qui s'appuie sur un ou \
deux signaux précis déjà présents dans les données (un aspect, un placement de maison...), pas \
une formule vague ni un simple rappel du score. Ces notes sont une impression interprétative \
de synthèse, pas un calcul scientifique : ne prétends jamais à une précision qu'elles n'ont \
pas, mais assume-les pleinement plutôt que de les noyer sous des réserves."""


def _sanitize_compatibility_ratings(raw_ratings: dict | None, mode: str) -> dict | None:
    expected_keys = {axis["key"] for axis in COMPATIBILITY_RATING_AXES.get(mode, [])}
    return _sanitize_ratings(raw_ratings, expected_keys)


def _extract_ratings_block(reading_text: str, block_key: str) -> tuple[str, dict | None]:
    """Isole le dernier bloc ```json final du texte de la lecture (voir
    `_compatibility_ratings_prompt_section`/`_timing_ratings_prompt_section`) : renvoie le
    texte nettoyé de ce bloc (pour l'affichage en prose) et les notes brutes parsées sous
    `block_key` (ou None si absent/invalide)."""
    matches = list(_RATINGS_JSON_BLOCK_RE.finditer(reading_text))
    if not matches:
        return reading_text, None

    last_match = matches[-1]
    try:
        parsed = json.loads(last_match.group(1))
    except json.JSONDecodeError:
        return reading_text, None

    ratings = parsed.get(block_key) if isinstance(parsed, dict) else None
    if not isinstance(ratings, dict):
        return reading_text, None

    cleaned_text = (reading_text[: last_match.start()] + reading_text[last_match.end() :]).rstrip()
    return cleaned_text, ratings


def _extract_compatibility_ratings(reading_text: str) -> tuple[str, dict | None]:
    return _extract_ratings_block(reading_text, "compatibility_ratings")


# Axes de notation (1 à 10) communs aux trois horizons du PRONOSTIC (semaine/mois/année) :
# des sphères de vie basiques plutôt que des significateurs par horizon, pour rester lisibles
# et comparables d'une lecture à l'autre. Notation générée par le modèle (même mécanisme que
# COMPATIBILITY_RATING_AXES) : cohérence d'identité visuelle sur tout le site plutôt qu'un
# système d'étoiles séparé.
TIMING_RATING_AXES = [
    {"key": "amour", "label": "Amour", "hint": "vie affective et sentimentale"},
    {"key": "amitie", "label": "Amitié", "hint": "relations sociales et amicales"},
    {"key": "professionnel", "label": "Professionnel", "hint": "travail, carrière, projets"},
    {
        "key": "sante",
        "label": "Santé",
        "hint": "tendance d'énergie physique générale — jamais de diagnostic ni de prédiction médicale",
    },
    {
        "key": "developpement_personnel",
        "label": "Développement personnel",
        "hint": "croissance intérieure, apprentissage, introspection",
    },
]

TIMING_HORIZON_LABELS_FR = {
    "week": "la semaine à venir",
    "month": "le mois à venir",
    "year": "les douze prochains mois",
}


def _timing_ratings_prompt_section() -> str:
    axes_desc = "\n".join(f'- "{axis["key"]}" ({axis["label"]}) : {axis["hint"]}' for axis in TIMING_RATING_AXES)
    keys_example = ", ".join(f'"{axis["key"]}": {{"score": <1-10>, "justification": "..."}}' for axis in TIMING_RATING_AXES)

    return f"""Termine IMPÉRATIVEMENT ta réponse par un bloc de notation chiffrée, dans ce \
format exact et rien d'autre après ce bloc :

```json
{{"timing_ratings": {{{keys_example}}}}}
```

Les axes à noter, un score ENTIER de 1 (période calme/difficile sur cet axe) à 10 (période \
très active/favorable sur cet axe) pour chacun, en te basant sur la profection et les transits \
déjà fournis :
{axes_desc}

Chaque `justification` est une phrase courte (15-25 mots) qui s'appuie sur un signal précis \
des données (un transit, la profection...), pas une généralité ni un simple rappel du score. \
Pour l'axe santé, reste impérativement sur une tendance d'énergie générale, jamais un \
diagnostic ou une prédiction médicale. Ces notes sont une impression interprétative de \
synthèse, pas un calcul scientifique : assume-les pleinement plutôt que de les noyer sous des \
réserves."""


def _sanitize_ratings(raw_ratings: dict | None, expected_keys: set[str]) -> dict | None:
    if not raw_ratings:
        return None
    sanitized = {}
    for key, value in raw_ratings.items():
        if key not in expected_keys or not isinstance(value, dict):
            continue
        score = value.get("score")
        if not isinstance(score, int) or not (1 <= score <= 10):
            continue
        justification = value.get("justification")
        sanitized[key] = {"score": score, "justification": str(justification) if justification else ""}
    return sanitized or None


def _extract_timing_ratings(reading_text: str) -> tuple[str, dict | None]:
    return _extract_ratings_block(reading_text, "timing_ratings")


def _sanitize_timing_ratings(raw_ratings: dict | None) -> dict | None:
    return _sanitize_ratings(raw_ratings, {axis["key"] for axis in TIMING_RATING_AXES})

# Nombre d'appels de relance autorisés quand une réponse s'arrête faute de budget de tokens
# (stop_reason == "max_tokens"), pour ne jamais renvoyer une lecture coupée en plein milieu
# d'une phrase à l'utilisateur.
MAX_CONTINUATION_ROUNDS = 2


def _astrocartography_max_tokens(request: schemas.ReadingRequest) -> int:
    """Base généreuse : le nombre de lignes réellement proches du lieu analysé varie
    beaucoup (0 à une dizaine) et n'est connu qu'après calcul, donc pas de dépendance au
    payload comme pour les lots — un budget fixe couvre confortablement le cas le plus riche.
    Relevé par rapport à une lecture générique de lignes : chaque ligne prioritaire est
    maintenant développée avec 3 couches de personnalisation (condition natale, thèmes
    confirmés, pertinence temporelle) plutôt que la seule signification générique."""
    return 4000


def _astrocartography_prompt_block(request: schemas.ReadingRequest) -> str:
    mode = request.astro_map_mode or "natal"
    intro = """Cette lecture porte sur l'ASTROCARTOGRAPHIE, une technique qui projette sur une \
carte du monde les lieux où chaque planète est angulaire (à l'un des 4 angles du thème : \
Ascendant, Descendant, Milieu du Ciel, Fond du Ciel) — vivre ou voyager sur une de ces lignes \
est traditionnellement associé à une activation de cette planète dans le domaine de vie de \
l'angle concerné. Tu reçois dans `focus_location` le lieu analysé (déjà déterminé par calcul \
déterministe, jamais par toi), et dans `nearby_lines` la liste des lignes qui passent à \
proximité de ce lieu (calcul de distance orthodromique déjà effectué), triée du score de \
priorité le plus élevé au plus faible (`priority_score`, calcul déterministe déjà effectué — \
ne le recalcule jamais, ne le cite jamais tel quel dans le texte)."""

    personalization = """CHAQUE ligne de `nearby_lines` est déjà personnalisée pour cette \
personne précise — ne te contente JAMAIS de sa `base_meaning` générique (planète × type de \
ligne, identique pour tout le monde ayant la même ligne) : c'est le point de départ, jamais le \
point d'arrivée. Utilise systématiquement les champs suivants pour nuancer :
- `natal_condition` : l'état de cette planète au thème natal. `dignity` ('domicile'/\
'exaltation' = la planète a les moyens de tenir sa promesse à cet endroit ; 'exil'/'chute' = \
le potentiel existe mais s'exprime avec plus d'efforts ou de maladresse ; 'pérégrin' = ni l'un \
ni l'autre, condition neutre). `aspect_quality` ('favorable' = le potentiel s'active \
facilement ; 'challenging' = une tension ou un prix à payer, à NOMMER explicitement plutôt \
qu'à ignorer, surtout si `friction_with_malefic` est vrai ; 'mixed' = les deux se combinent). \
`retrograde` : si vrai, la ligne peut demander un temps d'adaptation avant de porter ses \
fruits plutôt qu'un effet immédiat.
- `theme_confirme_lie` : si `present` est vrai, cette planète est déjà un pilier identifié de \
l'identité de la personne dans SA lecture natale (voir `reasons` — dispositeur dominant, \
maître de l'Ascendant, stellium). C'est le signal le plus fort de pertinence personnelle : \
ouvre l'interprétation de cette ligne en le mentionnant explicitement plutôt qu'en le glissant \
en fin de paragraphe — vivre sur cette ligne n'active pas juste "une planète", ça active le \
cœur même de son identité telle qu'établie dans son thème.
- `pertinence_temporelle` : si `active` est vrai (voir `reasons` — maître de l'année de \
profection en cours, période de Libération Zodiacale active), signale cette ligne comme une \
FENÊTRE D'ACTUALITÉ pour cette personne EN CE MOMENT précis de sa vie, pas comme un potentiel \
générique valable "un jour". Sans activation, présente-la comme un potentiel de fond durable.

Les lignes sont déjà triées par ordre de priorité décroissant : développe en profondeur les \
3 à 5 premières (celles qui combinent le plus de ces signaux), et résume les suivantes en une \
phrase chacune ou un simple regroupement en fin de lecture — ne traite jamais les 40 lignes \
possibles d'un thème avec la même profondeur, ce serait répétitif et diluerait ce qui compte \
vraiment pour cette personne. Si `nearby_lines` est vide, dis-le simplement plutôt que de \
forcer une interprétation."""

    if mode == "transit":
        scope = """MODE : CYCLOCARTOGRAPHIE (transit). Les lignes reçues reflètent les positions \
planétaires ACTUELLES, pas celles de la naissance — ce sont donc des lignes qui bougent et se \
déplacent avec le temps (rapidement pour la Lune et les planètes personnelles, lentement pour \
les planètes lourdes), à ne jamais présenter comme une caractéristique fixe ou permanente du \
lieu. Cadre-les comme un climat astrologique passager superposé à ce lieu à l'instant présent \
(`as_of_date`), utile pour comprendre une période de voyage ou une fenêtre temporelle précise, \
pas comme une prédiction durable."""
    else:
        scope = """MODE : ASTROCARTOGRAPHIE NATALE. Les lignes reçues sont calculées à partir de \
l'instant de naissance et ne changent jamais : elles représentent un potentiel structurel \
durable associé à ce lieu pour cette personne, à la manière d'un thème natal appliqué à la \
géographie plutôt qu'au temps."""

    guardrails = """Ne transforme jamais une ligne proche en injonction ("vous devez déménager \
ici") ni en verdict absolu ("ce lieu est mauvais pour vous") : présente toujours ces \
dynamiques comme un potentiel activé, à vivre consciemment, ni entièrement positif ni \
entièrement négatif — une ligne de Saturne par exemple n'est pas une malédiction mais une \
invitation à la structure et à l'effort. Ne fais aucune affirmation sur la sécurité, la \
politique, l'économie ou les conditions de vie réelles du lieu : tu n'as aucune donnée sur ces \
sujets, reste strictement sur la dimension symbolique/psychologique de la technique."""

    return f"""{intro}

{personalization}

{scope}

{guardrails}"""


def _select_significant_forecast_windows(windows: list[dict], max_count: int = 25) -> list[dict]:
    """Réduit la liste brute de fenêtres (potentiellement plusieurs centaines sur 10 ans, tous
    planètes/types de ligne confondus) aux plus significatives pour le LLM : les fenêtres où la
    ligne passe le plus près du lieu (`peak_distance_km` la plus faible), puis re-triées
    chronologiquement pour que la lecture suive un déroulé dans le temps plutôt que par ordre
    de proximité."""
    selected = sorted(windows, key=lambda w: w["peak_distance_km"])[:max_count]
    return sorted(selected, key=lambda w: w["start_date"])


def _astrocartography_forecast_max_tokens(request: schemas.ReadingRequest) -> int:
    """Les fenêtres sont déjà réduites aux plus significatives (voir
    _select_significant_forecast_windows) et l'horizon est plafonné à 10 ans côté API : un
    budget fixe généreux couvre confortablement le cas le plus riche."""
    return 4000


def _astrocartography_forecast_prompt_block(request: schemas.ReadingRequest) -> str:
    intro = """Cette lecture porte sur une PRÉVISION CYCLOCARTOGRAPHIQUE PLURIANNUELLE pour un \
LIEU FIXE : contrairement à la lecture d'astrocartographie classique (un instant donné, des \
lignes qui bougent), ici c'est le LIEU qui reste fixe (ex. le domicile de la personne) et on \
regarde, sur `forecast_period` (jusqu'à 10 ans), quelles lignes planétaires de transit viennent \
passer à proximité de ce lieu au fil du temps. Tu reçois dans `focus_location` le lieu analysé, \
dans `forecast_period` la période couverte (`start_date`/`end_date`/`years`/`threshold_km`), et \
dans `forecast_windows` la liste déjà calculée et déjà réduite aux fenêtres les plus \
significatives (triées chronologiquement), chacune avec `planet`, `line_type` (ASC/DC/MC/IC), \
`start_date`/`end_date` (la fenêtre où la ligne reste sous le seuil de distance), `peak_date` \
(le jour de plus grande proximité) et `peak_distance_km`, ainsi qu'une `meaning` de référence."""

    structure = """Structure la lecture de façon CHRONOLOGIQUE, par grandes périodes plutôt que \
fenêtre par fenêtre : quand plusieurs fenêtres se chevauchent ou se suivent de près dans le \
temps (même année, ou planètes différentes actives sur une période commune), regroupe-les en \
une seule période à commenter ensemble — la convergence de plusieurs lignes sur une même \
fenêtre temporelle est justement le signal le plus intéressant, pas un empilement de mentions \
isolées. Ne traite jamais chacune des fenêtres reçues comme un point de lecture séparé et \
égal : priorise les périodes où `peak_distance_km` est la plus faible et où plusieurs planètes \
se recoupent, mentionne les autres plus brièvement."""

    guardrails = """Ce sont des lignes de TRANSIT (cyclocartographie) : un climat astrologique \
passager superposé à ce lieu pendant la fenêtre indiquée, jamais une caractéristique fixe ou \
permanente. Ne formule JAMAIS de prédiction fermée ou datée avec certitude ("il se passera X \
tel jour") : reste toujours en dynamique disponible ("cette période pourrait favoriser...", \
"une tension est susceptible d'émerger autour de..."). Ne transforme jamais une fenêtre proche \
en injonction à voyager ou déménager, ni en verdict absolu sur cette période ("cette année sera \
mauvaise") : présente toujours ces dynamiques comme un potentiel activé, ni entièrement positif \
ni entièrement négatif. Ne fais aucune affirmation sur la sécurité, la politique, l'économie ou \
les conditions de vie réelles du lieu. Si `forecast_windows` est vide, dis-le simplement et \
explique qu'aucune ligne de transit majeure ne vient marquer ce lieu sur la période demandée, \
plutôt que de forcer une interprétation."""

    return f"""{intro}

{structure}

{guardrails}"""


def _witchy_calendar_max_tokens(request: schemas.ReadingRequest) -> int:
    """Une année complète compte typiquement 45-55 événements (lunaisons, éclipses, stations,
    ingrès) ; même à quelques dizaines de tokens chacun (blurb bref voulu, voir le prompt), le
    total reste modeste — un budget fixe généreux couvre confortablement le cas le plus riche."""
    return 6000


def _witchy_calendar_prompt_block(request: schemas.ReadingRequest) -> str:
    intro = """Cette lecture est un CALENDRIER ÉSOTÉRIQUE ANNUEL au ton "witchy" (astrologie \
mondaine + tradition païenne), un calendrier collectif valable pour tout le monde cette \
année-là — PAS une lecture centrée sur le thème natal d'un individu. Tu reçois dans `events` \
la liste déjà calculée et déjà triée chronologiquement de tous les événements de l'année \
(`year`) : lunaisons (Nouvelle/Pleine Lune, avec `super_moon` si applicable), éclipses \
solaires/lunaires, stations rétrogrades/directes de planètes, et ingrès de planètes lentes \
dans un nouveau signe. Chaque événement porte déjà `event_type`, `planet`, `sign` (signe \
occupé au moment de l'événement), `meaning_template` (le sens de référence à partir duquel \
rédiger, jamais à recopier tel quel) et `score` (1 à 5, déjà calculé — ne le recalcule \
jamais et ne cite jamais ce chiffre brut dans le texte, traduis-le en intensité ressentie)."""

    structure = """FORMAT IMPÉRATIF — c'est un calendrier SCANNABLE, pas une lecture \
développée : pour CHAQUE événement, un texte COURT de 1 à 3 phrases maximum, jamais plus. \
Structure la réponse chronologiquement, groupée par mois (## Janvier, ## Février, etc.) pour \
rester lisible sur une année complète. Pour chaque événement, réponds toujours à DEUX \
questions en une phrase ou deux : quelle énergie est à l'œuvre, ET à quoi c'est utile \
concrètement (une intention à poser, un petit rituel, un type d'action ou de recul \
recommandé) — jamais une description purement astronomique sans application pratique. Les \
événements dont `score` est le plus élevé (éclipses, super lunes, ingrès de planètes lentes) \
méritent une phrase de plus que les lunaisons ordinaires ou les stations de Mercure, mais \
aucun événement ne doit dépasser 3 phrases : pour un développement complet d'un événement \
particulier, la personne peut demander une lecture ciblée séparée, ce n'est pas le rôle de ce \
calendrier."""

    guardrails = """Ton évocateur et pratique, cohérent avec le positionnement "witchy" \
(intentions, rituels, symboles), mais jamais fataliste : reformule toujours en tendance ou \
énergie disponible, jamais en certitude ("cette période invite à..." plutôt que "il vous \
arrivera..."). N'invente aucune signification hors de `meaning_template` et du vocabulaire \
symbolique standard du signe occupé : reste sur la dimension symbolique, jamais de prédiction \
factuelle ou anxiogène. Si `events` est vide pour l'année demandée, dis-le simplement."""

    return f"""{intro}

{structure}

{guardrails}"""


_TIMING_MAX_TOKENS_BY_HORIZON = {"week": 2200, "month": 2800, "year": 3500}


def _timing_max_tokens(request: schemas.ReadingRequest) -> int:
    return _TIMING_MAX_TOKENS_BY_HORIZON.get(request.timing_horizon or "year", 3500)


def _zodiacal_releasing_max_tokens(request: schemas.ReadingRequest) -> int:
    """Plus de lots sélectionnés ou mode prévisionnel (frise sur 10 ans, années fortes,
    scénarios croisés) => lecture plus longue, donc plus de budget de tokens que les autres
    lectures spécialisées à un seul sujet."""
    n_lots = len(request.zr_selected_lots) or 2
    tokens = 3000 + 600 * n_lots
    if request.zr_mode == "predictive":
        tokens += 1500
    if request.zr_mode == "predictive" and request.zr_axis_key and request.zr_axis_key in _AXIS_PROMPT_MODULES:
        tokens += 800  # couche 1 (qualification natale) supplémentaire
    return min(tokens, 8000)

_SPECIALIZED_PROMPT_BLOCKS = {
    "lots": """Cette lecture porte spécifiquement sur les LOTS (parts arabes/hermétiques), une \
technique issue de l'astrologie hellénistique. Un lot est un point sensible calculé à partir \
de trois points du thème (le plus souvent l'Ascendant et deux autres points), qui affine la \
lecture d'un domaine de vie précis. Tu reçois la liste des lots déjà calculés (position, \
maison, aspects aux planètes natales) dans `lots`, ainsi qu'un contexte d'identité minimal \
dans `identity`. Pour chaque lot, explique d'abord en une phrase simple ce qu'il représente, \
puis interprète sa position et ses aspects. Chaque lot porte un champ `certainty` (lots \
classiques) ou `construction_logic` (lots modernes non-canoniques) : mentionne brièvement ce \
niveau de fiabilité pour les lots moins bien attestés (`certainty` moyenne, ou modernes), sans \
en faire un sujet central. Priorise Fortune et Esprit (les deux lots fondamentaux), et les \
lots dont un aspect a une orbe serrée (< 3°) : ne traite pas les 17 lots avec la même \
profondeur, ce serait répétitif et diluerait la lecture.""",
}


def _derived_houses_prompt_block(request: schemas.ReadingRequest) -> str:
    """Bloc de prompt pour la lecture des maisons dérivées, adapté à la relation choisie
    (voir maisons_derivees_extension.md section 4) : la maison de référence devient la
    maison 1 (identité) de la personne représentée, sans décalage d'un cran. Le module de
    prompt est injecté selon la relation, sur le même mécanisme que les axes thématiques."""
    intro = """Cette lecture porte spécifiquement sur les MAISONS DÉRIVÉES ('maisons de \
maisons'), une technique qui permet d'analyser une relation (partenaire, mère, associé \
d'affaires...) à partir du seul thème natal du consultant, sans disposer du thème de cette \
personne. Principe : la maison de référence ELLE-MÊME devient la maison 1 (identité) de la \
personne représentée, la maison suivante sa maison 2 (ressources), etc. — pas de décalage \
d'un cran (mapping complet fourni dans `derived_house_mapping`). Commence par expliquer ce \
principe en une phrase accessible."""

    relation_key = request.relation_key
    if not relation_key:
        return f"""{intro} Interprète ce que révèlent les planètes natales présentes dans \
les maisons dérivées les plus occupées, du point de vue de CETTE personne (pas du \
consultant). N'invente jamais qui est cette personne au-delà de ce que la maison de \
référence suggère usuellement (ex. maison 7 = partenaire) ; reste générique ('la personne \
représentée par cette maison')."""

    try:
        relation = resolve_relation(relation_key)
    except KeyError:
        relation = None

    if relation is None:
        return f"""{intro} Interprète ce que révèlent les planètes natales présentes dans \
les maisons dérivées les plus occupées, du point de vue de CETTE personne (pas du \
consultant)."""

    if relation["order"] == "second":
        return f"""{intro}

RELATION ANALYSÉE : {relation["label"]}
MAISON DE RÉFÉRENCE : {relation["reference_house"]} (dérivation de second ordre : \
{relation["path_description"]})

Cette relation est une dérivation de SECOND ORDRE (chaînage de deux dérivations de premier \
ordre) : rappelle explicitement, tôt dans la lecture, le chemin de dérivation utilisé (ex. \
"cette maison représente {relation["path_description"]}") pour que l'utilisateur comprenne \
l'origine de ce point, la technique étant peu intuitive. Analyse en priorité le maître de la \
maison {relation["reference_house"]} (signe, maison de placement, dignité), puis les \
planètes natales déjà présentes dans cette maison.

Angle d'interprétation : reste très général et plus spéculatif que pour une relation de \
premier ordre — ces dérivations de second ordre doivent être présentées avec davantage de \
réserve.

Ne jamais présenter cette lecture comme une description factuelle vérifiable d'une personne \
réelle — il s'agit de la dynamique relationnelle telle que suggérée par le thème natal de \
l'utilisateur, un miroir psychologique plutôt qu'un profil de tiers."""

    prompt = relation["prompt"] or {}
    priority_planets = ", ".join(prompt.get("priority_planets", [])) or "les planètes personnelles"
    angle = prompt.get("angle", "la dynamique relationnelle suggérée par le thème")
    caution = prompt.get("caution")
    caution_block = f"\n{caution}\n" if caution else ""

    return f"""{intro}

RELATION ANALYSÉE : {relation["label"]}
MAISON DE RÉFÉRENCE : {relation["reference_house"]}

Analyse cette relation en suivant cet ordre de priorité :
1. Maître de la maison {relation["reference_house"]} : signe, maison de placement, dignité (voir dignities.json)
2. Planètes natales déjà présentes en maison {relation["reference_house"]}
3. Aspects entre ce maître et {priority_planets}

Angle d'interprétation : {angle}
{caution_block}
Ne jamais présenter cette lecture comme une description factuelle vérifiable d'une personne \
réelle — il s'agit de la dynamique relationnelle telle que suggérée par le thème natal de \
l'utilisateur, un miroir psychologique plutôt qu'un profil de tiers."""


def _timing_prompt_block(request: schemas.ReadingRequest) -> str:
    horizon = request.timing_horizon or "year"
    horizon_label = TIMING_HORIZON_LABELS_FR.get(horizon, horizon)

    intro = f"""Cette lecture porte sur LE PRONOSTIC pour {horizon_label} : la période \
actuelle et son évolution sur cet horizon précis. Tu reçois trois éléments : (1) \
`profection`, la profection annuelle en cours (maison et planète maîtresse de l'année) ; (2) \
`current_transits`, les transits actuels de TOUTES les planètes (Lune, Mercure, Vénus, \
Soleil, Mars compris, pas seulement les lentes) vers le thème natal ; (3) `upcoming_events`, \
les événements de transit pertinents sur cet horizon, chacun avec une date de pic \
(`peak_date`) et une fenêtre active (`window_start`/`window_end`). Chaque aspect porte aussi \
un champ `intensity` (1 à 4) qui reflète déjà son poids (planète, type d'aspect, précision de \
l'orbe) : appuie-toi dessus pour doser l'espace que tu accordes à chacun, mais ne cite jamais \
ce chiffre brut dans le texte — traduis-le en mots."""

    if horizon == "week":
        scope_guidance = """Vise le CONCRET et le PONCTUEL : à cette échelle de temps, les \
transits rapides (notamment lunaires) sont les plus parlants et `upcoming_events` en contient \
volontairement même les mineurs — ne les écarte pas comme négligeables, ce sont eux qui \
donnent la texture quotidienne de la semaine. Structure la lecture par jour ou par petites \
fenêtres plutôt que par grands thèmes abstraits, et ancre chaque point dans une situation \
concrète possible (une conversation, une décision, un imprévu) plutôt qu'une tendance floue."""
    elif horizon == "month":
        scope_guidance = """Vise un équilibre entre grandes tendances et moments concrets : \
identifie 2-3 dynamiques de fond qui traversent le mois, puis situe dedans les moments les \
plus marquants (`upcoming_events`) avec leurs fenêtres de dates. Ni un survol trop abstrait, \
ni un déroulé jour par jour."""
    else:
        scope_guidance = """Vise les GRANDS ARCS qui traversent les douze prochains mois \
plutôt que le détail quotidien : structure la lecture autour des périodes les plus marquantes \
de l'année (fenêtres de plusieurs semaines à plusieurs mois), pas des transits lunaires \
isolés. Le thème de l'année (profection) doit chapeauter cette lecture d'ensemble."""

    structure_note = "un déroulé chronologique des jours/moments clés" if horizon == "week" else (
        "un aperçu chronologique des moments à venir les plus marquants"
    )
    structure = f"""Structure la lecture ainsi : d'abord le thème de la période (profection), \
puis la tendance actuelle (transits en cours, en insistant sur les plus intenses), puis \
{structure_note} en citant leurs fenêtres de dates (pas seulement le jour du pic). Ne fais \
JAMAIS de prédiction fermée ('il vous arrivera X') : formule toujours en dynamique ou thème \
disponible ('cette période favorise...', 'une tension pourrait émerger autour de...')."""

    ratings_section = _timing_ratings_prompt_section()

    return f"""{intro}

{scope_guidance}

{structure}

{ratings_section}"""


def _select_significant_events(events: list[dict], min_count: int = 5, max_count: int = 20) -> list[dict]:
    """Réduit la liste brute d'événements à venir (potentiellement des centaines, la Lune et \
    les autres planètes rapides étant désormais incluses) aux plus significatifs, en \
    s'appuyant sur `intensity` : commence par le seuil le plus strict et l'assouplit tant \
    qu'il n'y a pas assez d'événements à proposer au modèle."""
    candidates = events
    for min_intensity in (4, 3, 2, 1):
        candidates = [e for e in events if e["intensity"] >= min_intensity]
        if len(candidates) >= min_count or min_intensity == 1:
            break
    candidates = sorted(candidates, key=lambda e: (-e["intensity"], e["peak_orb"]))[:max_count]
    return sorted(candidates, key=lambda e: e["peak_date"])


_TIMING_HORIZON_DAYS = {"week": 7, "month": 30, "year": 365}


def _select_events_for_horizon(events: list[dict], horizon: str, as_of_date: date_type, max_count: int = 20) -> list[dict]:
    """Filtre les événements dont la fenêtre active recoupe l'horizon demandé, avec une
    sélection adaptée à l'échelle de temps : sur un an, on privilégie les signaux les plus
    intenses (grands arcs) comme `_select_significant_events` ; sur une semaine, on garde tout
    (y compris les transits lunaires mineurs, qui sont justement ce qui donne la texture
    concrète à cette échelle) ; le mois est un compromis entre les deux."""
    window_end = (as_of_date + timedelta(days=_TIMING_HORIZON_DAYS.get(horizon, 365))).isoformat()
    as_of_iso = as_of_date.isoformat()
    in_window = [e for e in events if e["window_start"] <= window_end and e["window_end"] >= as_of_iso]

    if horizon == "week":
        return sorted(in_window, key=lambda e: e["peak_date"])[:max_count]
    if horizon == "month":
        candidates = [e for e in in_window if e["intensity"] >= 2] or in_window
        candidates = sorted(candidates, key=lambda e: (-e["intensity"], e["peak_orb"]))[:max_count]
        return sorted(candidates, key=lambda e: e["peak_date"])
    return _select_significant_events(in_window, max_count=max_count)


# Modules de prompt par axe thématique de lots (voir prompts_par_axe_thematique.md), pour
# les projections à 10 ans (zr_mode='predictive'). Chaque module qualifie D'ABORD la nature
# de l'axe à partir du thème natal (couche 1, statique) avant de la situer dans le temps via
# la Libération Zodiacale déjà calculée (couche 2, dynamique) — jamais l'inverse. Le cas
# 'vue_complete' (17 lots) n'a volontairement pas de module dédié : il reprend la lecture
# générique déjà en place (convergence multi-lots), pas une qualification par axe.
_AXIS_PROMPT_MODULES = {
    "vocation_reussite": """AXE : Vocation & Réussite

Couche 1 — Avant toute chronologie, détermine la nature de la vocation de cette personne à \
partir de (voir `natal_focal_data`) : signe et maître du Milieu du Ciel, planètes en maison \
10, signe/maison/aspects du lot Esprit, et du lot Victoire. Ne nomme pas un métier précis — \
décris un MODE d'accomplissement (ex. "à travers la transmission et l'enseignement", "à \
travers la construction concrète et durable", "à travers la prise de risque et \
l'innovation").

Couche 2 — Pour chaque période L1/L2 de la Libération Zodiacale (lots Esprit/Victoire/\
Courage/Substance) sur les 10 prochaines années, explique COMMENT le signe actif cette \
période-là vient colorer ce mode d'accomplissement déjà défini en couche 1 — pas comme un \
évènement séparé, mais comme une nuance ou une phase de la même trajectoire.

Signale en particulier :
- Les Libérations du lien (tournants structurels majeurs, changements de direction)
- Les périodes de pointe (moments de concrétisation la plus probable)
- Toute période où plusieurs des lots sélectionnés convergent vers le même signe/la même maison""",
    "famille_racines": """AXE : Famille & Racines

Couche 1 — Détermine la nature du rapport de cette personne à ses racines à partir de (voir \
`natal_focal_data`) : signe/maître/planètes de la maison 4, position et aspects du lot Base, \
et les maisons dérivées pertinentes (`natal_focal_data.derived_houses` : maison 4 → maison 1 \
pour la mère, maison 10 ou 4 → maison 1 pour le père selon la convention retenue). Distingue \
clairement, si les données le permettent, le rapport au père vs à la mère vs à sa propre \
construction familiale future (Enfants/Mariage) — ce sont 3 sous-thèmes liés mais distincts.

Couche 2 — Pour chaque période L1/L2 des lots Base/Père/Mère/Enfants/Mariage sur 10 ans, \
relie le signe actif à une PHASE de ce rapport aux racines (consolidation, remise en \
question, ouverture à une nouvelle structure familiale, etc.) plutôt qu'à un événement \
familial daté et spécifique — reste au niveau de la dynamique, jamais de la prédiction \
factuelle.

MISE EN GARDE IMPÉRATIVE : cet axe touche à des sujets sensibles (deuil, filiation). \
N'émets JAMAIS de prédiction factuelle datée (naissance, décès, rupture) — reste au niveau \
des dynamiques et des invitations à la réflexion.""",
    "corps_circonstances": """AXE : Corps & Circonstances matérielles

Couche 1 — Détermine le rapport de base de cette personne à son corps et aux circonstances \
extérieures à partir de (voir `natal_focal_data`) : signe/maître/dignités de l'Ascendant, \
planètes en maison 1, et position/aspects du lot Fortune (le lot fondamental de la \
tradition, à traiter avec le plus de poids sur cet axe).

Couche 2 — Pour chaque période L1/L2 des lots Fortune/Maladie/Mort/Nécessité sur 10 ans, \
décris des TENDANCES générales de vitalité/stabilité matérielle (période de renforcement, \
période demandant davantage d'attention au corps, période de changement de circonstances) — \
JAMAIS de diagnostic, de pronostic médical, ou de prédiction d'événement grave daté. Rappelle \
systématiquement, si le climat est exigeant sur une période, qu'il s'agit d'un langage \
symbolique et que toute question de santé réelle relève d'un professionnel.

MISE EN GARDE IMPÉRATIVE — LA PLUS STRICTE DE CETTE LECTURE : le lot Mort et cet axe en \
général sont les plus à risque de dérive anxiogène. Ne produis JAMAIS de contenu qui \
pourrait inquiéter inutilement sur la santé ou la mortalité — reformule systématiquement en \
"transformation/renouvellement" plutôt qu'en langage funeste.""",
    "amour_relations": """AXE : Amour & Relations intimes

Couche 1 — Détermine le style amoureux de cette personne à partir de (voir \
`natal_focal_data`) : signe/maison/aspects de Vénus, signe/maître/planètes de la maison 7, \
et position/aspects du lot Éros (et, si disponible, la maison dérivée 7→1 pour qualifier le \
type de partenaire attiré, `natal_focal_data.derived_houses`).

Couche 2 — Pour chaque période L1/L2 des lots Éros/Mariage/Amis sur 10 ans, relie le signe \
actif à une PHASE du style amoureux déjà défini (période d'ouverture, période \
d'approfondissement d'un lien existant, période d'indépendance affective plus marquée) — \
sans jamais promettre une rencontre ou une rupture à date fixe.""",
    "epreuves_resilience": """AXE : Épreuves & Résilience

Couche 1 — Détermine le TYPE de défi récurrent et les ressources de résilience de cette \
personne à partir de (voir `natal_focal_data`) : signe/maison/aspects/dignité de Saturne, \
aspects tendus (carré/opposition) impliquant les planètes personnelles, et position/aspects \
du lot Némésis.

Couche 2 — Pour chaque période L1/L2 des lots Némésis/Nécessité/Courage sur 10 ans, présente \
les périodes non pas comme des "mauvaises années" mais comme des phases où cette dynamique \
de résilience déjà identifiée sera davantage sollicitée — toujours coupler un défi identifié \
à la ressource interne correspondante établie en couche 1, jamais l'un sans l'autre.

MISE EN GARDE : c'est l'axe où le risque de dérive vers un ton fataliste ou anxiogène est le \
plus élevé. Ne formule JAMAIS de langage fataliste ('vous allez souffrir', 'période noire') — \
reste toujours dans le registre de la dynamique et de la ressource mobilisable.""",
    "ouverture_reseau": """AXE : Ouverture & Réseau

Couche 1 — Détermine le mode de connexion sociale/exploratoire de cette personne à partir de \
(voir `natal_focal_data`) : signe/maison/aspects de Mercure, et signe/maître/planètes de la \
maison 11 (et maison 9 si le lot Voyages est sélectionné).

Couche 2 — Pour chaque période L1/L2 des lots Amis/Voyages sur 10 ans, relie le signe actif \
à une phase de ce mode de connexion (période d'expansion du réseau, période de consolidation \
d'amitiés existantes, période propice au mouvement géographique/intellectuel).""",
    "vue_complete": """AXE : Vue complète (17 lots)

Ne développe pas les 17 lots avec la même profondeur — priorise les 2-3 lots (ou petits \
groupes de lots) où les signaux convergent le plus fortement dans le temps (période de \
pointe + déliement du lien + plusieurs lots sur le même signe/la même maison à la fois), \
développe-les en détail, et mentionne les autres brièvement en une ou deux phrases. Il n'y a \
pas de couche de qualification natale dédiée pour ce cas générique : structure-toi \
uniquement sur la convergence temporelle déjà décrite ci-dessus.""",
}

# Axes avec une couche 1 (qualification natale) dédiée, nécessitant les données natales
# complètes dans le payload — 'vue_complete' n'en fait pas partie (voir module ci-dessus).
_AXES_REQUIRING_NATAL_FOCAL_DATA = {
    "vocation_reussite", "famille_racines", "corps_circonstances",
    "amour_relations", "epreuves_resilience", "ouverture_reseau",
}


def _axis_prompt_block(request: schemas.ReadingRequest) -> str:
    if request.zr_mode != "predictive" or not request.zr_axis_key:
        return ""
    return _AXIS_PROMPT_MODULES.get(request.zr_axis_key, "")


def _zodiacal_releasing_prompt_block(request: schemas.ReadingRequest) -> str:
    selected = request.zr_selected_lots or [FORTUNE_LOT_NAME, SPIRIT_LOT_NAME]

    intro = """Cette lecture porte spécifiquement sur la RÉPARTITION ZODIACALE (Zodiacal \
Releasing), une technique de timing hellénistique (Vettius Valens) qui découpe la vie en \
grandes périodes ('périodes L1') elles-mêmes subdivisées en sous-périodes ('périodes L2'). \
Elle est formellement définie pour le lot Fortune (déroulement de la vie matérielle, du \
corps, des circonstances extérieures) et le lot Esprit (déroulement de la vie active, des \
choix, de l'accomplissement) ; son application ici aux autres lots applique le même \
algorithme à un domaine de vie plus spécifique (amour, carrière, famille...) — présente \
alors cette extension comme exploratoire, pas comme une règle classique établie, sans pour \
autant t'excuser ou hésiter à l'utiliser."""

    lots_list = "\n".join(f"- {name}" for name in selected)
    scope = f"""Tu reçois dans `lots` un dictionnaire {{nom du lot : données de phase}} pour \
le ou les lots suivants, sélectionnés par l'utilisateur :
{lots_list}
Chaque entrée précise aussi `signification`, un rappel en une phrase de ce que ce lot \
représente : appuie-toi dessus pour ancrer la lecture dans le bon domaine de vie."""

    multiple_lots = len(selected) > 1

    if multiple_lots:
        depth = """Plusieurs lots sont sélectionnés : NE les traite PAS chacun dans une \
section séparée et cloisonnée façon 'd'abord Fortune, puis Esprit, puis...'. COMPILE-les en \
un seul récit qui avance dans le temps, en précisant à chaque étape quel(s) lot(s) sont \
concernés — c'est en voyant où leurs périodes se recoupent dans le temps que la lecture \
prend tout son sens, pas en les lisant côte à côte sans lien entre elles."""
        cross_lot_guidance = """

Quand plusieurs lots traversent une phase marquante (période de pointe, déliement du lien, \
ou simplement un climat de fond difficile ou faste selon le signe et la planète maîtresse) \
SUR LA MÊME FENÊTRE DE TEMPS, croise explicitement leurs domaines de vie respectifs (via \
`signification`) et propose un ou deux scénarios concrets et plausibles de ce que cette \
convergence pourrait recouvrir dans la vie de la personne. Exemple de raisonnement attendu : \
un lot lié à l'argent en climat tendu EN MÊME TEMPS qu'un lot lié au mariage également tendu \
peut évoquer une tension financière qui pèse sur le couple, une dépense commune difficile, ou \
une décision à deux compliquée par l'argent — ose nommer ce genre de scénario concret plutôt \
que de rester au niveau de l'énergie abstraite. Formule toujours ces hypothèses avec prudence \
('cela peut se traduire par...', 'un scénario possible est...', 'cela peut annoncer...'), \
jamais comme une certitude absolue — mais ne les édulcore pas non plus au point de les rendre \
méconnaissables."""
    else:
        depth = """Un seul lot est sélectionné : consacre-lui une lecture approfondie, sans \
te presser — une plongée détaillée sur ce domaine de vie précis, pas un survol."""
        cross_lot_guidance = ""

    sign_texture = """Pour donner de la texture à chaque période (pas seulement \
'favorable/difficile'), appuie-toi sur ce que représente traditionnellement le SIGNE de la \
période (ex. Cancer : foyer, famille, sécurité affective ; Lion : reconnaissance, créativité, \
enfants ; Balance : relations, partenariats, équilibre ; Scorpion : transformation, intimité, \
pertes/gains profonds — et ainsi de suite selon le signe rencontré) et sur sa planète \
maîtresse (`ruling_planet`), en plus de la `signification` propre du lot. C'est la \
combinaison signe + planète maîtresse + domaine du lot qui doit nourrir tes hypothèses \
concrètes, pas un simple horoscope général du signe."""

    if request.zr_mode == "predictive":
        mode_block = f"""MODE : PRÉVISIONNEL (environ 10 ans). Pour chaque lot, tu reçois \
dans `l1_periods` la liste chronologique complète des périodes L1 sur l'horizon demandé, \
ainsi que `current_l1` pour situer la période en cours dans cette liste.

Construis UNE frise chronologique en langage naturel des grandes périodes à venir sur la \
décennie, en citant les fenêtres de dates (`start_date`/`end_date`) et le signe de chaque \
période. Repère et signale explicitement les ANNÉES FORTES de cette décennie : les moments où \
plusieurs signaux convergent en même temps — changement de période L1 (bascule de thème de \
vie dans ce domaine), période(s) `is_peak_period` active(s) (sommet d'activité/d'enjeu), \
`is_loosing_of_the_bond` (tournant net, changement de trajectoire){" sur un ou plusieurs lots à la fois" if multiple_lots else ""}. \
Plus les signaux se superposent dans le temps, plus le moment mérite d'être mis en avant \
comme une année charnière et développé en conséquence ; à l'inverse, résume en une phrase les \
périodes plus calmes ou sans convergence particulière, sans t'y attarder.{cross_lot_guidance}

{sign_texture} Ne donne jamais une date comme une prédiction fermée d'un événement précis : \
parle de fenêtres propices à tel type de dynamique ou de thème de vie, jamais d'un événement \
certain qui \"arrivera\"."""
    else:
        mode_block = f"""MODE : ACTUEL. Pour chaque lot, tu reçois `current_l1` (la période en \
cours, plusieurs années), `current_l1_l2_periods` (sa subdivision complète en sous-périodes \
L2 de quelques mois chacune) et `current_l2` (la sous-période en cours). Explique d'abord le \
climat général de la période L1 en cours, puis précise ce que la sous-période L2 actuelle \
vient nuancer ou affiner par rapport à ce climat général.{cross_lot_guidance}

{sign_texture}"""

    badges = """Deux indicateurs accompagnent chaque période : `is_peak_period` (période 'de \
pointe', angulaire par rapport au signe parent — un sommet d'activité ou d'enjeu dans le \
domaine du lot) et `is_loosing_of_the_bond` ('déliement du lien' — un changement de \
trajectoire marqué, souvent vécu comme une rupture ou un tournant net). Si l'un des deux est \
vrai pour une période évoquée, signale-le explicitement comme un moment charnière."""

    axis_block = _axis_prompt_block(request)
    axis_section = f"\n\n{axis_block}\n\nLa couche 1 ci-dessus PRÉCÈDE et ENCADRE tout ce qui suit : qualifie-la avant d'aborder la chronologie." if axis_block else ""

    return f"""{intro}

{scope}
{axis_section}

{depth}

{mode_block}

{badges}

Donne toujours les fenêtres de dates (début/fin) pour situer temporellement chaque période \
évoquée. Ne fais jamais de prédiction fermée sur un événement précis et daté avec certitude : \
mais entre l'abstraction pure et la certitude, il y a un juste milieu concret que cette \
lecture doit viser — nomme des thèmes de vie et des scénarios plausibles, pas seulement des \
'dynamiques' et des 'tonalités'."""


def _compatibility_prompt_block(request: schemas.ReadingRequest) -> str:
    mode = request.relationship_mode or "romantic"
    mode_label = COMPATIBILITY_MODE_LABELS_FR.get(mode, mode)

    intro = f"""Cette lecture porte sur la COMPATIBILITÉ entre deux personnes (synastrie), \
dans le contexte d'une {mode_label} — garde ce contexte présent à l'esprit du début à la fin : \
les significateurs et les enjeux qui comptent changent radicalement selon qu'il s'agit d'un \
couple, d'une amitié ou d'une collaboration professionnelle. Elle s'appuie sur trois \
techniques complémentaires, toutes déjà calculées dans les données reçues :

1. `inter_aspects` : les aspects entre les planètes de la personne A (`planet_a`) et celles \
de la personne B (`planet_b`) — jamais entre deux planètes d'une même personne. Chaque aspect \
porte une liste `significator_matches` (peut être vide) : les couples de planètes reconnus \
comme particulièrement significatifs pour ce type de relation, avec leur poids ('très fort' à \
'faible') et leur signification déjà rédigée. La liste est déjà triée par poids décroissant \
puis par orbe la plus serrée : développe en priorité les premiers éléments, traite les \
suivants plus rapidement ou groupe-les ; les aspects sans `significator_matches` sont \
secondaires, à ne mentionner que s'ils viennent nuancer ou renforcer un point déjà établi.
2. `house_overlay` : dans quelle maison de l'autre thème tombe chaque planète \
(`a_planets_in_b_houses` et `b_planets_in_a_houses`), avec un `key_meaning` déjà renseigné \
quand ce placement est particulièrement significatif pour ce mode de relation (sinon `null` \
— reste alors secondaire). Sers-toi de `reference.houses_meanings` pour les maisons sans \
`key_meaning` mais qui reviennent avec plusieurs planètes.
3. `composite_chart` : un thème unique représentant la relation elle-même comme une entité \
(point médian de chaque paire de planètes homologues), dans `points` (par planète) et \
`ascendant`. Décrit 'à quoi ressemble ce duo vu de l'extérieur', en complément des deux \
techniques précédentes qui décrivent plutôt comment A et B interagissent individuellement."""

    time_known_note = """Vérifie `charts_time_known` : si `chart_a` ou `chart_b` est `false`, \
l'heure de naissance de cette personne est inconnue — précise que le `house_overlay` et \
l'Ascendant composite sont alors approximatifs pour elle, mais que les `inter_aspects` restent \
pleinement fiables (ils ne dépendent pas de l'heure)."""

    structure = """Structure la lecture ainsi : (1) une vue d'ensemble de la dynamique \
relationnelle en 2-3 phrases ; (2) le détail des inter-aspects les plus significatifs, \
organisés par thème plutôt que comme une liste plate (ex. regrouper ce qui touche à \
l'alchimie/l'attraction, puis ce qui touche à la communication, puis à l'engagement/la durée, \
selon ce que les données font ressortir) ; (3) ce que révèle le chevauchement de maisons sur \
la sphère de vie où chacun s'insère chez l'autre ; (4) le thème composite comme portrait de la \
relation elle-même ; (5) une section finale 'Points de vigilance et recommandations' qui nomme \
explicitement les frictions ou déséquilibres les plus significatifs (notamment tout aspect \
tendu impliquant Saturne : à la fois source de friction ET indicateur de longévité potentielle \
si bien géré) et propose des recommandations concrètes et actionnables pour composer avec — \
jamais un simple 'communiquez bien', mais quelque chose d'ancré dans les signaux relevés plus \
haut."""

    ethics = """RÈGLES SPÉCIFIQUES À CETTE LECTURE : ne rends jamais un verdict fermé sur la \
réussite ou l'échec de la relation ('vous êtes faits l'un pour l'autre' / 'ça ne marchera \
jamais') : les inter-aspects décrivent des dynamiques à vivre et à travailler, pas un destin. \
Ne porte aucun jugement de valeur sur la personne B (qui ne lit pas cette lecture) au-delà de \
ce que les données astrologiques appuient directement ; adresse-toi à la personne A comme \
consultante, en parlant de la relation et de ce qu'elle peut en faire, jamais comme si tu \
jugeais B dans l'absolu. N'invente aucun fait biographique sur B."""

    ratings_section = _compatibility_ratings_prompt_section(mode)

    return f"""{intro}

{time_known_note}

{structure}

{ethics}

{ratings_section}"""


def _basic_chart_data(chart_data: dict) -> dict:
    """Sous-ensemble du thème calculé pour les lectures basiques : pas de lots ni de
    maisons dérivées, qui ont leurs propres lectures dédiées."""
    excluded = {"lots", "derived_houses"}
    return {key: value for key, value in chart_data.items() if key not in excluded}


def _identity_context(chart_data: dict) -> dict:
    sun = next(p for p in chart_data["planets"] if p["name"] == "Sun")
    moon = next(p for p in chart_data["planets"] if p["name"] == "Moon")
    return {
        "sun": {"sign": sun["sign"], "degree": sun["degree"]},
        "moon": {"sign": moon["sign"], "degree": moon["degree"]},
        "ascendant": {"sign": chart_data["angles"]["ascendant"]["sign"], "degree": chart_data["angles"]["ascendant"]["degree"]},
        "is_day_chart": chart_data["is_day_chart"],
    }


_LANGUAGE_NAMES = {"fr": "français", "en": "anglais (English)", "es": "espagnol (español)"}


def _build_system_prompt(request: schemas.ReadingRequest) -> str:
    language_name = _LANGUAGE_NAMES.get(request.language, request.language)
    base = f"""Tu es un astrologue professionnel, expérimenté et bienveillant, qui rédige des \
lectures de thème natal en {language_name}. Rédige INTÉGRALEMENT ta réponse dans cette langue \
(y compris les titres de section), même si ces instructions te sont données en français.

RÈGLES IMPÉRATIVES :
1. Tu reçois dans le message utilisateur un JSON contenant les données déjà calculées \
nécessaires à cette lecture. Tu ne dois JAMAIS recalculer, corriger, ou inventer une \
position astrologique : appuie-toi exclusivement sur les données fournies.
2. N'affiche aucun JSON ni tableau de données brutes dans ta réponse : rédige un texte \
en langage naturel, fluide et structuré avec des titres.
3. Adopte un ton {request.tone}, adapté à un niveau {request.level}. Évite le jargon \
non expliqué ; quand tu introduis un terme technique, explique-le brièvement.
4. Ne formule jamais de prédiction déterministe ou anxiogène (notamment sur la santé \
ou la mort) : reformule toujours en dynamique psychologique ou en tendance nuancée.
5. Structure la lecture avec des sections Markdown (##).
6. Sois CONCRET, pas abstrait. Pour chaque trait ou dynamique évoqué, donne un exemple \
tangible de comportement, de réaction ou de situation de la vie quotidienne (travail, \
relations, décisions, habitudes) plutôt qu'une description théorique de "l'énergie" ou \
du "potentiel" de la planète. Bannis les formulations vagues type "cela peut se \
manifester de plusieurs façons" sans préciser comment. Préfère toujours une phrase \
illustrée ("vous avez probablement du mal à lâcher prise sur un projet avant qu'il soit \
parfait") à une phrase générique ("vous avez un fort besoin de perfection")."""

    if request.reading_type in BASIC_READING_TYPES:
        focus_descriptions = "\n".join(
            f"- {area} : {FOCUS_AREA_GUIDANCE.get(area, area)}" for area in request.focus_areas
        )
        return f"""{base}
7. Regarde le champ `convergence` de `dispositors_traditional` et `dispositors_modern` dans \
les données. Si son `level` vaut 'forte' ou 'notable', la majorité des chaînes de \
dispositeurs du thème se referment sur une même planète (`dominant_dispositor`) : \
signale explicitement ce pattern comme une planète clé de voûte du thème.

ZONES À COUVRIR DANS CETTE LECTURE :
{focus_descriptions}

Termine toujours par un court paragraphe de synthèse bienveillant et encourageant."""

    if request.reading_type == "zodiacal_releasing":
        specialized_block = _zodiacal_releasing_prompt_block(request)
    elif request.reading_type == "compatibility":
        specialized_block = _compatibility_prompt_block(request)
    elif request.reading_type == "timing":
        specialized_block = _timing_prompt_block(request)
    elif request.reading_type == "derived_houses":
        specialized_block = _derived_houses_prompt_block(request)
    elif request.reading_type == "astrocartography":
        specialized_block = _astrocartography_prompt_block(request)
    elif request.reading_type == "astrocartography_forecast":
        specialized_block = _astrocartography_forecast_prompt_block(request)
    elif request.reading_type == "witchy_calendar":
        specialized_block = _witchy_calendar_prompt_block(request)
    else:
        specialized_block = _SPECIALIZED_PROMPT_BLOCKS[request.reading_type]
    return f"""{base}

{specialized_block}

Termine toujours par un court paragraphe de synthèse bienveillant et encourageant."""


def _build_user_payload(
    chart: models.NatalChart, request: schemas.ReadingRequest, chart_b: models.NatalChart | None = None
) -> dict:
    payload = {
        "request_type": f"{request.reading_type}_reading",
        "subject": {
            "name": chart.subject_name,
            "relationship_to_user": chart.relationship_to_user,
            "birth_date": chart.birth_date.isoformat(),
            "birth_time_known": chart.birth_time_known,
            "birth_city": chart.birth_city,
            "birth_country": chart.birth_country,
        },
        "user_context": {"level": request.level, "language": request.language, "tone": request.tone},
    }

    chart_data = chart.computed_chart_data

    if request.reading_type in BASIC_READING_TYPES:
        payload["focus_areas"] = request.focus_areas
        payload["settings"] = {
            "house_system": chart.house_system,
            "zodiac_type": chart.zodiac_type,
            "rulership_system": chart.rulership_system,
        }
        payload["chart_data"] = _basic_chart_data(chart_data)
        payload["reference"] = {
            "houses_meanings": houses_meanings()["houses"],
            "rulerships_notes": rulerships()["notes"],
        }
    elif request.reading_type == "lots":
        payload["identity"] = _identity_context(chart_data)
        payload["lots"] = chart_data["lots"]
    elif request.reading_type == "derived_houses":
        relation = None
        if request.relation_key:
            try:
                relation = resolve_relation(request.relation_key)
            except KeyError:
                relation = None
        reference_house = relation["reference_house"] if relation else (request.reference_house or 7)
        mapping = next(d for d in chart_data["derived_houses"] if d["reference_house"] == reference_house)
        payload["identity"] = _identity_context(chart_data)
        payload["reference_house"] = reference_house
        if relation:
            payload["relation"] = {"key": relation["relation_key"], "label": relation["label"]}
            if relation["path_description"]:
                payload["relation"]["derivation_path"] = relation["path_description"]
        payload["derived_house_mapping"] = mapping
    elif request.reading_type == "timing":
        horizon = request.timing_horizon or "year"
        as_of = request.as_of_date or date_type.today()
        timing = timing_service.compute_timing(chart, request.as_of_date)
        forecast = timing_service.compute_forecast(chart, request.as_of_date)
        payload["identity"] = _identity_context(chart_data)
        payload["horizon"] = horizon
        payload["profection"] = timing["profection"]
        payload["current_transits"] = {"date": timing["date"].isoformat(), "aspects": timing["aspects"]}
        payload["upcoming_events"] = _select_events_for_horizon(forecast["events"], horizon, as_of)
    elif request.reading_type == "zodiacal_releasing":
        selected_lots = request.zr_selected_lots or [FORTUNE_LOT_NAME, SPIRIT_LOT_NAME]
        lookahead_years = 10 if request.zr_mode == "predictive" else 5
        zr = compute_zodiacal_releasing_for_chart(chart, request.as_of_date, lookahead_years)
        chart_lots_by_name = {lot["name"]: lot for lot in chart_data["lots"]}

        payload["identity"] = _identity_context(chart_data)
        payload["as_of_date"] = zr["as_of_date"]
        payload["mode"] = request.zr_mode
        payload["lots"] = {}
        for lot_name in selected_lots:
            lot_result = zr["lots"].get(lot_name)
            if lot_result is None:
                continue
            entry = {
                "lot_sign": lot_result["lot_sign"],
                "signification": chart_lots_by_name.get(lot_name, {}).get("signification"),
                "current_l1": lot_result["current_l1"],
            }
            if request.zr_mode == "predictive":
                entry["l1_periods"] = lot_result["l1_periods"]
            else:
                entry["current_l1_l2_periods"] = lot_result["current_l1_l2_periods"]
                entry["current_l2"] = lot_result["current_l2"]
            payload["lots"][lot_name] = entry
        if (
            request.zr_mode == "predictive"
            and request.zr_axis_key in _AXES_REQUIRING_NATAL_FOCAL_DATA
        ):
            payload["axis"] = request.zr_axis_key
            payload["natal_focal_data"] = {
                "angles": chart_data["angles"],
                "houses": chart_data["houses"],
                "planets": chart_data["planets"],
                "aspects": chart_data["aspects"],
                "derived_houses": chart_data["derived_houses"],
            }
    elif request.reading_type == "compatibility":
        assert chart_b is not None  # vérifié en amont par l'appelant (api/readings.py)
        mode = request.relationship_mode or "romantic"
        synastry = compute_synastry_for_charts(chart, chart_b, mode)

        payload["relationship_mode"] = mode
        payload["person_a"] = {"identity": _identity_context(chart_data)}
        payload["person_b"] = {
            "name": chart_b.subject_name,
            "birth_date": chart_b.birth_date.isoformat(),
            "birth_time_known": chart_b.birth_time_known,
            "birth_city": chart_b.birth_city,
            "identity": _identity_context(chart_b.computed_chart_data),
        }
        payload["inter_aspects"] = synastry["inter_aspects"]
        payload["house_overlay"] = synastry["house_overlay"]
        payload["composite_chart"] = synastry["composite_chart"]
        payload["charts_time_known"] = synastry["charts_time_known"]
        payload["reference"] = {"houses_meanings": houses_meanings()["houses"]}
    elif request.reading_type == "astrocartography":
        mode = request.astro_map_mode or "natal"
        focus_lat = request.astro_focus_latitude if request.astro_focus_latitude is not None else chart.birth_latitude
        focus_lon = request.astro_focus_longitude if request.astro_focus_longitude is not None else chart.birth_longitude
        focus_label = request.astro_focus_label or chart.birth_city or "lieu analysé"

        if mode == "transit":
            as_of = request.as_of_date or date_type.today()
            jd_ut = ephemeris.jd_ut_for_date_utc_noon(as_of.isoformat())
            payload["as_of_date"] = as_of.isoformat()
        else:
            as_of = date_type.today()
            jd_ut = astrocartography_service.jd_ut_for_chart(chart)
        lines = astrocartography_service.compute_lines_for_jd(jd_ut)
        nearby = analyze_nearby_lines(lines, focus_lat, focus_lon, threshold_km=500)
        significations = astrocartography_significations()["planet_line_meanings"]

        # Personnalisation (voir app/core/astrocartography_personalization.py) : croise chaque
        # ligne proche avec la condition natale de sa planète, les thèmes confirmés du thème
        # (dispositeur dominant, maître de l'Ascendant, stellium) et sa pertinence temporelle
        # actuelle (profection, Libération Zodiacale) — pas seulement la signification générique
        # planète × type de ligne, identique pour tout le monde.
        profection = compute_profection(chart.birth_date, chart_data["angles"]["ascendant"]["sign"], as_of)
        zr_data = compute_zodiacal_releasing_for_chart(chart, as_of)

        payload["identity"] = _identity_context(chart_data)
        payload["map_mode"] = mode
        payload["focus_location"] = {"label": focus_label, "latitude": focus_lat, "longitude": focus_lon}
        payload["nearby_lines"] = personalize_nearby_lines(nearby, chart_data, significations, profection, zr_data)
    elif request.reading_type == "astrocartography_forecast":
        focus_lat = request.astro_focus_latitude if request.astro_focus_latitude is not None else chart.birth_latitude
        focus_lon = request.astro_focus_longitude if request.astro_focus_longitude is not None else chart.birth_longitude
        focus_label = request.astro_focus_label or chart.birth_city or "lieu analysé"
        start_date = request.forecast_start_date or date_type.today()
        years = request.forecast_years
        threshold_km = request.forecast_threshold_km
        end_date = start_date + timedelta(days=round(years * 365.25))

        windows = astrocartography_service.compute_location_forecast(
            latitude=focus_lat, longitude=focus_lon, start_date=start_date, years=years, threshold_km=threshold_km
        )
        significant_windows = _select_significant_forecast_windows(windows)
        significations = astrocartography_significations()["planet_line_meanings"]

        payload["identity"] = _identity_context(chart_data)
        payload["focus_location"] = {"label": focus_label, "latitude": focus_lat, "longitude": focus_lon}
        payload["forecast_period"] = {
            "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "years": years, "threshold_km": threshold_km
        }
        # request_payload est ensuite stocké tel quel dans une colonne JSON (SavedReading) : les
        # dates doivent être des chaînes ISO, pas des objets `date` (non sérialisables par le
        # json.dumps par défaut de SQLAlchemy, ce qui ferait échouer le commit après coup, une
        # fois l'appel LLM déjà payé).
        payload["forecast_windows"] = [
            {
                **{k: (v.isoformat() if isinstance(v, date_type) else v) for k, v in window.items()},
                "meaning": significations.get(window["planet"], {}).get(window["line_type"], ""),
            }
            for window in significant_windows
        ]
        payload["total_windows_found"] = len(windows)
    elif request.reading_type == "witchy_calendar":
        # Calendrier collectif, indépendant du thème natal (voir app/core/witchy_calendar.py) :
        # calcul direct plutôt que via le cache partagé de witchy_calendar_service (réservé à
        # l'endpoint de consultation répétée), négligeable ici (~0.3s) face à la latence de
        # l'appel LLM qui suit.
        year = request.witchy_calendar_year or date_type.today().year
        payload["year"] = year
        payload["events"] = compute_witchy_calendar(year)

    return payload


async def generate_reading(
    chart: models.NatalChart, request: schemas.ReadingRequest, chart_b: models.NatalChart | None = None
) -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY n'est pas configurée. Ajoutez-la dans le fichier .env pour activer "
            "la génération de lectures."
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    system_prompt = _build_system_prompt(request)
    payload = _build_user_payload(chart, request, chart_b=chart_b)
    if request.reading_type == "zodiacal_releasing":
        max_tokens = _zodiacal_releasing_max_tokens(request)
    elif request.reading_type == "timing":
        max_tokens = _timing_max_tokens(request)
    elif request.reading_type == "astrocartography":
        max_tokens = _astrocartography_max_tokens(request)
    elif request.reading_type == "astrocartography_forecast":
        max_tokens = _astrocartography_forecast_max_tokens(request)
    elif request.reading_type == "witchy_calendar":
        max_tokens = _witchy_calendar_max_tokens(request)
    else:
        max_tokens = READING_TYPE_MAX_TOKENS.get(request.reading_type, 2000)

    messages: list[dict] = [{"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}]
    reading_text = ""
    tokens_used = 0

    for _ in range(MAX_CONTINUATION_ROUNDS + 1):
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        chunk = "".join(block.text for block in response.content if block.type == "text")
        reading_text += chunk
        tokens_used += response.usage.input_tokens + response.usage.output_tokens

        if response.stop_reason != "max_tokens":
            break

        # La réponse s'est arrêtée faute de budget, en plein milieu d'une phrase. Certains
        # modèles refusent le préremplissage (la conversation ne peut pas se terminer par un
        # tour "assistant") : on repasse donc le texte déjà généré comme tour "assistant" suivi
        # d'un tour "user" demandant de continuer exactement là où le modèle s'est arrêté, sans
        # rien répéter.
        messages.append({"role": "assistant", "content": chunk})
        messages.append(
            {
                "role": "user",
                "content": "Continue exactement là où tu t'es arrêté, sans rien répéter de ce "
                "qui précède et sans ajouter de préambule ni de transition — reprends le texte "
                "au milieu du mot ou de la phrase si nécessaire.",
            }
        )

    compatibility_ratings = None
    timing_ratings = None
    if request.reading_type == "compatibility":
        reading_text, raw_ratings = _extract_compatibility_ratings(reading_text)
        compatibility_ratings = _sanitize_compatibility_ratings(raw_ratings, request.relationship_mode or "romantic")
    elif request.reading_type == "timing":
        reading_text, raw_ratings = _extract_timing_ratings(reading_text)
        timing_ratings = _sanitize_timing_ratings(raw_ratings)

    return {
        "reading_text": reading_text,
        "model_used": settings.anthropic_model,
        "tokens_used": tokens_used,
        "request_payload": payload,
        "compatibility_ratings": compatibility_ratings,
        "timing_ratings": timing_ratings,
    }
