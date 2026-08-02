const SIGN_SYMBOLS = {
  Aries: "♈", Taurus: "♉", Gemini: "♊", Cancer: "♋", Leo: "♌", Virgo: "♍",
  Libra: "♎", Scorpio: "♏", Sagittarius: "♐", Capricorn: "♑", Aquarius: "♒", Pisces: "♓",
};

const SIGN_LABELS_FR = {
  Aries: "Bélier", Taurus: "Taureau", Gemini: "Gémeaux", Cancer: "Cancer", Leo: "Lion", Virgo: "Vierge",
  Libra: "Balance", Scorpio: "Scorpion", Sagittarius: "Sagittaire", Capricorn: "Capricorne",
  Aquarius: "Verseau", Pisces: "Poissons",
};

function signLabel(sign) {
  return `${SIGN_SYMBOLS[sign] || ""} ${SIGN_LABELS_FR[sign] || sign}`;
}

const PLANET_LABELS_FR = {
  Sun: "Soleil", Moon: "Lune", Mercury: "Mercure", Venus: "Vénus", Mars: "Mars",
  Jupiter: "Jupiter", Saturn: "Saturne", Uranus: "Uranus", Neptune: "Neptune", Pluto: "Pluton",
  north_node: "Nœud Nord", south_node: "Nœud Sud", chiron: "Chiron", lilith_mean: "Lilith",
  ascendant: "Ascendant", midheaven: "Milieu du Ciel", descendant: "Descendant", imum_coeli: "Fond du Ciel",
};

const PLANET_SYMBOLS = {
  Sun: "☉", Moon: "☽", Mercury: "☿", Venus: "♀", Mars: "♂",
  Jupiter: "♃", Saturn: "♄", Uranus: "⛢", Neptune: "♆", Pluto: "♇",
  north_node: "☊", south_node: "☋", chiron: "⚷", lilith_mean: "⚸",
};

const ZODIAC_SIGNS_ORDER = [
  "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
  "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
];

const SIGN_ELEMENTS = {
  Aries: "fire", Leo: "fire", Sagittarius: "fire",
  Taurus: "earth", Virgo: "earth", Capricorn: "earth",
  Gemini: "air", Libra: "air", Aquarius: "air",
  Cancer: "water", Scorpio: "water", Pisces: "water",
};

const ELEMENT_WHEEL_COLORS = {
  fire: "rgba(255, 107, 107, 0.15)",
  earth: "rgba(110, 200, 130, 0.15)",
  air: "rgba(110, 180, 231, 0.15)",
  water: "rgba(120, 140, 255, 0.15)",
};

// Une couleur distincte par type d'aspect : majeurs en teintes vives, mineurs plus discrets.
const ASPECT_COLORS = {
  conjunction: "#e0b34d",
  sextile: "#5fd4c0",
  square: "#ff5d5d",
  trine: "#4da3ff",
  opposition: "#ff5d9e",
  semi_sextile: "#8f8fce",
  semi_square: "#c97b7b",
  sesquiquadrate: "#c97b7b",
  quincunx: "#a875c9",
  quintile: "#7bc98f",
};

const MAJOR_ASPECTS = new Set(["conjunction", "sextile", "square", "trine", "opposition"]);

let currentChart = null;
let showMinorAspectsInWheel = false;

function planetLabel(name) {
  return PLANET_LABELS_FR[name] || name;
}

function el(html) {
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

function escapeHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ---------------------------------------------------------------------
// Liste des fuseaux horaires (menu déroulant)
// ---------------------------------------------------------------------
async function loadTimezones() {
  const select = document.getElementById("timezone");
  try {
    const res = await fetch("/api/reference/timezones");
    const zones = await res.json();
    select.innerHTML = zones.map((tz) => `<option value="${tz}">${tz}</option>`).join("");
    select.value = "Europe/Paris";
  } catch (err) {
    // Pas de réseau/API indisponible : on retombe sur un champ texte libre plutôt que de bloquer le formulaire.
    const fallbackInput = el(`<input type="text" id="timezone" value="Europe/Paris" placeholder="Europe/Paris" required />`);
    select.replaceWith(fallbackInput);
  }
}
loadTimezones();

// ---------------------------------------------------------------------
// Recherche de ville (géocodage)
// ---------------------------------------------------------------------
document.getElementById("search-city-btn").addEventListener("click", async () => {
  const query = document.getElementById("city_search").value.trim();
  const resultsDiv = document.getElementById("city-results");
  resultsDiv.innerHTML = "";
  if (query.length < 2) return;

  try {
    const res = await fetch(`/api/geocode?query=${encodeURIComponent(query)}`);
    if (!res.ok) {
      resultsDiv.innerHTML = `<p class="error">Recherche indisponible — saisissez les coordonnées manuellement.</p>`;
      return;
    }
    const locations = await res.json();
    if (locations.length === 0) {
      resultsDiv.innerHTML = `<p>Aucun résultat. Saisissez les coordonnées manuellement.</p>`;
      return;
    }
    locations.forEach((loc) => {
      const item = el(`<div class="city-result-item">${loc.display_name}</div>`);
      item.addEventListener("click", () => {
        document.getElementById("latitude").value = loc.latitude.toFixed(4);
        document.getElementById("longitude").value = loc.longitude.toFixed(4);
        if (loc.timezone) document.getElementById("timezone").value = loc.timezone;
        resultsDiv.innerHTML = "";
        document.getElementById("city_search").value = loc.display_name;
      });
      resultsDiv.appendChild(item);
    });
  } catch (err) {
    resultsDiv.innerHTML = `<p class="error">Recherche indisponible — saisissez les coordonnées manuellement.</p>`;
  }
});

document.getElementById("time_unknown").addEventListener("change", (e) => {
  document.getElementById("birth_time").disabled = e.target.checked;
});

// ---------------------------------------------------------------------
// Soumission du formulaire de naissance
// ---------------------------------------------------------------------
document.getElementById("birth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("form-error");
  const submitBtn = document.getElementById("submit-btn");
  errorEl.textContent = "";

  const timeUnknown = document.getElementById("time_unknown").checked;
  const optionalPoints = Array.from(document.getElementById("optional_points").selectedOptions).map((o) => o.value);

  const payload = {
    birth_data: {
      date: document.getElementById("birth_date").value,
      time: timeUnknown ? null : document.getElementById("birth_time").value,
      time_known: !timeUnknown,
      timezone: document.getElementById("timezone").value,
      location: {
        city: document.getElementById("city_search").value || null,
        country: null,
        latitude: parseFloat(document.getElementById("latitude").value),
        longitude: parseFloat(document.getElementById("longitude").value),
      },
    },
    settings: {
      house_system: document.getElementById("house_system").value,
      rulership_system: document.getElementById("rulership_system").value,
      optional_points: optionalPoints,
    },
    subject_name: document.getElementById("subject_name").value || null,
  };

  submitBtn.disabled = true;
  submitBtn.textContent = "Calcul en cours...";
  try {
    const res = await fetch("/api/charts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `Erreur ${res.status}`);
    }
    currentChart = await res.json();
    renderChart(currentChart);
    document.getElementById("results-section").classList.remove("hidden");
    document.getElementById("reading-section").classList.remove("hidden");
    document.getElementById("results-section").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Calculer le thème natal";
  }
});

