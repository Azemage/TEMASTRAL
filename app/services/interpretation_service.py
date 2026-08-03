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
from app.core.reference_data import houses_meanings, rulerships
from app.core.zodiacal_releasing import FORTUNE_LOT_NAME, SPIRIT_LOT_NAME
from app.services import timing_service
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
    return min(tokens, 8000)

_SPECIALIZED_PROMPT_BLOCKS = {
    "lots": """Cette lecture porte spécifiquement sur les LOTS (parts arabes/hermétiques), une \
technique issue de l'astrologie hellénistique. Un lot est un point sensible calculé à partir \
de trois points du thème (le plus souvent l'Ascendant et deux autres points), qui affine la \
lecture d'un domaine de vie précis. Tu reçois la liste des lots déjà calculés (position, \
maison, aspects aux planètes natales) dans `lots`, ainsi qu'un contexte d'identité minimal \
dans `identity`. Pour chaque lot, explique d'abord en une phrase simple ce qu'il représente, \
puis interprète sa position et ses aspects. Priorise le Lot de Fortune et le Lot d'Esprit \
(les deux lots fondamentaux), et les lots dont un aspect a une orbe serrée (< 3°) : ne traite \
pas les 14 lots avec la même profondeur, ce serait répétitif et diluerait la lecture.""",
    "derived_houses": """Cette lecture porte spécifiquement sur les MAISONS DÉRIVÉES \
('maisons de maisons'), une technique qui permet d'analyser une tierce personne (partenaire, \
mère, père, enfant...) à partir du seul thème natal du consultant, sans disposer du thème de \
cette personne. Principe : la maison `reference_house` du consultant devient la maison 1 \
(identité) de la personne représentée, la maison suivante sa maison 2 (ressources), etc. \
(mapping complet fourni dans `derived_house_mapping`). Commence par expliquer ce principe en \
une phrase accessible, puis interprète ce que révèlent les planètes natales présentes dans \
les maisons dérivées les plus occupées, du point de vue de CETTE personne (pas du \
consultant). N'invente jamais qui est cette personne au-delà de ce que la maison de \
référence suggère usuellement (ex. maison 7 = partenaire) ; si ce n'est pas fourni, reste \
générique ('la personne représentée par cette maison').""",
}


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


def _zodiacal_releasing_prompt_block(request: schemas.ReadingRequest) -> str:
    selected = request.zr_selected_lots or [FORTUNE_LOT_NAME, SPIRIT_LOT_NAME]

    intro = """Cette lecture porte spécifiquement sur la RÉPARTITION ZODIACALE (Zodiacal \
Releasing), une technique de timing hellénistique (Vettius Valens) qui découpe la vie en \
grandes périodes ('périodes L1') elles-mêmes subdivisées en sous-périodes ('périodes L2'). \
Elle est formellement définie pour le Lot de Fortune (déroulement de la vie matérielle, du \
corps, des circonstances extérieures) et le Lot d'Esprit (déroulement de la vie active, des \
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

    return f"""{intro}

{scope}

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


def _build_system_prompt(request: schemas.ReadingRequest) -> str:
    base = f"""Tu es un astrologue professionnel, expérimenté et bienveillant, qui rédige des \
lectures de thème natal en {request.language}.

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
        reference_house = request.reference_house or 7
        mapping = next(d for d in chart_data["derived_houses"] if d["reference_house"] == reference_house)
        payload["identity"] = _identity_context(chart_data)
        payload["reference_house"] = reference_house
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

        # La réponse s'est arrêtée faute de budget, en plein milieu d'une phrase : on repasse
        # le texte déjà généré comme tour "assistant" (technique de préremplissage) pour que
        # l'appel suivant reprenne exactement où le modèle s'est arrêté, sans le renvoyer à
        # l'utilisateur coupé en plein mot.
        if messages[-1]["role"] == "assistant":
            messages[-1] = {"role": "assistant", "content": messages[-1]["content"] + chunk}
        else:
            messages.append({"role": "assistant", "content": chunk})

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
