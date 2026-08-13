// ---------------------------------------------------------------------
// Internationalisation (fr / en / es). Ce fichier doit être chargé AVANT
// app.js dans index.html. Toute la sortie du LLM (les "lectures") est déjà
// paramétrée côté serveur par ReadingRequest.language ; ce fichier couvre le
// reste : l'interface statique et le vocabulaire de référence fermé (signes,
// planètes, aspects, maisons, lots, relations dérivées, axes thématiques).
// ---------------------------------------------------------------------

const LANG_STORAGE_KEY = "temastral_lang";
const SUPPORTED_LANGUAGES = ["fr", "en", "es"];

function getLanguage() {
  const stored = localStorage.getItem(LANG_STORAGE_KEY);
  return SUPPORTED_LANGUAGES.includes(stored) ? stored : "fr";
}

function setLanguage(lang) {
  if (!SUPPORTED_LANGUAGES.includes(lang)) return;
  localStorage.setItem(LANG_STORAGE_KEY, lang);
  document.documentElement.lang = lang;
}

// Applique les traductions à tout le HTML statique porteur d'attributs data-i18n /
// data-i18n-placeholder, et met en surbrillance le drapeau actif.
function applyStaticTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((elt) => {
    const key = elt.getAttribute("data-i18n");
    if ("i18nHtml" in elt.dataset) {
      elt.innerHTML = t(key);
    } else {
      elt.textContent = t(key);
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((elt) => {
    elt.setAttribute("placeholder", t(elt.getAttribute("data-i18n-placeholder")));
  });
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === getLanguage());
  });
}

// Renvoie une entrée {fr,en,es} dans la langue courante, avec repli sur le français.
function pick(entry) {
  if (!entry) return "";
  return entry[getLanguage()] || entry.fr || "";
}

function t(key) {
  const entry = UI_TEXT[key];
  if (!entry) {
    console.warn(`i18n: clé manquante "${key}"`);
    return key;
  }
  return pick(entry);
}

// Interpolation simple : tf("compat_time_warning", { names: "..." }) remplace {names}.
function tf(key, vars) {
  let text = t(key);
  for (const [name, value] of Object.entries(vars || {})) {
    text = text.replace(`{${name}}`, value);
  }
  return text;
}

// ---------------------------------------------------------------------
// Vocabulaire de référence fermé (signes, planètes, aspects, maisons...).
// Les clés restent les identifiants canoniques déjà utilisés par l'API
// (ex. "Taurus", "conjunction", clé de relation, code d'axe, nom de lot) —
// seul l'affichage change avec la langue, jamais les valeurs envoyées au
// serveur (zr_selected_lots, relation_key, etc. restent en clé canonique).
// ---------------------------------------------------------------------

const SIGN_NAMES = {
  Aries: { fr: "Bélier", en: "Aries", es: "Aries" },
  Taurus: { fr: "Taureau", en: "Taurus", es: "Tauro" },
  Gemini: { fr: "Gémeaux", en: "Gemini", es: "Géminis" },
  Cancer: { fr: "Cancer", en: "Cancer", es: "Cáncer" },
  Leo: { fr: "Lion", en: "Leo", es: "Leo" },
  Virgo: { fr: "Vierge", en: "Virgo", es: "Virgo" },
  Libra: { fr: "Balance", en: "Libra", es: "Libra" },
  Scorpio: { fr: "Scorpion", en: "Scorpio", es: "Escorpio" },
  Sagittarius: { fr: "Sagittaire", en: "Sagittarius", es: "Sagitario" },
  Capricorn: { fr: "Capricorne", en: "Capricorn", es: "Capricornio" },
  Aquarius: { fr: "Verseau", en: "Aquarius", es: "Acuario" },
  Pisces: { fr: "Poissons", en: "Pisces", es: "Piscis" },
};

const PLANET_NAMES = {
  Sun: { fr: "Soleil", en: "Sun", es: "Sol" },
  Moon: { fr: "Lune", en: "Moon", es: "Luna" },
  Mercury: { fr: "Mercure", en: "Mercury", es: "Mercurio" },
  Venus: { fr: "Vénus", en: "Venus", es: "Venus" },
  Mars: { fr: "Mars", en: "Mars", es: "Marte" },
  Jupiter: { fr: "Jupiter", en: "Jupiter", es: "Júpiter" },
  Saturn: { fr: "Saturne", en: "Saturn", es: "Saturno" },
  Uranus: { fr: "Uranus", en: "Uranus", es: "Urano" },
  Neptune: { fr: "Neptune", en: "Neptune", es: "Neptuno" },
  Pluto: { fr: "Pluton", en: "Pluto", es: "Plutón" },
  north_node: { fr: "Nœud Nord", en: "North Node", es: "Nodo Norte" },
  south_node: { fr: "Nœud Sud", en: "South Node", es: "Nodo Sur" },
  chiron: { fr: "Chiron", en: "Chiron", es: "Quirón" },
  lilith_mean: { fr: "Lilith", en: "Lilith", es: "Lilith" },
  ascendant: { fr: "Ascendant", en: "Ascendant", es: "Ascendente" },
  midheaven: { fr: "Milieu du Ciel", en: "Midheaven", es: "Medio Cielo" },
  descendant: { fr: "Descendant", en: "Descendant", es: "Descendente" },
  imum_coeli: { fr: "Fond du Ciel", en: "Imum Coeli", es: "Fondo del Cielo" },
};

const ASPECT_TYPE_NAMES = {
  conjunction: { fr: "Conjonction", en: "Conjunction", es: "Conjunción" },
  sextile: { fr: "Sextile", en: "Sextile", es: "Sextil" },
  square: { fr: "Carré", en: "Square", es: "Cuadratura" },
  trine: { fr: "Trigone", en: "Trine", es: "Trígono" },
  opposition: { fr: "Opposition", en: "Opposition", es: "Oposición" },
  semi_sextile: { fr: "Semi-sextile", en: "Semi-sextile", es: "Semisextil" },
  semi_square: { fr: "Semi-carré", en: "Semi-square", es: "Semicuadratura" },
  sesquiquadrate: { fr: "Sesqui-carré", en: "Sesquiquadrate", es: "Sesquicuadratura" },
  quincunx: { fr: "Quinconce", en: "Quincunx", es: "Quincuncio" },
  quintile: { fr: "Quintile", en: "Quintile", es: "Quintil" },
};

function aspectTypeLabel(type) {
  return pick(ASPECT_TYPE_NAMES[type]) || type;
}

const SIGN_SYMBOLS = {
  Aries: "♈", Taurus: "♉", Gemini: "♊", Cancer: "♋", Leo: "♌", Virgo: "♍",
  Libra: "♎", Scorpio: "♏", Sagittarius: "♐", Capricorn: "♑", Aquarius: "♒", Pisces: "♓",
};

const PLANET_SYMBOLS = {
  Sun: "☉", Moon: "☽", Mercury: "☿", Venus: "♀", Mars: "♂",
  Jupiter: "♃", Saturn: "♄", Uranus: "⛢", Neptune: "♆", Pluto: "♇",
  north_node: "☊", south_node: "☋", chiron: "⚷", lilith_mean: "⚸",
};

function signLabel(sign) {
  return `${SIGN_SYMBOLS[sign] || ""} ${pick(SIGN_NAMES[sign]) || sign}`;
}

function planetLabel(name) {
  return pick(PLANET_NAMES[name]) || name;
}

const ASTRO_LINE_TYPE_NAMES = {
  ASC: { fr: "Ascendant", en: "Ascendant", es: "Ascendente" },
  DC: { fr: "Descendant", en: "Descendant", es: "Descendente" },
  MC: { fr: "Milieu du Ciel", en: "Midheaven", es: "Medio Cielo" },
  IC: { fr: "Fond du Ciel", en: "Imum Coeli", es: "Fondo del Cielo" },
};

function astroLineTypeLabel(lineType) {
  return pick(ASTRO_LINE_TYPE_NAMES[lineType]) || lineType;
}

const HOUSE_KEYWORDS = {
  1: { fr: "identité", en: "identity", es: "identidad" },
  2: { fr: "ressources", en: "resources", es: "recursos" },
  3: { fr: "communication", en: "communication", es: "comunicación" },
  4: { fr: "foyer", en: "home", es: "hogar" },
  5: { fr: "création", en: "creation", es: "creación" },
  6: { fr: "quotidien", en: "daily life", es: "vida cotidiana" },
  7: { fr: "partenariat", en: "partnership", es: "asociación" },
  8: { fr: "transformation", en: "transformation", es: "transformación" },
  9: { fr: "expansion", en: "expansion", es: "expansión" },
  10: { fr: "vocation", en: "vocation", es: "vocación" },
  11: { fr: "communauté", en: "community", es: "comunidad" },
  12: { fr: "transcendance", en: "transcendence", es: "trascendencia" },
};