const TRAIT_ORIGIN_LABELS_FR = {
  ascendant: "Ascendant", sun: "Soleil", moon: "Lune", mercury: "Mercure", venus: "Vénus", mars: "Mars",
  jupiter: "Jupiter", saturn: "Saturne", dominant_element: "Élément dominant", dominant_modality: "Modalité dominante",
};

const ELEMENT_LABELS_FR = { fire: "🔥 Feu", earth: "🌍 Terre", air: "💨 Air", water: "💧 Eau" };
const MODALITY_LABELS_FR = { cardinal: "Cardinal", fixed: "Fixe", mutable: "Mutable" };

function renderTraitTags(characterTraits) {
  if (!characterTraits || !characterTraits.keywords || characterTraits.keywords.length === 0) return "";
  const dominant = new Set(characterTraits.dominant_traits || []);
  const tags = characterTraits.keywords
    .map((trait) => `<span class="trait-tag${dominant.has(trait) ? " trait-tag-dominant" : ""}">${trait}</span>`)
    .join("");

  const sourceRows = (characterTraits.sources || [])
    .map((s) => {
      const originLabel = TRAIT_ORIGIN_LABELS_FR[s.origin] || s.origin;
      const isSignBased = !s.origin.startsWith("dominant_");
      const labelText = s.origin === "dominant_element" ? ELEMENT_LABELS_FR[s.label] || s.label
        : s.origin === "dominant_modality" ? MODALITY_LABELS_FR[s.label] || s.label
        : signLabel(s.label);
      const heading = isSignBased ? `${originLabel} en ${labelText}` : `${originLabel} : ${labelText}`;
      const houseInfo = s.house ? ` (maison ${s.house}${s.house_context ? " — " + s.house_context : ""})` : "";
      return `<li><strong>${heading}</strong>${houseInfo} : ${s.traits.join(", ")}</li>`;
    })
    .join("");

  const generational = (characterTraits.generational_placements || [])
    .map((p) => `<li><strong>${planetLabel(p.planet)}</strong> en ${signLabel(p.sign)}, maison ${p.house} : ${p.note}</li>`)
    .join("");

  return `
    <div class="trait-tags">${tags}</div>
    <details class="traits-detail">
      <summary>Détail par planète</summary>
      <ul>${sourceRows}</ul>
      ${
        generational
          ? `<p class="reading-section-intro">Planètes générationnelles (le signe est partagé par toute une tranche d'âge — c'est ici la maison occupée qui individualise) :</p><ul>${generational}</ul>`
          : ""
      }
    </details>
  `;
}

// ---------------------------------------------------------------------
// Roue astrale (SVG) : zodiaque, maisons, planètes, aspects colorés
// ---------------------------------------------------------------------
function polarToXY(cx, cy, radius, angleDeg) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + radius * Math.cos(rad), y: cy - radius * Math.sin(rad) };
}

// Angle SVG (sens trigonométrique standard) pour une longitude écliptique donnée,
// avec l'Ascendant fixé à 9h (180°) et le zodiaque qui avance dans le sens
// Ascendant -> Fond du Ciel -> Descendant -> Milieu du Ciel, comme sur une roue
// astrologique classique.
function longitudeToWheelAngle(longitude, ascendant) {
  const offset = (((longitude - ascendant) % 360) + 360) % 360;
  return (180 + offset) % 360;
}

// Écart angulaire, en degrés, entre deux longitudes en tenant compte du passage 360°->0°.
function forwardOffset(fromLongitude, toLongitude) {
  return (((toLongitude - fromLongitude) % 360) + 360) % 360;
}

function arcPoints(cx, cy, radius, startAngle, sweepDegrees, segments = 10) {
  const points = [];
  for (let i = 0; i <= segments; i++) {
    const angle = startAngle + (sweepDegrees * i) / segments;
    points.push(polarToXY(cx, cy, radius, angle));
  }
  return points;
}

function pointsToPath(points) {
  return points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(" ");
}

