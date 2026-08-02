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
};

let currentChart = null;

function planetLabel(name) {
  return PLANET_LABELS_FR[name] || name;
}

function el(html) {
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
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

function renderTraitTags(characterTraits) {
  if (!characterTraits || !characterTraits.keywords || characterTraits.keywords.length === 0) return "";
  const tags = characterTraits.keywords.map((trait) => `<span class="trait-tag">${trait}</span>`).join("");
  return `<div class="trait-tags">${tags}</div>`;
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

  renderPlanetsTab(data);
  renderHousesTab(data);
  renderAspectsTab(data);
  renderBalanceTab(data);
  renderDispositorsTab(data);
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
// Onglets
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