// Clé = nom canonique du lot (identique dans les 3 langues pour les échanges API :
// zr_selected_lots envoie toujours la clé, jamais le libellé traduit).
const LOT_LABELS = {
  Fortune: { fr: "Fortune", en: "Fortune", es: "Fortuna" },
  Esprit: { fr: "Esprit", en: "Spirit", es: "Espíritu" },
  "Éros": { fr: "Éros", en: "Eros", es: "Eros" },
  "Nécessité": { fr: "Nécessité", en: "Necessity", es: "Necesidad" },
  Courage: { fr: "Courage", en: "Courage", es: "Coraje" },
  Victoire: { fr: "Victoire", en: "Victory", es: "Victoria" },
  "Némésis": { fr: "Némésis", en: "Nemesis", es: "Némesis" },
  Base: { fr: "Base", en: "Foundation", es: "Base" },
  Mort: { fr: "Mort", en: "Death", es: "Muerte" },
  Substance: { fr: "Substance", en: "Substance", es: "Sustancia" },
  Amis: { fr: "Amis", en: "Friends", es: "Amigos" },
  Mariage: { fr: "Mariage", en: "Marriage", es: "Matrimonio" },
  Enfants: { fr: "Enfants", en: "Children", es: "Hijos" },
  "Père": { fr: "Père", en: "Father", es: "Padre" },
  "Mère": { fr: "Mère", en: "Mother", es: "Madre" },
  Voyages: { fr: "Voyages", en: "Travel", es: "Viajes" },
  Maladie: { fr: "Maladie", en: "Sickness", es: "Enfermedad" },
};

const LOT_SIGNIFICATIONS = {
  Fortune: {
    fr: "corps, vitalité, bien-être matériel, circonstances extérieures",
    en: "body, vitality, material well-being, outer circumstances",
    es: "cuerpo, vitalidad, bienestar material, circunstancias externas",
  },
  Esprit: {
    fr: "volonté, vocation, choix, action consciente",
    en: "will, vocation, choices, conscious action",
    es: "voluntad, vocación, elecciones, acción consciente",
  },
  "Éros": {
    fr: "désir, amour, attraction, passion",
    en: "desire, love, attraction, passion",
    es: "deseo, amor, atracción, pasión",
  },
  "Nécessité": {
    fr: "contraintes, obligations, ce qui doit être enduré",
    en: "constraints, obligations, what must be endured",
    es: "restricciones, obligaciones, lo que debe soportarse",
  },
  Courage: {
    fr: "audace, initiative, capacité à agir face au risque",
    en: "boldness, initiative, ability to act in the face of risk",
    es: "audacia, iniciativa, capacidad de actuar ante el riesgo",
  },
  Victoire: {
    fr: "succès, reconnaissance, récompense de l'effort",
    en: "success, recognition, reward for effort",
    es: "éxito, reconocimiento, recompensa del esfuerzo",
  },
  "Némésis": {
    fr: "adversité, épreuves, conséquences, ce qui remet en question",
    en: "adversity, trials, consequences, what challenges you",
    es: "adversidad, pruebas, consecuencias, lo que cuestiona",
  },
  Base: {
    fr: "fondations de vie, stabilité, origine profonde",
    en: "life foundations, stability, deep origins",
    es: "fundamentos de vida, estabilidad, origen profundo",
  },
  Mort: {
    fr: "transformation profonde, fin de cycle",
    en: "deep transformation, end of a cycle",
    es: "transformación profunda, fin de ciclo",
  },
  Substance: {
    fr: "richesse, ressources durables, biens matériels",
    en: "wealth, lasting resources, material assets",
    es: "riqueza, recursos duraderos, bienes materiales",
  },
  Amis: {
    fr: "amitié, alliés, réseau de soutien",
    en: "friendship, allies, support network",
    es: "amistad, aliados, red de apoyo",
  },
  Mariage: {
    fr: "union, engagement conjugal",
    en: "union, marital commitment",
    es: "unión, compromiso conyugal",
  },
  Enfants: {
    fr: "fécondité, relation aux enfants",
    en: "fertility, relationship to children",
    es: "fertilidad, relación con los hijos",
  },
  "Père": {
    fr: "relation au père, autorité",
    en: "relationship to the father, authority",
    es: "relación con el padre, autoridad",
  },
  "Mère": {
    fr: "relation à la mère, fonction nourricière",
    en: "relationship to the mother, nurturing function",
    es: "relación con la madre, función nutricia",
  },
  Voyages: {
    fr: "déplacements, expansion géographique et philosophique",
    en: "travel, geographic and philosophical expansion",
    es: "desplazamientos, expansión geográfica y filosófica",
  },
  Maladie: {
    fr: "vulnérabilités de santé",
    en: "health vulnerabilities",
    es: "vulnerabilidades de salud",
  },
};

function lotLabel(name) {
  return pick(LOT_LABELS[name]) || name;
}

function lotSignification(name) {
  return pick(LOT_SIGNIFICATIONS[name]) || name;
}

// Clé = relation_key canonique (voir app/reference_data/derived_house_relations.json).
const DERIVED_RELATION_LABELS = {
  sibling: { fr: "Frères/sœurs", en: "Siblings", es: "Hermanos" },
  mother: { fr: "Mère", en: "Mother", es: "Madre" },
  child: { fr: "Enfants", en: "Children", es: "Hijos" },
  partner: { fr: "Partenaire", en: "Partner", es: "Pareja" },
  father: { fr: "Père", en: "Father", es: "Padre" },
  father_hellenistic: {
    fr: "Père (tradition hellénistique, M4)",
    en: "Father (Hellenistic tradition, H4)",
    es: "Padre (tradición helenística, C4)",
  },
  friend: { fr: "Amis", en: "Friends", es: "Amigos" },
  business_partner: { fr: "Associé d'affaires", en: "Business partner", es: "Socio de negocios" },
  authority: {
    fr: "Supérieur hiérarchique / figure d'autorité",
    en: "Superior / authority figure",
    es: "Superior jerárquico / figura de autoridad",
  },
  employee: { fr: "Employé / subordonné", en: "Employee / subordinate", es: "Empleado / subordinado" },
  rival: { fr: "Rival / ennemi déclaré", en: "Rival / declared enemy", es: "Rival / enemigo declarado" },
  neighbor: { fr: "Voisin", en: "Neighbor", es: "Vecino" },
  network: { fr: "Groupe / réseau / association", en: "Group / network / association", es: "Grupo / red / asociación" },
  hidden_enemy: {
    fr: "Ennemi caché / adversaire secret",
    en: "Hidden enemy / secret adversary",
    es: "Enemigo oculto / adversario secreto",
  },
  belle_famille: {
    fr: "Belle-mère / beau-père (parents du partenaire)",
    en: "Parents-in-law (partner's parents)",
    es: "Suegros (padres de la pareja)",
  },
  grand_mere_maternelle: {
    fr: "Grand-mère maternelle (mère de la mère)",
    en: "Maternal grandmother (mother's mother)",
    es: "Abuela materna (madre de la madre)",
  },
  grand_pere_paternel: {
    fr: "Grand-père paternel (père du père)",
    en: "Paternal grandfather (father's father)",
    es: "Abuelo paterno (padre del padre)",
  },
  neveux_nieces: {
    fr: "Neveux / nièces (enfants de la fratrie)",
    en: "Nephews / nieces (siblings' children)",
    es: "Sobrinos (hijos de los hermanos)",
  },
  beaux_freres_soeurs: {
    fr: "Beaux-frères / belles-sœurs (fratrie du partenaire)",
    en: "Siblings-in-law (partner's siblings)",
    es: "Cuñados (hermanos de la pareja)",
  },
  petits_enfants: {
    fr: "Petits-enfants (enfants des enfants)",
    en: "Grandchildren (children's children)",
    es: "Nietos (hijos de los hijos)",
  },
  patron_partenaire: {
    fr: "Patron du partenaire",
    en: "Partner's boss",
    es: "Jefe de la pareja",
  },
};

function derivedRelationLabel(key, fallback) {
  return pick(DERIVED_RELATION_LABELS[key]) || fallback || key;
}

