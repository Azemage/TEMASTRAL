// Signes/planètes/aspects : symboles et libellés traduits fournis par i18n.js
// (SIGN_SYMBOLS, PLANET_SYMBOLS, signLabel, planetLabel, aspectTypeLabel, t, tf, pick...).

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

function el(html) {
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

function escapeHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ---------------------------------------------------------------------
// Langue : applique les traductions statiques au chargement et à chaque
// changement, et re-rend les panneaux dynamiques actuellement visibles.
// ---------------------------------------------------------------------
applyStaticTranslations();

document.querySelectorAll(".lang-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    setLanguage(btn.dataset.lang);
    applyStaticTranslations();
    rerenderAfterLanguageChange();
  });
});

function rerenderAfterLanguageChange() {
  if (!currentChart) return;
  const data = currentChart.computed_chart_data;
  renderChart(currentChart);
  if (timingLoadedForChartId === currentChart.id) loadTimingDataPanel(document.getElementById("timing-date")?.value);
  if (zrLoadedForChartId === currentChart.id) {
    document.getElementById("zr-axis-panel").dataset.loaded = "";
    loadZrDataPanel(document.getElementById("zr-date")?.value);
  }
  if (astroLinesCache[selectedAstroMode]) renderAstroMapPanel(astroLinesCache[selectedAstroMode]);
  renderAstroSavedLocationsList();
}

// ---------------------------------------------------------------------
// Liste des fuseaux horaires (menu déroulant)
// ---------------------------------------------------------------------
async function loadTimezonesInto(selectId, fallbackDefault = "Europe/Paris") {
  const select = document.getElementById(selectId);
  if (!select) return;
  try {
    const res = await fetch("/api/reference/timezones");
    const zones = await res.json();
    select.innerHTML = zones.map((tz) => `<option value="${tz}">${tz}</option>`).join("");
    select.value = fallbackDefault;
  } catch (err) {
    // Pas de réseau/API indisponible : on retombe sur un champ texte libre plutôt que de bloquer le formulaire.
    const fallbackInput = el(
      `<input type="text" id="${selectId}" value="${fallbackDefault}" placeholder="${fallbackDefault}" required />`
    );
    select.replaceWith(fallbackInput);
  }
}
loadTimezonesInto("timezone");

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
      resultsDiv.innerHTML = `<p class="error">${t("search_unavailable")}</p>`;
      return;
    }
    const locations = await res.json();
    if (locations.length === 0) {
      resultsDiv.innerHTML = `<p>${t("no_results")}</p>`;
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
    resultsDiv.innerHTML = `<p class="error">${t("search_unavailable")}</p>`;
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
  submitBtn.textContent = t("status_calculating");
  try {
    const res = await fetch("/api/charts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${t("error_prefix")} ${res.status}`);
    }
    currentChart = await res.json();
    renderChart(currentChart);
    document.getElementById("results-section").classList.remove("hidden");
    document.getElementById("section-toggle-row").classList.remove("hidden");
    // Les sections restent repliées par défaut (allège l'affichage initial) : seuls les
    // boutons pour les révéler à la demande sont montrés, voir écouteurs .section-toggle-btn.
    ["reading-section", "astro-section", "witchy-section", "weekly-weather-section"].forEach((id) => document.getElementById(id).classList.add("hidden"));
    document.querySelectorAll(".section-toggle-btn").forEach((btn) => btn.classList.remove("active"));
    resetAstrocartographyStateForNewChart();
    resetWitchyCalendarStateForNewChart();
    resetWeeklyWeatherStateForNewChart();
    document.getElementById("results-section").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = t("btn_calculate_chart");
  }
});