function buildWheelSVG(data, { showMinorAspects }) {
  const cx = 300;
  const cy = 300;
  const rOuter = 290;
  const rZodiacInner = 250;
  const rPlanetBase = 205;
  const rPlanetLaneStep = 18;
  const rAspectCircle = 135;
  const ascendant = data.angles.ascendant.absolute_longitude;

  // --- Anneau du zodiaque (12 secteurs de 30°, colorés par élément) ---
  let zodiacSvg = "";
  ZODIAC_SIGNS_ORDER.forEach((sign, i) => {
    const signStartLon = i * 30;
    const startAngle = longitudeToWheelAngle(signStartLon, ascendant);
    const outer = arcPoints(cx, cy, rOuter, startAngle, 30);
    const inner = arcPoints(cx, cy, rZodiacInner, startAngle + 30, -30);
    const path = pointsToPath([...outer, ...inner]) + " Z";
    const color = ELEMENT_WHEEL_COLORS[SIGN_ELEMENTS[sign]];
    zodiacSvg += `<path d="${path}" fill="${color}" stroke="#2c2f4a" stroke-width="1" />`;

    const midAngle = startAngle + 15;
    const labelPos = polarToXY(cx, cy, (rOuter + rZodiacInner) / 2, midAngle);
    zodiacSvg += `<text x="${labelPos.x.toFixed(2)}" y="${labelPos.y.toFixed(2)}" class="wheel-sign-symbol" text-anchor="middle" dominant-baseline="middle">${SIGN_SYMBOLS[sign]}</text>`;
  });

  // --- Cuspides des maisons (lignes radiales + numéros) ---
  let housesSvg = "";
  data.houses.forEach((house, i) => {
    const angle = longitudeToWheelAngle(house.absolute_longitude, ascendant);
    const inner = polarToXY(cx, cy, 0, angle);
    const outer = polarToXY(cx, cy, rZodiacInner, angle);
    const isAngular = [1, 4, 7, 10].includes(house.number);
    housesSvg += `<line x1="${inner.x.toFixed(2)}" y1="${inner.y.toFixed(2)}" x2="${outer.x.toFixed(2)}" y2="${outer.y.toFixed(2)}" stroke="${isAngular ? "#9a9cbd" : "#3a3d5c"}" stroke-width="${isAngular ? 1.5 : 1}" />`;

    const next = data.houses[(i + 1) % 12];
    const nextAngle = angle + forwardOffset(house.absolute_longitude, next.absolute_longitude);
    const midAngle = (angle + nextAngle) / 2;
    const labelPos = polarToXY(cx, cy, rAspectCircle + 18, midAngle);
    housesSvg += `<text x="${labelPos.x.toFixed(2)}" y="${labelPos.y.toFixed(2)}" class="wheel-house-number" text-anchor="middle" dominant-baseline="middle">${house.number}</text>`;
  });

  // --- Cercle intérieur (support des lignes d'aspect) ---
  const aspectCircleSvg = `<circle cx="${cx}" cy="${cy}" r="${rAspectCircle}" fill="none" stroke="#2c2f4a" stroke-width="1" />`;

  // --- Planètes : glyphe sur un anneau dédié + trait radial vers le point exact ---
  // Tri par angle affiché (relatif à l'Ascendant), pas par longitude brute : sinon la
  // coupure 0°/360° du zodiaque casse la détection de proximité près de l'Ascendant.
  const sortedPlanets = [...data.planets].sort(
    (a, b) => longitudeToWheelAngle(a.absolute_longitude, ascendant) - longitudeToWheelAngle(b.absolute_longitude, ascendant)
  );
  let lastAngle = null;
  let lane = 0;
  let planetsSvg = "";
  const planetPoints = {};
  sortedPlanets.forEach((planet) => {
    const trueAngle = longitudeToWheelAngle(planet.absolute_longitude, ascendant);
    if (lastAngle !== null && forwardOffset(0, trueAngle - lastAngle) < 6) {
      lane = (lane + 1) % 3;
    } else {
      lane = 0;
    }
    lastAngle = trueAngle;

    const displayRadius = rPlanetBase + lane * rPlanetLaneStep;
    const glyphPos = polarToXY(cx, cy, displayRadius, trueAngle);
    const tickInner = polarToXY(cx, cy, rAspectCircle, trueAngle);
    const tickOuter = polarToXY(cx, cy, rZodiacInner, trueAngle);
    planetPoints[planet.name] = polarToXY(cx, cy, rAspectCircle, trueAngle);

    const planetTooltip = escapeHtml(
      `${planetLabel(planet.name)} — ${signLabel(planet.sign)} ${planet.degree}° — Maison ${planet.house ?? "—"}${planet.retrograde ? " · rétrograde" : ""}`
    );

    planetsSvg += `<line x1="${tickInner.x.toFixed(2)}" y1="${tickInner.y.toFixed(2)}" x2="${tickOuter.x.toFixed(2)}" y2="${tickOuter.y.toFixed(2)}" stroke="#4a4d6c" stroke-width="0.75" stroke-dasharray="2,2" />`;
    planetsSvg += `<g class="wheel-hoverable" data-tooltip="${planetTooltip}">`;
    planetsSvg += `<circle cx="${glyphPos.x.toFixed(2)}" cy="${glyphPos.y.toFixed(2)}" r="16" fill="transparent" pointer-events="all" />`;
    planetsSvg += `<circle cx="${glyphPos.x.toFixed(2)}" cy="${glyphPos.y.toFixed(2)}" r="11" fill="#1a1e33" stroke="${planet.retrograde ? "#ff8080" : "#b28dff"}" stroke-width="1.5" />`;
    planetsSvg += `<text x="${glyphPos.x.toFixed(2)}" y="${glyphPos.y.toFixed(2)}" class="wheel-planet-symbol" text-anchor="middle" dominant-baseline="middle">${PLANET_SYMBOLS[planet.name] || "•"}</text>`;
    planetsSvg += `</g>`;
  });

  // --- Aspects : traits colorés reliant les points exacts sur le cercle intérieur ---
  let aspectsSvg = "";
  data.aspects.forEach((aspect) => {
    if (!showMinorAspects && !MAJOR_ASPECTS.has(aspect.type)) return;
    const p1 = planetPoints[aspect.planet1];
    const p2 = planetPoints[aspect.planet2];
    if (!p1 || !p2) return;
    const color = ASPECT_COLORS[aspect.type] || "#888";
    const isMajor = MAJOR_ASPECTS.has(aspect.type);
    const aspectTooltip = escapeHtml(
      `${planetLabel(aspect.planet1)} ${aspect.type_fr} ${planetLabel(aspect.planet2)} — orbe ${aspect.orb}° (${aspect.applying ? "applicatif" : "séparatif"})`
    );
    aspectsSvg += `<g class="wheel-hoverable" data-tooltip="${aspectTooltip}">`;
    aspectsSvg += `<line x1="${p1.x.toFixed(2)}" y1="${p1.y.toFixed(2)}" x2="${p2.x.toFixed(2)}" y2="${p2.y.toFixed(2)}" stroke="transparent" stroke-width="10" pointer-events="all" />`;
    aspectsSvg += `<line x1="${p1.x.toFixed(2)}" y1="${p1.y.toFixed(2)}" x2="${p2.x.toFixed(2)}" y2="${p2.y.toFixed(2)}" stroke="${color}" stroke-width="${isMajor ? 1.4 : 0.9}" stroke-opacity="0.75" ${isMajor ? "" : 'stroke-dasharray="3,3"'} pointer-events="none" />`;
    aspectsSvg += `</g>`;
  });

  return `
    <svg viewBox="0 0 600 600" class="wheel-svg" xmlns="http://www.w3.org/2000/svg">
      <circle cx="${cx}" cy="${cy}" r="${rOuter}" fill="#12152a" />
      ${zodiacSvg}
      <circle cx="${cx}" cy="${cy}" r="${rZodiacInner}" fill="none" stroke="#2c2f4a" stroke-width="1.5" />
      ${aspectCircleSvg}
      ${aspectsSvg}
      ${housesSvg}
      ${planetsSvg}
    </svg>
  `;
}

function renderAspectLegend() {
  const items = [
    ["conjunction", "Conjonction"], ["sextile", "Sextile"], ["square", "Carré"],
    ["trine", "Trigone"], ["opposition", "Opposition"],
  ];
  const minorItems = [
    ["semi_sextile", "Semi-sextile"], ["semi_square", "Semi-carré"], ["sesquiquadrate", "Sesqui-carré"],
    ["quincunx", "Quinconce"], ["quintile", "Quintile"],
  ];
  const swatch = ([key, label]) =>
    `<span class="legend-item"><span class="legend-swatch" style="background:${ASPECT_COLORS[key]}"></span>${label}</span>`;

  return `
    <div class="wheel-legend">
      <div class="wheel-legend-row">${items.map(swatch).join("")}</div>
      <div class="wheel-legend-row wheel-legend-minor ${showMinorAspectsInWheel ? "" : "hidden"}">${minorItems.map(swatch).join("")}</div>
    </div>
  `;
}

