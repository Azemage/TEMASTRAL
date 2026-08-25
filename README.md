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
- Points additionnels optionnels (voir `optional_points`, sélecteur dans "Options avancées") :
  Nœud Nord/Sud et Lilith moyenne (calcul orbital pur, aucun fichier supplémentaire) sont
  sélectionnés par défaut à la création d'un thème ; Chiron et les 4 principaux astéroïdes
  (Cérès, Pallas, Junon, Vesta) sont opt-in et nécessitent le fichier Swiss Ephemeris
  `seas_18.se1` (fourni dans `app/ephe/`, ~220 Ko, couvre ~1900-2200 pour ces 5 corps) —
  `swe.set_ephe_path()` est repositionné **par thread** (`app/core/ephemeris.py::
  _ensure_ephe_path_for_this_thread`) car cet appel est thread-local dans pyswisseph, ce qui
  fait échouer ces corps en silence dans les endpoints FastAPI (exécutés dans un thread de
  pool) si on ne le fait qu'une fois à l'import. Tous ces points s'intègrent automatiquement à
  la roue, aux tableaux (Planètes), aux aspects et à la lecture LLM (qui reçoit le thème tel
  quel, aucun filtrage) — sans figurer dans le nuage de traits de caractère déterministe
  ci-dessous, volontairement réservé aux planètes classiques.
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
- Pronostic : transits actuels de toutes les planètes (Lune, Mercure, Vénus, Soleil, Mars et
  Chiron compris, pas seulement les lentes classiques) + prévision des transits à venir sur 12
  mois (détection
  des pics d'orbe, échantillonnage adapté à la vitesse de chaque planète pour ne manquer aucun
  passage rapide, gère les boucles rétrogrades) + profection annuelle. Chaque aspect/transit
  porte une note d'intensité (1 à 4) combinant poids de la planète, dureté de l'aspect et
  précision de l'orbe, affichée avec le même composant d'étoiles que le reste du site (voir
  ci-dessous) ; un filtre d'intensité minimale (3+ étoiles par défaut) garde la liste —
  potentiellement des centaines d'événements une fois la Lune incluse — lisible sans perdre
  l'accès aux transits mineurs. Trois lectures à horizon différent (semaine/mois/année)
  puisent dans les mêmes données mais avec une sélection et une consigne adaptées à l'échelle :
  la semaine garde même les transits mineurs pour rester concrète, l'année privilégie les
  grands arcs. Chacune se termine par une notation (1 à 10, en étoiles) sur cinq sphères de vie
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
  par une notation chiffrée (1 à 10, affichée en étoiles) sur 4 axes propres à chaque mode
  (ex. en amoureux : passion & alchimie, complicité émotionnelle, engagement & durabilité,
  valeurs partagées), générée par le modèle avec une courte justification par axe — une
  impression interprétative de synthèse, pas un score scientifique. Le mode personne/entreprise
  n'est pas encore implémenté (nécessite un thème d'entreprise dédié, cf. section V2 de la spec)
