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
- Traits de caractère (résumé rapide déterministe, combinant planète+signe+maison) : tags de
  personnalité pour les 6 planètes personnelles (Soleil/Lune/Ascendant/Mercure/Vénus/Mars) et
  les 2 planètes sociales (Jupiter/Saturne), contextualisés par leur maison ; les tags qui
  reviennent depuis plusieurs sources sont signalés comme traits dominants ; Uranus/Neptune/
  Pluton (générationnelles) sont affichées à part, car leur signe seul n'individualise pas —
  seule leur maison le fait
- Roue astrale SVG interactive (info-bulles, plein écran, aspects colorés par type)
- Lots (parts arabes) : bibliothèque complète des 17 lots validés (10 lots classiques
  hellénistiques + 7 lots modernes non-canoniques construits par analogie ; Argent/Richesse,
  Commerce/Affaires et Carrière ne sont plus implémentés, fusionnés/redondants avec
  Substance/Esprit/Victoire), formules jour/nuit, aspects natals, avec un champ `certainty`
  (lots classiques) ou `construction_logic` (lots modernes) exposé dans l'UI sous forme de
  badge — pas seulement stocké
- Axes thématiques de lots (raccourcis de sélection, non verrouillants) : 6 axes de vie
  (Vocation & Réussite, Famille & Racines, Corps & Circonstances matérielles, Amour &
  Relations intimes, Épreuves & Résilience, Ouverture & Réseau) + une vue complète des 17
  lots ; pour une projection à 10 ans sur un axe, la lecture qualifie D'ABORD la nature de
  l'axe à partir du thème natal (points focaux propres à l'axe : Milieu du Ciel, Vénus,
  Saturne, maisons dérivées pertinentes...) avant de la situer dans le temps via la
  Libération Zodiacale déjà calculée — avec des mises en garde renforcées et systématiques
  sur les axes les plus sensibles (santé/mort, filiation, résilience)
- Maisons dérivées : mapping complet pour les 12 maisons de référence possibles, avec une
  liste de relations nommées (partenaire, mère, père, associé d'affaires, supérieur
  hiérarchique, rival déclaré...) et des relations de second ordre (belle-famille,
  grands-parents...) calculées par chaînage générique de la même formule ; la lecture LLM
  adapte ses priorités d'analyse (points focaux, angle d'interprétation, mises en garde)
  à la relation choisie
- Pronostic : transits actuels de toutes les planètes (Lune, Mercure, Vénus, Soleil, Mars
  compris, pas seulement les lentes) + prévision des transits à venir sur 12 mois (détection
  des pics d'orbe, échantillonnage adapté à la vitesse de chaque planète pour ne manquer aucun
  passage rapide, gère les boucles rétrogrades) + profection annuelle. Chaque aspect/transit
  porte une note d'intensité (1 à 4 🔥) combinant poids de la planète, dureté de l'aspect et
  précision de l'orbe ; un filtre d'intensité minimale (3+ flammes par défaut) garde la liste
  — potentiellement des centaines d'événements une fois la Lune incluse — lisible sans perdre
  l'accès aux transits mineurs. Trois lectures à horizon différent (semaine/mois/année)
  puisent dans les mêmes données mais avec une sélection et une consigne adaptées à l'échelle :
  la semaine garde même les transits mineurs pour rester concrète, l'année privilégie les
  grands arcs. Chacune se termine par une notation (1 à 10, en jauges) sur cinq sphères de vie
  (amour, amitié, professionnel, santé, développement personnel), même mécanisme que la
  notation de compatibilité pour une identité cohérente sur le site