function requestElementFullscreen(element) {
  const request = element.requestFullscreen || element.webkitRequestFullscreen;
  if (request) request.call(element);
}

function exitFullscreen() {
  const exit = document.exitFullscreen || document.webkitExitFullscreen;
  if (exit) exit.call(document);
}

function isFullscreenActive() {
  return !!(document.fullscreenElement || document.webkitFullscreenElement);
}

function attachWheelTooltip(wrapper) {
  const tooltip = document.createElement("div");
  tooltip.className = "wheel-tooltip hidden";
  wrapper.appendChild(tooltip);

  wrapper.addEventListener("mousemove", (e) => {
    const target = e.target.closest("[data-tooltip]");
    if (!target) {
      tooltip.classList.add("hidden");
      return;
    }
    tooltip.textContent = target.getAttribute("data-tooltip");
    tooltip.classList.remove("hidden");
    const rect = wrapper.getBoundingClientRect();
    let left = e.clientX - rect.left + 16;
    let top = e.clientY - rect.top + 16;
    // Évite que l'info-bulle ne déborde du cadre à droite/en bas.
    if (left + 260 > rect.width) left = e.clientX - rect.left - 270;
    if (top + 50 > rect.height) top = e.clientY - rect.top - 50;
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  });
  wrapper.addEventListener("mouseleave", () => tooltip.classList.add("hidden"));
}

function renderWheelTab(data) {
  ensureWheelFullscreenListener();
  const container = document.getElementById("tab-wheel");
  container.innerHTML = `
    <div class="wheel-controls">
      <label class="checkbox-label wheel-toggle">
        <input type="checkbox" id="toggle-minor-aspects" ${showMinorAspectsInWheel ? "checked" : ""} />
        Afficher les aspects mineurs
      </label>
      <button type="button" id="wheel-fullscreen-btn" class="wheel-fullscreen-btn">🔍 Plein écran</button>
    </div>
    <div id="wheel-fullscreen-target" class="wheel-fullscreen-target">
      <div class="wheel-wrapper">${buildWheelSVG(data, { showMinorAspects: showMinorAspectsInWheel })}</div>
      ${renderAspectLegend()}
    </div>
  `;

  document.getElementById("toggle-minor-aspects").addEventListener("change", (e) => {
    showMinorAspectsInWheel = e.target.checked;
    renderWheelTab(data);
  });

  const fullscreenTarget = document.getElementById("wheel-fullscreen-target");
  attachWheelTooltip(fullscreenTarget);

  document.getElementById("wheel-fullscreen-btn").addEventListener("click", () => {
    if (isFullscreenActive()) {
      exitFullscreen();
    } else {
      requestElementFullscreen(fullscreenTarget);
    }
  });
  updateWheelFullscreenState();
}

// Recherche les éléments courants par id plutôt que de fermer sur des références figées :
// le contenu de l'onglet est régénéré à chaque bascule "aspects mineurs", donc un handler
// attaché une seule fois sur `document` doit toujours cibler le DOM actuel, pas l'ancien.
function updateWheelFullscreenState() {
  const btn = document.getElementById("wheel-fullscreen-btn");
  const target = document.getElementById("wheel-fullscreen-target");
  if (!btn || !target) return;
  const active = isFullscreenActive();
  btn.textContent = active ? "✕ Quitter le plein écran" : "🔍 Plein écran";
  target.classList.toggle("is-fullscreen", active);
}

let wheelFullscreenListenerAttached = false;
function ensureWheelFullscreenListener() {
  if (wheelFullscreenListenerAttached) return;
  document.addEventListener("fullscreenchange", updateWheelFullscreenState);
  document.addEventListener("webkitfullscreenchange", updateWheelFullscreenState);
  wheelFullscreenListenerAttached = true;
}

// ---------------------------------------------------------------------
// Rendu du thème
// ---------------------------------------------------------------------
function renderChart(chart) {
  const data = chart.computed_chart_data;

  const asc = data.angles.ascendant;
  const sun = data.planets.find((p) => p.name === "Sun");
  const moon = data.planets.find((p) => p.name === "Moon");

  document.getElementById("chart-summary").innerHTML = `
    <p>
      <strong>${chart.subject_name || "Thème"}</strong> —
      né${chart.subject_name ? "(e)" : ""} le ${chart.birth_date}
      ${chart.birth_time_known ? "à " + (chart.birth_time || "") : "(heure inconnue)"}
      à ${chart.birth_city || ""}
    </p>
    <p>
      ☉ Soleil en ${SIGN_SYMBOLS[sun.sign]} ${sun.sign_fr} ${sun.degree}°
      &nbsp;|&nbsp; ☽ Lune en ${SIGN_SYMBOLS[moon.sign]} ${moon.sign_fr} ${moon.degree}°
      &nbsp;|&nbsp; Ascendant ${SIGN_SYMBOLS[asc.sign]} ${asc.sign_fr} ${asc.degree}°
      &nbsp;|&nbsp; Thème de ${data.is_day_chart ? "jour" : "nuit"}
    </p>
    ${!data.time_known ? '<p class="error">Heure de naissance inconnue : maisons et angles sont approximatifs (calculés à midi).</p>' : ""}
    ${renderTraitTags(data.character_traits)}
  `;

  renderWheelTab(data);
  renderPlanetsTab(data);
  renderHousesTab(data);
  renderAspectsTab(data);
  renderBalanceTab(data);
  renderDispositorsTab(data);
  renderLotsDataPanel(data);
  renderDerivedHousesDataPanel(data);
  timingLoadedForChartId = null; // nouveau thème : re-fetcher le timing au prochain accès
  zrLoadedForChartId = null; // nouveau thème : re-fetcher les phases au prochain accès
}

function renderPlanetsTab(data) {
  const rows = data.planets
    .map(
      (p) => `
      <tr>
        <td>${planetLabel(p.name)}</td>
        <td>${SIGN_SYMBOLS[p.sign]} ${p.sign_fr}</td>
        <td>${p.degree}°</td>
        <td>Maison ${p.house ?? "—"}</td>
        <td>${p.retrograde ? '<span class="retro">Rétrograde</span>' : "—"}</td>
      </tr>`
    )
    .join("");

  const angleRows = ["ascendant", "midheaven", "descendant", "imum_coeli"]
    .map((key) => {
      const a = data.angles[key];
      const labels = { ascendant: "Ascendant", midheaven: "Milieu du Ciel", descendant: "Descendant", imum_coeli: "Fond du Ciel" };
      return `<tr><td>${labels[key]}</td><td>${SIGN_SYMBOLS[a.sign]} ${a.sign_fr}</td><td>${a.degree}°</td><td>—</td><td>—</td></tr>`;
    })
    .join("");

  document.getElementById("tab-planets").innerHTML = `
    <table>
      <thead><tr><th>Corps</th><th>Signe</th><th>Degré</th><th>Maison</th><th>Mouvement</th></tr></thead>
      <tbody>${rows}${angleRows}</tbody>
    </table>
  `;
}

