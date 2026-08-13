# Temastral — Lecture de carte natale astrologique

Application de calcul et de lecture de thème natal :
- **Calcul déterministe** (jamais halluciné) des positions planétaires, maisons, angles,
  aspects, balances élément/modalité et dispositeurs, via [Swiss Ephemeris](https://www.astro.com/swisseph/)
  (`pyswisseph`, algorithme Moshier — aucun fichier d'éphémérides externe requis).
- **Interprétation rédigée** déléguée à un modèle Claude (API Anthropic), à partir du JSON
  calculé — le modèle ne recalcule et n'invente jamais de position astrologique.

Stack : Python / FastAPI, SQLite (via SQLAlchemy), frontend web minimal servi par le
backend (Jinja2 + JS vanilla), usage anonyme par session (pas de comptes au MVP).

## Langues

Trois langues via les drapeaux en haut de page (🇫🇷/🇬🇧/🇪🇸), persistées en local
(`localStorage`) : l'interface (boutons, libellés, en-têtes, messages) et le vocabulaire de
référence fermé (signes, planètes, aspects, maisons, lots, relations dérivées, axes
thématiques) sont traduits côté client (`app/static/i18n.js`), sans toucher au calcul
déterministe. Les lectures générées par le LLM sont paramétrées côté serveur par
`ReadingRequest.language` (envoyé automatiquement dans la langue choisie à chaque requête de
lecture) : le modèle rédige intégralement sa réponse dans cette langue. Reste en français pour
l'instant : les textes narratifs longs des données de référence (ex. `meaning`/`key_meaning`
de la synastrie, notes libres des dispositeurs) qui n'ont pas de version traduite côté serveur.

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
  (mois), calculées pour les 17 lots (formellement définie pour le lot Fortune et le lot
  Esprit ; extension exploratoire du même algorithme aux 15 autres lots), avec détection des
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
- Astrocartographie & cyclocartographie, dans une partie séparée du thème natal et de la
  lecture interprétée : projette sur une carte du monde (SVG, projection équirectangulaire,
  contours des terres émergées `app/static/world_land.json`, Natural Earth 110m — domaine
  public) les lignes ASC/DC/MC/IC des 10 planètes classiques — les lieux où chacune est angulaire.
  Deux variantes : **natale** (lignes fixes calculées à l'instant de naissance, mises en cache
  par thème, jamais recalculées) et **cyclocartographie** (lignes de transit reflétant les
  positions planétaires actuelles, calculées une fois par jour et partagées par tous les
  utilisateurs — pas de tâche cron, calcul paresseux à la première requête du jour). Formules
  d'astronomie sphérique standard (temps sidéral de Greenwich, ascension droite/déclinaison
  équatoriales, angle horaire de lever/coucher), indépendantes de tout logiciel commercial et
  vérifiées contre des repères connus (ligne de MC du Soleil ≈ longitude de l'heure solaire
  apparente, ASC/DC exactement à ±90° du MC à l'équateur). Lieux sauvegardés (ex. "et si je
  déménageais à Lisbonne ?") : recherche de ville (géocodage), calcul déterministe des lignes
  natales les plus proches (distance orthodromique), lecture LLM dédiée qui commente les lignes
  proches du lieu choisi (par défaut le lieu de naissance) en s'appuyant sur les significations
  par planète/type de ligne — jamais d'affirmation sur la sécurité/l'économie/la politique du
  lieu, toujours cadré comme un potentiel symbolique plutôt qu'un verdict. **Personnalisation
  par croisement avec le thème natal** (`app/core/astrocartography_personalization.py`) : la
  signification générique de chaque ligne proche n'est qu'un point de départ — elle est
  enrichie avec (1) la condition natale de la planète (dignité essentielle, qualité de ses
  aspects natals, rétrogradation), (2) sa présence dans les thèmes confirmés du thème
  (dispositeur final dominant, maître de l'Ascendant, membre d'un stellium — le signal le plus
  personnalisant), (3) sa pertinence temporelle actuelle (maître de l'année de profection en
  cours, période de Libération Zodiacale active sur les lots Fortune/Esprit). Un score de
  priorité déterministe (somme pondérée des 3 couches, jamais laissé au LLM) trie les lignes ;
  le prompt développe en détail les plus prioritaires et résume les autres. En mode
  cyclocartographie, une **date arbitraire** peut être choisie (pas seulement aujourd'hui :
  ex. "dans 6 mois je pars à Madrid") — les lignes de transit sont recalculées pour cette date
  et la lecture LLM en tient compte (`as_of_date`). **Prévision multi-années pour un lieu
  fixe** (inverse de la cyclocartographie du jour) : le lieu reste fixe (ex. domicile actuel) et
  l'outil balaie plusieurs années pour détecter les fenêtres de temps où une ligne de transit
  passe à proximité (`GET /api/astrocartography/location-forecast`), regroupées par
  planète/type de ligne avec date de pic de proximité — la Lune est exclue par défaut (sa ligne
  de MC balaie ~12°/jour, trop de fenêtres courtes sur un horizon pluriannuel pour être
  pertinente) mais reste sélectionnable explicitement. Horizon **plafonné à 10 ans** (trop de
  données au-delà pour rester lisible), avec une **lecture LLM dédiée**
  (`reading_type=astrocartography_forecast`) : les fenêtres de transit sur la période sont
  réduites aux ~25 plus significatives (les plus proches du lieu), re-triées chronologiquement,
  et le prompt demande explicitement de regrouper les périodes qui se recoupent plutôt que de
  traiter chaque fenêtre comme un point isolé — toujours cadré comme climat passager, jamais
  comme prédiction datée avec certitude. **Villes intéressantes suggérées automatiquement**,
  en mode natal (score sur les 12 premières, `GET /api/charts/{id}/astrocartography/interesting-cities`)
  **et en mode cyclocartographie** (top 5 recalculé à chaque changement de date,
  `GET /api/astrocartography/transit/interesting-cities`) : parmi ~240 grandes villes mondiales
  (Natural Earth 110m populated places, domaine public), celles proches de plusieurs lignes
  (natales ou de transit selon le mode) et/ou d'un croisement de deux lignes planétaires
  distinctes sont détectées et classées par score déterministe, puis affichées à la fois en
  liste et sous forme de repères losange sur la carte. Un croisement de lignes est ici une
  approximation cartographique des *parans* traditionnels : le point où deux courbes de
  planètes différentes se croisent effectivement sur la projection (interpolation linéaire entre
  échantillons de latitude consécutifs), pas le calcul astronomique classique par latitude
  d'angularité simultanée — voir `advanced_technique_parans` dans les significations pour la
  distinction
- Calendrier ésotérique annuel (`app/core/witchy_calendar.py`), collectif et indépendant du
  thème natal (le même pour tout le monde une année donnée, mis en cache une seule fois par
  année civile — même principe que les lignes de transit) : lunaisons (Nouvelle/Pleine Lune,
  avec détection de super lune sous ~360 000 km), éclipses solaires/lunaires (fonctions dédiées
  de Swiss Ephemeris `sol_eclipse_when_glob`/`lun_eclipse_when`, plus fiables qu'une détection
  manuelle), stations rétrogrades/directes des 8 planètes concernées, et ingrès de planètes
  lentes (Jupiter à Pluton) dans un nouveau signe — recherche de racine par bissection sur les
  fonctions astronomiques concernées (élongation Lune-Soleil, vitesse apparente, longitude),
  échantillonnée quotidiennement puis affinée. Score de priorité déterministe (poids de base +
  modificateurs, ex. éclipse solaire/super lune/planète rare en station) converti en note 1-5.
  Lecture LLM dédiée (`reading_type=witchy_calendar`) au format volontairement scannable (1 à 3
  phrases par événement, jamais plus), qui répond systématiquement à "quelle énergie" et "à
  quoi c'est utile" (intention, rituel, type d'action) dans un ton évocateur mais jamais
  fataliste. Portée de cette version : les grandes conjonctions planétaires et la
  personnalisation croisée avec le thème natal (V2 du document source) ne sont pas encore
  implémentées.