// Section 3 (Lecture interprétée), 4 (Astrocartographie) et 5 (Calendrier ésotérique) restent
// repliées par défaut sous la roue natale : chaque bouton révèle/replie sa propre section,
// indépendamment des autres.
document.querySelectorAll(".section-toggle-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = document.getElementById(btn.dataset.target);
    if (!target) return;
    const wasHidden = target.classList.contains("hidden");
    target.classList.toggle("hidden");
    btn.classList.toggle("active", wasHidden);
    if (wasHidden) target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

function renderTraitTags(characterTraits) {
  if (!characterTraits || !characterTraits.keywords || characterTraits.keywords.length === 0) return "";
  const dominant = new Set(characterTraits.dominant_traits || []);
  const tags = characterTraits.keywords
    .map((trait) => `<span class="trait-tag${dominant.has(trait) ? " trait-tag-dominant" : ""}">${trait}</span>`)
    .join("");

  const sourceRows = (characterTraits.sources || [])
    .map((s) => {
      const originLabel = pick(TRAIT_ORIGIN_LABELS[s.origin]) || s.origin;
      const isSignBased = !s.origin.startsWith("dominant_");
      const labelText = s.origin === "dominant_element" ? pick(ELEMENT_LABELS[s.label]) || s.label
        : s.origin === "dominant_modality" ? pick(MODALITY_LABELS[s.label]) || s.label
        : signLabel(s.label);
      const heading = isSignBased ? `${originLabel} ${t("in_sign")} ${labelText}` : `${originLabel} : ${labelText}`;
      const houseInfo = s.house ? ` (${t("house_prefix").toLowerCase()} ${s.house}${s.house_context ? " — " + s.house_context : ""})` : "";
      return `<li><strong>${heading}</strong>${houseInfo} : ${s.traits.join(", ")}</li>`;
    })
    .join("");

  const generational = (characterTraits.generational_placements || [])
    .map((p) => `<li><strong>${planetLabel(p.planet)}</strong> ${t("in_sign")} ${signLabel(p.sign)}, ${t("house_prefix").toLowerCase()} ${p.house} : ${p.note}</li>`)
    .join("");

  return `
    <div class="trait-tags">${tags}</div>
    <details class="traits-detail">
      <summary>${t("detail_by_planet")}</summary>
      <ul>${sourceRows}</ul>
      ${
        generational
          ? `<p class="reading-section-intro">${t("generational_planets_note")}</p><ul>${generational}</ul>`
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
    // Traits nettement plus marqués que les pointillés fins de position des planètes
    // (`stroke-dasharray="2,2"`, couleur `#4a4d6c` plus bas) : sans ce contraste, les deux se
    // confondaient facilement à l'œil. Les 4 axes (ASC/DSC/MC/IC) ressortent encore davantage.
    const isAngular = [1, 4, 7, 10].includes(house.number);
    housesSvg += `<line x1="${inner.x.toFixed(2)}" y1="${inner.y.toFixed(2)}" x2="${outer.x.toFixed(2)}" y2="${outer.y.toFixed(2)}" stroke="${isAngular ? "#f1f2ff" : "#6d70a8"}" stroke-width="${isAngular ? 2.4 : 1.4}" />`;

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
  // Carte planète -> aspects la concernant, pour l'afficher dans l'info-bulle au survol
  // (même filtre showMinorAspects que les traits effectivement dessinés, pour rester cohérent
  // avec ce que l'utilisateur voit sur la roue).
  const aspectsByPlanet = {};
  data.aspects.forEach((aspect) => {
    if (!showMinorAspects && !MAJOR_ASPECTS.has(aspect.type)) return;
    const describe = (otherPlanet) => ({
      orb: aspect.orb,
      text: `${aspectTypeLabel(aspect.type)} ${planetLabel(otherPlanet)} (${t("orb_prefix")} ${aspect.orb}°)`,
    });
    (aspectsByPlanet[aspect.planet1] ||= []).push(describe(aspect.planet2));
    (aspectsByPlanet[aspect.planet2] ||= []).push(describe(aspect.planet1));
  });

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

    const planetAspects = (aspectsByPlanet[planet.name] || []).sort((a, b) => a.orb - b.orb);
    const aspectsLines = planetAspects.length ? "\n" + planetAspects.map((a) => a.text).join("\n") : "";
    const planetTooltip = escapeHtml(
      `${planetLabel(planet.name)} — ${signLabel(planet.sign)} ${planet.degree}° — ${t("house_prefix")} ${planet.house ?? "—"}${planet.retrograde ? " · " + t("retrograde") : ""}` +
        aspectsLines
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
      `${planetLabel(aspect.planet1)} ${aspectTypeLabel(aspect.type)} ${planetLabel(aspect.planet2)} — ${t("orb_prefix")} ${aspect.orb}° (${aspect.applying ? t("applying") : t("separating")})`
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
  const items = ["conjunction", "sextile", "square", "trine", "opposition"];
  const minorItems = ["semi_sextile", "semi_square", "sesquiquadrate", "quincunx", "quintile"];
  const swatch = (key) =>
    `<span class="legend-item"><span class="legend-swatch" style="background:${ASPECT_COLORS[key]}"></span>${aspectTypeLabel(key)}</span>`;

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
    const tooltipRect = tooltip.getBoundingClientRect();
    let left = e.clientX - rect.left + 16;
    let top = e.clientY - rect.top + 16;
    // Évite que l'info-bulle ne déborde du cadre à droite/en bas — hauteur mesurée dynamiquement
    // (pas une constante fixe) car le survol d'une planète avec plusieurs aspects peut afficher
    // une info-bulle sur de nombreuses lignes.
    if (left + tooltipRect.width > rect.width) left = e.clientX - rect.left - tooltipRect.width - 10;
    if (top + tooltipRect.height > rect.height) top = e.clientY - rect.top - tooltipRect.height - 10;
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
        ${t("show_minor_aspects")}
      </label>
      <button type="button" id="wheel-fullscreen-btn" class="wheel-fullscreen-btn">${t("fullscreen")}</button>
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
  btn.textContent = active ? t("exit_fullscreen") : t("fullscreen");
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
      <strong>${chart.subject_name || t("chart_default_name")}</strong> —
      ${t("born_prefix")} ${t("on_date")} ${chart.birth_date}
      ${chart.birth_time_known ? t("at_time") + " " + (chart.birth_time || "") : t("unknown_time_paren")}
      ${t("in_city")} ${chart.birth_city || ""}
    </p>
    <p>
      ☉ ${planetLabel("Sun")} ${t("in_sign")} ${signLabel(sun.sign)} ${sun.degree}°
      &nbsp;|&nbsp; ☽ ${planetLabel("Moon")} ${t("in_sign")} ${signLabel(moon.sign)} ${moon.degree}°
      &nbsp;|&nbsp; ${planetLabel("ascendant")} ${signLabel(asc.sign)} ${asc.degree}°
      &nbsp;|&nbsp; ${data.is_day_chart ? t("day_chart_label") : t("night_chart_label")}
    </p>
    ${!data.time_known ? `<p class="error">${t("unknown_birth_time_warning")}</p>` : ""}
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
  compatChartsLoadedForChartId = null; // nouveau thème : re-fetcher la liste des cartes au prochain accès
  compatChartBId = null;
}

function renderPlanetsTab(data) {
  const rows = data.planets
    .map(
      (p) => `
      <tr>
        <td>${planetLabel(p.name)}</td>
        <td>${signLabel(p.sign)}</td>
        <td>${p.degree}°</td>
        <td>${t("house_prefix")} ${p.house ?? "—"}</td>
        <td>${p.retrograde ? `<span class="retro">${t("retrograde")}</span>` : "—"}</td>
      </tr>`
    )
    .join("");

  const angleRows = ["ascendant", "midheaven", "descendant", "imum_coeli"]
    .map((key) => {
      const a = data.angles[key];
      return `<tr><td>${planetLabel(key)}</td><td>${signLabel(a.sign)}</td><td>${a.degree}°</td><td>—</td><td>—</td></tr>`;
    })
    .join("");

  document.getElementById("tab-planets").innerHTML = `
    <table>
      <thead><tr><th>${t("th_body")}</th><th>${t("th_sign")}</th><th>${t("th_degree")}</th><th>${t("house_prefix")}</th><th>${t("th_movement")}</th></tr></thead>
      <tbody>${rows}${angleRows}</tbody>
    </table>
  `;
}

function renderHousesTab(data) {
  const rows = data.houses
    .map((h) => `<tr><td>${t("house_prefix")} ${h.number}</td><td>${signLabel(h.sign)}</td><td>${h.degree}°</td></tr>`)
    .join("");
  document.getElementById("tab-houses").innerHTML = `
    <table>
      <thead><tr><th>${t("house_prefix")}</th><th>${t("th_sign")}</th><th>${t("th_degree")}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderAspectsTab(data) {
  if (data.aspects.length === 0) {
    document.getElementById("tab-aspects").innerHTML = `<p>${t("no_aspect_detected")}</p>`;
    return;
  }
  const rows = data.aspects
    .map(
      (a) => `
      <tr>
        <td>${planetLabel(a.planet1)}</td>
        <td>${aspectTypeLabel(a.type)}</td>
        <td>${planetLabel(a.planet2)}</td>
        <td>${t("orb_prefix")} ${a.orb}°</td>
        <td>${a.applying ? t("applying") : t("separating")}</td>
      </tr>`
    )
    .join("");
  document.getElementById("tab-aspects").innerHTML = `
    <table>
      <thead><tr><th>${t("th_body")} 1</th><th>${t("th_aspect")}</th><th>${t("th_body")} 2</th><th>${t("th_orb")}</th><th>${t("th_direction")}</th></tr></thead>
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
    <h3>${t("tab_balance")}</h3>
    ${balanceBar(pick(ELEMENT_LABELS.fire), e.fire, maxE)}
    ${balanceBar(pick(ELEMENT_LABELS.earth), e.earth, maxE)}
    ${balanceBar(pick(ELEMENT_LABELS.air), e.air, maxE)}
    ${balanceBar(pick(ELEMENT_LABELS.water), e.water, maxE)}
    <h3>${t("modalities_title")}</h3>
    ${balanceBar(pick(MODALITY_LABELS.cardinal), m.cardinal, maxM)}
    ${balanceBar(pick(MODALITY_LABELS.fixed), m.fixed, maxM)}
    ${balanceBar(pick(MODALITY_LABELS.mutable), m.mutable, maxM)}
  `;
}

function renderConvergenceSummary(convergence) {
  if (!convergence || !convergence.dominant_dispositor) {
    return `<p>${t("no_clear_convergence")}</p>`;
  }
  const { dominant_dispositor, dominant_count, total_chains, level } = convergence;
  const label = planetLabel(dominant_dispositor);
  const summary = `<p class="convergence-summary">🔑 <strong>${t("final_dispositor_of_chart")} ${label}</strong> (${dominant_count}/${total_chains})</p>`;

  if (level === "forte" || level === "notable") {
    const badge = level === "forte" ? t("strong_convergence") : t("notable_convergence");
    return `${summary}<div class="convergence-alert convergence-${level}">⚡ ${badge} : ${label}</div>`;
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
        <td>${d.self_disposed ? t("yes_self_ruled") : "—"}</td>
      </tr>`
    )
    .join("");

  const chains = analysis.dispositor_chains
    .map((c) => `<li>${c.chain.map(planetLabel).join(" → ")} ${c.type === "loop" ? t("loop_suffix") : c.final_dispositor ? `— ${t("final_dispositor_prefix")} ${planetLabel(c.final_dispositor)}` : ""}</li>`)
    .join("");

  const mutual =
    analysis.mutual_receptions.length > 0
      ? `<ul>${analysis.mutual_receptions.map((r) => `<li>${r.planets.map(planetLabel).join(" ↔ ")} (${r.signs.map(signLabel).join(" / ")})</li>`).join("")}</ul>`
      : `<p>${t("no_mutual_reception")}</p>`;

  return `
    <h3>${title}</h3>
    ${renderConvergenceSummary(analysis.convergence)}
    <table>
      <thead><tr><th>${t("th_planet_generic")}</th><th>${t("th_sign_occupied")}</th><th>${t("th_ruler_trad_modern")}</th><th>${t("th_self_disposed")}</th></tr></thead>
      <tbody>${dispositorRows}</tbody>
    </table>
    <details class="chains-detail">
      <summary>${t("see_dispositor_chains_detail")} (${analysis.dispositor_chains.length})</summary>
      <ul>${chains}</ul>
    </details>
    <h4>${t("mutual_receptions_title")}</h4>
    ${mutual}
  `;
}

function renderDispositorsTab(data) {
  document.getElementById("tab-dispositors").innerHTML =
    renderDispositorsSection(data.dispositors_traditional, t("traditional_system")) +
    renderDispositorsSection(data.dispositors_modern, t("modern_system"));
}

// ---------------------------------------------------------------------
// Lots (parts arabes) — affichés dans "Lecture interprétée > Lots"
// ---------------------------------------------------------------------
function renderLotsDataPanel(data) {
  const container = document.getElementById("lots-data-panel");
  if (!data.lots || data.lots.length === 0) {
    container.innerHTML = `<p>${t("no_lot_calculated")}</p>`;
    return;
  }
  const rows = data.lots
    .map((lot) => {
      const aspects = lot.aspects_to_natal.length
        ? lot.aspects_to_natal.map((a) => `${planetLabel(a.planet)} ${aspectTypeLabel(a.type)} (${a.orb}°)`).join(", ")
        : "—";
      let reliabilityBadge = "";
      if (lot.category === "moderne_non_canonique") {
        reliabilityBadge = `<span class="lot-badge lot-badge-modern" title="${escapeHtml(lot.construction_logic || "")}">${t("badge_non_canonical")}</span>`;
      } else if (lot.certainty && lot.certainty.toLowerCase().startsWith("moyenne")) {
        reliabilityBadge = `<span class="lot-badge lot-badge-disputed" title="${escapeHtml(lot.certainty)}">${t("badge_disputed_attribution")}</span>`;
      }
      return `
      <tr>
        <td>${lotLabel(lot.name)} ${reliabilityBadge}</td>
        <td>${lotSignification(lot.name)}</td>
        <td>${signLabel(lot.sign)} ${lot.degree}°</td>
        <td>${t("house_prefix")} ${lot.house}</td>
        <td>${aspects}</td>
      </tr>`;
    })
    .join("");

  container.innerHTML = `
    <p>${tf("lots_day_night_note", { dayNight: data.is_day_chart ? t("day_chart") : t("night_chart") })}</p>
    <table>
      <thead><tr><th>${t("th_lot")}</th><th>${t("th_meaning")}</th><th>${t("th_position")}</th><th>${t("house_prefix")}</th><th>${t("th_natal_aspects")}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// ---------------------------------------------------------------------
// Maisons dérivées — affichées dans "Lecture interprétée > Maisons dérivées"
// ---------------------------------------------------------------------
let selectedDerivedRelationKey = "partner";
let derivedHouseRelationsConfig = null;

function deriveHouseClient(n1, n2) {
  return ((n1 - 1 + (n2 - 1)) % 12) + 1;
}

async function loadDerivedHouseRelationsConfig() {
  if (derivedHouseRelationsConfig) return derivedHouseRelationsConfig;
  const res = await fetch("/api/reference/derived-house-relations");
  derivedHouseRelationsConfig = await res.json();
  return derivedHouseRelationsConfig;
}

function referenceHouseForRelationKey(relationKey, config) {
  if (relationKey.startsWith("custom:")) {
    const [, n1Str, n2Str] = relationKey.split(":");
    return deriveHouseClient(parseInt(n1Str, 10), parseInt(n2Str, 10));
  }
  const first = config.first_order.find((r) => r.key === relationKey);
  if (first) return first.reference_house;
  const second = config.second_order.find((r) => r.key === relationKey);
  if (second) return deriveHouseClient(second.n1, second.n2);
  return 7;
}

async function renderDerivedHousesDataPanel(data) {
  const container = document.getElementById("derived-data-panel");
  if (!data.derived_houses || data.derived_houses.length === 0) {
    container.innerHTML = `<p>${t("derived_houses_unavailable")}</p>`;
    return;
  }

  const config = await loadDerivedHouseRelationsConfig();

  const optionsFor = (list) =>
    list
      .map(
        (r) => `<option value="${r.key}" ${r.key === selectedDerivedRelationKey ? "selected" : ""}>${derivedRelationLabel(r.key, r.label)}</option>`
      )
      .join("");
  const firstOrderOptions = optionsFor(config.first_order);
  const secondOrderOptions = optionsFor(config.second_order);
  const customSelected = selectedDerivedRelationKey.startsWith("custom:") ? "selected" : "";

  container.innerHTML = `
    <div class="form-row">
      <label for="derived-house-select">${t("label_relation_to_analyze")}</label>
      <select id="derived-house-select">
        <optgroup label="${t("zr_relations_group_direct")}">${firstOrderOptions}</optgroup>
        <optgroup label="${t("zr_relations_group_second_order")}">${secondOrderOptions}</optgroup>
        <option value="__custom__" ${customSelected}>${t("option_custom_relation")}</option>
      </select>
    </div>
    <div id="derived-custom-selectors" class="form-row hidden">
      <label for="derived-custom-n1">${t("label_from_whom")}</label>
      <select id="derived-custom-n1">${firstOrderOptions}</select>
      <label for="derived-custom-n2">${t("label_which_relation")}</label>
      <select id="derived-custom-n2">${firstOrderOptions}</select>
    </div>
    <p class="derived-house-explainer">${t("derived_house_explainer")}</p>
    <div id="derived-house-table"></div>
  `;

  const relationSelect = document.getElementById("derived-house-select");
  const customSelectors = document.getElementById("derived-custom-selectors");
  const customN1 = document.getElementById("derived-custom-n1");
  const customN2 = document.getElementById("derived-custom-n2");

  const renderTable = (relationKey) => {
    const referenceHouse = referenceHouseForRelationKey(relationKey, config);
    const entry = data.derived_houses.find((d) => d.reference_house === referenceHouse);
    const rows = entry.mapping
      .map(
        (m) => `
      <tr>
        <td>${t("house_prefix")} ${m.derived_house_number}</td>
        <td>${t("their_house")} ${m.represents_house} — ${pick(HOUSE_KEYWORDS[m.represents_house]) || m.keyword}</td>
        <td>${m.planets.length ? m.planets.map(planetLabel).join(", ") : "—"}</td>
      </tr>`
      )
      .join("");
    document.getElementById("derived-house-table").innerHTML = `
      <table>
        <thead><tr><th>${t("th_my_natal_house")}</th><th>${t("th_represents_for_them")}</th><th>${t("th_relevant_natal_planets")}</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  };

  const applyCustomVisibility = () => {
    customSelectors.classList.toggle("hidden", relationSelect.value !== "__custom__");
  };

  const customRelationKey = () => {
    const n1 = config.first_order.find((r) => r.key === customN1.value).reference_house;
    const n2 = config.first_order.find((r) => r.key === customN2.value).reference_house;
    return `custom:${n1}:${n2}`;
  };

  relationSelect.addEventListener("change", () => {
    applyCustomVisibility();
    selectedDerivedRelationKey = relationSelect.value === "__custom__" ? customRelationKey() : relationSelect.value;
    renderTable(selectedDerivedRelationKey);
  });
  [customN1, customN2].forEach((el) =>
    el.addEventListener("change", () => {
      selectedDerivedRelationKey = customRelationKey();
      renderTable(selectedDerivedRelationKey);
    })
  );

  applyCustomVisibility();
  renderTable(selectedDerivedRelationKey);
}

// ---------------------------------------------------------------------
// Les 12 prochains mois (transits actuels + prévisions + profection)
// ---------------------------------------------------------------------
let timingLoadedForChartId = null;
let currentForecastEvents = [];