// Clé = code d'axe thématique (voir app/reference_data/axes_thematiques_lots.json).
const AXIS_LABELS = {
  famille_racines: { fr: "Famille & Racines", en: "Family & Roots", es: "Familia y Raíces" },
  corps_circonstances: {
    fr: "Corps & Circonstances matérielles",
    en: "Body & Material Circumstances",
    es: "Cuerpo y Circunstancias materiales",
  },
  amour_relations: { fr: "Amour & Relations intimes", en: "Love & Intimate Relationships", es: "Amor y Relaciones íntimas" },
  vocation_reussite: { fr: "Vocation & Réussite", en: "Vocation & Success", es: "Vocación y Éxito" },
  epreuves_resilience: { fr: "Épreuves & Résilience", en: "Trials & Resilience", es: "Pruebas y Resiliencia" },
  ouverture_reseau: { fr: "Ouverture & Réseau", en: "Openness & Network", es: "Apertura y Red" },
  vue_complete: { fr: "Vue complète", en: "Full view", es: "Vista completa" },
};

function axisLabel(code, fallback) {
  return pick(AXIS_LABELS[code]) || fallback || code;
}

const ELEMENT_LABELS = {
  fire: { fr: "🔥 Feu", en: "🔥 Fire", es: "🔥 Fuego" },
  earth: { fr: "🌍 Terre", en: "🌍 Earth", es: "🌍 Tierra" },
  air: { fr: "💨 Air", en: "💨 Air", es: "💨 Aire" },
  water: { fr: "💧 Eau", en: "💧 Water", es: "💧 Agua" },
};

const MODALITY_LABELS = {
  cardinal: { fr: "Cardinal", en: "Cardinal", es: "Cardinal" },
  fixed: { fr: "Fixe", en: "Fixed", es: "Fijo" },
  mutable: { fr: "Mutable", en: "Mutable", es: "Mutable" },
};

const TRAIT_ORIGIN_LABELS = {
  ascendant: { fr: "Ascendant", en: "Ascendant", es: "Ascendente" },
  sun: { fr: "Soleil", en: "Sun", es: "Sol" },
  moon: { fr: "Lune", en: "Moon", es: "Luna" },
  mercury: { fr: "Mercure", en: "Mercury", es: "Mercurio" },
  venus: { fr: "Vénus", en: "Venus", es: "Venus" },
  mars: { fr: "Mars", en: "Mars", es: "Marte" },
  jupiter: { fr: "Jupiter", en: "Jupiter", es: "Júpiter" },
  saturn: { fr: "Saturne", en: "Saturn", es: "Saturno" },
  dominant_element: { fr: "Élément dominant", en: "Dominant element", es: "Elemento dominante" },
  dominant_modality: { fr: "Modalité dominante", en: "Dominant modality", es: "Modalidad dominante" },
};

const FAVORABILITY_LABELS = {
  favorable: { fr: "Favorable", en: "Favorable", es: "Favorable" },
  a_nuancer: { fr: "À nuancer", en: "Mixed", es: "Matizable" },
  exigeant: { fr: "Exigeant", en: "Demanding", es: "Exigente" },
  instable: { fr: "Instable", en: "Unstable", es: "Inestable" },
  intense: { fr: "Intense", en: "Intense", es: "Intenso" },
  neutre: { fr: "Neutre", en: "Neutral", es: "Neutro" },
};

// Clé = libellé brut renvoyé par l'API (synastry_compatibility.json n'a pas de version
// canonique/anglaise pour ce champ) — traduction par correspondance exacte de chaîne.
const SIGNIFICATOR_WEIGHT_LABELS = {
  "très fort": { fr: "très fort", en: "very strong", es: "muy fuerte" },
  "fort": { fr: "fort", en: "strong", es: "fuerte" },
  "fort (symbolique)": { fr: "fort (symbolique)", en: "strong (symbolic)", es: "fuerte (simbólico)" },
  "moyen": { fr: "moyen", en: "medium", es: "medio" },
  "faible": { fr: "faible", en: "weak", es: "débil" },
};

function significatorWeightLabel(weight) {
  return pick(SIGNIFICATOR_WEIGHT_LABELS[weight]) || weight;
}

const COMPAT_MODE_LABELS = {
  romantic: { fr: "amoureuse", en: "romantic", es: "romántica" },
  friendship: { fr: "amicale", en: "friendship", es: "de amistad" },
  professional: { fr: "professionnelle", en: "professional", es: "profesional" },
};

// Doit rester synchronisé avec COMPATIBILITY_RATING_AXES dans app/services/interpretation_service.py.
const COMPAT_RATING_AXES = {
  romantic: [
    { key: "passion_alchimie", label: { fr: "Passion & alchimie", en: "Passion & chemistry", es: "Pasión y química" } },
    { key: "complicite_emotionnelle", label: { fr: "Complicité émotionnelle", en: "Emotional closeness", es: "Complicidad emocional" } },
    { key: "engagement_duree", label: { fr: "Engagement & durabilité", en: "Commitment & longevity", es: "Compromiso y duración" } },
    { key: "valeurs_partagees", label: { fr: "Valeurs partagées", en: "Shared values", es: "Valores compartidos" } },
  ],
  friendship: [
    { key: "complicite_humour", label: { fr: "Complicité & humour", en: "Closeness & humor", es: "Complicidad y humor" } },
    { key: "confort_relationnel", label: { fr: "Confort relationnel", en: "Relational comfort", es: "Confort relacional" } },
    { key: "plaisir_partage", label: { fr: "Plaisir partagé", en: "Shared enjoyment", es: "Placer compartido" } },
    { key: "stimulation_intellectuelle", label: { fr: "Stimulation intellectuelle", en: "Intellectual stimulation", es: "Estimulación intelectual" } },
  ],
  professional: [
    { key: "communication_pro", label: { fr: "Communication professionnelle", en: "Professional communication", es: "Comunicación profesional" } },
    { key: "rigueur_fiabilite", label: { fr: "Rigueur & fiabilité partagées", en: "Shared rigor & reliability", es: "Rigor y fiabilidad compartidos" } },
    { key: "rythme_travail", label: { fr: "Rythme de travail", en: "Work pace", es: "Ritmo de trabajo" } },
    { key: "reconnaissance_croissance", label: { fr: "Reconnaissance & croissance mutuelle", en: "Recognition & mutual growth", es: "Reconocimiento y crecimiento mutuo" } },
  ],
};

function compatRatingAxes(mode) {
  return (COMPAT_RATING_AXES[mode] || []).map((axis) => ({ key: axis.key, label: pick(axis.label) }));
}

const TIMING_RATING_AXES = [
  { key: "amour", label: { fr: "Amour", en: "Love", es: "Amor" } },
  { key: "amitie", label: { fr: "Amitié", en: "Friendship", es: "Amistad" } },
  { key: "professionnel", label: { fr: "Professionnel", en: "Professional", es: "Profesional" } },
  { key: "sante", label: { fr: "Santé", en: "Health", es: "Salud" } },
  { key: "developpement_personnel", label: { fr: "Développement personnel", en: "Personal growth", es: "Desarrollo personal" } },
];

function timingRatingAxes() {
  return TIMING_RATING_AXES.map((axis) => ({ key: axis.key, label: pick(axis.label) }));
}

