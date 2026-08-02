"""Génère la lecture rédigée d'un thème via l'API Anthropic, à partir du JSON calculé.

Principe directeur du cahier des charges : le calcul astrologique est déterministe et
codé en dur (jamais délégué au modèle) ; seule la mise en mots — nuancée, pédagogique,
non déterministe — est confiée au LLM. Le modèle reçoit uniquement les données déjà
calculées et ne doit jamais recalculer ou inventer de positions.
"""

from __future__ import annotations

import json

from anthropic import AsyncAnthropic

from app import models, schemas
from app.config import get_settings
from app.core.reference_data import houses_meanings, rulerships

FOCUS_AREA_GUIDANCE = {
    "general": "vue d'ensemble de la personnalité (Soleil, Lune, Ascendant) et dynamiques dominantes du thème",
    "love": "vie affective et amoureuse (Vénus, Mars, maison VII, aspects vers ces points)",
    "career": "vocation et carrière (Midciel, maison X, Saturne, dispositeur du Midciel)",
    "family": "famille, foyer, racines (Lune, maison IV, maison X selon la tradition retenue)",
    "timing": "période à venir : transits, profections, fenêtres favorables/défavorables",
}

READING_TYPE_MAX_TOKENS = {
    "global": 3500,
    "love": 1800,
    "career": 1800,
    "family": 1800,
    "timing": 2000,
}


def _build_system_prompt(request: schemas.ReadingRequest) -> str:
    focus_descriptions = "\n".join(
        f"- {area} : {FOCUS_AREA_GUIDANCE.get(area, area)}" for area in request.focus_areas
    )
    return f"""Tu es un astrologue professionnel, expérimenté et bienveillant, qui rédige des \
lectures de thème natal en {request.language}.

RÈGLES IMPÉRATIVES :
1. Tu reçois dans le message utilisateur un JSON contenant TOUTES les données déjà \
calculées du thème (positions planétaires, maisons, aspects, dispositeurs, balances \
élément/modalité). Tu ne dois JAMAIS recalculer, corriger, ou inventer une position \
astrologique : appuie-toi exclusivement sur les données fournies.
2. N'affiche aucun JSON ni tableau de données brutes dans ta réponse : rédige un texte \
en langage naturel, fluide et structuré avec des titres.
3. Adopte un ton {request.tone}, adapté à un niveau {request.level}. Évite le jargon \
non expliqué ; quand tu introduis un terme technique (ex. 'dispositeur', 'lot'), \
explique-le brièvement.
4. Ne formule jamais de prédiction déterministe ou anxiogène (notamment sur la santé \
ou la mort) : reformule toujours en dynamique psychologique ou en tendance nuancée.
5. Structure la lecture avec des sections Markdown (##) correspondant aux zones \
demandées ci-dessous.
6. Regarde le champ `convergence` de `dispositors_traditional` et `dispositors_modern` dans \
les données. Si son `level` vaut 'forte' ou 'notable', la majorité des chaînes de \
dispositeurs du thème se referment sur une même planète (`dominant_dispositor`) : \
signale explicitement ce pattern comme une planète clé de voûte du thème, dont les \
qualités colorent une grande partie de la personnalité, plutôt que de la traiter comme \
une planète parmi d'autres.
7. Sois CONCRET, pas abstrait. Pour chaque trait ou dynamique évoqué, donne un exemple \
tangible de comportement, de réaction ou de situation de la vie quotidienne (travail, \
relations, décisions, habitudes) plutôt qu'une description théorique de "l'énergie" ou \
du "potentiel" de la planète. Bannis les formulations vagues type "cela peut se \
manifester de plusieurs façons" ou "cette énergie est présente dans votre thème" sans \
préciser comment. Préfère toujours une phrase illustrée ("vous avez probablement du mal \
à lâcher prise sur un projet avant qu'il soit parfait") à une phrase générique ("vous \
avez un fort besoin de perfection").

ZONES À COUVRIR DANS CETTE LECTURE :
{focus_descriptions}

Termine toujours par un court paragraphe de synthèse bienveillant et encourageant."""


def _build_user_payload(chart: models.NatalChart, request: schemas.ReadingRequest) -> dict:
    return {
        "request_type": f"{request.reading_type}_reading",
        "focus_areas": request.focus_areas,
        "subject": {
            "name": chart.subject_name,
            "relationship_to_user": chart.relationship_to_user,
            "birth_date": chart.birth_date.isoformat(),
            "birth_time_known": chart.birth_time_known,
            "birth_city": chart.birth_city,
            "birth_country": chart.birth_country,
        },
        "settings": {
            "house_system": chart.house_system,
            "zodiac_type": chart.zodiac_type,
            "rulership_system": chart.rulership_system,
        },
        "chart_data": chart.computed_chart_data,
        "reference": {
            "houses_meanings": houses_meanings()["houses"],
            "rulerships_notes": rulerships()["notes"],
        },
        "user_context": {
            "level": request.level,
            "language": request.language,
            "tone": request.tone,
        },
    }


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
    max_tokens = READING_TYPE_MAX_TOKENS.get(request.reading_type, 2000)

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )

    reading_text = "".join(block.text for block in response.content if block.type == "text")
    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    return {
        "reading_text": reading_text,
        "model_used": settings.anthropic_model,
        "tokens_used": tokens_used,
        "request_payload": payload,
    }