function flameBadge(intensity) {
  return `<span class="intensity-flames" title="${t("th_intensity")} ${intensity}/4">${starRatingHtml(intensity, { max: 4, compact: true, showScore: false })}</span>`;
}

function renderUpcomingEventsTable(events, minIntensity) {
  const filtered = events.filter((e) => e.intensity >= minIntensity);
  if (filtered.length === 0) {
    return `<p>${t("no_transit_at_intensity")}</p>`;
  }
  const rows = filtered
    .map(
      (e) => `
      <tr>
        <td>${flameBadge(e.intensity)}</td>
        <td>${planetLabel(e.transiting_planet)}</td>
        <td>${aspectTypeLabel(e.type)}</td>
        <td>${planetLabel(e.natal_point)}</td>
        <td>${e.window_start} → ${e.window_end}</td>
        <td><span class="favorability-badge favorability-${e.favorability}">${pick(FAVORABILITY_LABELS[e.favorability]) || e.favorability}</span></td>
      </tr>`
    )
    .join("");
  return `
    <p class="reading-section-intro">${filtered.length}/${events.length}</p>
    <table>
      <thead><tr><th>${t("th_intensity")}</th><th>${t("th_transit")}</th><th>${t("th_aspect")}</th><th>${t("th_natal_point")}</th><th>${t("th_active_window")}</th><th>${t("th_trend")}</th></tr></thead>
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
        <td>${p.retrograde ? `<span class="retro">${t("retrograde")}</span>` : "—"}</td>
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
        <td>${aspectTypeLabel(a.type)}</td>
        <td>${planetLabel(a.natal_point)}</td>
        <td>${t("orb_prefix")} ${a.orb}° · ${a.applying ? t("applying") : t("separating")}</td>
        <td><span class="favorability-badge favorability-${a.favorability}">${pick(FAVORABILITY_LABELS[a.favorability]) || a.favorability}</span></td>
      </tr>`
        )
        .join("")
    : `<tr><td colspan="6">${t("no_active_aspect")}</td></tr>`;

  const prof = timing.profection;
  currentForecastEvents = forecast.events;

  document.getElementById("timing-data-panel").innerHTML = `
    <div class="form-row timing-controls">
      <label for="timing-date">${t("label_date")}</label>
      <input type="date" id="timing-date" value="${timing.date}" />
      <button type="button" id="timing-refresh-btn">${t("btn_recalculate")}</button>
    </div>

    <h3>${t("timing_upcoming_events_title")}</h3>
    <div class="form-row timing-controls">
      <label for="timing-intensity-filter">${t("label_min_intensity")}</label>
      <select id="timing-intensity-filter">
        <option value="4">${t("intensity_4_only")}</option>
        <option value="3" selected>${t("intensity_3_plus")}</option>
        <option value="2">${t("intensity_2_plus")}</option>
        <option value="1">${t("intensity_all")}</option>
      </select>
    </div>
    <div id="timing-upcoming-events-container">${renderUpcomingEventsTable(forecast.events, 3)}</div>

    <h3>${t("timing_profection_title")}</h3>
    <p>
      ${t("house_prefix")} <strong>${prof.profected_house}</strong> (${signLabel(prof.profected_sign)}) —
      <strong>${planetLabel(prof.year_ruler)}</strong>.
      ${prof.profected_year_start} → ${prof.profected_year_end} (${prof.age})
    </p>

    <h3>${t("timing_transiting_planets_title")} (${timing.date})</h3>
    <table>
      <thead><tr><th>${t("th_planet")}</th><th>${t("th_position")}</th><th>${t("th_movement")}</th></tr></thead>
      <tbody>${transitRows}</tbody>
    </table>

    <h3>${t("timing_active_aspects_title")}</h3>
    <table>
      <thead><tr><th>${t("th_intensity")}</th><th>${t("th_transit")}</th><th>${t("th_aspect")}</th><th>${t("th_natal_point")}</th><th>${t("th_detail")}</th><th>${t("th_trend")}</th></tr></thead>
      <tbody>${aspectRows}</tbody>
    </table>
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
  container.innerHTML = `<p>${t("status_computing_timing")}</p>`;
  try {
    const dateParam = date ? `?date=${date}` : "";
    const [timingRes, forecastRes] = await Promise.all([
      fetch(`/api/charts/${currentChart.id}/timing${dateParam}`),
      fetch(`/api/charts/${currentChart.id}/timing/forecast${dateParam}`),
    ]);
    if (!timingRes.ok) throw new Error(`${t("error_prefix")} ${timingRes.status}`);
    if (!forecastRes.ok) throw new Error(`${t("error_prefix")} ${forecastRes.status}`);
    const timing = await timingRes.json();
    const forecast = await forecastRes.json();
    renderTimingDataPanel(timing, forecast);
    timingLoadedForChartId = currentChart.id;
  } catch (err) {
    container.innerHTML = `<p class="error">${t("error_loading_timing")} ${err.message}</p>`;
  }
}

// ---------------------------------------------------------------------
// Libération zodiacale (phases L1/L2) — affichée dans "Lecture interprétée > Lots"
// ---------------------------------------------------------------------
let zrLoadedForChartId = null;

function renderZrPeriodCard(period, title) {
  if (!period) return `<p>${title} : ${t("zr_no_period_available")}</p>`;
  const badges = `
    ${period.is_peak_period ? `<span class="zr-badge zr-badge-peak">${t("zr_peak_period")}</span>` : ""}
    ${period.is_loosing_of_the_bond ? `<span class="zr-badge zr-badge-loosing">${t("zr_loosing_of_bond")}</span>` : ""}
  `;
  return `
    <div class="zr-phase-card">
      <h4>${title} : ${signLabel(period.sign)} ${badges}</h4>
      <p>${period.start_date} → ${period.end_date} (${period.duration_years}) —
      ${t("zr_master")} : ${planetLabel(period.ruling_planet)}</p>
    </div>`;
}

const ZR_DEFAULT_SELECTED_LOTS = new Set(["Fortune", "Esprit"]);
let selectedZrAxisKey = null;
let axesThematiquesLotsConfig = null;

function renderZrLotCard(lotName, lotResult, checked) {
  const l2Rows = lotResult.current_l1_l2_periods
    .map((p) => {
      const badges = `${p.is_peak_period ? `<span class="zr-badge zr-badge-peak">${t("zr_peak")}</span>` : ""}${p.is_loosing_of_the_bond ? `<span class="zr-badge zr-badge-loosing">${t("zr_loosing")}</span>` : ""}`;
      const isCurrent = lotResult.current_l2 && p.start_date === lotResult.current_l2.start_date && p.sign === lotResult.current_l2.sign;
      return `<tr class="${isCurrent ? "zr-current-row" : ""}"><td>${signLabel(p.sign)}</td><td>${p.start_date} → ${p.end_date}</td><td>${badges || "—"}</td></tr>`;
    })
    .join("");

  return `
    <div class="zr-lot-card">
      <div class="zr-lot-header">
        <label class="zr-lot-checkbox-label">
          <input type="checkbox" class="zr-lot-checkbox" value="${lotName}" ${checked ? "checked" : ""} />
          <strong>${lotLabel(lotName)}</strong>
        </label>
        <span class="zr-lot-current-sign">${signLabel(lotResult.lot_sign)}</span>
      </div>
      <details ${checked ? "open" : ""}>
        <summary>${t("zr_view_phases")}</summary>
        ${renderZrPeriodCard(lotResult.current_l1, t("zr_l1_current"))}
        ${renderZrPeriodCard(lotResult.current_l2, t("zr_l2_current"))}
        <details>
          <summary>${t("zr_l2_detail")} (${lotResult.current_l1_l2_periods.length})</summary>
          <table>
            <thead><tr><th>${t("th_sign")}</th><th>${t("th_period")}</th><th></th></tr></thead>
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
      <label for="zr-date">${t("label_date")}</label>
      <input type="date" id="zr-date" value="${zr.as_of_date}" />
      <button type="button" id="zr-refresh-btn">${t("btn_recalculate")}</button>
    </div>
    ${zr.edge_case_same_sign_applied ? `<p class="error">${t("zr_error_same_sign")}</p>` : ""}
    <p class="reading-section-intro">${t("zr_hint_check_lots")}</p>
    ${lotCards}
  `;

  document.getElementById("zr-refresh-btn").addEventListener("click", () => {
    loadZrDataPanel(document.getElementById("zr-date").value);
  });
  container.querySelectorAll(".zr-lot-checkbox").forEach((el) => {
    el.addEventListener("change", () => {
      selectedZrAxisKey = null; // sélection manuelle : la présélection d'axe ne verrouille jamais le choix
    });
  });
}

async function loadAxesThematiquesLotsConfig() {
  if (axesThematiquesLotsConfig) return axesThematiquesLotsConfig;
  const res = await fetch("/api/reference/axes-thematiques-lots");
  axesThematiquesLotsConfig = await res.json();
  return axesThematiquesLotsConfig;
}

async function renderZrAxisPanel() {
  const container = document.getElementById("zr-axis-panel");
  if (!container || container.dataset.loaded === "true") return;
  const config = await loadAxesThematiquesLotsConfig();
  const axisButtons = config.axes_thematiques.axes
    .map((axis) => `<button type="button" class="zr-axis-btn" data-axis-code="${axis.code}">${axisLabel(axis.code, axis.nom)}</button>`)
    .join("");
  container.innerHTML = `
    <p class="reading-section-intro">${t("zr_axis_intro")}</p>
    <div class="zr-axis-buttons">${axisButtons}</div>
  `;
  container.dataset.loaded = "true";

  container.querySelectorAll(".zr-axis-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const axis = config.axes_thematiques.axes.find((a) => a.code === btn.dataset.axisCode);
      if (!axis) return;
      selectedZrAxisKey = axis.code;
      document.querySelectorAll(".zr-lot-checkbox").forEach((el) => {
        el.checked = axis.lots.includes(el.value);
      });
      // Cette fonctionnalité qualifie l'axe à partir du thème natal avant de le situer dans
      // le temps : elle ne s'applique qu'aux projections à 10 ans (voir prompts_par_axe_thematique.md).
      selectedZrMode = "predictive";
      document.querySelectorAll(".zr-mode-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.zrMode === "predictive");
      });
      container.querySelectorAll(".zr-axis-btn").forEach((b) => b.classList.toggle("active", b === btn));
    });
  });
}

async function loadZrDataPanel(date) {
  if (!currentChart) return;
  renderZrAxisPanel();
  const container = document.getElementById("zr-data-panel");
  const previouslyChecked = new Set(
    Array.from(container.querySelectorAll(".zr-lot-checkbox:checked")).map((el) => el.value)
  );
  container.innerHTML = `<p>${t("status_computing_phases")}</p>`;
  try {
    const dateParam = date ? `?date=${date}` : "";
    const res = await fetch(`/api/charts/${currentChart.id}/zodiacal-releasing${dateParam}`);
    if (!res.ok) throw new Error(`${t("error_prefix")} ${res.status}`);
    const zr = await res.json();
    renderZrDataPanel(zr, previouslyChecked);
    zrLoadedForChartId = currentChart.id;
  } catch (err) {
    container.innerHTML = `<p class="error">${t("error_loading_phases")} ${err.message}</p>`;
  }
}

// ---------------------------------------------------------------------
// Compatibilité (synastrie) — deuxième thème + inter-aspects/chevauchement/composite
// ---------------------------------------------------------------------
let selectedCompatMode = "romantic";
let compatChartBId = null;
let compatChartsLoadedForChartId = null;

// Composant d'étoiles de notation UNIQUE, partagé par TOUTES les évaluations du site
// (Compatibilité, Pronostic, calendrier ésotérique, intensité des transits, villes suggérées
// d'astrocartographie) pour une seule identité visuelle de notation sur tout le site — voir
// .star-rating dans style.css pour les paliers de brillance/halo associés.
// `score` et `max` peuvent être n'importe quelle échelle : tout est ramené en interne sur 5
// étoiles à remplissage continu (classique système "5 étoiles"), le palier de brillance
// (1 terne -> 5 doré et lumineux) étant calculé proportionnellement au score plutôt que codé
// en dur par fonctionnalité.
const STAR_RATING_GLYPHS = "★★★★★";

function starRatingHtml(score, { max = 10, compact = false, showScore = true } = {}) {
  if (score == null) return "";
  const clamped = Math.max(0, Math.min(max, score));
  const scaledToTen = (clamped / max) * 10;
  const fillPct = Math.max(0, Math.min(100, (scaledToTen / 10) * 100));
  const tier = Math.max(1, Math.min(5, Math.ceil(scaledToTen / 2) || 1));
  const scoreOutOfFive = Math.round((scaledToTen / 2) * 2) / 2; // arrondi au 0,5 le plus proche
  const scoreLabel = showScore ? `<span class="star-rating-score">${scoreOutOfFive}/5</span>` : "";
  return `<span class="star-rating star-rating--tier-${tier}${compact ? " star-rating--compact" : ""}">
    <span class="star-rating-stack">
      <span class="star-rating-bg">${STAR_RATING_GLYPHS}</span>
      <span class="star-rating-fg" style="width:${fillPct}%">${STAR_RATING_GLYPHS}</span>
    </span>${scoreLabel}
  </span>`;
}

// Notation par étoiles (1 à 10) partagée par Compatibilité et Pronostic, pour une identité
// visuelle cohérente sur tout le site plutôt qu'un système par fonctionnalité.
function renderRatingGauges(title, axes, ratings) {
  if (!ratings) return "";
  const rows = axes
    .map((axis) => {
      const entry = ratings[axis.key];
      if (!entry) return "";
      return `
        <div class="rating-gauge-row">
          <div class="rating-gauge-header">
            <span class="rating-gauge-label">${axis.label}</span>
            ${starRatingHtml(entry.score, { max: 10 })}
          </div>
          <p class="rating-gauge-justification">${entry.justification}</p>
        </div>`;
    })
    .join("");
  if (!rows) return "";
  return `<div class="rating-gauges"><h3>${title}</h3>${rows}</div>`;
}

function renderCompatibilityRatings(ratings, mode) {
  return renderRatingGauges(t("compat_ratings_title"), compatRatingAxes(mode), ratings);
}

function renderTimingRatings(ratings) {
  return renderRatingGauges(t("timing_ratings_title"), timingRatingAxes(), ratings);
}

function compatWeightSlug(label) {
  if (label.includes("très fort")) return "very-strong";
  if (label.includes("fort")) return "strong";
  if (label.includes("moyen")) return "medium";
  return "weak";
}

async function loadCompatChartOptions() {
  if (!currentChart) return;
  const select = document.getElementById("compat-chart-b-select");
  try {
    const res = await fetch("/api/charts");
    if (!res.ok) throw new Error(`${t("error_prefix")} ${res.status}`);
    const charts = await res.json();
    const others = charts.filter((c) => c.id !== currentChart.id);
    const placeholder = `<option value="">${t("option_select_existing_chart")}</option>`;
    select.innerHTML =
      placeholder +
      others.map((c) => `<option value="${c.id}">${c.subject_name || "—"} (${c.birth_date})</option>`).join("");
    if (compatChartBId) select.value = compatChartBId;
    compatChartsLoadedForChartId = currentChart.id;
  } catch (err) {
    select.innerHTML = `<option value="">${t("error_charts_unavailable")}</option>`;
  }
}

async function loadCompatibilityData() {
  if (!currentChart || !compatChartBId) return;
  const panel = document.getElementById("compat-data-panel");
  panel.innerHTML = `<p>${t("status_computing_compat")}</p>`;
  try {
    const res = await fetch(
      `/api/charts/${currentChart.id}/compatibility?chart_b_id=${compatChartBId}&mode=${selectedCompatMode}`
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${t("error_prefix")} ${res.status}`);
    }
    renderCompatibilityData(await res.json());
  } catch (err) {
    panel.innerHTML = `<p class="error">${t("error_computing_compat")} ${err.message}</p>`;
  }
}