// ---------------------------------------------------------------------
// Interface statique (boutons, libellés, en-têtes, messages).
// ---------------------------------------------------------------------
const UI_TEXT = {
  app_title: { fr: "✨ Temastral", en: "✨ Temastral", es: "✨ Temastral" },
  app_subtitle: {
    fr: "Calcul de thème natal (Swiss Ephemeris) &amp; lecture interprétée par IA",
    en: "Natal chart calculation (Swiss Ephemeris) &amp; AI-interpreted reading",
    es: "Cálculo de carta natal (Swiss Ephemeris) y lectura interpretada por IA",
  },
  footer_note: {
    fr: "Calculs déterministes (Swiss Ephemeris) — l'interprétation est générée par un modèle de langage et doit être lue comme un éclairage, pas une prédiction absolue.",
    en: "Deterministic calculations (Swiss Ephemeris) — the interpretation is generated by a language model and should be read as insight, not an absolute prediction.",
    es: "Cálculos deterministas (Swiss Ephemeris) — la interpretación es generada por un modelo de lenguaje y debe leerse como una perspectiva, no una predicción absoluta.",
  },

  section1_title: { fr: "1. Données de naissance", en: "1. Birth data", es: "1. Datos de nacimiento" },
  label_name: { fr: "Nom (optionnel)", en: "Name (optional)", es: "Nombre (opcional)" },
  placeholder_name: { fr: "Ex. Benoît", en: "E.g. John", es: "Ej. Juan" },
  label_birth_date: { fr: "Date de naissance", en: "Birth date", es: "Fecha de nacimiento" },
  label_birth_time: { fr: "Heure de naissance", en: "Birth time", es: "Hora de nacimiento" },
  label_time_unknown: {
    fr: "Heure inconnue (maisons/angles approximatifs)",
    en: "Unknown time (approximate houses/angles)",
    es: "Hora desconocida (casas/ángulos aproximados)",
  },
  label_birth_city: { fr: "Ville de naissance", en: "Birth city", es: "Ciudad de nacimiento" },
  placeholder_city: { fr: "Ex. Lyon, France", en: "E.g. London, UK", es: "Ej. Madrid, España" },
  btn_search: { fr: "Rechercher", en: "Search", es: "Buscar" },
  label_latitude: { fr: "Latitude", en: "Latitude", es: "Latitud" },
  label_longitude: { fr: "Longitude", en: "Longitude", es: "Longitud" },
  label_timezone: { fr: "Fuseau horaire", en: "Timezone", es: "Zona horaria" },
  loading: { fr: "Chargement...", en: "Loading...", es: "Cargando..." },
  advanced_options: { fr: "Options avancées", en: "Advanced options", es: "Opciones avanzadas" },
  label_house_system: { fr: "Système de maisons", en: "House system", es: "Sistema de casas" },
  house_system_placidus: { fr: "Placidus", en: "Placidus", es: "Placidus" },
  house_system_whole_sign: { fr: "Signes intégraux", en: "Whole Sign", es: "Signos enteros" },
  house_system_koch: { fr: "Koch", en: "Koch", es: "Koch" },
  house_system_equal: { fr: "Maisons égales", en: "Equal houses", es: "Casas iguales" },
  house_system_regiomontanus: { fr: "Regiomontanus", en: "Regiomontanus", es: "Regiomontano" },
  label_rulership_system: { fr: "Dispositeurs", en: "Rulerships", es: "Regencias" },
  rulership_both: { fr: "Traditionnel + moderne", en: "Traditional + modern", es: "Tradicional + moderno" },
  rulership_traditional: { fr: "Traditionnel", en: "Traditional", es: "Tradicional" },
  rulership_modern: { fr: "Moderne", en: "Modern", es: "Moderno" },
  label_optional_points: { fr: "Points additionnels", en: "Additional points", es: "Puntos adicionales" },
  point_north_node: { fr: "Nœud Nord", en: "North Node", es: "Nodo Norte" },
  point_south_node: { fr: "Nœud Sud", en: "South Node", es: "Nodo Sur" },
  point_chiron: { fr: "Chiron", en: "Chiron", es: "Quirón" },
  point_lilith: { fr: "Lilith moyenne", en: "Mean Lilith", es: "Lilith media" },
  btn_calculate_chart: { fr: "Calculer le thème natal", en: "Calculate natal chart", es: "Calcular la carta natal" },
  status_calculating: { fr: "Calcul en cours...", en: "Calculating...", es: "Calculando..." },
  no_results: { fr: "Aucun résultat. Saisissez les coordonnées manuellement.", en: "No results. Enter coordinates manually.", es: "Sin resultados. Introduce las coordenadas manualmente." },
  search_unavailable: {
    fr: "Recherche indisponible — saisissez les coordonnées manuellement.",
    en: "Search unavailable — enter coordinates manually.",
    es: "Búsqueda no disponible — introduce las coordenadas manualmente.",
  },

  section2_title: { fr: "2. Thème natal", en: "2. Natal chart", es: "2. Carta natal" },
  tab_wheel: { fr: "Roue", en: "Wheel", es: "Rueda" },
  tab_planets: { fr: "Planètes", en: "Planets", es: "Planetas" },
  tab_houses: { fr: "Maisons", en: "Houses", es: "Casas" },
  tab_aspects: { fr: "Aspects", en: "Aspects", es: "Aspectos" },
  tab_balance: { fr: "Éléments", en: "Elements", es: "Elementos" },
  modalities_title: { fr: "Modalités", en: "Modalities", es: "Modalidades" },
  tab_dispositors: { fr: "Dispositeurs", en: "Rulerships", es: "Regencias" },

  section3_title: { fr: "3. Lecture interprétée", en: "3. Interpreted reading", es: "3. Lectura interpretada" },
  reading_section_intro: {
    fr: "Chaque catégorie ci-dessous a son propre prompt d'interprétation, focalisé sur sa technique : la lecture générale ne voit que le thème de base (planètes, maisons, aspects, dispositeurs), pas les lots ni les maisons dérivées.",
    en: "Each category below has its own interpretation prompt, focused on its technique: the general reading only sees the base chart (planets, houses, aspects, rulerships), not the lots or derived houses.",
    es: "Cada categoría siguiente tiene su propio prompt de interpretación, centrado en su técnica: la lectura general solo ve la carta base (planetas, casas, aspectos, regencias), no las suertes ni las casas derivadas.",
  },
  reading_tab_global: { fr: "Générale", en: "General", es: "General" },
  reading_tab_lots: { fr: "Lots", en: "Lots", es: "Suertes" },
  reading_tab_derived: { fr: "Maisons dérivées", en: "Derived houses", es: "Casas derivadas" },
  reading_tab_timing: { fr: "Pronostic", en: "Forecast", es: "Pronóstico" },
  reading_tab_compatibility: { fr: "Compatibilité", en: "Compatibility", es: "Compatibilidad" },

  label_focus_areas: { fr: "Zones à couvrir", en: "Areas to cover", es: "Áreas a cubrir" },
  focus_general: { fr: "Vue d'ensemble", en: "Overview", es: "Visión general" },
  focus_love: { fr: "Amour", en: "Love", es: "Amor" },
  focus_career: { fr: "Carrière", en: "Career", es: "Carrera" },
  focus_family: { fr: "Famille", en: "Family", es: "Familia" },
  btn_generate_reading: { fr: "Générer la lecture", en: "Generate reading", es: "Generar lectura" },
  status_generating: { fr: "Génération en cours...", en: "Generating...", es: "Generando..." },
  error_calculate_chart_first: { fr: "Calculez d'abord un thème natal.", en: "Calculate a natal chart first.", es: "Primero calcula una carta natal." },
  error_select_focus_area: { fr: "Sélectionnez au moins une zone.", en: "Select at least one area.", es: "Selecciona al menos un área." },

  btn_generate_lots_reading: { fr: "Générer la lecture des lots", en: "Generate lots reading", es: "Generar lectura de suertes" },
  zr_section_title: { fr: "Phases de vie (Libération zodiacale)", en: "Life phases (Zodiacal Releasing)", es: "Fases de vida (Liberación zodiacal)" },
  zr_section_intro: {
    fr: "Technique de timing hellénistique distincte des lots ci-dessus : elle découpe la vie en grandes périodes (L1) et sous-périodes (L2), calculées ici pour chacun des 17 lots. Formellement définie pour le lot Fortune et le lot Esprit ; son application aux autres lots est une extension exploratoire du même algorithme à un domaine de vie plus précis.",
    en: "Hellenistic timing technique distinct from the lots above: it divides life into major periods (L1) and sub-periods (L2), computed here for each of the 17 lots. Formally defined for the Fortune and Spirit lots; its application to other lots is an exploratory extension of the same algorithm to a more specific life domain.",
    es: "Técnica de timing helenística distinta de las suertes anteriores: divide la vida en grandes períodos (L1) y subperíodos (L2), calculados aquí para cada una de las 17 suertes. Formalmente definida para las suertes de la Fortuna y el Espíritu; su aplicación a otras suertes es una extensión exploratoria del mismo algoritmo a un ámbito de vida más específico.",
  },
  zr_mode_current: { fr: "Vue actuelle", en: "Current view", es: "Vista actual" },
  zr_mode_predictive: { fr: "Prévisionnelle (10 ans)", en: "Forecast (10 years)", es: "Previsional (10 años)" },
  btn_generate_zr_reading: { fr: "Générer la lecture des phases", en: "Generate phases reading", es: "Generar lectura de fases" },
  zr_axis_intro: { fr: "Axes thématiques (raccourcis de sélection, projection 10 ans) :", en: "Thematic axes (selection shortcuts, 10-year projection):", es: "Ejes temáticos (atajos de selección, proyección a 10 años):" },
  zr_relations_group_direct: { fr: "Relations directes", en: "Direct relations", es: "Relaciones directas" },
  zr_hint_check_lots: {
    fr: "Cochez un ou plusieurs lots ci-dessous pour la lecture (par défaut : Fortune + Esprit), ou utilisez un axe thématique ci-dessus comme raccourci de sélection. Un seul lot coché donne une lecture approfondie ; plusieurs lots ajoutent une lecture croisée entre eux.",
    en: "Check one or more lots below for the reading (default: Fortune + Spirit), or use a thematic axis above as a selection shortcut. A single checked lot gives an in-depth reading; several lots add a cross-reading between them.",
    es: "Marca una o varias suertes a continuación para la lectura (por defecto: Fortuna + Espíritu), o usa un eje temático arriba como atajo de selección. Una sola suerte marcada da una lectura profunda; varias suertes añaden una lectura cruzada entre ellas.",
  },
  zr_error_same_sign: {
    fr: "Fortune et Esprit dans le même signe : le calcul du lot Esprit a été décalé d'un signe, selon la convention documentée.",
    en: "Fortune and Spirit in the same sign: the Spirit lot calculation was shifted by one sign, per the documented convention.",
    es: "Fortuna y Espíritu en el mismo signo: el cálculo de la suerte del Espíritu se desplazó un signo, según la convención documentada.",
  },
  zr_error_no_lot_selected: { fr: "Cochez au moins un lot pour générer une lecture.", en: "Check at least one lot to generate a reading.", es: "Marca al menos una suerte para generar una lectura." },
  zr_view_phases: { fr: "Voir les phases", en: "View phases", es: "Ver fases" },
  zr_l1_current: { fr: "Phase L1 en cours", en: "Current L1 phase", es: "Fase L1 actual" },
  zr_l2_current: { fr: "Sous-phase L2 en cours", en: "Current L2 sub-phase", es: "Subfase L2 actual" },
  zr_l2_detail: { fr: "Détail des sous-phases L2 de la phase L1 en cours", en: "Detail of L2 sub-phases within the current L1 phase", es: "Detalle de las subfases L2 de la fase L1 actual" },
  zr_peak_period: { fr: "Période de pointe", en: "Peak period", es: "Período de pico" },
  zr_peak: { fr: "Pointe", en: "Peak", es: "Pico" },
  zr_loosing_of_bond: { fr: "Déliement du lien", en: "Loosing of the bond", es: "Liberación del vínculo" },
  zr_loosing: { fr: "Déliement", en: "Loosing", es: "Liberación" },
  zr_master: { fr: "maître", en: "ruler", es: "regente" },
  zr_no_period_available: { fr: "aucune période disponible.", en: "no period available.", es: "sin período disponible." },
  th_sign: { fr: "Signe", en: "Sign", es: "Signo" },
  th_period: { fr: "Période", en: "Period", es: "Período" },
  btn_recalculate: { fr: "Recalculer", en: "Recalculate", es: "Recalcular" },
  label_date: { fr: "Date", en: "Date", es: "Fecha" },
  status_computing_phases: { fr: "Calcul en cours (phases et sous-phases)...", en: "Computing (phases and sub-phases)...", es: "Calculando (fases y subfases)..." },
  error_loading_phases: { fr: "Impossible de charger les phases :", en: "Could not load phases:", es: "No se pudieron cargar las fases:" },

  btn_generate_derived_reading: { fr: "Générer la lecture des maisons dérivées", en: "Generate derived houses reading", es: "Generar lectura de casas derivadas" },
  label_relation_to_analyze: { fr: "Relation à analyser", en: "Relation to analyze", es: "Relación a analizar" },
  zr_relations_group_second_order: { fr: "Relations de second ordre", en: "Second-order relations", es: "Relaciones de segundo orden" },
  option_custom_relation: { fr: "Autre (avancé : composer une relation)…", en: "Other (advanced: build a relation)…", es: "Otra (avanzado: componer una relación)…" },
  label_from_whom: { fr: "À partir de qui", en: "Starting from whom", es: "A partir de quién" },
  label_which_relation: { fr: "Quelle relation de cette personne", en: "Which relation of that person", es: "Qué relación de esa persona" },
  derived_house_explainer: {
    fr: "La maison de référence elle-même est la maison 1 (identité) de la personne représentée ; la maison suivante est sa maison 2 (ressources), etc.",
    en: "The reference house itself is house 1 (identity) of the represented person; the next house is their house 2 (resources), etc.",
    es: "La casa de referencia misma es la casa 1 (identidad) de la persona representada; la siguiente casa es su casa 2 (recursos), etc.",
  },
  derived_houses_unavailable: { fr: "Maisons dérivées non disponibles.", en: "Derived houses unavailable.", es: "Casas derivadas no disponibles." },
  th_my_natal_house: { fr: "Ma maison natale", en: "My natal house", es: "Mi casa natal" },
  th_represents_for_them: { fr: "Représente, pour elle", en: "Represents, for them", es: "Representa, para ella" },
  th_relevant_natal_planets: { fr: "Planètes natales concernées", en: "Relevant natal planets", es: "Planetas natales relevantes" },
  their_house: { fr: "Sa maison", en: "Their house", es: "Su casa" },

  timing_section_intro: {
    fr: "Toutes les planètes (Lune, Mercure, Vénus, Soleil et Mars compris) sont prises en compte : l'horizon reste borné aux douze prochains mois, donc même les transits rapides restent pertinents à afficher.",
    en: "All planets (including Moon, Mercury, Venus, Sun and Mars) are taken into account: the horizon stays bounded to the next twelve months, so even fast transits remain worth showing.",
    es: "Se tienen en cuenta todos los planetas (incluidos Luna, Mercurio, Venus, Sol y Marte): el horizonte se mantiene limitado a los próximos doce meses, por lo que incluso los tránsitos rápidos siguen siendo relevantes.",
  },
  timing_btn_week: { fr: "Lecture de la semaine", en: "Weekly reading", es: "Lectura de la semana" },
  timing_hint_week: { fr: "(plus précise)", en: "(more precise)", es: "(más precisa)" },
  timing_btn_month: { fr: "Lecture du mois", en: "Monthly reading", es: "Lectura del mes" },
  timing_btn_year: { fr: "Lecture des 12 prochains mois", en: "Next 12 months reading", es: "Lectura de los próximos 12 meses" },
  timing_hint_year: { fr: "(plus globale)", en: "(more global)", es: "(más global)" },
  timing_upcoming_events_title: { fr: "Transits à venir (12 prochains mois)", en: "Upcoming transits (next 12 months)", es: "Tránsitos próximos (12 meses siguientes)" },
  label_min_intensity: { fr: "Intensité minimale", en: "Minimum intensity", es: "Intensidad mínima" },
  intensity_4_only: { fr: "🔥🔥🔥🔥 uniquement", en: "🔥🔥🔥🔥 only", es: "🔥🔥🔥🔥 únicamente" },
  intensity_3_plus: { fr: "🔥🔥🔥 et plus (recommandé)", en: "🔥🔥🔥 and above (recommended)", es: "🔥🔥🔥 o más (recomendado)" },
  intensity_2_plus: { fr: "🔥🔥 et plus", en: "🔥🔥 and above", es: "🔥🔥 o más" },
  intensity_all: { fr: "Tous, y compris les transits mineurs", en: "All, including minor transits", es: "Todos, incluidos los tránsitos menores" },
  timing_profection_title: { fr: "Profection de l'année", en: "Annual profection", es: "Profección del año" },
  timing_transiting_planets_title: { fr: "Planètes en transit", en: "Transiting planets", es: "Planetas en tránsito" },
  timing_active_aspects_title: { fr: "Aspects actifs vers le thème natal", en: "Active aspects to the natal chart", es: "Aspectos activos hacia la carta natal" },
  th_intensity: { fr: "Intensité", en: "Intensity", es: "Intensidad" },
  th_transit: { fr: "Transit", en: "Transit", es: "Tránsito" },
  th_aspect: { fr: "Aspect", en: "Aspect", es: "Aspecto" },
  th_natal_point: { fr: "Point natal", en: "Natal point", es: "Punto natal" },
  th_active_window: { fr: "Fenêtre active", en: "Active window", es: "Ventana activa" },
  th_trend: { fr: "Tendance", en: "Trend", es: "Tendencia" },
  th_detail: { fr: "Détail", en: "Detail", es: "Detalle" },
  th_planet: { fr: "Planète", en: "Planet", es: "Planeta" },
  th_position: { fr: "Position", en: "Position", es: "Posición" },
  th_movement: { fr: "Mouvement", en: "Movement", es: "Movimiento" },
  no_transit_at_intensity: { fr: "Aucun transit à ce niveau d'intensité sur les 12 prochains mois.", en: "No transit at this intensity level over the next 12 months.", es: "Ningún tránsito con este nivel de intensidad en los próximos 12 meses." },
  no_active_aspect: { fr: "Aucun aspect actif avec l'orbe utilisé (3°).", en: "No active aspect with the orb used (3°).", es: "Ningún aspecto activo con el orbe usado (3°)." },
  status_computing_timing: { fr: "Calcul en cours (transits + prévisions sur l'année)...", en: "Computing (transits + yearly forecast)...", es: "Calculando (tránsitos + previsión del año)..." },
  error_loading_timing: { fr: "Impossible de charger le timing :", en: "Could not load timing:", es: "No se pudo cargar el timing:" },

  compat_section_intro: {
    fr: "Calcule la compatibilité entre le thème ci-dessus et celui d'une deuxième personne, à partir de trois techniques : aspects croisés entre les deux thèmes, chevauchement de maisons, et thème composite (la relation vue comme une entité à part entière). Choisissez d'abord le type de relation — les significateurs pertinents changent radicalement selon le contexte — puis sélectionnez ou créez le second thème.",
    en: "Computes compatibility between the chart above and a second person's, using three techniques: cross-aspects between the two charts, house overlay, and composite chart (the relationship seen as an entity in its own right). First choose the relationship type — the relevant significators change radically depending on context — then select or create the second chart.",
    es: "Calcula la compatibilidad entre la carta anterior y la de una segunda persona, mediante tres técnicas: aspectos cruzados entre ambas cartas, superposición de casas y carta compuesta (la relación vista como una entidad propia). Primero elige el tipo de relación — los significadores relevantes cambian radicalmente según el contexto — y luego selecciona o crea la segunda carta.",
  },
  label_relation_type: { fr: "Type de relation", en: "Relationship type", es: "Tipo de relación" },
  compat_mode_romantic: { fr: "Amoureuse", en: "Romantic", es: "Romántica" },
  compat_mode_friendship: { fr: "Amitié", en: "Friendship", es: "Amistad" },
  compat_mode_professional: { fr: "Professionnelle", en: "Professional", es: "Profesional" },
  label_second_person: { fr: "Deuxième personne", en: "Second person", es: "Segunda persona" },
  option_select_existing_chart: { fr: "— Sélectionner une carte existante —", en: "— Select an existing chart —", es: "— Seleccionar una carta existente —" },
  btn_create_new_chart: { fr: "+ Créer une nouvelle carte", en: "+ Create a new chart", es: "+ Crear una nueva carta" },
  compat_second_person_title: { fr: "Données de naissance — deuxième personne", en: "Birth data — second person", es: "Datos de nacimiento — segunda persona" },
  placeholder_name_b: { fr: "Ex. Camille", en: "E.g. Jane", es: "Ej. María" },
  btn_calculate_this_chart: { fr: "Calculer ce thème", en: "Calculate this chart", es: "Calcular esta carta" },
  btn_generate_compat_reading: { fr: "Générer la lecture de compatibilité", en: "Generate compatibility reading", es: "Generar lectura de compatibilidad" },
  error_select_second_chart: { fr: "Sélectionnez ou créez d'abord le thème de la deuxième personne.", en: "Select or create the second person's chart first.", es: "Primero selecciona o crea la carta de la segunda persona." },
  error_fill_birth_date_coords: { fr: "Complétez au moins la date de naissance et les coordonnées.", en: "Fill in at least the birth date and coordinates.", es: "Completa al menos la fecha de nacimiento y las coordenadas." },
  error_charts_unavailable: { fr: "Impossible de charger les cartes existantes", en: "Could not load existing charts", es: "No se pudieron cargar las cartas existentes" },
  status_computing_compat: { fr: "Calcul de la compatibilité en cours...", en: "Computing compatibility...", es: "Calculando la compatibilidad..." },
  error_computing_compat: { fr: "Impossible de calculer la compatibilité :", en: "Could not compute compatibility:", es: "No se pudo calcular la compatibilidad:" },
  compat_time_unknown_first: { fr: "le premier thème", en: "the first chart", es: "la primera carta" },
  compat_time_unknown_second: { fr: "le second thème", en: "the second chart", es: "la segunda carta" },
  compat_time_unknown_and: { fr: "et", en: "and", es: "y" },
  compat_time_warning: {
    fr: "Heure de naissance inconnue pour {names} : le chevauchement de maisons et l'Ascendant composite sont approximatifs. Les aspects croisés restent fiables (ils ne dépendent pas de l'heure).",
    en: "Unknown birth time for {names}: house overlay and the composite Ascendant are approximate. Cross-aspects remain reliable (they don't depend on the time).",
    es: "Hora de nacimiento desconocida para {names}: la superposición de casas y el Ascendente compuesto son aproximados. Los aspectos cruzados siguen siendo fiables (no dependen de la hora).",
  },
  compat_cross_aspects_title: { fr: "Aspects croisés", en: "Cross-aspects", es: "Aspectos cruzados" },
  compat_sorted_by_importance: {
    fr: "Triés par importance pour une relation {mode} : les plus significatifs apparaissent en premier.",
    en: "Sorted by importance for a {mode} relationship: the most significant appear first.",
    es: "Ordenados por importancia para una relación {mode}: los más significativos aparecen primero.",
  },
  th_planet_you: { fr: "Planète (vous)", en: "Planet (you)", es: "Planeta (tú)" },
  th_planet_other: { fr: "Planète (l'autre)", en: "Planet (the other)", es: "Planeta (el otro)" },
  th_orb: { fr: "Orbe", en: "Orb", es: "Orbe" },
  th_weight: { fr: "Poids", en: "Weight", es: "Peso" },
  compat_house_overlay_title: { fr: "Chevauchement de maisons", en: "House overlay", es: "Superposición de casas" },
  compat_your_planets_in_their_houses: { fr: "Vos planètes dans les maisons de l'autre", en: "Your planets in the other's houses", es: "Tus planetas en las casas del otro" },
  compat_their_planets_in_your_houses: { fr: "Les planètes de l'autre dans vos maisons", en: "The other's planets in your houses", es: "Los planetas del otro en tus casas" },
  th_house: { fr: "Maison", en: "House", es: "Casa" },
  th_meaning: { fr: "Signification", en: "Meaning", es: "Significado" },
  compat_composite_title: { fr: "Thème composite (la relation comme entité)", en: "Composite chart (the relationship as an entity)", es: "Carta compuesta (la relación como entidad)" },
  th_point: { fr: "Point", en: "Point", es: "Punto" },
  composite_ascendant: { fr: "Ascendant composite", en: "Composite Ascendant", es: "Ascendente compuesto" },

  th_body: { fr: "Corps", en: "Body", es: "Cuerpo" },
  th_degree: { fr: "Degré", en: "Degree", es: "Grado" },
  th_direction: { fr: "Direction", en: "Direction", es: "Dirección" },
  th_lot: { fr: "Lot", en: "Lot", es: "Suerte" },
  th_natal_aspects: { fr: "Aspects natals", en: "Natal aspects", es: "Aspectos natales" },
  house_prefix: { fr: "Maison", en: "House", es: "Casa" },
  retrograde: { fr: "Rétrograde", en: "Retrograde", es: "Retrógrado" },
  applying: { fr: "applicatif", en: "applying", es: "aplicativo" },
  separating: { fr: "séparatif", en: "separating", es: "separativo" },
  orb_prefix: { fr: "orbe", en: "orb", es: "orbe" },
  yes_self_ruled: { fr: "Oui (maître de son propre signe)", en: "Yes (ruler of its own sign)", es: "Sí (regente de su propio signo)" },
  no_dash: { fr: "—", en: "—", es: "—" },
  no_clear_convergence: {
    fr: "Aucune convergence claire : les chaînes de dispositeurs se répartissent entre plusieurs planètes finales.",
    en: "No clear convergence: rulership chains spread across several final planets.",
    es: "Sin convergencia clara: las cadenas de regencia se reparten entre varios planetas finales.",
  },
  final_dispositor_of_chart: { fr: "Dispositeur final du thème :", en: "Final ruler of the chart:", es: "Regente final de la carta:" },
  strong_convergence: { fr: "Convergence forte — planète clé de voûte", en: "Strong convergence — keystone planet", es: "Convergencia fuerte — planeta clave" },
  notable_convergence: { fr: "Convergence notable", en: "Notable convergence", es: "Convergencia notable" },
  traditional_system: { fr: "Système traditionnel", en: "Traditional system", es: "Sistema tradicional" },
  modern_system: { fr: "Système moderne", en: "Modern system", es: "Sistema moderno" },
  th_planet_generic: { fr: "Planète", en: "Planet", es: "Planeta" },
  th_sign_occupied: { fr: "Signe occupé", en: "Occupied sign", es: "Signo ocupado" },
  th_ruler_trad_modern: { fr: "Maître trad. / moderne", en: "Trad. / modern ruler", es: "Regente trad. / moderno" },
  th_self_disposed: { fr: "Auto-disposée", en: "Self-disposed", es: "Auto-regida" },
  see_dispositor_chains_detail: { fr: "Voir le détail des chaînes de dispositeurs", en: "View rulership chain detail", es: "Ver el detalle de las cadenas de regencia" },
  mutual_receptions_title: { fr: "Réceptions mutuelles", en: "Mutual receptions", es: "Recepciones mutuas" },
  no_mutual_reception: { fr: "Aucune réception mutuelle détectée.", en: "No mutual reception detected.", es: "No se detectó ninguna recepción mutua." },
  loop_suffix: { fr: "(boucle)", en: "(loop)", es: "(bucle)" },
  final_dispositor_prefix: { fr: "dispositeur final :", en: "final ruler:", es: "regente final:" },

  detail_by_planet: { fr: "Détail par planète", en: "Detail by planet", es: "Detalle por planeta" },
  generational_planets_note: {
    fr: "Planètes générationnelles (le signe est partagé par toute une tranche d'âge — c'est ici la maison occupée qui individualise) :",
    en: "Generational planets (the sign is shared by an entire age group — here it's the occupied house that individualizes):",
    es: "Planetas generacionales (el signo es compartido por toda una generación — aquí es la casa ocupada la que individualiza):",
  },

  no_lot_calculated: { fr: "Aucun lot calculé.", en: "No lot calculated.", es: "Ninguna suerte calculada." },
  lots_day_night_note: {
    fr: "Un thème de {dayNight} utilise les formules diurnes/nocturnes appropriées pour chaque lot. 10 lots classiques (tradition hellénistique) et 7 lots modernes non-canoniques (construits par analogie, voir badge) : survolez un badge pour le détail.",
    en: "A {dayNight} chart uses the appropriate day/night formulas for each lot. 10 classical lots (Hellenistic tradition) and 7 modern non-canonical lots (built by analogy, see badge): hover a badge for detail.",
    es: "Una carta {dayNight} utiliza las fórmulas de día/noche apropiadas para cada suerte. 10 suertes clásicas (tradición helenística) y 7 suertes modernas no canónicas (construidas por analogía, ver insignia): pasa el cursor sobre una insignia para más detalle.",
  },
  day_chart: { fr: "jour", en: "day", es: "día" },
  night_chart: { fr: "nuit", en: "night", es: "noche" },
  badge_non_canonical: { fr: "non-canonique", en: "non-canonical", es: "no canónica" },
  badge_disputed_attribution: { fr: "attribution disputée", en: "disputed attribution", es: "atribución disputada" },

  in_sign: { fr: "en", en: "in", es: "en" },
  born_prefix: { fr: "né", en: "born", es: "nacido/a" },
  on_date: { fr: "le", en: "on", es: "el" },
  at_time: { fr: "à", en: "at", es: "a las" },
  unknown_time_paren: { fr: "(heure inconnue)", en: "(unknown time)", es: "(hora desconocida)" },
  in_city: { fr: "à", en: "in", es: "en" },
  day_chart_label: { fr: "Thème de jour", en: "Day chart", es: "Carta diurna" },
  night_chart_label: { fr: "Thème de nuit", en: "Night chart", es: "Carta nocturna" },
  unknown_birth_time_warning: {
    fr: "Heure de naissance inconnue : maisons et angles sont approximatifs (calculés à midi).",
    en: "Unknown birth time: houses and angles are approximate (computed at noon).",
    es: "Hora de nacimiento desconocida: las casas y los ángulos son aproximados (calculados al mediodía).",
  },
  chart_default_name: { fr: "Thème", en: "Chart", es: "Carta" },

  no_aspect_detected: { fr: "Aucun aspect détecté avec les orbes actuels.", en: "No aspect detected with the current orbs.", es: "No se detectó ningún aspecto con los orbes actuales." },

  show_minor_aspects: { fr: "Afficher les aspects mineurs", en: "Show minor aspects", es: "Mostrar aspectos menores" },
  fullscreen: { fr: "🔍 Plein écran", en: "🔍 Fullscreen", es: "🔍 Pantalla completa" },
  exit_fullscreen: { fr: "✕ Quitter le plein écran", en: "✕ Exit fullscreen", es: "✕ Salir de pantalla completa" },

  error_prefix: { fr: "Erreur", en: "Error", es: "Error" },
  compat_ratings_title: { fr: "Notes de compatibilité", en: "Compatibility ratings", es: "Puntuaciones de compatibilidad" },
  timing_ratings_title: { fr: "Notes du pronostic", en: "Forecast ratings", es: "Puntuaciones del pronóstico" },

  astro_section_title: { fr: "4. Astrocartographie", en: "4. Astrocartography", es: "4. Astrocartografía" },
  astro_section_intro: {
    fr: "Projette sur une carte du monde les lieux où chaque planète est angulaire (Ascendant, Descendant, Milieu du Ciel, Fond du Ciel). Deux variantes : l'astrocartographie natale (lignes fixes, calculées une seule fois à la naissance) et la cyclocartographie (lignes de transit, qui reflètent les positions planétaires actuelles).",
    en: "Projects onto a world map the places where each planet is angular (Ascendant, Descendant, Midheaven, Imum Coeli). Two variants: natal astrocartography (fixed lines, computed once at birth) and cyclocartography (transit lines, reflecting current planetary positions).",
    es: "Proyecta sobre un mapa del mundo los lugares donde cada planeta está angular (Ascendente, Descendente, Medio Cielo, Fondo del Cielo). Dos variantes: astrocartografía natal (líneas fijas, calculadas una sola vez al nacer) y ciclocartografía (líneas de tránsito, que reflejan las posiciones planetarias actuales).",
  },
  astro_mode_natal: { fr: "Natale", en: "Natal", es: "Natal" },
  astro_mode_transit: { fr: "Cyclocartographie (transit)", en: "Cyclocartography (transit)", es: "Ciclocartografía (tránsito)" },
  astro_saved_locations_title: { fr: "Lieux sauvegardés", en: "Saved locations", es: "Lugares guardados" },
  astro_saved_locations_intro: {
    fr: "Enregistrez un lieu (ex. une destination de déménagement envisagée) pour voir quelles lignes natales en passent à proximité.",
    en: "Save a location (e.g. a possible relocation destination) to see which natal lines pass nearby.",
    es: "Guarda un lugar (por ejemplo, un posible destino de mudanza) para ver qué líneas natales pasan cerca.",
  },
  label_location_to_analyze: { fr: "Lieu à analyser", en: "Location to analyze", es: "Lugar a analizar" },
  btn_generate_astro_reading: { fr: "Générer la lecture d'astrocartographie", en: "Generate astrocartography reading", es: "Generar lectura de astrocartografía" },
  status_computing_astro: { fr: "Calcul des lignes en cours...", en: "Computing lines...", es: "Calculando las líneas..." },
  error_loading_astro: { fr: "Impossible de charger les lignes :", en: "Could not load the lines:", es: "No se pudieron cargar las líneas:" },
  astro_no_saved_locations: { fr: "Aucun lieu sauvegardé pour l'instant.", en: "No saved locations yet.", es: "Aún no hay lugares guardados." },
  astro_no_nearby_lines: { fr: "Aucune ligne natale à proximité.", en: "No natal line nearby.", es: "Ninguna línea natal cerca." },
  astro_use_for_reading: { fr: "Utiliser pour la lecture", en: "Use for reading", es: "Usar para la lectura" },
  astro_planets_filter_title: { fr: "Planètes affichées", en: "Displayed planets", es: "Planetas mostrados" },
  astro_line_types_filter_title: { fr: "Types de lignes", en: "Line types", es: "Tipos de línea" },
  astro_focus_default_note: {
    fr: "Par défaut, la lecture porte sur votre lieu de naissance — cliquez \"Utiliser pour la lecture\" sur un lieu sauvegardé pour l'analyser à la place.",
    en: "By default, the reading focuses on your birthplace — click \"Use for reading\" on a saved location to analyze it instead.",
    es: "Por defecto, la lectura se centra en tu lugar de nacimiento — haz clic en \"Usar para la lectura\" en un lugar guardado para analizarlo en su lugar.",
  },
  astro_reading_focus_label: { fr: "Lieu analysé pour cette lecture :", en: "Location analyzed for this reading:", es: "Lugar analizado para esta lectura:" },
  btn_delete: { fr: "Supprimer", en: "Delete", es: "Eliminar" },
  astro_transit_date_label: { fr: "Date à analyser", en: "Date to analyze", es: "Fecha a analizar" },
  astro_transit_date_today: { fr: "Aujourd'hui", en: "Today", es: "Hoy" },
  astro_forecast_title: {
    fr: "Prévision multi-années pour un lieu fixe",
    en: "Multi-year forecast for a fixed location",
    es: "Previsión de varios años para un lugar fijo",
  },
  astro_forecast_intro: {
    fr: "Le lieu reste fixe (ex. votre lieu de vie) : cet outil calcule, sur plusieurs années, les fenêtres de temps où une ligne de transit (cyclocartographie) passe à proximité.",
    en: "The location stays fixed (e.g. where you live): this tool computes, over several years, the time windows where a transit (cyclocartography) line passes nearby.",
    es: "El lugar permanece fijo (por ejemplo, donde vives): esta herramienta calcula, durante varios años, las ventanas de tiempo en las que una línea de tránsito (ciclocartografía) pasa cerca.",
  },
  astro_forecast_location_note: {
    fr: "Utilise le lieu actuellement sélectionné ci-dessus (« Utiliser pour la lecture ») ou, à défaut, le lieu de naissance.",
    en: "Uses the location currently selected above (\"Use for reading\") or, failing that, the birthplace.",
    es: "Usa el lugar actualmente seleccionado arriba (\"Usar para la lectura\") o, en su defecto, el lugar de nacimiento.",
  },
  astro_forecast_start_date_label: { fr: "Date de départ", en: "Start date", es: "Fecha de inicio" },
  astro_forecast_years_label: { fr: "Horizon (années)", en: "Horizon (years)", es: "Horizonte (años)" },
  astro_forecast_threshold_label: { fr: "Seuil de proximité (km)", en: "Proximity threshold (km)", es: "Umbral de proximidad (km)" },
  btn_compute_forecast: { fr: "Calculer la prévision", en: "Compute forecast", es: "Calcular la previsión" },
  status_computing_forecast: { fr: "Calcul de la prévision en cours...", en: "Computing forecast...", es: "Calculando la previsión..." },
  error_loading_forecast: { fr: "Impossible de calculer la prévision :", en: "Could not compute the forecast:", es: "No se pudo calcular la previsión:" },
  astro_forecast_no_windows: {
    fr: "Aucune ligne ne passe à proximité de ce lieu sur cette période avec ce seuil.",
    en: "No line passes near this location over this period with this threshold.",
    es: "Ninguna línea pasa cerca de este lugar en este período con este umbral.",
  },
  astro_forecast_col_line: { fr: "Ligne", en: "Line", es: "Línea" },
  astro_forecast_col_period: { fr: "Période", en: "Period", es: "Período" },
  astro_forecast_col_peak: { fr: "Pic de proximité", en: "Closest approach", es: "Máxima proximidad" },
  astro_forecast_col_distance: { fr: "Distance", en: "Distance", es: "Distancia" },
  astro_interesting_cities_title: {
    fr: "Villes intéressantes suggérées",
    en: "Suggested interesting cities",
    es: "Ciudades interesantes sugeridas",
  },
  astro_interesting_cities_intro: {
    fr: "Parmi les grandes villes mondiales, celles où plusieurs lignes natales passent à proximité ou se croisent — suggestion automatique, visible sur la carte (mode natal).",
    en: "Among major world cities, the ones where several natal lines pass nearby or cross — automatic suggestion, shown on the map (natal mode).",
    es: "Entre las principales ciudades del mundo, aquellas donde varias líneas natales pasan cerca o se cruzan — sugerencia automática, visible en el mapa (modo natal).",
  },
  astro_no_interesting_cities: {
    fr: "Aucune ville marquante trouvée avec ce seuil.",
    en: "No standout city found with this threshold.",
    es: "No se encontró ninguna ciudad destacada con este umbral.",
  },
  astro_score_label: { fr: "Score :", en: "Score:", es: "Puntuación:" },
  astro_crossings_label: { fr: "Croisements :", en: "Crossings:", es: "Cruces:" },
  btn_forecast_ai_reading: {
    fr: "Analyse IA de cette prévision",
    en: "AI analysis of this forecast",
    es: "Análisis IA de esta previsión",
  },
  astro_transit_cities_title: {
    fr: "Top 5 des villes marquées par le ciel du jour",
    en: "Top 5 cities marked by today's sky",
    es: "Top 5 de ciudades marcadas por el cielo del día",
  },
  astro_transit_cities_intro: {
    fr: "Recalculé automatiquement à chaque changement de date : les villes les plus proches des lignes de transit (et de leurs croisements) à cette date précise.",
    en: "Recomputed automatically on every date change: the cities closest to the transit lines (and their crossings) on this specific date.",
    es: "Recalculado automáticamente en cada cambio de fecha: las ciudades más cercanas a las líneas de tránsito (y sus cruces) en esta fecha concreta.",
  },

  witchy_section_title: { fr: "Calendrier ésotérique", en: "Esoteric calendar", es: "Calendario esotérico" },
  witchy_section_intro: {
    fr: "Calendrier annuel collectif (le même pour tout le monde cette année-là, indépendant de votre thème natal) : lunaisons, éclipses, stations rétrogrades et changements de signe des planètes lentes.",
    en: "Collective yearly calendar (the same for everyone that year, independent of your natal chart): lunations, eclipses, retrograde stations and slow-planet sign changes.",
    es: "Calendario anual colectivo (el mismo para todos ese año, independiente de tu carta natal): lunaciones, eclipses, estaciones retrógradas y cambios de signo de los planetas lentos.",
  },
  witchy_year_label: { fr: "Année", en: "Year", es: "Año" },
  btn_load_witchy_calendar: { fr: "Charger le calendrier", en: "Load calendar", es: "Cargar el calendario" },
  btn_generate_witchy_reading: {
    fr: "Générer la lecture du calendrier",
    en: "Generate calendar reading",
    es: "Generar la lectura del calendario",
  },
  status_loading_witchy_calendar: { fr: "Calcul du calendrier en cours...", en: "Computing calendar...", es: "Calculando el calendario..." },
  error_loading_witchy_calendar: { fr: "Impossible de charger le calendrier :", en: "Could not load the calendar:", es: "No se pudo cargar el calendario:" },
  witchy_no_events: { fr: "Aucun événement calculé pour cette année.", en: "No events computed for this year.", es: "Ningún evento calculado para este año." },
  witchy_super_moon_badge: { fr: "Super Lune", en: "Supermoon", es: "Superluna" },
  witchy_label_nouvelle_lune: { fr: "Nouvelle Lune en {sign}", en: "New Moon in {sign}", es: "Luna Nueva en {sign}" },
  witchy_label_pleine_lune: { fr: "Pleine Lune en {sign}", en: "Full Moon in {sign}", es: "Luna Llena en {sign}" },
  witchy_label_eclipse_solaire: { fr: "Éclipse solaire en {sign}", en: "Solar Eclipse in {sign}", es: "Eclipse solar en {sign}" },
  witchy_label_eclipse_lunaire: { fr: "Éclipse lunaire en {sign}", en: "Lunar Eclipse in {sign}", es: "Eclipse lunar en {sign}" },
  witchy_label_station_retrograde: {
    fr: "{planet} rétrograde en {sign}",
    en: "{planet} turns retrograde in {sign}",
    es: "{planet} retrógrado en {sign}",
  },
  witchy_label_station_directe: {
    fr: "{planet} redevient direct en {sign}",
    en: "{planet} turns direct in {sign}",
    es: "{planet} se vuelve directo en {sign}",
  },
  witchy_label_ingres: { fr: "{planet} entre en {sign}", en: "{planet} enters {sign}", es: "{planet} entra en {sign}" },
};