- Lecture interprétée par l'API Anthropic avec **prompt dédié par catégorie** : lecture
  générale (thème de base uniquement — planètes/maisons/aspects/dispositeurs, sans les lots
  ni les maisons dérivées), et six lectures spécialisées (Lots, Maisons dérivées, Timing,
  Libération zodiacale, Compatibilité, Astrocartographie) qui ne reçoivent que les données de
  leur propre technique
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
| POST | `/api/charts/{id}/readings` | Génère une lecture interprétée (LLM). `reading_type` = `global`\|`love`\|`career`\|`family`\|`lots`\|`derived_houses`\|`timing`\|`zodiacal_releasing`\|`compatibility`\|`astrocartography`\|`astrocartography_forecast`\|`witchy_calendar` ; `relation_key` (voir `/api/reference/derived-house-relations`, ou `custom:N1:N2` pour une relation de second ordre composée librement) pour `derived_houses` (repli sur `reference_house` 1-12 si absent), `as_of_date` pour `timing`/`zodiacal_releasing`/`astrocartography` (mode `transit` uniquement — date de la cyclocartographie, défaut aujourd'hui), `timing_horizon` (`week`\|`month`\|`year`, défaut `year`) pour `timing`, `zr_selected_lots`+`zr_mode` (`current`\|`predictive`)+`zr_axis_key` (voir `/api/reference/axes-thematiques-lots`, qualification natale en couche 1 pour les projections 10 ans) pour `zodiacal_releasing`, `chart_b_id`+`relationship_mode` pour `compatibility`, `astro_map_mode` (`natal`\|`transit`)+`astro_focus_latitude`/`astro_focus_longitude`/`astro_focus_label` (défaut : lieu de naissance) pour `astrocartography`, `astro_focus_latitude`/`astro_focus_longitude`/`astro_focus_label`+`forecast_start_date`+`forecast_years` (≤ 10)+`forecast_threshold_km` pour `astrocartography_forecast`, `witchy_calendar_year` (défaut : année en cours) pour `witchy_calendar` |
| GET | `/api/charts/{id}/readings` | Liste les lectures déjà générées pour un thème |
| GET | `/api/charts/{id}/timing?date=YYYY-MM-DD` | Transits actuels de toutes les planètes + profection annuelle, calculés à la demande (non persisté) |
| GET | `/api/charts/{id}/timing/forecast?date=...&months=12` | Transits à venir sur la période, toutes planètes (pics d'orbe, fenêtres actives, intensité 1-4) |
| GET | `/api/reference/derived-house-relations` | Liste des relations disponibles pour les maisons dérivées (premier ordre + presets de second ordre), avec les indications de priorité d'analyse utilisées par le prompt LLM |
| GET | `/api/reference/axes-thematiques-lots` | Liste finale validée des 17 lots + les 7 axes thématiques (raccourcis de sélection) pour les projections à 10 ans |
| GET | `/api/charts/{id}/zodiacal-releasing?date=YYYY-MM-DD&lookahead_years=5` | Phases L1/sous-phases L2 en cours pour les 17 lots, calculées à la demande (non persisté) |
| GET | `/api/charts/{id}/compatibility?chart_b_id=...&mode=romantic\|friendship\|professional` | Inter-aspects pondérés, chevauchement de maisons et thème composite entre deux thèmes, calculés à la demande (non persisté) |
| GET | `/api/charts/{id}/astrocartography` | Lignes ASC/DC/MC/IC natales des 10 planètes classiques, calculées une seule fois par thème puis mises en cache |
| GET | `/api/astrocartography/transit?date=YYYY-MM-DD` | Lignes de transit (cyclocartographie) du jour demandé (défaut aujourd'hui, UTC), calculées une seule fois par jour et partagées par tous les utilisateurs |
| POST/GET | `/api/charts/{id}/saved-locations` | Crée/liste les lieux sauvegardés (ville, coordonnées) avec l'analyse déterministe des lignes natales à proximité (distance orthodromique) |
| DELETE | `/api/saved-locations/{id}` | Supprime un lieu sauvegardé |
| GET | `/api/astrocartography/location-forecast?latitude=...&longitude=...&start_date=YYYY-MM-DD&years=10&planets=...&line_types=...&threshold_km=300&step_days=3` | Prévision multi-années (max 10 ans) pour un lieu fixe : fenêtres de temps où une ligne de transit passe à proximité, groupées par planète/type de ligne (`start_date`/`years`/`threshold_km`/`step_days` optionnels ; `planets`/`line_types` listes séparées par des virgules, défaut toutes sauf la Lune / ASC,DC,MC,IC) |
| GET | `/api/charts/{id}/astrocartography/interesting-cities?threshold_km=300&top_n=12` | Villes suggérées automatiquement (mode natal, parmi les grandes villes mondiales), classées par score de proximité aux lignes natales et aux croisements de lignes |
| GET | `/api/astrocartography/transit/interesting-cities?date=YYYY-MM-DD&threshold_km=300&top_n=5` | Équivalent pour la cyclocartographie : top 5 villes par défaut, basé sur les lignes de transit de la date demandée (défaut aujourd'hui) — recalculé à chaque date différente |
| GET | `/api/reference/astrocartography-significations` | Significations par planète et type de ligne (ASC/DC/MC/IC) utilisées par le prompt LLM |
| GET | `/api/witchy-calendar?year=YYYY` | Calendrier ésotérique annuel (lunaisons, éclipses, stations rétrogrades, ingrès de planètes lentes), collectif et mis en cache par année (défaut : année en cours) |
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