function renderHousesTab(data) {
  const rows = data.houses
    .map((h) => `<tr><td>Maison ${h.number}</td><td>${SIGN_SYMBOLS[h.sign]} ${h.sign_fr}</td><td>${h.degree}°</td></tr>`)
    .join("");
  document.getElementById("tab-houses").innerHTML = `
    <table>
      <thead><tr><th>Maison</th><th>Signe</th><th>Degré</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderAspectsTab(data) {
  if (data.aspects.length === 0) {
    document.getElementById("tab-aspects").innerHTML = "<p>Aucun aspect détecté avec les orbes actuels.</p>";
    return;
  }
  const rows = data.aspects
    .map(
      (a) => `
      <tr>
        <td>${planetLabel(a.planet1)}</td>
        <td>${a.type_fr}</td>
        <td>${planetLabel(a.planet2)}</td>
        <td>orbe ${a.orb}°</td>
        <td>${a.applying ? "applicatif" : "séparatif"}</td>
      </tr>`
    )
    .join("");
  document.getElementById("tab-aspects").innerHTML = `
    <table>
      <thead><tr><th>Corps 1</th><th>Aspect</th><th>Corps 2</th><th>Orbe</th><th>Direction</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function balanceBar(label, value, max) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return `
    <div class="balance-bar-row">
      <span class="balance-bar-label">${label}</span>
      <div class="balance-bar-track"><div class="balance-bar-fill" style="width:${pct}%"></div></div>
      <span>${value}</span>
    </div>`;
}

function renderBalanceTab(data) {
  const e = data.elements_balance;
  const m = data.modality_balance;
  const maxE = Math.max(...Object.values(e), 1);
  const maxM = Math.max(...Object.values(m), 1);
  document.getElementById("tab-balance").innerHTML = `
    <h3>Éléments</h3>
    ${balanceBar("🔥 Feu", e.fire, maxE)}
    ${balanceBar("🌍 Terre", e.earth, maxE)}
    ${balanceBar("💨 Air", e.air, maxE)}
    ${balanceBar("💧 Eau", e.water, maxE)}
    <h3>Modalités</h3>
    ${balanceBar("Cardinal", m.cardinal, maxM)}
    ${balanceBar("Fixe", m.fixed, maxM)}
    ${balanceBar("Mutable", m.mutable, maxM)}
  `;
}

function renderConvergenceSummary(convergence) {
  if (!convergence || !convergence.dominant_dispositor) {
    return "<p>Aucune convergence claire : les chaînes de dispositeurs se répartissent entre plusieurs planètes finales.</p>";
  }
  const { dominant_dispositor, dominant_count, total_chains, level } = convergence;
  const label = planetLabel(dominant_dispositor);
  const summary = `<p class="convergence-summary">🔑 <strong>Dispositeur final du thème : ${label}</strong> (${dominant_count} planète${dominant_count > 1 ? "s" : ""} sur ${total_chains} convergent vers lui)</p>`;

  if (level === "forte" || level === "notable") {
    const badge = level === "forte" ? "Convergence forte — planète clé de voûte" : "Convergence notable";
    return `${summary}<div class="convergence-alert convergence-${level}">⚡ ${badge} : la majorité des chaînes de maîtrise du thème se referment sur ${label}. C'est un pattern peu fréquent statistiquement — cette planète mérite d'être lue comme un axe central du thème, pas seulement comme une planète parmi d'autres.</div>`;
  }
  return summary;
}

function renderDispositorsSection(analysis, title) {
  if (!analysis) return "";
  const dispositorRows = analysis.dispositors
    .map(
      (d) => `
      <tr>
        <td>${planetLabel(d.planet)}</td>
        <td>${signLabel(d.sign_occupied)}</td>
        <td>${planetLabel(d.rulers.traditional)} / ${planetLabel(d.rulers.modern)}</td>
        <td>${d.self_disposed ? "Oui (maître de son propre signe)" : "—"}</td>
      </tr>`
    )
    .join("");

  const chains = analysis.dispositor_chains
    .map((c) => `<li>${c.chain.map(planetLabel).join(" → ")} ${c.type === "loop" ? "(boucle)" : c.final_dispositor ? `— dispositeur final : ${planetLabel(c.final_dispositor)}` : ""}</li>`)
    .join("");

  const mutual =
    analysis.mutual_receptions.length > 0
      ? `<ul>${analysis.mutual_receptions.map((r) => `<li>${r.planets.map(planetLabel).join(" ↔ ")} (${r.signs.map(signLabel).join(" / ")})</li>`).join("")}</ul>`
      : "<p>Aucune réception mutuelle détectée.</p>";

  return `
    <h3>${title}</h3>
    ${renderConvergenceSummary(analysis.convergence)}
    <table>
      <thead><tr><th>Planète</th><th>Signe occupé</th><th>Maître trad. / moderne</th><th>Auto-disposée</th></tr></thead>
      <tbody>${dispositorRows}</tbody>
    </table>
    <details class="chains-detail">
      <summary>Voir le détail des chaînes de dispositeurs (${analysis.dispositor_chains.length})</summary>
      <ul>${chains}</ul>
    </details>
    <h4>Réceptions mutuelles</h4>
    ${mutual}
  `;
}

function renderDispositorsTab(data) {
  document.getElementById("tab-dispositors").innerHTML =
    renderDispositorsSection(data.dispositors_traditional, "Système traditionnel") +
    renderDispositorsSection(data.dispositors_modern, "Système moderne");
}