function renderCompatibilityData(data) {
  const panel = document.getElementById("compat-data-panel");

  const missingTimeFor = [];
  if (!data.charts_time_known.chart_a) missingTimeFor.push(t("compat_time_unknown_first"));
  if (!data.charts_time_known.chart_b) missingTimeFor.push(t("compat_time_unknown_second"));
  const timeWarning = missingTimeFor.length
    ? `<p class="error">${tf("compat_time_warning", { names: missingTimeFor.join(` ${t("compat_time_unknown_and")} `) })}</p>`
    : "";

  const aspectRows = data.inter_aspects
    .map((a) => {
      const bestMatch = a.significator_matches[0];
      const weightBadge = bestMatch
        ? `<span class="compat-weight-badge compat-weight-${compatWeightSlug(bestMatch.weight)}">${significatorWeightLabel(bestMatch.weight)}</span>`
        : "—";
      const meaningRow = bestMatch
        ? `<tr class="compat-meaning-row"><td colspan="5">${bestMatch.meaning}</td></tr>`
        : "";
      return `
      <tr>
        <td>${planetLabel(a.planet_a)}</td>
        <td>${aspectTypeLabel(a.type)}</td>
        <td>${planetLabel(a.planet_b)}</td>
        <td>${t("orb_prefix")} ${a.orb}°</td>
        <td>${weightBadge}</td>
      </tr>
      ${meaningRow}`;
    })
    .join("");

  const overlayRows = (entries) =>
    entries
      .map(
        (e) =>
          `<tr><td>${planetLabel(e.planet)}</td><td>${t("house_prefix")} ${e.house}</td><td>${e.key_meaning || "—"}</td></tr>`
      )
      .join("");

  const compositeRows = Object.entries(data.composite_chart.points)
    .map(([name, p]) => `<tr><td>${planetLabel(name)}</td><td>${signLabel(p.sign)} ${p.degree}°</td></tr>`)
    .join("");

  panel.innerHTML = `
    ${timeWarning}
    <h3>${t("compat_cross_aspects_title")} (${data.inter_aspects.length})</h3>
    <p class="reading-section-intro">${tf("compat_sorted_by_importance", { mode: pick(COMPAT_MODE_LABELS[data.relationship_mode]) || data.relationship_mode })}</p>
    <table>
      <thead><tr><th>${t("th_planet_you")}</th><th>${t("th_aspect")}</th><th>${t("th_planet_other")}</th><th>${t("th_orb")}</th><th>${t("th_weight")}</th></tr></thead>
      <tbody>${aspectRows}</tbody>
    </table>

    <h3>${t("compat_house_overlay_title")}</h3>
    <div class="compat-overlay-columns">
      <div>
        <h4>${t("compat_your_planets_in_their_houses")}</h4>
        <table>
          <thead><tr><th>${t("th_planet_generic")}</th><th>${t("th_house")}</th><th>${t("th_meaning")}</th></tr></thead>
          <tbody>${overlayRows(data.house_overlay.a_planets_in_b_houses)}</tbody>
        </table>
      </div>
      <div>
        <h4>${t("compat_their_planets_in_your_houses")}</h4>
        <table>
          <thead><tr><th>${t("th_planet_generic")}</th><th>${t("th_house")}</th><th>${t("th_meaning")}</th></tr></thead>
          <tbody>${overlayRows(data.house_overlay.b_planets_in_a_houses)}</tbody>
        </table>
      </div>
    </div>

    <h3>${t("compat_composite_title")}</h3>
    <table>
      <thead><tr><th>${t("th_point")}</th><th>${t("th_position")}</th></tr></thead>
      <tbody>
        <tr><td>${t("composite_ascendant")}</td><td>${signLabel(data.composite_chart.ascendant.sign)} ${data.composite_chart.ascendant.degree}°</td></tr>
        ${compositeRows}
      </tbody>
    </table>
  `;
}

document.querySelectorAll(".compat-mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".compat-mode-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    selectedCompatMode = btn.dataset.compatMode;
    if (compatChartBId) loadCompatibilityData();
  });
});

document.getElementById("compat-chart-b-select").addEventListener("change", (e) => {
  compatChartBId = e.target.value || null;
  document.getElementById("compat-chart-b-form").classList.add("hidden");
  if (compatChartBId) {
    loadCompatibilityData();
  } else {
    document.getElementById("compat-data-panel").innerHTML = "";
  }
});

document.getElementById("compat-new-chart-b-btn").addEventListener("click", () => {
  document.getElementById("compat-chart-b-form").classList.toggle("hidden");
  document.getElementById("compat-chart-b-select").value = "";
  compatChartBId = null;
});

loadTimezonesInto("b_timezone");

document.getElementById("b-search-city-btn").addEventListener("click", async () => {
  const query = document.getElementById("b_city_search").value.trim();
  const resultsDiv = document.getElementById("b-city-results");
  resultsDiv.innerHTML = "";
  if (query.length < 2) return;

  try {
    const res = await fetch(`/api/geocode?query=${encodeURIComponent(query)}`);
    if (!res.ok) {
      resultsDiv.innerHTML = `<p class="error">${t("search_unavailable")}</p>`;
      return;
    }
    const locations = await res.json();
    if (locations.length === 0) {
      resultsDiv.innerHTML = `<p>${t("no_results")}</p>`;
      return;
    }
    locations.forEach((loc) => {
      const item = el(`<div class="city-result-item">${loc.display_name}</div>`);
      item.addEventListener("click", () => {
        document.getElementById("b_latitude").value = loc.latitude.toFixed(4);
        document.getElementById("b_longitude").value = loc.longitude.toFixed(4);
        if (loc.timezone) document.getElementById("b_timezone").value = loc.timezone;
        resultsDiv.innerHTML = "";
        document.getElementById("b_city_search").value = loc.display_name;
      });
      resultsDiv.appendChild(item);
    });
  } catch (err) {
    resultsDiv.innerHTML = `<p class="error">${t("search_unavailable")}</p>`;
  }
});

document.getElementById("b_time_unknown").addEventListener("change", (e) => {
  document.getElementById("b_birth_time").disabled = e.target.checked;
});

document.getElementById("compat-create-chart-b-btn").addEventListener("click", async () => {
  const errorEl = document.getElementById("compat-chart-b-error");
  const btn = document.getElementById("compat-create-chart-b-btn");
  errorEl.textContent = "";

  const timeUnknown = document.getElementById("b_time_unknown").checked;
  const latitude = parseFloat(document.getElementById("b_latitude").value);
  const longitude = parseFloat(document.getElementById("b_longitude").value);
  const birthDate = document.getElementById("b_birth_date").value;

  if (!birthDate || Number.isNaN(latitude) || Number.isNaN(longitude)) {
    errorEl.textContent = t("error_fill_birth_date_coords");
    return;
  }

  const payload = {
    birth_data: {
      date: birthDate,
      time: timeUnknown ? null : document.getElementById("b_birth_time").value,
      time_known: !timeUnknown,
      timezone: document.getElementById("b_timezone").value,
      location: {
        city: document.getElementById("b_city_search").value || null,
        country: null,
        latitude,
        longitude,
      },
    },
    subject_name: document.getElementById("b_subject_name").value || null,
  };

  btn.disabled = true;
  btn.textContent = t("status_calculating");
  try {
    const res = await fetch("/api/charts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${t("error_prefix")} ${res.status}`);
    }
    const newChart = await res.json();
    compatChartBId = newChart.id;
    await loadCompatChartOptions();
    document.getElementById("compat-chart-b-select").value = compatChartBId;
    document.getElementById("compat-chart-b-form").classList.add("hidden");
    loadCompatibilityData();
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = t("btn_calculate_this_chart");
  }
});