- **Notation unifiée en 5 étoiles sur tout le site** (`starRatingHtml()` dans `app.js`) : un seul
  composant visuel pour toutes les évaluations (compatibilité, pronostic, intensité des
  transits, calendrier ésotérique, villes suggérées d'astrocartographie), chacune ramenée en
  interne sur une échelle 0-10 puis affichée en 5 étoiles à remplissage continu (technique CSS
  classique : étoiles pleines superposées et rognées en largeur sur les étoiles ternes de fond,
  pas seulement des paliers demi-étoile) avec 5 paliers de brillance — terne et discret en bas
  de l'échelle, doré et lumineux (halo) au-delà de 8/10 — plutôt qu'un système par fonctionnalité
  (jauges, flammes, texte brut). Un point d'incohérence a été corrigé dans le survol des
  marqueurs de la carte du monde d'astrocartographie (`buildAstroMapSVG` dans `app.js`) : la
  liste des villes suggérées à côté de la carte utilisait déjà `starRatingHtml`/5 comme partout
  ailleurs, mais l'info-bulle au survol d'un marqueur recalculait indépendamment un score sur
  10 (`/10`, jamais passé par le composant unifié) — corrigé pour recalculer la même échelle 0-5
  que la liste (même base de normalisation, `citiesMaxScore`/`maxScore`), les deux affichages
  montrant maintenant strictement le même chiffre pour une même ville. Les notations générées
  par le modèle (compatibilité, pronostic) reçoivent une rubrique de calibration explicite dans
  le prompt pour éviter le biais de
  prudence qui pousse un LLM à se réfugier systématiquement autour de 5-6/10
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
  manuelle), stations rétrogrades/directes des 8 planètes concernées, ingrès de planètes
  lentes (Jupiter à Pluton) dans un nouveau signe, et **grandes conjonctions** — aspect majeur
  exact (conjonction/carré/opposition) entre deux planètes lentes, détecté dynamiquement
  (dates variant sur des décennies, pas une liste figée) pour chacune des 10 paires possibles,
  vérifié contre la grande conjonction Jupiter-Saturne du 21 décembre 2020 (référence connue).
  Recherche de racine par bissection sur les fonctions astronomiques concernées (élongation
  Lune-Soleil, vitesse apparente, longitude, écart angulaire dirigé entre deux planètes),
  échantillonnée quotidiennement puis affinée. Score de priorité déterministe (poids de base +
  modificateurs, ex. éclipse solaire/super lune/planète rare en station) converti en note 1-5.
  **Personnalisation par croisement avec le thème natal** (`app/core/witchy_calendar_personalization.py`,
  toujours activée dans la lecture) : deux mécanismes indépendants selon le type d'événement —
  aspect natal serré (événements ponctuels : lunaisons, éclipses, stations ; orbe 2° pour
  conjonction/opposition, 1,5° pour carré/trigone/sextile ; priorité aux luminaires/Ascendant
  sur une planète lente même à orbe plus large) pour les événements ponctuels, maison natale
  traversée (événements qui durent : ingrès, grandes conjonctions) pour les événements de
  fond — avec amplification explicite si la cible touchée fait partie des thèmes confirmés du
  thème (réutilise `compute_theme_confirme` d'`astrocartography_personalization.py` : dispositeur
  final dominant, maître de l'Ascendant, stellium). Lecture LLM dédiée
  (`reading_type=witchy_calendar`) au format volontairement scannable (1 à 3 phrases par
  événement pour le bloc global, + 1 à 2 phrases de bloc personnel visiblement distinct
  lorsqu'un croisement est détecté), qui répond systématiquement à "quelle énergie" et "à quoi
  c'est utile" (intention, rituel, type d'action) dans un ton évocateur mais jamais fataliste.
  **Deux modes de lecture** (V3) : le mode aperçu ci-dessus reste concis et affiche en plus,
  pour chaque événement, jusqu'à 2 **signaux contextuels forts** (`contextual_signals`,
  `app/core/witchy_calendar.py::compute_contextual_signals`) — inter-aspects transit-transit du
  jour même, majeurs et à orbe serrée (< 2°), impliquant un acteur principal de l'événement (ex.
  Soleil/Lune pour une éclipse), en excluant l'aspect entre les acteurs eux-mêmes puisqu'il EST
  déjà l'événement — et, pour les éclipses uniquement, un `location_context` (hémisphère +
  visibilité locale calculée avec `swe.sol_eclipse_how`/`lun_eclipse_how` depuis le lieu de
  naissance, présentée comme un détail contextuel, jamais comme condition de validité de
  l'énergie). En cliquant sur une ligne du calendrier (ou en choisissant n'importe quelle date),
  un second mode **détail journée** (`reading_type=witchy_day_detail`) donne l'analyse complète
  de la "carte du jour" à cette date : `app/core/day_chart.py::compute_day_chart` réutilise
  intégralement le moteur d'aspects/dispositeurs du thème natal (positions de toutes les
  planètes de ce jour, tous leurs aspects entre elles, dispositeurs traditionnel/moderne) et
  `compute_theme_confirme` (déjà utilisé pour l'astrocartographie), relu ici comme le "climat
  énergétique collectif de la journée" plutôt que l'identité d'une personne — sans Ascendant ni
  maisons, puisqu'aucun lieu n'est associé à une date seule. La personnalisation y reste active
  via `personalize_day_chart`, qui généralise le mécanisme d'aspect natal à chaque planète de la
  carte du jour (pas seulement à l'événement principal) pour signaler les "résonances
  personnelles" de la journée.
- Météo de la semaine (`app/core/weekly_weather.py`), collective et mise en cache une fois par
  semaine (même principe que le calendrier witchy), une seule ligne partagée par tous les
  utilisateurs (`GlobalWeeklyWeatherCache`, clé = date de début de semaine) — cache invalidé par
  un `SCHEMA_VERSION` entier embarqué dans le JSON calculé et vérifié à chaque lecture
  (`weekly_weather_service.get_or_compute_weekly_weather`) : une ligne déjà en base mais écrite
  avant l'ajout d'un champ (ex. `combination_lines`, voir plus bas) est recalculée et réécrite en
  place plutôt que servie indéfiniment sous une forme périmée — sans ce garde-fou une semaine
  déjà visitée avant un déploiement pouvait silencieusement continuer à masquer les nouveaux
  champs ajoutés depuis, symptôme réellement rencontré en test (tableau des combinaisons absent
  malgré le code correct). Parcours jour par jour de la Lune, Mercure,
  Vénus et Mars (les seules planètes pertinentes à l'échelle d'une semaine — les planètes lentes
  n'y produisent aucun changement notable), ingrès détectés par comparaison quotidienne,
  rétrogradations (réutilise directement `compute_station_events` du calendrier witchy, filtré
  aux 3 planètes rapides), événements du calendrier ésotérique tombant dans la semaine (aucun
  recalcul), et aspects majeurs entre ces 4 planètes qui deviennent EXACTS pendant la semaine
  (transit-transit, recherche de racine par bissection extraite en module partagé
  `app/core/root_finding.py`, réutilisé aussi par `witchy_calendar.py`). Tous ces éléments sont
  fusionnés en une liste de **points clés notés** (même esprit que le score du calendrier witchy,
  affichés avec le composant d'étoiles unifié du site) pour prioriser ce qui compte le plus dans
  la semaine. Deux lectures LLM : `reading_type=weekly_weather` (climat collectif + impact
  personnel, ce dernier réutilisant tel quel `timing_service.compute_timing`/`compute_forecast`
  déjà spécifiés pour le Pronostic hebdomadaire — même calcul, pas de doublon) ; et
  `reading_type=weekly_weather_by_sign`, le format "horoscope de presse" classique (un
  paragraphe de 2 à 4 phrases par signe, pas une simple ligne) — chaque signe traité comme son
  propre Ascendant générique (maisons en signes intégraux), la maison générique touchée par le
  signe de l'événement principal de la semaine déterminée par `zodiac.signs_distance` (déjà
  existante, même formule mod-12 que les maisons dérivées), entièrement indépendant du thème
  natal réel de l'utilisateur. Chaque signe reçoit aussi une **note déterministe 1-5** (affichée
  en étoiles, triée du signe le mieux loti au plus discret) : la maison générique est relue comme
  l'aspect qu'elle représente structurellement depuis la maison 1 (maison N = (N-1)×30°), et
  réutilise le champ `nature` déjà défini pour cet aspect dans `aspects.json` (trigone/sextile
  "harmonieux" notés haut, quinconce "mineur inconfortable" noté bas) — même vocabulaire que
  partout ailleurs dans l'app, aucune doctrine nouvelle introduite, et la note n'entre jamais
  dans le texte généré par le LLM (qui ne fait qu'en adapter le ton).
- Météo de la semaine — **aspects vers les planètes générationnelles** (`generational_aspects`,
  `app/core/weekly_weather.py::_compute_generational_aspects`) : en plus des aspects entre
  Lune/Mercure/Vénus/Mars, détecte les aspects majeurs qui deviennent EXACTS pendant la semaine
  entre une planète rapide (Mercure/Vénus/Mars) et un point lent — Jupiter à Pluton, mais aussi
  Chiron et l'axe des Nœuds (représenté par le Nœud Nord seul, un aspect à l'un valant
  automatiquement le même aspect à l'autre) — un événement plus rare, marquant le climat
  collectif au-delà de cette seule semaine (même recherche de racine par bissection, noté un
  cran au-dessus du même aspect entre deux planètes rapides). La Lune forme aussi ces aspects
  (`moon_generational_aspects`, calcul séparé — trop fréquent pour la notation collective
  "officielle", mais réutilisé par la bibliothèque de combinaisons ci-dessous et pour repérer
  des combinaisons éditoriales ponctuelles comme Lune-Pluton).
- Météo de la semaine — **bibliothèque de combinaisons hebdomadaires** (`combination_lines`,
  `app/core/weekly_weather_combinations.py`, config dans `app/reference_data/
  weekly_combinations_library.json`) : ~10 lignes de texte français entièrement déterministes
  (formule + lookup, aucun appel LLM), affichées directement dans l'app ET injectées comme
  donnée factuelle dans le prompt de la lecture complète (le LLM les synthétise, il ne les
  régénère jamais — même principe que les `themes_confirmes` du thème natal). Cinq sources,
  par ordre de priorité : (1) combinaisons éditoriales composées, une table de configuration
  condition+texte (ex. "Mercure rétrograde + planète lente en signe de terre", "Vénus et Mars
  tous deux en aspect tendu à la même planète lente") ; (2) phrases d'aspect rapide→lente
  assemblées par formule combinable (thème de la planète rapide + modulateur selon le type
  d'aspect + thème du point lent, 2-3 variantes de phrasé sélectionnées de façon déterministe
  — pas aléatoire — pour rester reproductible) ; (3) la MÊME formule appliquée aux aspects
  ENTRE planètes rapides elles-mêmes (`transit_transit_aspects`, ex. Lune conjonction Vénus —
  réutilise `fast_planet_themes` pour les deux opérandes plutôt que `slow_point_themes` ;
  chaque aspect rapide-rapide obtient ainsi sa propre ligne descriptive, pas seulement un
  libellé technique nu comme dans le tableau séparé "Aspects entre planètes rapides") ;
  (4) degrés remarquables (critiques cardinaux/fixes/mutables, degré anarétique 29°, point
  0° Bélier) détectés sur les 4 planètes rapides, orbe serré ; (5) position de chaque planète
  rapide dans son signe, réutilisant telle quelle `planets_in_signs_full.json` — toujours
  présentes en entier, même sans aucun signal notable, les 4 autres catégories se partageant
  le reste du budget de ~10 lignes plutôt que de les évincer (les aspects lunaires vers les
  planètes lentes, structurellement bien plus fréquents que ceux des 3 autres planètes
  rapides, sont explicitement relégués en dernier parmi les aspects pour ne pas noyer le
  reste). Portée volontairement limitée au français pour cet affichage direct (comme
  `meaning_template` ailleurs dans l'app) — pensé d'abord comme matière première pour la
  lecture IA, qui elle traduit dans la langue demandée.
- Météo de la semaine — **notation par domaine de vie** (`app/core/weekly_weather_domains.py`,
  config dans `app/reference_data/weekly_domain_scoring.json`) sur le modèle classique de
  l'horoscope hebdomadaire : une note 1-5 pour chacun des domaines de vie présents (amour,
  argent, santé — incluant désormais Chiron —, travail quotidien, et optionnellement
  cheminement/évolution — l'axe des Nœuds, sans correspondance par maison, uniquement par
  planète), calculée en combinant deux composantes — les transits personnels vers le thème
  natal réel (mêmes données que le Pronostic hebdomadaire, filtrés par domaine via les maisons/
  planètes de référence de chaque domaine) et les aspects rapide→générationnelle ci-dessus
  (climat collectif, pondéré deux fois plus léger qu'un transit vraiment personnel), chacun
  pondéré selon qu'il est applicatif ou séparatif. Barème conçu pour que 1/5 et 5/5 restent
  RARES mais réellement ATTEIGNABLES par le calcul (plusieurs signaux tendus/positifs
  convergents), jamais exclus par construction — un plancher artificiel à 2/5 avait d'abord été
  découvert dans ce système ainsi que dans le calendrier ésotérique et la météo par signe (voir
  `_score_from_raw`/`_HOUSE_ASPECT_NATURE_SCORE`), corrigé partout pour la même raison : la
  prudence se joue dans la formulation du texte, jamais dans la manipulation du chiffre. Le
  plancher structurel levé, les bornes `final_scale` d'origine (-4.5/-1.5/1.5/4.5) se sont
  révélées trop larges en usage réel — mesuré sur 300 échantillons (3 profils x 20 semaines,
  climat collectif réel), elles produisaient 65.7% de notes 3 et seulement 3.0%/1.7% de notes
  1/5 : le 1/5 restait de fait quasi inatteignable sans jamais être interdit par le code, ce qui
  revient au même pour l'utilisateur. Recalibrées à -2.5/-0.5/0.5/2.5 sur le même échantillon
  (10.3%/22.7%/35.3%/21.3%/10.3%) — un seul aspect exigeant applicatif suffit désormais à
  atteindre 1/5, sans exiger la convergence de plusieurs tensions à la fois. Calcul
  entièrement déterministe (code, jamais le LLM) ; exposé via `GET /api/charts/{chart_id}/
  weekly-weather/domain-scores` (personnel, donc jamais mis en cache, contrairement à la couche
  collective) et affiché avec le même composant d'étoiles unifié. La lecture LLM `weekly_weather`
  reçoit ces notes pour en adapter le ton (jamais le chiffre cité tel quel, mais un score bas
  doit se lire clairement comme tel, pas dilué dans un optimisme de façade) et formuler un point
  fort / un point de vigilance à partir du signal le plus marquant de chaque domaine, avec les
  mêmes garde-fous que le reste de l'app (aucun conseil financier ou médical concret).
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
| GET | `/api/weekly-weather?start_date=YYYY-MM-DD` | Couche collective de la météo de la semaine (Lune/Mercure/Vénus/Mars, événements du calendrier witchy dans la semaine, points clés notés), mise en cache par semaine (défaut : aujourd'hui) |
| GET | `/api/weekly-weather/by-sign?start_date=YYYY-MM-DD` | Mapping générique maison/signe (technique "horoscope de presse") pour les 12 signes, basé sur le signe de l'événement principal de la semaine |
| GET | `/api/charts/{id}/weekly-weather/domain-scores?start_date=YYYY-MM-DD` | Notation 1-5 par domaine de vie (amour/argent/santé/travail quotidien) pour la semaine demandée, combinant transits personnels et climat collectif rapide→générationnelle — personnel donc calculé à la demande, jamais mis en cache |
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