- Libération zodiacale (Zodiacal Releasing) : phases L1 (plusieurs années) et sous-phases L2
  (mois), calculées pour les 14 lots (formellement définie pour le Lot de Fortune et le Lot
  d'Esprit ; extension exploratoire du même algorithme aux 12 autres lots), avec détection des
  périodes de pointe et des "déliements du lien" (changements de trajectoire marqués) —
  technique hellénistique (Vettius Valens), calcul sans dérive sur des dizaines d'années. La
  lecture dédiée permet de cocher un ou plusieurs lots (lecture approfondie sur un seul lot,
  ou lecture croisée si plusieurs sont sélectionnés) et de choisir entre une vue de la période
  actuelle ou une vue prévisionnelle sur les ~10 prochaines années
- Compatibilité (synastrie) entre deux thèmes, pour trois modes de relation (amoureuse, amitié,
  professionnelle — le mode change radicalement les significateurs pertinents) : aspects
  croisés entre les planètes des deux thèmes (pondérés fort/moyen/faible selon le mode, jamais
  un score en %), chevauchement de maisons (dans quelle maison de l'autre tombe chaque
  planète), et thème composite (point médian de chaque paire de planètes homologues,
  représentant la relation comme une entité). La lecture dédiée compile ces trois techniques
  en une analyse structurée avec une section recommandations/points de vigilance, et se termine
  par une notation chiffrée (1 à 10, affichée en jauges) sur 4 axes propres à chaque mode
  (ex. en amoureux : passion & alchimie, complicité émotionnelle, engagement & durabilité,
  valeurs partagées), générée par le modèle avec une courte justification par axe — une
  impression interprétative de synthèse, pas un score scientifique. Le mode personne/entreprise
  n'est pas encore implémenté (nécessite un thème d'entreprise dédié, cf. section V2 de la spec)
- Lecture interprétée par l'API Anthropic avec **prompt dédié par catégorie** : lecture
  générale (thème de base uniquement — planètes/maisons/aspects/dispositeurs, sans les lots
  ni les maisons dérivées), et cinq lectures spécialisées (Lots, Maisons dérivées, Timing,
  Libération zodiacale, Compatibilité) qui ne reçoivent que les données de leur propre technique
- Web app simple pour saisir une naissance, visualiser le thème et générer une lecture,
  organisée en "Thème natal" (données calculées) et "Lecture interprétée" (générale + les
  5 lectures spécialisées, chacune affichant d'abord ses données puis un bouton de génération ;
  la lecture des phases de Libération zodiacale est un second bouton dans l'onglet Lots ;
  l'onglet Compatibilité permet de sélectionner une carte existante ou d'en créer une nouvelle
  pour la deuxième personne, directement depuis cet onglet)

Pas encore implémenté (voir cahier des charges fourni, section V2/V3) : révolution solaire,
progressions secondaires, mode de compatibilité personne/entreprise, comptes utilisateurs.

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
| POST | `/api/charts/{id}/readings` | Génère une lecture interprétée (LLM). `reading_type` = `global`\|`love`\|`career`\|`family`\|`lots`\|`derived_houses`\|`timing`\|`zodiacal_releasing`\|`compatibility` ; `relation_key` (voir `/api/reference/derived-house-relations`, ou `custom:N1:N2` pour une relation de second ordre composée librement) pour `derived_houses` (repli sur `reference_house` 1-12 si absent), `as_of_date` pour `timing`/`zodiacal_releasing`, `timing_horizon` (`week`\|`month`\|`year`, défaut `year`) pour `timing`, `zr_selected_lots`+`zr_mode` (`current`\|`predictive`)+`zr_axis_key` (voir `/api/reference/axes-thematiques-lots`, qualification natale en couche 1 pour les projections 10 ans) pour `zodiacal_releasing`, `chart_b_id`+`relationship_mode` pour `compatibility` |
| GET | `/api/charts/{id}/readings` | Liste les lectures déjà générées pour un thème |
| GET | `/api/charts/{id}/timing?date=YYYY-MM-DD` | Transits actuels de toutes les planètes + profection annuelle, calculés à la demande (non persisté) |
| GET | `/api/charts/{id}/timing/forecast?date=...&months=12` | Transits à venir sur la période, toutes planètes (pics d'orbe, fenêtres actives, intensité 1-4) |
| GET | `/api/reference/derived-house-relations` | Liste des relations disponibles pour les maisons dérivées (premier ordre + presets de second ordre), avec les indications de priorité d'analyse utilisées par le prompt LLM |
| GET | `/api/reference/axes-thematiques-lots` | Liste finale validée des 17 lots + les 7 axes thématiques (raccourcis de sélection) pour les projections à 10 ans |
| GET | `/api/charts/{id}/zodiacal-releasing?date=YYYY-MM-DD&lookahead_years=5` | Phases L1/sous-phases L2 en cours pour les 17 lots, calculées à la demande (non persisté) |
| GET | `/api/charts/{id}/compatibility?chart_b_id=...&mode=romantic\|friendship\|professional` | Inter-aspects pondérés, chevauchement de maisons et thème composite entre deux thèmes, calculés à la demande (non persisté) |
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