document.getElementById("generate-compat-reading-btn").addEventListener("click", async () => {
  const errorEl = document.getElementById("compat-reading-error");
  const outputEl = document.getElementById("compat-reading-output");
  const btn = document.getElementById("generate-compat-reading-btn");
  const defaultLabel = t("btn_generate_compat_reading");
  errorEl.textContent = "";
  outputEl.innerHTML = "";

  if (!currentChart) {
    errorEl.textContent = t("error_calculate_chart_first");
    return;
  }
  if (!compatChartBId) {
    errorEl.textContent = t("error_select_second_chart");
    return;
  }

  btn.disabled = true;
  btn.textContent = t("status_generating");
  try {
    const res = await fetch(`/api/charts/${currentChart.id}/readings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reading_type: "compatibility",
        chart_b_id: compatChartBId,
        relationship_mode: selectedCompatMode,
        language: getLanguage(),
      }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${t("error_prefix")} ${res.status}`);
    }
    const reading = await res.json();
    outputEl.innerHTML =
      renderCompatibilityRatings(reading.compatibility_ratings, selectedCompatMode) +
      tinyMarkdownToHtml(reading.reading_text);
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = defaultLabel;
  }
});

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
    if (btn.dataset.readingTab === "compatibility" && currentChart && compatChartsLoadedForChartId !== currentChart.id) {
      loadCompatChartOptions();
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
    errorEl.textContent = t("error_calculate_chart_first");
    return;
  }

  const focusAreas = Array.from(document.querySelectorAll('input[name="focus"]:checked')).map((c) => c.value);
  if (focusAreas.length === 0) {
    errorEl.textContent = t("error_select_focus_area");
    return;
  }

  btn.disabled = true;
  btn.textContent = t("status_generating");
  try {
    const res = await fetch(`/api/charts/${currentChart.id}/readings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reading_type: "global", focus_areas: focusAreas, language: getLanguage() }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${t("error_prefix")} ${res.status}`);
    }
    const reading = await res.json();
    outputEl.innerHTML = tinyMarkdownToHtml(reading.reading_text);
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = t("btn_generate_reading");
  }
});

// ---------------------------------------------------------------------
// Lectures spécialisées (Lots / Maisons dérivées / Timing)
// ---------------------------------------------------------------------
async function generateSpecializedReading({ btnId, errorId, outputId, defaultLabel, requestBody, renderExtra }) {
  const errorEl = document.getElementById(errorId);
  const outputEl = document.getElementById(outputId);
  const btn = document.getElementById(btnId);
  errorEl.textContent = "";
  outputEl.innerHTML = "";

  if (!currentChart) {
    errorEl.textContent = t("error_calculate_chart_first");
    return;
  }

  btn.disabled = true;
  btn.textContent = t("status_generating");
  try {
    const res = await fetch(`/api/charts/${currentChart.id}/readings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...requestBody, language: getLanguage() }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${t("error_prefix")} ${res.status}`);
    }
    const reading = await res.json();
    const extraHtml = renderExtra ? renderExtra(reading) : "";
    outputEl.innerHTML = extraHtml + tinyMarkdownToHtml(reading.reading_text);
  } catch (err) {
    errorEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.innerHTML = defaultLabel;
  }
}

document.getElementById("generate-lots-reading-btn").addEventListener("click", () => {
  generateSpecializedReading({
    btnId: "generate-lots-reading-btn",
    errorId: "lots-reading-error",
    outputId: "lots-reading-output",
    defaultLabel: t("btn_generate_lots_reading"),
    requestBody: { reading_type: "lots" },
  });
});

let selectedZrMode = "current";
document.querySelectorAll(".zr-mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".zr-mode-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    selectedZrMode = btn.dataset.zrMode;
    if (selectedZrMode !== "predictive") {
      selectedZrAxisKey = null;
      document.querySelectorAll(".zr-axis-btn").forEach((b) => b.classList.remove("active"));
    }
  });
});

document.getElementById("generate-zr-reading-btn").addEventListener("click", () => {
  const errorEl = document.getElementById("zr-reading-error");
  const selectedLots = Array.from(document.querySelectorAll(".zr-lot-checkbox:checked")).map((el) => el.value);
  if (selectedLots.length === 0) {
    errorEl.textContent = t("zr_error_no_lot_selected");
    return;
  }
  errorEl.textContent = "";
  const dateInput = document.getElementById("zr-date");
  generateSpecializedReading({
    btnId: "generate-zr-reading-btn",
    errorId: "zr-reading-error",
    outputId: "zr-reading-output",
    defaultLabel: t("btn_generate_zr_reading"),
    requestBody: {
      reading_type: "zodiacal_releasing",
      as_of_date: dateInput ? dateInput.value : undefined,
      zr_selected_lots: selectedLots,
      zr_mode: selectedZrMode,
      zr_axis_key: selectedZrMode === "predictive" ? selectedZrAxisKey : null,
    },
  });
});

document.getElementById("generate-derived-reading-btn").addEventListener("click", () => {
  generateSpecializedReading({
    btnId: "generate-derived-reading-btn",
    errorId: "derived-reading-error",
    outputId: "derived-reading-output",
    defaultLabel: t("btn_generate_derived_reading"),
    requestBody: { reading_type: "derived_houses", relation_key: selectedDerivedRelationKey },
  });
});

document.querySelectorAll(".timing-horizon-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const horizon = btn.dataset.horizon;
    const dateInput = document.getElementById("timing-date");
    generateSpecializedReading({
      btnId: btn.id,
      errorId: "timing-reading-error",
      outputId: "timing-reading-output",
      defaultLabel: btn.innerHTML,
      requestBody: {
        reading_type: "timing",
        timing_horizon: horizon,
        as_of_date: dateInput ? dateInput.value : undefined,
      },
      renderExtra: (reading) => renderTimingRatings(reading.timing_ratings),
    });
  });
});

// ---------------------------------------------------------------------
// Astrocartographie / Cyclocartographie — partie séparée du thème natal et
// de la lecture interprétée : projette sur une carte du monde les lieux où
// chaque planète est angulaire (ASC/DC/MC/IC).
// ---------------------------------------------------------------------
const ASTROCARTOGRAPHY_PLANETS = [
  "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
];
const ASTRO_LINE_TYPES = ["ASC", "DC", "MC", "IC"];
const ASTRO_LINE_COLORS = {
  Sun: "#e0b34d", Moon: "#c9c9e8", Mercury: "#5fd4c0", Venus: "#ff8fc9", Mars: "#ff5d5d",
  Jupiter: "#4da3ff", Saturn: "#a875c9", Uranus: "#5fe0c0", Neptune: "#6c8cff", Pluto: "#c98fff",
};

let selectedAstroMode = "natal";
let astroLinesCache = { natal: null, transit: null };
let astroSelectedPlanets = new Set(ASTROCARTOGRAPHY_PLANETS);
let astroSelectedLineTypes = new Set(["MC", "IC"]);
let astroSavedLocations = [];
let astroFocusLocation = null; // {label, latitude, longitude} — null = lieu de naissance (défaut serveur)
let astroInterestingCities = []; // villes suggérées automatiquement (proches de lignes fortes/croisements), mode natal uniquement

function resetAstrocartographyStateForNewChart() {
  astroLinesCache = { natal: null, transit: null };
  astroSavedLocations = [];
  astroFocusLocation = null;
  astroInterestingCities = [];
  astroTransitDate = null;
  const dateInput = document.getElementById("astro-transit-date");
  if (dateInput) dateInput.value = "";
  const forecastResults = document.getElementById("astro-forecast-results");
  if (forecastResults) forecastResults.innerHTML = "";
  const forecastError = document.getElementById("astro-forecast-error");
  if (forecastError) forecastError.textContent = "";
  const forecastAiBtn = document.getElementById("astro-forecast-ai-btn");
  if (forecastAiBtn) forecastAiBtn.classList.add("hidden");
  const forecastAiError = document.getElementById("astro-forecast-ai-error");
  if (forecastAiError) forecastAiError.textContent = "";
  const forecastAiOutput = document.getElementById("astro-forecast-ai-output");
  if (forecastAiOutput) forecastAiOutput.innerHTML = "";
  const citiesList = document.getElementById("astro-interesting-cities-list");
  if (citiesList) citiesList.innerHTML = "";
  const citiesError = document.getElementById("astro-interesting-cities-error");
  if (citiesError) citiesError.textContent = "";
  loadAstroLines(selectedAstroMode);
  loadAstroSavedLocations();
  loadAstroInterestingCities();
}

function astroLonToX(lon, width) {
  return ((lon + 180) / 360) * width;
}

function astroLatToY(lat, height) {
  return ((90 - lat) / 180) * height;
}

// Contours des terres émergées (Natural Earth 110m, domaine public), pour que les lignes
// d'astrocartographie s'affichent sur une vraie carte du monde plutôt que sur une simple
// grille. Chargé une seule fois puis mis en cache — fichier statique auto-hébergé, aucune
// dépendance externe au moment de l'affichage.
let worldLandRings = [];
let worldLandLoaded = false;

async function loadWorldLandData() {
  if (worldLandLoaded) return worldLandRings;
  try {
    const res = await fetch("/static/world_land.json");
    worldLandRings = await res.json();
  } catch (err) {
    worldLandRings = [];
  }
  worldLandLoaded = true;
  return worldLandRings;
}

function buildWorldLandPathData(width, height) {
  // Chaque anneau (contour d'une masse continentale ou d'une île) est projeté et fermé
  // directement, sans découpage à l'antiméridien : aucun contour de ce jeu de données ne le
  // traverse (l'Antarctique, seul cas concerné, est déjà remplacé par une bande polaire dont
  // les bords -180/180 sont volontaires, voir le script de génération de world_land.json).
  return worldLandRings
    .map(
      (ring) =>
        ring
          .map((p, i) => `${i === 0 ? "M" : "L"} ${astroLonToX(p[0], width).toFixed(1)} ${astroLatToY(p[1], height).toFixed(1)}`)
          .join(" ") + " Z"
    )
    .join(" ");
}

// Une ligne ASC/DC peut franchir la ligne de changement de date (±180°) : sans ce découpage,
// le tracé traverserait la carte à l'horizontale au lieu de "sortir" d'un bord et "rentrer"
// de l'autre.
function splitAstroLineAtDateLine(points) {
  const segments = [];
  let current = [];
  for (const point of points) {
    if (current.length > 0 && Math.abs(point.lon - current[current.length - 1].lon) > 180) {
      segments.push(current);
      current = [];
    }
    current.push(point);
  }
  if (current.length) segments.push(current);
  return segments;
}

function diamondPoints(cx, cy, r) {
  return `${cx},${(cy - r).toFixed(1)} ${(cx + r).toFixed(1)},${cy} ${cx},${(cy + r).toFixed(1)} ${(cx - r).toFixed(1)},${cy}`;
}

