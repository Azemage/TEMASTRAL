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
    "timing": 3500,
    "compatibility": 4500,
}

COMPATIBILITY_MODE_LABELS_FR = {
    "romantic": "relation amoureuse/romantique",
    "friendship": "amitié",
    "professional": "relation professionnelle (collègue, associé, employeur)",
}

# Nombre d'appels de relance autorisés quand une réponse s'arrête faute de budget de tokens
# (stop_reason == "max_tokens"), pour ne jamais renvoyer une lecture coupée en plein milieu
# d'une phrase à l'utilisateur.
MAX_CONTINUATION_ROUNDS = 2


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
    "timing": """Cette lecture porte spécifiquement sur LES DOUZE PROCHAINS MOIS : la période \
actuelle et les mois à venir. Tu reçois trois éléments : (1) `profection`, la profection \
annuelle en cours (maison et planète maîtresse de l'année) ; (2) `current_transits`, les \
transits actuels de TOUTES les planètes (Lune, Mercure, Vénus, Soleil, Mars compris, pas \
seulement les lentes) vers le thème natal ; (3) `upcoming_events`, une sélection déjà filtrée \
des événements de transit les plus significatifs à venir sur les douze prochains mois \
(les transits mineurs ou trop fréquents, notamment lunaires, ont été écartés en amont), \
chacun avec une date de pic (`peak_date`) et une fenêtre active (`window_start`/`window_end`). \
Chaque aspect porte aussi un champ `intensity` (1 à 4) qui reflète déjà son poids (planète, \
type d'aspect, précision de l'orbe) : appuie-toi dessus pour doser l'espace que tu accordes à \
chacun, mais ne cite jamais ce chiffre brut dans le texte — traduis-le en mots. Structure la \
lecture ainsi : d'abord le thème de l'année (profection), puis la tendance actuelle (transits \
en cours, en insistant sur les plus intenses), puis un aperçu chronologique des périodes à \
venir les plus marquantes en citant leurs fenêtres de dates (pas seulement le jour du pic). Ne \
fais JAMAIS de prédiction fermée ('il vous arrivera X') : formule toujours en dynamique ou \
thème disponible ('cette période favorise...', 'une tension pourrait émerger autour de...').""",
}


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

    return f"""{intro}

{time_known_note}

{structure}

{ethics}"""


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
        timing = timing_service.compute_timing(chart, request.as_of_date)
        forecast = timing_service.compute_forecast(chart, request.as_of_date)
        payload["identity"] = _identity_context(chart_data)
        payload["profection"] = timing["profection"]
        payload["current_transits"] = {"date": timing["date"].isoformat(), "aspects": timing["aspects"]}
        payload["upcoming_events"] = _select_significant_events(forecast["events"])
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

    return {
        "reading_text": reading_text,
        "model_used": settings.anthropic_model,
        "tokens_used": tokens_used,
        "request_payload": payload,
    }