// ---------------------------------------------------------------------
// Lots (parts arabes) — affichés dans "Lecture interprétée > Lots"
// ---------------------------------------------------------------------
function renderLotsDataPanel(data) {
  const container = document.getElementById("lots-data-panel");
  if (!data.lots || data.lots.length === 0) {
    container.innerHTML = "<p>Aucun lot calculé.</p>";
    return;
  }
  const rows = data.lots
    .map((lot) => {
      const aspects = lot.aspects_to_natal.length
        ? lot.aspects_to_natal.map((a) => `${planetLabel(a.planet)} ${a.type_fr} (${a.orb}°)`).join(", ")
        : "—";
      return `
      <tr>
        <td>${lot.name}</td>
        <td>${lot.signification}</td>
        <td>${signLabel(lot.sign)} ${lot.degree}°</td>
        <td>Maison ${lot.house}</td>
        <td>${aspects}</td>
      </tr>`;
    })
    .join("");

  container.innerHTML = `
    <p>Un thème de ${data.is_day_chart ? "jour" : "nuit"} utilise les formules diurnes/nocturnes appropriées pour chaque lot.</p>
    <table>
      <thead><tr><th>Lot</th><th>Signification</th><th>Position</th><th>Maison</th><th>Aspects natals</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// ---------------------------------------------------------------------
// Maisons dérivées — affichées dans "Lecture interprétée > Maisons dérivées"
// ---------------------------------------------------------------------
const DERIVED_HOUSE_PRESET_LABELS = {
  3: "Frères/sœurs", 4: "Mère", 5: "Enfants", 7: "Partenaire", 10: "Père", 11: "Amis",
};
let selectedDerivedReferenceHouse = 7;

function renderDerivedHousesDataPanel(data) {
  const container = document.getElementById("derived-data-panel");
  if (!data.derived_houses || data.derived_houses.length === 0) {
    container.innerHTML = "<p>Maisons dérivées non disponibles.</p>";
    return;
  }

  const options = Array.from({ length: 12 }, (_, i) => i + 1)
    .map((n) => {
      const preset = DERIVED_HOUSE_PRESET_LABELS[n];
      return `<option value="${n}" ${n === selectedDerivedReferenceHouse ? "selected" : ""}>Maison ${n}${preset ? " — " + preset : ""}</option>`;
    })
    .join("");

  container.innerHTML = `
    <div class="form-row">
      <label for="derived-house-select">Maison de référence (la personne à analyser)</label>
      <select id="derived-house-select">${options}</select>
    </div>
    <p class="derived-house-explainer">
      Maison de référence + 1 = la maison 1 (identité) de cette personne, +2 = sa maison 2 (argent), etc.
    </p>
    <div id="derived-house-table"></div>
  `;

  const renderTable = (referenceHouse) => {
    const entry = data.derived_houses.find((d) => d.reference_house === referenceHouse);
    const rows = entry.mapping
      .map(
        (m) => `
      <tr>
        <td>Maison ${m.derived_house_number}</td>
        <td>Sa maison ${m.represents_house} — ${m.keyword}</td>
        <td>${m.planets.length ? m.planets.map(planetLabel).join(", ") : "—"}</td>
      </tr>`
      )
      .join("");
    document.getElementById("derived-house-table").innerHTML = `
      <table>
        <thead><tr><th>Ma maison natale</th><th>Représente, pour elle</th><th>Planètes natales concernées</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  };

  document.getElementById("derived-house-select").addEventListener("change", (e) => {
    selectedDerivedReferenceHouse = parseInt(e.target.value, 10);
    renderTable(selectedDerivedReferenceHouse);
  });
  renderTable(selectedDerivedReferenceHouse);
}

// ---------------------------------------------------------------------
// Les 12 prochains mois (transits actuels + prévisions + profection)
// ---------------------------------------------------------------------
let timingLoadedForChartId = null;
let currentForecastEvents = [];

const FAVORABILITY_LABELS_FR = {
  favorable: "Favorable", a_nuancer: "À nuancer", exigeant: "Exigeant",
  instable: "Instable", intense: "Intense", neutre: "Neutre",
};

function flameBadge(intensity) {
  return `<span class="intensity-flames" title="Intensité ${intensity}/4">${"🔥".repeat(intensity)}</span>`;
}

function renderUpcomingEventsTable(events, minIntensity) {
  const filtered = events.filter((e) => e.intensity >= minIntensity);
  if (filtered.length === 0) {
    return "<p>Aucun transit à ce niveau d'intensité sur les 12 prochains mois.</p>";
  }
  const rows = filtered
    .map(
      (e) => `
      <tr>
        <td>${flameBadge(e.intensity)}</td>
        <td>${planetLabel(e.transiting_planet)}</td>
        <td>${e.type_fr}</td>
        <td>${planetLabel(e.natal_point)}</td>
        <td>${e.window_start} → ${e.window_end}</td>
        <td><span class="favorability-badge favorability-${e.favorability}">${FAVORABILITY_LABELS_FR[e.favorability] || e.favorability}</span></td>
      </tr>`
    )
    .join("");
  return `
    <p class="reading-section-intro">${filtered.length} transit${filtered.length > 1 ? "s" : ""} affiché${filtered.length > 1 ? "s" : ""} sur ${events.length} au total.</p>
    <table>
      <thead><tr><th>Intensité</th><th>Transit</th><th>Aspect</th><th>Point natal</th><th>Fenêtre active</th><th>Tendance</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderTimingDataPanel(timing, forecast) {
  const transitRows = timing.transiting_planets
    .map(
      (p) => `
      <tr>
        <td>${planetLabel(p.name)}</td>
        <td>${signLabel(p.sign)} ${p.degree}°</td>
        <td>${p.retrograde ? '<span class="retro">Rétrograde</span>' : "—"}</td>
      </tr>`
    )
    .join("");

  const aspectRows = timing.aspects.length
    ? timing.aspects
        .map(
          (a) => `
      <tr>
        <td>${flameBadge(a.intensity)}</td>
        <td>${planetLabel(a.transiting_planet)}</td>
        <td>${a.type_fr}</td>
        <td>${planetLabel(a.natal_point)}</td>
        <td>orbe ${a.orb}° · ${a.applying ? "applicatif" : "séparatif"}</td>
        <td><span class="favorability-badge favorability-${a.favorability}">${FAVORABILITY_LABELS_FR[a.favorability] || a.favorability}</span></td>
      </tr>`
        )
        .join("")
    : `<tr><td colspan="6">Aucun aspect actif avec l'orbe utilisé (3°).</td></tr>`;

  const prof = timing.profection;
  currentForecastEvents = forecast.events;

  document.getElementById("timing-data-panel").innerHTML = `
    <div class="form-row timing-controls">
      <label for="timing-date">Date</label>
      <input type="date" id="timing-date" value="${timing.date}" />
      <button type="button" id="timing-refresh-btn">Recalculer</button>
    </div>

    <h3>Profection de l'année</h3>
    <p>
      Année profectée en <strong>maison ${prof.profected_house}</strong> (${signLabel(prof.profected_sign)}) —
      planète maîtresse de l'année : <strong>${planetLabel(prof.year_ruler)}</strong>.
      Période du ${prof.profected_year_start} au ${prof.profected_year_end} (${prof.age} ans révolus).
    </p>

    <h3>Planètes en transit (${timing.date})</h3>
    <table>
      <thead><tr><th>Planète</th><th>Position</th><th>Mouvement</th></tr></thead>
      <tbody>${transitRows}</tbody>
    </table>

    <h3>Aspects actifs vers le thème natal</h3>
    <table>
      <thead><tr><th>Intensité</th><th>Transit</th><th>Aspect</th><th>Point natal</th><th>Détail</th><th>Tendance</th></tr></thead>
      <tbody>${aspectRows}</tbody>
    </table>

    <h3>Transits à venir (12 prochains mois)</h3>
    <div class="form-row timing-controls">
      <label for="timing-intensity-filter">Intensité minimale</label>
      <select id="timing-intensity-filter">
        <option value="4">🔥🔥🔥🔥 uniquement</option>
        <option value="3" selected>🔥🔥🔥 et plus (recommandé)</option>
        <option value="2">🔥🔥 et plus</option>
        <option value="1">Tous, y compris les transits mineurs</option>
      </select>
    </div>
    <div id="timing-upcoming-events-container">${renderUpcomingEventsTable(forecast.events, 3)}</div>
  `;

  document.getElementById("timing-intensity-filter").addEventListener("change", (event) => {
    document.getElementById("timing-upcoming-events-container").innerHTML = renderUpcomingEventsTable(
      currentForecastEvents,
      parseInt(event.target.value, 10)
    );
  });

  document.getElementById("timing-refresh-btn").addEventListener("click", () => {
    loadTimingDataPanel(document.getElementById("timing-date").value);
  });
}