function buildAstroMapSVG(lines, savedLocations, interestingCities) {
  const width = 720;
  const height = 360;
  const landPath = buildWorldLandPathData(width, height);
  let grid = "";
  for (let lon = -180; lon <= 180; lon += 30) {
    const x = astroLonToX(lon, width);
    grid += `<line x1="${x.toFixed(1)}" y1="0" x2="${x.toFixed(1)}" y2="${height}" stroke="#3a3f66" stroke-width="${lon === 0 ? 1 : 0.5}" stroke-opacity="0.5" />`;
  }
  for (let lat = -90; lat <= 90; lat += 30) {
    const y = astroLatToY(lat, height);
    grid += `<line x1="0" y1="${y.toFixed(1)}" x2="${width}" y2="${y.toFixed(1)}" stroke="#3a3f66" stroke-width="${lat === 0 ? 1 : 0.5}" stroke-opacity="0.5" />`;
  }

  let linesSvg = "";
  lines
    .filter((line) => astroSelectedPlanets.has(line.planet) && astroSelectedLineTypes.has(line.line_type))
    .forEach((line) => {
      const color = ASTRO_LINE_COLORS[line.planet] || "#888";
      const tooltip = escapeHtml(`${planetLabel(line.planet)} — ${astroLineTypeLabel(line.line_type)}`);
      splitAstroLineAtDateLine(line.line_points).forEach((segment) => {
        if (segment.length < 2) return;
        const path = segment
          .map((p, i) => `${i === 0 ? "M" : "L"} ${astroLonToX(p.lon, width).toFixed(1)} ${astroLatToY(p.lat, height).toFixed(1)}`)
          .join(" ");
        linesSvg += `<g class="wheel-hoverable" data-tooltip="${tooltip}">`;
        linesSvg += `<path d="${path}" fill="none" stroke="transparent" stroke-width="10" pointer-events="stroke" />`;
        linesSvg += `<path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-opacity="0.85" pointer-events="none" />`;
        linesSvg += `</g>`;
      });
    });

  let markersSvg = "";
  const citiesMaxScore = Math.max(...(interestingCities || []).map((c) => c.score), 0.0001);
  (interestingCities || []).forEach((c) => {
    const x = astroLonToX(c.longitude, width);
    const y = astroLatToY(c.latitude, height);
    const normalizedScore = Math.round((c.score / citiesMaxScore) * 10 * 10) / 10;
    const tooltip = escapeHtml(`${c.name}, ${c.country} — ${t("astro_score_label")} ${normalizedScore}/10`);
    markersSvg += `<g class="wheel-hoverable" data-tooltip="${tooltip}"><polygon points="${diamondPoints(x, y, 5)}" fill="#ffd24d" stroke="#12152a" stroke-width="1.2" /></g>`;
  });
  (savedLocations || []).forEach((loc) => {
    const x = astroLonToX(loc.longitude, width);
    const y = astroLatToY(loc.latitude, height);
    const tooltip = escapeHtml(loc.city || loc.label || `${loc.latitude.toFixed(1)}, ${loc.longitude.toFixed(1)}`);
    markersSvg += `<g class="wheel-hoverable" data-tooltip="${tooltip}"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5" fill="#ff5d9e" stroke="#12152a" stroke-width="1.5" /></g>`;
  });

  return `
    <svg viewBox="0 0 ${width} ${height}" class="astro-map-svg" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="${width}" height="${height}" fill="#10142a" />
      <path d="${landPath}" fill="#2a3160" stroke="#454d8a" stroke-width="0.6" fill-rule="evenodd" />
      ${grid}
      ${linesSvg}
      ${markersSvg}
    </svg>`;
}

function renderAstroMapPanel(lines) {
  const panel = document.getElementById("astro-map-panel");
  if (!panel) return;

  const planetCheckboxes = ASTROCARTOGRAPHY_PLANETS.map(
    (p) => `
    <label class="checkbox-label astro-filter-planet">
      <input type="checkbox" class="astro-planet-checkbox" value="${p}" ${astroSelectedPlanets.has(p) ? "checked" : ""} />
      <span style="color:${ASTRO_LINE_COLORS[p]}">●</span> ${planetLabel(p)}
    </label>`
  ).join("");
  const lineTypeCheckboxes = ASTRO_LINE_TYPES.map(
    (lt) => `
    <label class="checkbox-label">
      <input type="checkbox" class="astro-linetype-checkbox" value="${lt}" ${astroSelectedLineTypes.has(lt) ? "checked" : ""} />
      ${astroLineTypeLabel(lt)}
    </label>`
  ).join("");

  panel.innerHTML = `
    <div class="astro-map-controls">
      <div class="astro-map-filter-group">
        <span class="astro-filter-title">${t("astro_planets_filter_title")}</span>
        ${planetCheckboxes}
      </div>
      <div class="astro-map-filter-group">
        <span class="astro-filter-title">${t("astro_line_types_filter_title")}</span>
        ${lineTypeCheckboxes}
      </div>
    </div>
    <div class="astro-map-wrapper">${buildAstroMapSVG(lines, astroSavedLocations, astroInterestingCities)}</div>
  `;
  attachWheelTooltip(panel.querySelector(".astro-map-wrapper"));

  const redraw = () => {
    panel.querySelector(".astro-map-wrapper").innerHTML = buildAstroMapSVG(lines, astroSavedLocations, astroInterestingCities);
  };
  panel.querySelectorAll(".astro-planet-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) astroSelectedPlanets.add(cb.value);
      else astroSelectedPlanets.delete(cb.value);
      redraw();
    });
  });
  panel.querySelectorAll(".astro-linetype-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) astroSelectedLineTypes.add(cb.value);
      else astroSelectedLineTypes.delete(cb.value);
      redraw();
    });
  });
}

let astroTransitDate = null; // null = aujourd'hui (défaut serveur)

function astroTransitUrl() {
  return astroTransitDate ? `/api/astrocartography/transit?date=${astroTransitDate}` : "/api/astrocartography/transit";
}

async function loadAstroLines(mode) {
  if (!currentChart) return;
  const panel = document.getElementById("astro-map-panel");
  panel.innerHTML = `<p>${t("status_computing_astro")}</p>`;
  try {
    const [_land, res] = await Promise.all([
      loadWorldLandData(),
      fetch(mode === "transit" ? astroTransitUrl() : `/api/charts/${currentChart.id}/astrocartography`),
    ]);
    if (!res.ok) throw new Error(`${t("error_prefix")} ${res.status}`);
    const data = await res.json();
    astroLinesCache[mode] = data.lines;
    renderAstroMapPanel(data.lines);
  } catch (err) {
    panel.innerHTML = `<p class="error">${t("error_loading_astro")} ${err.message}</p>`;
  }
}

document.querySelectorAll(".astro-mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".astro-mode-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    selectedAstroMode = btn.dataset.astroMode;
    document.getElementById("astro-transit-date-row").classList.toggle("hidden", selectedAstroMode !== "transit");
    if (astroLinesCache[selectedAstroMode]) {
      renderAstroMapPanel(astroLinesCache[selectedAstroMode]);
    } else {
      loadAstroLines(selectedAstroMode);
    }
    loadAstroInterestingCities();
  });
});

document.getElementById("astro-transit-date").addEventListener("change", (e) => {
  astroTransitDate = e.target.value || null;
  astroLinesCache.transit = null; // la date a changé : le cache précédent ne vaut plus rien
  if (selectedAstroMode === "transit") {
    loadAstroLines("transit");
    loadAstroInterestingCities();
  }
});

document.getElementById("astro-transit-date-today-btn").addEventListener("click", () => {
  astroTransitDate = null;
  document.getElementById("astro-transit-date").value = "";
  astroLinesCache.transit = null;
  if (selectedAstroMode === "transit") {
    loadAstroLines("transit");
    loadAstroInterestingCities();
  }
});

// Point d'entrée unique pour changer le lieu de focus de la lecture d'astrocartographie,
// depuis les lieux sauvegardés OU les villes suggérées : garde les deux listes synchronisées
// (surbrillance + pastille "utilisé pour la lecture" sur la bonne carte, dans les deux).
function setAstroFocusLocation(location) {
  astroFocusLocation = location;
  renderAstroSavedLocationsList();
  renderAstroInterestingCitiesList();
}

function isAstroFocusedLocation(latitude, longitude) {
  return !!astroFocusLocation && astroFocusLocation.latitude === latitude && astroFocusLocation.longitude === longitude;
}

function astroFocusBadgeHtml() {
  return `<span class="astro-focus-badge">${t("astro_focus_badge_label")}</span>`;
}

function renderAstroSavedLocationsList() {
  const container = document.getElementById("astro-saved-locations-list");
  if (!container) return;
  if (astroSavedLocations.length === 0) {
    container.innerHTML = `<p>${t("astro_no_saved_locations")}</p>`;
    return;
  }
  container.innerHTML =
    `<p class="reading-section-intro">${t("astro_focus_default_note")}</p>` +
    astroSavedLocations
      .map((loc) => {
        const nearby = (loc.nearby_lines_analysis || [])
          .map((n) => `${planetLabel(n.planet)} ${astroLineTypeLabel(n.line_type)} (${n.distance_km} km)`)
          .join(", ") || t("astro_no_nearby_lines");
        const isFocused = isAstroFocusedLocation(loc.latitude, loc.longitude);
        return `
        <div class="astro-location-card${isFocused ? " astro-location-focused" : ""}" data-location-id="${loc.id}">
          <div class="astro-location-header">
            <strong>${loc.city || loc.label || `${loc.latitude.toFixed(2)}, ${loc.longitude.toFixed(2)}`}</strong>
            ${isFocused ? astroFocusBadgeHtml() : `<button type="button" class="astro-location-focus-btn" data-location-id="${loc.id}">${t("astro_use_for_reading")}</button>`}
            <button type="button" class="astro-location-delete-btn" data-location-id="${loc.id}">${t("btn_delete")}</button>
          </div>
          <p class="reading-section-intro">${nearby}</p>
        </div>`;
      })
      .join("");

  container.querySelectorAll(".astro-location-delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/saved-locations/${btn.dataset.locationId}`, { method: "DELETE" });
      if (astroFocusLocation) {
        const stillExists = astroSavedLocations.find((l) => l.id === btn.dataset.locationId);
        if (stillExists) astroFocusLocation = null;
      }
      loadAstroSavedLocations();
    });
  });
  container.querySelectorAll(".astro-location-focus-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const loc = astroSavedLocations.find((l) => l.id === btn.dataset.locationId);
      setAstroFocusLocation(loc ? { label: loc.city || loc.label, latitude: loc.latitude, longitude: loc.longitude } : null);
    });
  });
}

function renderAstroInterestingCitiesList() {
  const container = document.getElementById("astro-interesting-cities-list");
  if (!container) return;
  if (astroInterestingCities.length === 0) {
    container.innerHTML = `<p>${t("astro_no_interesting_cities")}</p>`;
    return;
  }
  // c.score est un score déterministe RELATIF (sert au tri, pas de plafond fixe) : on le
  // normalise sur 10 par rapport au maximum de la liste affichée (top 5) pour l'exprimer dans
  // le même langage visuel d'étoiles que le reste du site.
  const maxScore = Math.max(...astroInterestingCities.map((c) => c.score), 0.0001);
  container.innerHTML = astroInterestingCities
    .map((c, index) => {
      const linesText = c.nearby_lines
        .map((n) => `${planetLabel(n.planet)} ${astroLineTypeLabel(n.line_type)} (${n.distance_km} km)`)
        .join(", ");
      const crossingsText = c.nearby_crossings
        .map((cr) => `${planetLabel(cr.planet_a)} × ${planetLabel(cr.planet_b)} (${cr.distance_km} km)`)
        .join(", ");
      const isFocused = isAstroFocusedLocation(c.latitude, c.longitude);
      return `
      <div class="astro-location-card${isFocused ? " astro-location-focused" : ""}" data-city-index="${index}">
        <div class="astro-location-header">
          <strong>${escapeHtml(c.name)}, ${escapeHtml(c.country)}</strong>
          ${starRatingHtml(c.score, { max: maxScore })}
          ${isFocused ? astroFocusBadgeHtml() : `<button type="button" class="astro-location-focus-btn" data-city-index="${index}">${t("astro_use_for_reading")}</button>`}
        </div>
        ${linesText ? `<p class="astro-city-detail">${escapeHtml(linesText)}</p>` : ""}
        ${crossingsText ? `<p class="astro-city-detail astro-city-crossings">${t("astro_crossings_label")} ${escapeHtml(crossingsText)}</p>` : ""}
      </div>`;
    })
    .join("");

  container.querySelectorAll(".astro-location-focus-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const city = astroInterestingCities[Number(btn.dataset.cityIndex)];
      if (!city) return;
      setAstroFocusLocation({ label: `${city.name}, ${city.country}`, latitude: city.latitude, longitude: city.longitude });
    });
  });
}

