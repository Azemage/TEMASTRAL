# Temastral — Lecture de carte natale astrologique

Application de calcul et de lecture de thème natal :
- **Calcul déterministe** (jamais halluciné) des positions planétaires, maisons, angles,
  aspects, balances élément/modalité et dispositeurs, via [Swiss Ephemeris](https://www.astro.com/swisseph/)
  (`pyswisseph`, algorithme Moshier — aucun fichier d'éphémérides externe requis).
- **Interprétation rédigée** déléguée à un modèle Claude (API Anthropic), à partir du JSON
  calculé — le modèle ne recalcule et n'invente jamais de position astrologique.

Stack : Python / FastAPI, SQLite (via SQLAlchemy), frontend web minimal servi par le
backend (Jinja2 + JS vanilla), usage anonyme par session (pas de comptes au MVP).

## Périmètre de ce MVP

Implémenté :
- Thème natal complet (planètes, angles, maisons — Placidus/Koch/Whole Sign/Équal/Regiomontanus,
  aspects majeurs et mineurs avec orbes configurables, applicatif/séparatif, balance éléments/modalités)
- Dispositeurs : maîtres traditionnel et moderne, chaînes de dispositeurs, réceptions mutuelles,
  détection de convergence (planète "clé de voûte" du thème)
- Traits de caractère (résumé rapide déterministe : Soleil/Lune/Ascendant/dominantes)
- Roue astrale SVG interactive (info-bulles, plein écran, aspects colorés par type)
- Lots (parts arabes) : bibliothèque complète (14 lots), formules jour/nuit, aspects natals
- Maisons dérivées : mapping complet pour les 12 maisons de référence possibles
- Timing : transits actuels (planètes lentes) vers le thème natal + profection annuelle
- Lecture interprétée par l'API Anthropic (globale ou ciblée : amour, carrière, famille)
- Web app simple pour saisir une naissance, visualiser le thème et générer une lecture

Pas encore implémenté (voir cahier des charges fourni, section V2/V3) : révolution solaire,
progressions secondaires, synastrie et composite, calendrier visuel des périodes favorables
(libération zodiacale), comptes utilisateurs. Les tables de référence
(`app/reference_data/lot_timing_rules.json`, etc.) sont déjà en place pour faciliter ces
extensions.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditez .env et renseignez ANTHROPIC_API_KEY pour activer la génération de lectures.
```

## Lancement

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

- Web app : http://127.0.0.1:8000/
- Documentation API interactive (Swagger) : http://127.0.0.1:8000/docs

## Tests

```bash
source .venv/bin/activate
python3 -m pytest tests/ -v
```

## Architecture

```
app/
  core/                 # Calculs déterministes (aucun appel réseau)
    ephemeris.py         # Wrapper pyswisseph : temps -> jour julien, positions, maisons
    chart_calculator.py  # Assemble le thème natal complet
    aspects.py            # Détection des aspects (majeurs/mineurs, orbes, applicatif/séparatif)
    dispositors.py         # Maîtrise planétaire, chaînes, réceptions mutuelles
    zodiac.py               # Signes, éléments, modalités
    reference_data.py        # Chargement des tables JSON (app/reference_data/)
  services/
    chart_service.py      # Orchestration calcul + persistance
    interpretation_service.py  # Construction du prompt + appel API Anthropic
    session_service.py     # Sessions anonymes
  api/                    # Routes FastAPI (charts, readings, reference, geocode)
  reference_data/          # Tables JSON de référence (maîtrises, dignités, aspects, maisons, lots, config)
  models.py / schemas.py / database.py / config.py
  templates/ , static/     # Web app (Jinja2 + JS vanilla)
tests/                     # Tests unitaires (calcul, dispositeurs, API)
```

Principe directeur repris du cahier des charges : tout ce qui est dans `app/core/` et
`app/services/chart_service.py` est déterministe et testé unitairement. Seul
`interpretation_service.py` fait appel à un LLM, et uniquement pour la mise en mots.

## Points d'API principaux

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/charts` | Calcule et sauvegarde un thème natal à partir des données de naissance |
| GET | `/api/charts` | Liste les thèmes de la session courante |
| GET | `/api/charts/{id}` | Récupère un thème calculé |
| POST | `/api/charts/{id}/readings` | Génère une lecture interprétée (LLM) pour un thème |
| GET | `/api/charts/{id}/readings` | Liste les lectures déjà générées pour un thème |
| GET | `/api/charts/{id}/timing?date=YYYY-MM-DD` | Transits actuels (planètes lentes) + profection annuelle, calculés à la demande (non persisté) |
| GET | `/api/reference/config` | Options de configuration (systèmes de maisons, dispositeurs, points optionnels) |
| GET | `/api/reference/timezones` | Liste des ~490 fuseaux horaires IANA canoniques |
| GET | `/api/geocode?query=...` | Recherche ville -> latitude/longitude/fuseau horaire |

La session anonyme est gérée par un cookie HTTPOnly posé automatiquement à la première requête ;
un client API pur peut aussi transmettre l'en-tête `X-Session-Token`.

## Limites connues

- **Précision** : l'algorithme Moshier intégré à `pyswisseph` est précis à quelques secondes
  d'arc — largement suffisant pour une lecture natale, mais Chiron nécessite un fichier
  d'éphémérides externe (`seas_18.se1`) non fourni. S'il est absent, Chiron est omis
  silencieusement du thème et listé dans `computed_chart_data.unavailable_points`. Pour
  l'activer, placez les fichiers Swiss Ephemeris dans un dossier et modifiez
  `app/core/ephemeris.py` (`swe.set_ephe_path(...)`, flag `FLG_SWIEPH`).
- **Géocodage** (`/api/geocode`) utilise Nominatim (OpenStreetMap) et nécessite un accès
  réseau sortant ; en son absence, le formulaire permet toujours la saisie manuelle des
  coordonnées et du fuseau horaire.
- **Heure de naissance inconnue** : le thème est calculé avec une heure fixée à midi ;
  maisons et angles doivent alors être considérés comme approximatifs
  (`computed_chart_data.time_known = false`).