async function loadTimingDataPanel(date) {
  if (!currentChart) return;
  const container = document.getElementById("timing-data-panel");
  container.innerHTML = "<p>Calcul en cours (transits + prévisions sur l'année)...</p>";
  try {
    const dateParam = date ? `?date=${date}` : "";
    const [timingRes, forecastRes] = await Promise.all([
      fetch(`/api/charts/${currentChart.id}/timing${dateParam}`),
      fetch(`/api/charts/${currentChart.id}/timing/forecast${dateParam}`),
    ]);
    if (!timingRes.ok) throw new Error(`Erreur ${timingRes.status} (transits)`);
    if (!forecastRes.ok) throw new Error(`Erreur ${forecastRes.status} (prévisions)`);
    const timing = await timingRes.json();
    const forecast = await forecastRes.json();
    renderTimingDataPanel(timing, forecast);
    timingLoadedForChartId = currentChart.id;
  } catch (err) {
    container.innerHTML = `<p class="error">Impossible de charger le timing : ${err.message}</p>`;
  }
}

// ---------------------------------------------------------------------
// Libération zodiacale (phases L1/L2) — affichée dans "Lecture interprétée > Lots"
// ---------------------------------------------------------------------
let zrLoadedForChartId = null;

function renderZrPeriodCard(period, title) {
  if (!period) return `<p>${title} : aucune période disponible.</p>`;
  const badges = `
    ${period.is_peak_period ? '<span class="zr-badge zr-badge-peak">Période de pointe</span>' : ""}
    ${period.is_loosing_of_the_bond ? '<span class="zr-badge zr-badge-loosing">Déliement du lien</span>' : ""}
  `;
  return `
    <div class="zr-phase-card">
      <h4>${title} : ${signLabel(period.sign)} ${badges}</h4>
      <p>Du ${period.start_date} au ${period.end_date} (${period.duration_years} an${period.duration_years > 1 ? "s" : ""}) —
      maître : ${planetLabel(period.ruling_planet)}</p>
    </div>`;
}

const ZR_DEFAULT_SELECTED_LOTS = new Set(["Lot de Fortune", "Lot d'Esprit"]);

function renderZrLotCard(lotName, lotResult, checked) {
  const l2Rows = lotResult.current_l1_l2_periods
    .map((p) => {
      const badges = `${p.is_peak_period ? '<span class="zr-badge zr-badge-peak">Pointe</span>' : ""}${p.is_loosing_of_the_bond ? '<span class="zr-badge zr-badge-loosing">Déliement</span>' : ""}`;
      const isCurrent = lotResult.current_l2 && p.start_date === lotResult.current_l2.start_date && p.sign === lotResult.current_l2.sign;
      return `<tr class="${isCurrent ? "zr-current-row" : ""}"><td>${signLabel(p.sign)}</td><td>${p.start_date} → ${p.end_date}</td><td>${badges || "—"}</td></tr>`;
    })
    .join("");

  return `
    <div class="zr-lot-card">
      <div class="zr-lot-header">
        <label class="zr-lot-checkbox-label">
          <input type="checkbox" class="zr-lot-checkbox" value="${lotName}" ${checked ? "checked" : ""} />
          <strong>${lotName}</strong>
        </label>
        <span class="zr-lot-current-sign">${signLabel(lotResult.lot_sign)}</span>
      </div>
      <details ${checked ? "open" : ""}>
        <summary>Voir les phases</summary>
        ${renderZrPeriodCard(lotResult.current_l1, "Phase L1 en cours")}
        ${renderZrPeriodCard(lotResult.current_l2, "Sous-phase L2 en cours")}
        <details>
          <summary>Détail des sous-phases L2 de la phase L1 en cours (${lotResult.current_l1_l2_periods.length})</summary>
          <table>
            <thead><tr><th>Signe</th><th>Période</th><th></th></tr></thead>
            <tbody>${l2Rows}</tbody>
          </table>
        </details>
      </details>
    </div>`;
}

function renderZrDataPanel(zr, previouslyChecked) {
  const container = document.getElementById("zr-data-panel");
  // Conserve la sélection de lots de l'utilisateur si elle recalcule juste la date, plutôt
  // que de revenir systématiquement à Fortune + Esprit.
  const selectedLots = previouslyChecked && previouslyChecked.size > 0 ? previouslyChecked : ZR_DEFAULT_SELECTED_LOTS;

  const lotCards = Object.entries(zr.lots)
    .map(([lotName, lotResult]) => renderZrLotCard(lotName, lotResult, selectedLots.has(lotName)))
    .join("");

  container.innerHTML = `
    <div class="form-row timing-controls">
      <label for="zr-date">Date</label>
      <input type="date" id="zr-date" value="${zr.as_of_date}" />
      <button type="button" id="zr-refresh-btn">Recalculer</button>
    </div>
    ${zr.edge_case_same_sign_applied ? '<p class="error">Lot de Fortune et Lot d\'Esprit dans le même signe : le calcul du Lot d\'Esprit a été décalé d\'un signe, selon la convention documentée.</p>' : ""}
    <p class="reading-section-intro">Cochez un ou plusieurs lots ci-dessous pour la lecture (par défaut : Fortune + Esprit). Un seul lot coché donne une lecture approfondie ; plusieurs lots ajoutent une lecture croisée entre eux.</p>
    ${lotCards}
  `;

  document.getElementById("zr-refresh-btn").addEventListener("click", () => {
    loadZrDataPanel(document.getElementById("zr-date").value);
  });
}