function updateInterestingCitiesPanelLabels() {
  const titleEl = document.getElementById("astro-interesting-cities-title");
  const introEl = document.getElementById("astro-interesting-cities-intro");
  if (!titleEl || !introEl) return;
  if (selectedAstroMode === "transit") {
    titleEl.textContent = t("astro_transit_cities_title");
    introEl.textContent = t("astro_transit_cities_intro");
  } else {
    titleEl.textContent = t("astro_interesting_cities_title");
    introEl.textContent = t("astro_interesting_cities_intro");
  }
}

async function loadAstroInterestingCities() {
  if (!currentChart) return;
  updateInterestingCitiesPanelLabels();
  const requestedMode = selectedAstroMode;
  try {
    const url =
      requestedMode === "transit"
        ? `/api/astrocartography/transit/interesting-cities?top_n=5${astroTransitDate ? `&date=${astroTransitDate}` : ""}`
        : `/api/charts/${currentChart.id}/astrocartography/interesting-cities`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${t("error_prefix")} ${res.status}`);
    const cities = await res.json();
    if (requestedMode !== selectedAstroMode) return; // le mode a changé pendant la requête : résultat obsolète
    astroInterestingCities = cities;
    renderAstroInterestingCitiesList();
    if (astroLinesCache[selectedAstroMode]) renderAstroMapPanel(astroLinesCache[selectedAstroMode]);
  } catch (err) {
    document.getElementById("astro-interesting-cities-error").textContent = err.message;
  }
}

async function loadAstroSavedLocations() {
  if (!currentChart) return;
  try {
    const res = await fetch(`/api/charts/${currentChart.id}/saved-locations`);
    if (!res.ok) throw new Error(`${t("error_prefix")} ${res.status}`);
    astroSavedLocations = await res.json();
    renderAstroSavedLocationsList();
    renderAstroInterestingCitiesList();
    if (astroLinesCache[selectedAstroMode]) renderAstroMapPanel(astroLinesCache[selectedAstroMode]);
  } catch (err) {
    document.getElementById("astro-location-error").textContent = err.message;
  }
}

document.getElementById("astro-search-city-btn").addEventListener("click", async () => {
  const query = document.getElementById("astro_city_search").value.trim();
  const resultsDiv = document.getElementById("astro-city-results");
  const errorEl = document.getElementById("astro-location-error");
  resultsDiv.innerHTML = "";
  errorEl.textContent = "";
  if (query.length < 2) return;

  try {
    const res = await fetch(`/api/geocode?query=${encodeURIComponent(query)}`);
    if (!res.ok) {
      resultsDiv.innerHTML = `<p class="error">${t("search_unavailable")}</p>`;
      return;
    }
    const locations = await res.json();
    if (locations.length === 0) {
      resultsDiv.innerHTML = `<p>${t("no_results")}</p>`;
      return;
    }
    locations.forEach((loc) => {
      const item = el(`<div class="city-result-item">${loc.display_name}</div>`);
      item.addEventListener("click", async () => {
        resultsDiv.innerHTML = "";
        if (!currentChart) return;
        const [city, ...rest] = loc.display_name.split(",");
        const country = rest.length ? rest[rest.length - 1].trim() : null;
        try {
          const res2 = await fetch(`/api/charts/${currentChart.id}/saved-locations`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ city: city.trim(), country, latitude: loc.latitude, longitude: loc.longitude }),
          });
          if (!res2.ok) {
            const detail = await res2.json().catch(() => ({}));
            throw new Error(detail.detail || `${t("error_prefix")} ${res2.status}`);
          }
          document.getElementById("astro_city_search").value = "";
          await loadAstroSavedLocations();
        } catch (err) {
          errorEl.textContent = err.message;
        }
      });
      resultsDiv.appendChild(item);
    });
  } catch (err) {
    resultsDiv.innerHTML = `<p class="error">${t("search_unavailable")}</p>`;
  }
});

function renderAstroForecastResults(data) {
  const container = document.getElementById("astro-forecast-results");
  if (!data.windows.length) {
    container.innerHTML = `<p>${t("astro_forecast_no_windows")}</p>`;
    return;
  }
  const rows = data.windows
    .map((w) => {
      const lineLabel = escapeHtml(`${planetLabel(w.planet)} — ${astroLineTypeLabel(w.line_type)}`);
      const period = w.start_date === w.end_date ? w.start_date : `${w.start_date} → ${w.end_date}`;
      return `
      <tr>
        <td>${lineLabel}</td>
        <td>${period}</td>
        <td>${w.peak_date}</td>
        <td>${w.peak_distance_km.toFixed(0)} km</td>
      </tr>`;
    })
    .join("");
  container.innerHTML = `
    <table class="astro-forecast-table">
      <thead>
        <tr>
          <th>${t("astro_forecast_col_line")}</th>
          <th>${t("astro_forecast_col_period")}</th>
          <th>${t("astro_forecast_col_peak")}</th>
          <th>${t("astro_forecast_col_distance")}</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function clampForecastYears() {
  const input = document.getElementById("astro-forecast-years");
  const clamped = Math.min(10, Math.max(1, parseInt(input.value, 10) || 10));
  input.value = clamped;
  return clamped;
}

document.getElementById("astro-forecast-btn").addEventListener("click", async () => {
  const errorEl = document.getElementById("astro-forecast-error");
  const resultsEl = document.getElementById("astro-forecast-results");
  const aiBtn = document.getElementById("astro-forecast-ai-btn");
  errorEl.textContent = "";
  aiBtn.classList.add("hidden");
  if (!currentChart) return;

  const latitude = astroFocusLocation ? astroFocusLocation.latitude : currentChart.birth_latitude;
  const longitude = astroFocusLocation ? astroFocusLocation.longitude : currentChart.birth_longitude;
  const startDate = document.getElementById("astro-forecast-start-date").value || undefined;
  const years = clampForecastYears();
  const thresholdKm = document.getElementById("astro-forecast-threshold").value || 300;

  resultsEl.innerHTML = `<p>${t("status_computing_forecast")}</p>`;
  try {
    const params = new URLSearchParams({
      latitude: String(latitude),
      longitude: String(longitude),
      years: String(years),
      threshold_km: String(thresholdKm),
    });
    if (startDate) params.set("start_date", startDate);
    const res = await fetch(`/api/astrocartography/location-forecast?${params}`);
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `${t("error_prefix")} ${res.status}`);
    }
    const data = await res.json();
    renderAstroForecastResults(data);
    aiBtn.classList.remove("hidden");
  } catch (err) {
    resultsEl.innerHTML = "";
    errorEl.textContent = `${t("error_loading_forecast")} ${err.message}`;
  }
});

document.getElementById("astro-forecast-ai-btn").addEventListener("click", () => {
  const latitude = astroFocusLocation ? astroFocusLocation.latitude : currentChart.birth_latitude;
  const longitude = astroFocusLocation ? astroFocusLocation.longitude : currentChart.birth_longitude;
  const label = astroFocusLocation ? astroFocusLocation.label : currentChart.birth_city;
  const startDate = document.getElementById("astro-forecast-start-date").value || undefined;
  const years = clampForecastYears();
  const thresholdKm = document.getElementById("astro-forecast-threshold").value || 300;

  generateSpecializedReading({
    btnId: "astro-forecast-ai-btn",
    errorId: "astro-forecast-ai-error",
    outputId: "astro-forecast-ai-output",
    defaultLabel: t("btn_forecast_ai_reading"),
    requestBody: {
      reading_type: "astrocartography_forecast",
      astro_focus_latitude: latitude,
      astro_focus_longitude: longitude,
      astro_focus_label: label,
      forecast_start_date: startDate,
      forecast_years: years,
      forecast_threshold_km: Number(thresholdKm),
    },
  });
});

document.getElementById("generate-astro-reading-btn").addEventListener("click", () => {
  generateSpecializedReading({
    btnId: "generate-astro-reading-btn",
    errorId: "astro-reading-error",
    outputId: "astro-reading-output",
    defaultLabel: t("btn_generate_astro_reading"),
    requestBody: {
      reading_type: "astrocartography",
      astro_map_mode: selectedAstroMode,
      astro_focus_latitude: astroFocusLocation ? astroFocusLocation.latitude : undefined,
      astro_focus_longitude: astroFocusLocation ? astroFocusLocation.longitude : undefined,
      astro_focus_label: astroFocusLocation ? astroFocusLocation.label : undefined,
      as_of_date: selectedAstroMode === "transit" ? astroTransitDate || undefined : undefined,
    },
  });
});

// ---------------------------------------------------------------------
// Calendrier ésotérique : calendrier annuel collectif (lunaisons, éclipses,
// stations rétrogrades, ingrès de planètes lentes), indépendant du thème natal.
// ---------------------------------------------------------------------
let witchyCalendarEvents = [];
let witchySelectedYear = new Date().getFullYear();
let selectedWitchyDayDetailDate = null;

function witchyEventLabel(event) {
  return tf(`witchy_label_${event.event_type}`, {
    sign: event.sign ? signLabel(event.sign) : "",
    planet: event.planet ? planetLabel(event.planet) : "",
    planetB: event.planet_b ? planetLabel(event.planet_b) : "",
    aspect: event.aspect_type ? aspectTypeLabel(event.aspect_type) : "",
  });
}

function resetWitchyCalendarStateForNewChart() {
  witchyCalendarEvents = [];
  witchySelectedYear = new Date().getFullYear();
  const yearInput = document.getElementById("witchy-year");
  if (yearInput) yearInput.value = witchySelectedYear;
  const list = document.getElementById("witchy-events-list");
  if (list) list.innerHTML = "";
  const errorEl = document.getElementById("witchy-error");
  if (errorEl) errorEl.textContent = "";
  const readingError = document.getElementById("witchy-reading-error");
  if (readingError) readingError.textContent = "";
  const readingOutput = document.getElementById("witchy-reading-output");
  if (readingOutput) readingOutput.innerHTML = "";
  selectedWitchyDayDetailDate = null;
  const dayDetailDateInput = document.getElementById("witchy-day-detail-date");
  if (dayDetailDateInput) dayDetailDateInput.value = "";
  const dayDetailError = document.getElementById("witchy-day-detail-error");
  if (dayDetailError) dayDetailError.textContent = "";
  const dayDetailOutput = document.getElementById("witchy-day-detail-output");
  if (dayDetailOutput) dayDetailOutput.innerHTML = "";
  loadWitchyCalendar();
}

function renderWitchyEventsList() {
  const container = document.getElementById("witchy-events-list");
  if (!container) return;
  if (witchyCalendarEvents.length === 0) {
    container.innerHTML = `<p>${t("witchy_no_events")}</p>`;
    return;
  }
  container.innerHTML = `
    <table class="astro-forecast-table">
      <tbody>
        ${witchyCalendarEvents
          .map(
            (e) => `
          <tr class="witchy-event-row" data-date="${e.event_date}" tabindex="0">
            <td>${e.event_date}</td>
            <td>${escapeHtml(witchyEventLabel(e))}${e.super_moon ? ` <span class="witchy-super-badge">${t("witchy_super_moon_badge")}</span>` : ""}</td>
            <td>${starRatingHtml(e.score, { max: 5, compact: true, showScore: false })}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
  container.querySelectorAll(".witchy-event-row").forEach((row) => {
    const activate = () => {
      const dateInput = document.getElementById("witchy-day-detail-date");
      if (dateInput) dateInput.value = row.dataset.date;
      selectedWitchyDayDetailDate = row.dataset.date;
      applyWitchySelectedDateHighlight();
      document.getElementById("generate-witchy-day-detail-btn")?.click();
    };
    row.addEventListener("click", activate);
    row.addEventListener("keydown", (evt) => {
      if (evt.key === "Enter" || evt.key === " ") {
        evt.preventDefault();
        activate();
      }
    });
  });
  applyWitchySelectedDateHighlight();
}

