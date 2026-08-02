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

from anthropic import AsyncAnthropic

from app import models, schemas
from app.config import get_settings
from app.core.reference_data import houses_meanings, rulerships
from app.core.zodiacal_releasing import FORTUNE_LOT_NAME, SPIRIT_LOT_NAME
from app.services import timing_service
from app.services.zodiacal_releasing_service import compute_zodiacal_releasing_for_chart

BASIC_READING_TYPES = {"global", "love", "career", "family"}

FOCUS_AREA_GUIDANCE = {
    "general": "vue d'ensemble de la personnalité (Soleil, Lune, Ascendant) et dynamiques dominantes du thème",
    "love": "vie affective et amoureuse (Vénus, Mars, maison VII, aspects vers ces points)",
    "career": "vocation et carrière (Midciel, maison X, Saturne, dispositeur du Midciel)",
    "family": "famille, foyer, racines (Lune, maison IV, maison X selon la tradition retenue)",
}

READING_TYPE_MAX_TOKENS = {
    "global": 3500,
    "love": 1800,
    "career": 1800,
    "family": 1800,
    "lots": 2500,
    "derived_houses": 2000,
    "timing": 3000,
}


def _zodiacal_releasing_max_tokens(request: schemas.ReadingRequest) -> int:
    """Plus de lots sélectionnés ou mode prévisionnel (frise sur 10 ans) => lecture plus
    longue, donc plus de budget de tokens que les autres lectures spécialisées à un seul
    sujet."""
    n_lots = len(request.zr_selected_lots) or 2
    tokens = 2500 + 500 * n_lots
    if request.zr_mode == "predictive":
        tokens += 1000
    return min(tokens, 7000)

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
    "timing": """Cette lecture porte spécifiquement sur le TIMING : la période actuelle et \
les mois à venir. Tu reçois trois éléments : (1) `profection`, la profection annuelle en \
cours (maison et planète maîtresse de l'année) ; (2) `current_transits`, les transits \
actuels des planètes lentes (Jupiter à Pluton) vers le thème natal ; (3) `upcoming_events`, \
une liste d'événements de transit significatifs à venir sur les prochains mois, chacun avec \
une date de pic (`peak_date`) et une fenêtre active (`window_start`/`window_end`). Structure \
la lecture ainsi : d'abord le thème de l'année (profection), puis la tendance actuelle \
(transits en cours), puis un aperçu chronologique des 3 à 5 périodes à venir les plus \
marquantes en citant leurs fenêtres de dates (pas seulement le jour du pic). Ne fais JAMAIS \
de prédiction fermée ('il vous arrivera X') : formule toujours en dynamique ou thème \
disponible ('cette période favorise...', 'une tension pourrait émerger autour de...').""",
}


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

    if len(selected) == 1:
        depth = """Un seul lot est sélectionné : consacre-lui une lecture approfondie, sans \
te presser — une plongée détaillée sur ce domaine de vie précis, pas un survol."""
    else:
        depth = """Plusieurs lots sont sélectionnés : traite d'abord chacun individuellement \
(brièvement), PUIS ajoute une section de LECTURE CROISÉE qui relie leurs phases entre elles \
— par exemple des périodes de pointe ou des déliements du lien qui se chevauchent dans le \
temps (convergence de plusieurs domaines de vie sur la même période), ou au contraire un lot \
en phase calme pendant qu'un autre traverse un tournant. Cette mise en résonance entre lots \
est la vraie valeur ajoutée d'une sélection multiple : ne la saute pas."""

    if request.zr_mode == "predictive":
        mode_block = """MODE : PRÉVISIONNEL (environ 10 ans). Pour chaque lot, tu reçois \
dans `l1_periods` la liste chronologique des périodes L1 sur l'horizon demandé, ainsi que \
`current_l1` pour situer la période en cours dans cette liste. Construis une frise \
chronologique en langage naturel des grandes périodes à venir sur la décennie, en citant \
leurs fenêtres de dates (`start_date`/`end_date`) et leur signe. Mets en avant les \
transitions marquantes : changement de période L1 (bascule de thème de vie dans ce domaine), \
périodes `is_peak_period` (sommets d'activité/d'enjeu) et `is_loosing_of_the_bond` (tournants \
nets, changements de trajectoire). Ne donne jamais une date comme une prédiction fermée \
d'événement précis : parle de fenêtres propices à tel type de dynamique, jamais d'un \
événement certain qui \"arrivera\"."""
    else:
        mode_block = """MODE : ACTUEL. Pour chaque lot, tu reçois `current_l1` (la période en \
cours, plusieurs années), `current_l1_l2_periods` (sa subdivision complète en sous-périodes \
L2 de quelques mois chacune) et `current_l2` (la sous-période en cours). Explique d'abord le \
climat général de la période L1 en cours, puis précise ce que la sous-période L2 actuelle \
vient nuancer ou affiner par rapport à ce climat général."""

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
évoquée. Ne fais jamais de prédiction fermée : parle de dynamiques, de thèmes dominants et de \
tonalité de la période, jamais d'événements certains."""


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

    specialized_block = (
        _zodiacal_releasing_prompt_block(request)
        if request.reading_type == "zodiacal_releasing"
        else _SPECIALIZED_PROMPT_BLOCKS[request.reading_type]
    )
    return f"""{base}

{specialized_block}

Termine toujours par un court paragraphe de synthèse bienveillant et encourageant."""


def _build_user_payload(chart: models.NatalChart, request: schemas.ReadingRequest) -> dict:
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
        timing = timing_service.compute_timing(chart, request.as_of_date)
        forecast = timing_service.compute_forecast(chart, request.as_of_date)
        payload["identity"] = _identity_context(chart_data)
        payload["profection"] = timing["profection"]
        payload["current_transits"] = {"date": timing["date"].isoformat(), "aspects": timing["aspects"]}
        payload["upcoming_events"] = forecast["events"]
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

    return payload


async def generate_reading(chart: models.NatalChart, request: schemas.ReadingRequest) -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY n'est pas configurée. Ajoutez-la dans le fichier .env pour activer "
            "la génération de lectures."
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    system_prompt = _build_system_prompt(request)
    payload = _build_user_payload(chart, request)
    if request.reading_type == "zodiacal_releasing":
        max_tokens = _zodiacal_releasing_max_tokens(request)
    else:
        max_tokens = READING_TYPE_MAX_TOKENS.get(request.reading_type, 2000)

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
    )

    reading_text = "".join(block.text for block in response.content if block.type == "text")
    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    return {
        "reading_text": reading_text,
        "model_used": settings.anthropic_model,
        "tokens_used": tokens_used,
        "request_payload": payload,
    }