async function loadZrDataPanel(date) {
  if (!currentChart) return;
  const container = document.getElementById("zr-data-panel");
  const previouslyChecked = new Set(
    Array.from(container.querySelectorAll(".zr-lot-checkbox:checked")).map((el) => el.value)
  );
  container.innerHTML = "<p>Calcul en cours (phases et sous-phases)...</p>";
  try {
    const dateParam = date ? `?date=${date}` : "";
    const res = await fetch(`/api/charts/${currentChart.id}/zodiacal-releasing${dateParam}`);
    if (!res.ok) throw new Error(`Erreur ${res.status}`);
    const zr = await res.json();
    renderZrDataPanel(zr, previouslyChecked);
    zrLoadedForChartId = currentChart.id;
  } catch (err) {
    container.innerHTML = `<p class="error">Impossible de charger les phases : ${err.message}</p>`;
  }
}

// ---------------------------------------------------------------------
// Onglets (section "Thème natal")
// ---------------------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.remove("hidden");
  });
});

// ---------------------------------------------------------------------
// Sous-onglets de "Lecture interprétée" (Générale / Lots / Maisons dérivées / Timing)
// ---------------------------------------------------------------------
document.querySelectorAll(".reading-tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".reading-tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".reading-tab-panel").forEach((p) => p.classList.add("hidden"));
    btn.classList.add("active");
    document.getElementById(`reading-tab-${btn.dataset.readingTab}`).classList.remove("hidden");

    if (btn.dataset.readingTab === "timing" && currentChart && timingLoadedForChartId !== currentChart.id) {
      loadTimingDataPanel();
    }
    if (btn.dataset.readingTab === "lots" && currentChart && zrLoadedForChartId !== currentChart.id) {
      loadZrDataPanel();
    }
  });
});

// ---------------------------------------------------------------------
// Lecture interprétée (LLM)
// ---------------------------------------------------------------------
function tinyMarkdownToHtml(text) {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const lines = escaped.split("\n");
  let html = "";
  let inList = false;
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (line.startsWith("## ")) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h3>${line.slice(3)}</h3>`;
    } else if (line.startsWith("# ")) {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<h2>${line.slice(2)}</h2>`;
    } else if (line.startsWith("- ")) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${line.slice(2)}</li>`;
    } else if (line === "") {
      if (inList) { html += "</ul>"; inList = false; }
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      html += `<p>${line}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

document.getElementById("generate-reading-btn").addEventListener("click", async () => {
  const errorEl = document.getElementById("reading-error");
  const outputEl = document.getElementById("reading-output");
  const btn = document.getElementById("generate-reading-btn");
  errorEl.textContent = "";
  outputEl.innerHTML = "";

  if (!currentChart) {
    errorEl.textContent = "Calculez d'abord un thème natal.";
    return;
  }

  const focusAreas = Array.from(document.querySelectorAll('input[name="focus"]:checked')).map((c) => c.value);
  if (focusAreas.length === 0) {
    errorEl.textContent = "Sélectionnez au moins une zone.";
    return;
  }

  btn.disabled = true;
  btn.textContent = "Génération en cours...";
  try {
    const res = await fetch(`/api/charts/${currentChart.id}/readings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reading_type: "global", focus_areas: focusAreas }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `Erreur ${res.status}`);
    }
    const reading = await res.json();
    outputEl.innerHTML = tinyMarkdownToHtml(reading.reading_text);
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Générer la lecture";
  }
});

// ---------------------------------------------------------------------
// Lectures spécialisées (Lots / Maisons dérivées / Timing)
// ---------------------------------------------------------------------
async function generateSpecializedReading({ btnId, errorId, outputId, defaultLabel, requestBody }) {
  const errorEl = document.getElementById(errorId);
  const outputEl = document.getElementById(outputId);
  const btn = document.getElementById(btnId);
  errorEl.textContent = "";
  outputEl.innerHTML = "";

  if (!currentChart) {
    errorEl.textContent = "Calculez d'abord un thème natal.";
    return;
  }

  btn.disabled = true;
  btn.textContent = "Génération en cours...";
  try {
    const res = await fetch(`/api/charts/${currentChart.id}/readings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `Erreur ${res.status}`);
    }
    const reading = await res.json();
    outputEl.innerHTML = tinyMarkdownToHtml(reading.reading_text);
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = defaultLabel;
  }
}

document.getElementById("generate-lots-reading-btn").addEventListener("click", () => {
  generateSpecializedReading({
    btnId: "generate-lots-reading-btn",
    errorId: "lots-reading-error",
    outputId: "lots-reading-output",
    defaultLabel: "Générer la lecture des lots",
    requestBody: { reading_type: "lots" },
  });
});

let selectedZrMode = "current";
document.querySelectorAll(".zr-mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".zr-mode-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    selectedZrMode = btn.dataset.zrMode;
  });
});

document.getElementById("generate-zr-reading-btn").addEventListener("click", () => {
  const errorEl = document.getElementById("zr-reading-error");
  const selectedLots = Array.from(document.querySelectorAll(".zr-lot-checkbox:checked")).map((el) => el.value);
  if (selectedLots.length === 0) {
    errorEl.textContent = "Cochez au moins un lot pour générer une lecture.";
    return;
  }
  errorEl.textContent = "";
  const dateInput = document.getElementById("zr-date");
  generateSpecializedReading({
    btnId: "generate-zr-reading-btn",
    errorId: "zr-reading-error",
    outputId: "zr-reading-output",
    defaultLabel: "Générer la lecture des phases",
    requestBody: {
      reading_type: "zodiacal_releasing",
      as_of_date: dateInput ? dateInput.value : undefined,
      zr_selected_lots: selectedLots,
      zr_mode: selectedZrMode,
    },
  });
});

document.getElementById("generate-derived-reading-btn").addEventListener("click", () => {
  generateSpecializedReading({
    btnId: "generate-derived-reading-btn",
    errorId: "derived-reading-error",
    outputId: "derived-reading-output",
    defaultLabel: "Générer la lecture des maisons dérivées",
    requestBody: { reading_type: "derived_houses", reference_house: selectedDerivedReferenceHouse },
  });
});

document.getElementById("generate-timing-reading-btn").addEventListener("click", () => {
  const dateInput = document.getElementById("timing-date");
  generateSpecializedReading({
    btnId: "generate-timing-reading-btn",
    errorId: "timing-reading-error",
    outputId: "timing-reading-output",
    defaultLabel: "Générer la lecture des 12 prochains mois",
    requestBody: { reading_type: "timing", as_of_date: dateInput ? dateInput.value : undefined },
  });
});