// Met en surbrillance, dans la liste, la ligne correspondant à la date actuellement affichée
// dans la barre "Carte du jour" — qu'elle vienne d'un clic sur une ligne ou d'une saisie
// manuelle dans le champ date, pour que les deux façons de choisir une date restent cohérentes.
function applyWitchySelectedDateHighlight() {
  const container = document.getElementById("witchy-events-list");
  if (!container) return;
  container.querySelectorAll(".witchy-event-row").forEach((row) => {
    row.classList.toggle("witchy-event-row-selected", row.dataset.date === selectedWitchyDayDetailDate);
  });
}

async function loadWitchyCalendar() {
  const errorEl = document.getElementById("witchy-error");
  const container = document.getElementById("witchy-events-list");
  errorEl.textContent = "";
  container.innerHTML = `<p>${t("status_loading_witchy_calendar")}</p>`;
  try {
    const res = await fetch(`/api/witchy-calendar?year=${witchySelectedYear}`);
    if (!res.ok) throw new Error(`${t("error_prefix")} ${res.status}`);
    const data = await res.json();
    witchyCalendarEvents = data.events;
    renderWitchyEventsList();
  } catch (err) {
    container.innerHTML = "";
    errorEl.textContent = `${t("error_loading_witchy_calendar")} ${err.message}`;
  }
}

document.getElementById("witchy-load-btn").addEventListener("click", () => {
  const yearInput = document.getElementById("witchy-year");
  witchySelectedYear = parseInt(yearInput.value, 10) || new Date().getFullYear();
  loadWitchyCalendar();
});

document.getElementById("generate-witchy-reading-btn").addEventListener("click", () => {
  generateSpecializedReading({
    btnId: "generate-witchy-reading-btn",
    errorId: "witchy-reading-error",
    outputId: "witchy-reading-output",
    defaultLabel: t("btn_generate_witchy_reading"),
    requestBody: {
      reading_type: "witchy_calendar",
      witchy_calendar_year: witchySelectedYear,
    },
  });
});

document.getElementById("generate-witchy-day-detail-btn").addEventListener("click", () => {
  const dateInput = document.getElementById("witchy-day-detail-date");
  const errorEl = document.getElementById("witchy-day-detail-error");
  if (!dateInput.value) {
    errorEl.textContent = t("error_witchy_day_detail_no_date");
    return;
  }
  errorEl.textContent = "";
  generateSpecializedReading({
    btnId: "generate-witchy-day-detail-btn",
    errorId: "witchy-day-detail-error",
    outputId: "witchy-day-detail-output",
    defaultLabel: t("btn_generate_witchy_day_detail"),
    requestBody: {
      reading_type: "witchy_day_detail",
      witchy_day_detail_date: dateInput.value,
    },
  });
});

document.getElementById("witchy-day-detail-date").addEventListener("input", (evt) => {
  selectedWitchyDayDetailDate = evt.target.value || null;
  applyWitchySelectedDateHighlight();
});

// ---------------------------------------------------------------------
// Météo de la semaine : couche collective (Lune/Mercure/Vénus/Mars, indépendante du thème
// natal) + impact personnel (réutilise le Pronostic) + météo par signe (12 signes, technique
// générique — voir app/core/weekly_weather.py).
// ---------------------------------------------------------------------
let weeklyWeatherData = null;
let weeklyWeatherStartDate = null;

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

let weeklyWeatherBySignData = null;

function resetWeeklyWeatherStateForNewChart() {
  weeklyWeatherData = null;
  weeklyWeatherBySignData = null;
  weeklyWeatherStartDate = null;
  const dateInput = document.getElementById("weekly-weather-start-date");
  if (dateInput) dateInput.value = "";
  [
    "weekly-weather-highlights",
    "weekly-weather-planets",
    "weekly-weather-aspects",
    "weekly-weather-reading-output",
    "weekly-weather-by-sign-scores",
    "weekly-weather-by-sign-output",
  ].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = "";
  });
  ["weekly-weather-error", "weekly-weather-reading-error", "weekly-weather-by-sign-error"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = "";
  });
}

function weeklyWeatherHighlightLabel(h) {
  if (h.kind === "aspect_exact") {
    return tf("weekly_weather_highlight_aspect", {
      planetA: planetLabel(h.planet),
      planetB: planetLabel(h.planet_b),
      aspect: aspectTypeLabel(h.aspect_type),
    });
  }
  if (h.kind === "ingres_lune" || h.kind === "ingres_rapide") {
    return tf("weekly_weather_highlight_ingress", { planet: planetLabel(h.planet), sign: signLabel(h.sign) });
  }
  if (h.kind === "station") {
    const eventType = h.direction === "retrograde" ? "station_retrograde" : "station_directe";
    return witchyEventLabel({ event_type: eventType, planet: h.planet, sign: h.sign });
  }
  // Événements du calendrier ésotérique (lunaisons, éclipses, ingrès de planètes lentes,
  // grandes conjonctions) : `kind` porte alors directement l'`event_type` du calendrier witchy
  // (voir app/core/weekly_weather.py) — mêmes libellés déjà définis, réutilisés tels quels.
  return witchyEventLabel({ event_type: h.kind, planet: h.planet, sign: h.sign, planet_b: h.planet_b, aspect_type: h.aspect_type });
}

function renderWeeklyWeatherHighlights() {
  const container = document.getElementById("weekly-weather-highlights");
  if (!container || !weeklyWeatherData) return;
  const highlights = weeklyWeatherData.highlights;
  if (highlights.length === 0) {
    container.innerHTML = `<h3>${t("weekly_weather_highlights_title")}</h3><p>${t("weekly_weather_no_highlights")}</p>`;
    return;
  }
  container.innerHTML = `
    <h3>${t("weekly_weather_highlights_title")}</h3>
    <table class="astro-forecast-table">
      <tbody>
        ${highlights
          .map(
            (h) => `
          <tr>
            <td>${h.date}</td>
            <td>${escapeHtml(weeklyWeatherHighlightLabel(h))}</td>
            <td>${starRatingHtml(h.score, { max: 5, compact: true, showScore: false })}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

function renderWeeklyWeatherPlanets() {
  const container = document.getElementById("weekly-weather-planets");
  if (!container || !weeklyWeatherData) return;
  const moon = weeklyWeatherData.moon_path;
  const moonStart = moon[0];
  const moonEnd = moon[moon.length - 1];
  const moonMovement =
    weeklyWeatherData.moon_ingresses.map((i) => tf("weekly_weather_ingress_note", { date: i.date, sign: signLabel(i.to_sign) })).join(" · ") || "—";
  const fastRows = weeklyWeatherData.fast_planets
    .map((p) => {
      const retro = p.retrograde_start || p.retrograde_end ? ` <span class="retro">${t("retrograde")}</span>` : "";
      const movement = p.ingress ? tf("weekly_weather_ingress_note", { date: p.ingress.date, sign: signLabel(p.ingress.to_sign) }) : "—";
      return `
        <tr>
          <td>${planetLabel(p.name)}${retro}</td>
          <td>${signLabel(p.sign_start)} ${p.degree_start}°</td>
          <td>${signLabel(p.sign_end)} ${p.degree_end}°</td>
          <td>${movement}</td>
        </tr>`;
    })
    .join("");
  container.innerHTML = `
    <h3>${t("weekly_weather_planets_title")}</h3>
    <table class="astro-forecast-table">
      <thead>
        <tr>
          <th>${t("th_transit")}</th>
          <th>${t("weekly_weather_th_start")}</th>
          <th>${t("weekly_weather_th_end")}</th>
          <th>${t("weekly_weather_th_movement")}</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>${planetLabel("Moon")}</td>
          <td>${signLabel(moonStart.sign)} ${moonStart.degree}°</td>
          <td>${signLabel(moonEnd.sign)} ${moonEnd.degree}°</td>
          <td>${moonMovement}</td>
        </tr>
        ${fastRows}
      </tbody>
    </table>`;
}

function renderWeeklyWeatherAspects() {
  const container = document.getElementById("weekly-weather-aspects");
  if (!container || !weeklyWeatherData) return;
  const aspects = weeklyWeatherData.transit_transit_aspects;
  if (aspects.length === 0) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `
    <h3>${t("weekly_weather_aspects_title")}</h3>
    <table class="astro-forecast-table">
      <tbody>
        ${aspects
          .map(
            (a) => `
          <tr>
            <td>${a.date}</td>
            <td>${planetLabel(a.planet_a)} ${aspectTypeLabel(a.aspect_type)} ${planetLabel(a.planet_b)}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

function renderWeeklyWeatherBySignScores() {
  const container = document.getElementById("weekly-weather-by-sign-scores");
  if (!container || !weeklyWeatherBySignData) return;
  const rows = [...weeklyWeatherBySignData.by_sign].sort((a, b) => b.score - a.score);
  container.innerHTML = `
    <table class="astro-forecast-table">
      <tbody>
        ${rows
          .map(
            (row) => `
          <tr${row.is_main_event_sign ? ' class="weekly-weather-main-sign-row"' : ""}>
            <td>${signLabel(row.sign)}${row.is_main_event_sign ? ` <span class="astro-focus-badge">${t("weekly_weather_main_event_sign_badge")}</span>` : ""}</td>
            <td>${starRatingHtml(row.score, { max: 5, compact: true, showScore: false })}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

async function loadWeeklyWeather() {
  const errorEl = document.getElementById("weekly-weather-error");
  errorEl.textContent = "";
  try {
    const [collectiveRes, bySignRes] = await Promise.all([
      fetch(`/api/weekly-weather?start_date=${weeklyWeatherStartDate}`),
      fetch(`/api/weekly-weather/by-sign?start_date=${weeklyWeatherStartDate}`),
    ]);
    if (!collectiveRes.ok) throw new Error(`${t("error_prefix")} ${collectiveRes.status}`);
    if (!bySignRes.ok) throw new Error(`${t("error_prefix")} ${bySignRes.status}`);
    weeklyWeatherData = await collectiveRes.json();
    weeklyWeatherBySignData = await bySignRes.json();
    renderWeeklyWeatherHighlights();
    renderWeeklyWeatherPlanets();
    renderWeeklyWeatherAspects();
    renderWeeklyWeatherBySignScores();
  } catch (err) {
    errorEl.textContent = `${t("error_loading_weekly_weather")} ${err.message}`;
  }
}

document.getElementById("weekly-weather-load-btn").addEventListener("click", () => {
  const dateInput = document.getElementById("weekly-weather-start-date");
  weeklyWeatherStartDate = dateInput.value || todayIsoDate();
  dateInput.value = weeklyWeatherStartDate;
  loadWeeklyWeather();
});

document.getElementById("generate-weekly-weather-reading-btn").addEventListener("click", () => {
  generateSpecializedReading({
    btnId: "generate-weekly-weather-reading-btn",
    errorId: "weekly-weather-reading-error",
    outputId: "weekly-weather-reading-output",
    defaultLabel: t("btn_generate_weekly_weather_reading"),
    requestBody: {
      reading_type: "weekly_weather",
      weekly_weather_start_date: weeklyWeatherStartDate || todayIsoDate(),
    },
  });
});

document.getElementById("generate-weekly-weather-by-sign-btn").addEventListener("click", () => {
  generateSpecializedReading({
    btnId: "generate-weekly-weather-by-sign-btn",
    errorId: "weekly-weather-by-sign-error",
    outputId: "weekly-weather-by-sign-output",
    defaultLabel: t("btn_generate_weekly_weather_by_sign"),
    requestBody: {
      reading_type: "weekly_weather_by_sign",
      weekly_weather_start_date: weeklyWeatherStartDate || todayIsoDate(),
    },
  });
});
