const CFG_KEY = "sgm_settings";
const LIVE_INTERVAL = 45_000;
const PREMATCH_INTERVAL = 300_000;

const state = {
  tab: "prematch",
  settings: loadSettings(),
  liveSnapshots: {},
  timers: { live: null, prematch: null },
  fetching: { live: false, prematch: false, history: false },
  hasData: { live: false, prematch: false, history: false },
  historyTips: [],
  historyFilter: "all",
  lastTip: null,
  live: {
    fixtures: [],
    ranked: [],
    skipped: [],
    selectedKey: null,
    scannedAt: null,
  },
  prematch: {
    ranked: [],
    fixtures: [],
    selectedKey: null,
  },
  match: {
    mode: null,
    key: null,
    stats: null,
    statsLoading: false,
    statsFixtureId: null,
    transfermarkt: null,
    transfermarktLoading: false,
    returnTab: null,
  },
};

const els = {
  statusPrematch: document.getElementById("status-prematch"),
  bestPrematch: document.getElementById("best-prematch"),
  tablePrematch: document.getElementById("table-prematch"),
  rankingPrematch: document.getElementById("ranking-prematch"),
  prematchFixtures: document.getElementById("prematch-fixtures"),
  prematchFixturesList: document.getElementById("prematch-fixtures-list"),
  prematchRefresh: document.getElementById("prematch-refresh"),
  statusLive: document.getElementById("status-live"),
  bestLive: document.getElementById("best-live"),
  tableLive: document.getElementById("table-live"),
  rankingLive: document.getElementById("ranking-live"),

  liveFixtures: document.getElementById("live-fixtures"),
  liveFixturesList: document.getElementById("live-fixtures-list"),
  liveContent: document.getElementById("live-content"),
  liveBanner: document.getElementById("live-banner"),
  liveSourceBadge: document.getElementById("live-source-badge"),
  liveRefresh: document.getElementById("live-refresh"),
  liveCount: document.getElementById("live-count"),
  refreshBtn: document.getElementById("refresh"),
  settingsBtn: document.getElementById("settings-btn"),
  drawer: document.getElementById("settings-drawer"),
  drawerBackdrop: document.getElementById("drawer-backdrop"),
  saveSettings: document.getElementById("save-settings"),
  cfgBankroll: document.getElementById("cfg-bankroll"),
  cfgLeague: document.getElementById("cfg-league"),
  cfgAuto: document.getElementById("cfg-auto"),
  cfgNotify: document.getElementById("cfg-notify"),
  historyStats: document.getElementById("history-stats"),
  historyLearning: document.getElementById("history-learning"),
  historyLastTip: document.getElementById("history-last-tip"),
  historyFeed: document.getElementById("history-feed"),
  historyEmpty: document.getElementById("history-empty"),
  liveLastTip: document.getElementById("live-last-tip"),
  panelMatch: document.getElementById("panel-match"),
  matchPageBody: document.getElementById("match-page-body"),
  matchBack: document.getElementById("match-back"),
  matchStatsRefresh: document.getElementById("match-stats-refresh"),
  matchPageLabel: document.getElementById("match-page-label"),
  appShell: document.querySelector(".app-shell"),
  desktopSidebar: document.getElementById("desktop-sidebar"),
  desktopStatus: document.getElementById("desktop-status"),
  desktopStatusSync: document.getElementById("desktop-status-sync"),
  desktopLiveBadge: document.getElementById("desktop-live-badge"),
};

const isDesktopApp =
  new URLSearchParams(location.search).get("desktop") === "1" ||
  localStorage.getItem("sgm_desktop") === "1";

function loadSettings() {
  try {
    return {
      bankroll: null,
      league: "",
      autoRefresh: true,
      notify: false,
      ...JSON.parse(localStorage.getItem(CFG_KEY) || "{}"),
    };
  } catch {
    return { bankroll: null, league: "", autoRefresh: true, notify: false };
  }
}

function saveSettingsToStorage() {
  const bankroll = parseFloat(els.cfgBankroll.value);
  state.settings = {
    bankroll: Number.isFinite(bankroll) && bankroll > 0 ? bankroll : null,
    league: (els.cfgLeague.value || "").trim(),
    autoRefresh: els.cfgAuto.checked,
    notify: els.cfgNotify.checked,
  };
  localStorage.setItem(CFG_KEY, JSON.stringify(state.settings));
  closeDrawer();
  scheduleAutoRefresh();
  if (state.settings.notify) setupPushSubscription();
  refreshCurrent();
}

function applySettingsToForm() {
  els.cfgBankroll.value = state.settings.bankroll ?? "";
  els.cfgLeague.value = state.settings.league || "";
  els.cfgAuto.checked = state.settings.autoRefresh !== false;
  els.cfgNotify.checked = !!state.settings.notify;
}

async function applyBranding() {
  try {
    const res = await fetch("/api/branding");
    if (!res.ok) return;
    const b = await res.json();
    document.getElementById("app-title").textContent = b.app_name || "Betting Brain";
    document.getElementById("app-tagline").textContent =
      b.tagline || "Dicas inteligentes · pré-jogo e ao vivo";
    document.title = b.app_name_full || b.app_name || "Betting Brain";
    const icon = b.icons?.favicon || b.icons?.icon_192;
    if (icon) {
      document.getElementById("app-icon").src = icon;
      document.querySelector('link[rel="icon"]').href = icon;
      document.querySelector('link[rel="apple-touch-icon"]').href = b.icons?.icon_192 || icon;
    }
    if (b.theme_color) {
      document.querySelector('meta[name="theme-color"]').content = b.theme_color;
    }
    if (b.author) {
      document.getElementById("app-footer").textContent =
        `${b.app_name} · ${b.author} — Aposta com responsabilidade.`;
    }
    if (isDesktopApp) {
      const deskTitle = document.getElementById("desktop-brand-title");
      if (deskTitle) deskTitle.textContent = b.app_name_full || b.app_name || "SindGreenMentor";
      const deskIcon = document.getElementById("desktop-brand-icon");
      const deskIconSrc = b.icons?.icon_192 || b.icons?.favicon;
      if (deskIcon && deskIconSrc) deskIcon.src = deskIconSrc;
    }
  } catch { /* defaults */ }
}

function formatKickoff(iso) {
  try {
    return new Date(iso).toLocaleString("pt-PT", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso || "—"; }
}

function formatAgePt(iso) {
  if (!iso) return "";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const mins = Math.floor((Date.now() - then.getTime()) / 60_000);
  if (mins < 1) return "agora mesmo";
  if (mins === 1) return "há 1 minuto";
  if (mins < 60) return `há ${mins} minutos`;
  const hours = Math.floor(mins / 60);
  if (hours === 1) return "há 1 hora";
  if (hours < 24) return `há ${hours} horas`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "há 1 dia";
  return `há ${days} dias`;
}

function renderLastTipNote(el, tip, { liveOnly = false } = {}) {
  if (!el) return;
  if (!tip?.logged_at) {
    el.classList.add("hidden");
    el.innerHTML = "";
    return;
  }
  const age = formatAgePt(tip.logged_at);
  const mode = tip.mode === "live" ? "LIVE" : "Pré-jogo";
  const detail = `${tip.home} vs ${tip.away} · ${tip.market}`;
  const prefix = liveOnly ? "Última dica live enviada" : "Última tip enviada";
  el.classList.remove("hidden");
  el.innerHTML = `${prefix} <strong>${age}</strong> · ${mode} · ${detail}`;
}

function evClass(pct) { return pct >= 0 ? "ev-pos" : "ev-neg"; }

function formatEnvCompact(env) {
  if (!env?.weather) return "";
  const w = env.weather;
  const alt = env.altitude_m > 0 ? ` · ${Math.round(env.altitude_m)}m` : "";
  const rain = w.precipitation_mm > 0 ? ` · ${Math.round(w.precipitation_mm)}mm` : "";
  return `${Math.round(w.temperature_c)}°C · ${w.condition_label || w.condition}${rain}${alt}`;
}

function renderEnvironmentBlock(env, impact) {
  if (!env?.weather) return "";
  const w = env.weather;
  const t = env.travel || {};
  const venueNote = env.venue_correction
    ? `<p class="env-venue-correction">Corrigido: jogo em <strong>${env.stadium || env.venue}</strong> (casa habitual: ${env.venue_correction.usual_home}) · ${(env.venue_correction.sources || []).join(" + ")}</p>`
    : "";
  const metrics = [
    ["Estádio do jogo", env.stadium || env.venue || "—"],
    ["Temperatura", `${w.temperature_c}°C`],
    ["Condição", w.condition_label || w.condition],
    ["Chuva", `${w.precipitation_mm} mm`],
    ["Vento", `${w.wind_kmh} km/h`],
    ["Humidade", `${w.humidity_pct}%`],
    ["Severidade meteo", w.severity != null ? String(w.severity) : "—"],
    ["Altitude estádio", env.altitude_m > 0 ? `${env.altitude_m} m` : "—"],
    ["Alt. casa / fora", `${env.home_altitude_m} m / ${env.away_altitude_m} m`],
  ];
  if (t.distance_km > 0) {
    metrics.push(["Viagem visitante", `${t.distance_km} km · ${t.hours}h`]);
    if (t.timezone_diff) metrics.push(["Fuso horário", `±${t.timezone_diff}h`]);
  }
  const src = env.weather_source_label || env.weather_source || "";
  const venue = env.venue || env.stadium || env.city || "";
  const impactRows = [];
  if (impact?.home) {
    const h = impact.home;
    impactRows.push(
      `${h.team} (casa): ataque ${h.attack_orig}→${h.attack}, defesa ${h.defense_orig}→${h.defense}`
    );
  }
  if (impact?.away) {
    const a = impact.away;
    impactRows.push(
      `${a.team} (fora): ataque ${a.attack_orig}→${a.attack}, defesa ${a.defense_orig}→${a.defense}`
    );
  }
  return `
    <div class="env-section">
      <div class="env-section-title">Clima e altitude</div>
      ${venueNote}
      ${venue ? `<div class="meta env-venue">${venue}${env.city && env.city !== venue ? ` · ${env.city}` : ""}</div>` : ""}
      <div class="env-metrics">${metrics
        .map(
          ([label, val]) =>
            `<div class="env-metric"><span class="label">${label}</span><span>${val}</span></div>`
        )
        .join("")}</div>
      ${src ? `<div class="meta env-source">Fonte: ${src}</div>` : ""}
      ${
        impactRows.length
          ? `<div class="env-impact"><div class="meta">Impacto no modelo</div>${impactRows
              .map((line) => `<div class="env-impact-line">${line}</div>`)
              .join("")}</div>`
          : ""
      }
    </div>`;
}

function getMatchContext(mode, key) {
  if (mode === "live") {
    const ranked = findLiveRanked(key);
    const fixture = findLiveFixture(key) || ranked;
    const skipReason = findLiveSkipped(key);
    const fx = ranked || fixture;
    if (!fx) return null;
    return {
      mode,
      key,
      ranked,
      fixture,
      fx,
      skipReason,
      fixtureId: fx.fixture_id || ranked?.fixture_id || null,
    };
  }
  const ranked = findPrematchRanked(key);
  const fixture = (state.prematch.fixtures || []).find((f) => liveMatchKey(f.home, f.away) === key);
  const fx = ranked || fixture;
  if (!fx) return null;
  return {
    mode,
    key,
    ranked,
    fixture,
    fx,
    skipReason: null,
    fixtureId: fx.fixture_id || ranked?.fixture_id || null,
  };
}

function statBarWidth(home, away) {
  const h = Number(home) || 0;
  const a = Number(away) || 0;
  const total = h + a;
  if (total <= 0) return { home: 50, away: 50 };
  return { home: Math.round((h / total) * 100), away: Math.round((a / total) * 100) };
}

function renderStatCompare(label, homeVal, awayVal, homeName, awayName) {
  const h = homeVal ?? 0;
  const a = awayVal ?? 0;
  if (h === 0 && a === 0 && homeVal == null && awayVal == null) return "";
  const widths = statBarWidth(h, a);
  return `
    <div class="stat-compare">
      <div class="stat-compare-head">
        <span class="stat-team home" title="${homeName}">${h}</span>
        <span class="stat-label">${label}</span>
        <span class="stat-team away" title="${awayName}">${a}</span>
      </div>
      <div class="stat-dual-bar">
        <div class="stat-bar-home" style="width:${widths.home}%"></div>
        <div class="stat-bar-away" style="width:${widths.away}%"></div>
      </div>
    </div>`;
}

function renderPossessionBar(homePct, awayPct, homeName, awayName) {
  if (homePct == null && awayPct == null) return "";
  const h = homePct ?? (awayPct != null ? 100 - awayPct : 50);
  const a = awayPct ?? 100 - h;
  return `
    <div class="possession-block">
      <div class="possession-labels">
        <span class="stat-team home">${homeName}</span>
        <span class="stat-label">Posse de bola</span>
        <span class="stat-team away">${awayName}</span>
      </div>
      <div class="possession-bar">
        <div class="possession-home" style="width:${h}%"><span>${h}%</span></div>
        <div class="possession-away" style="width:${a}%"><span>${a}%</span></div>
      </div>
    </div>`;
}

function eventIcon(type, detail) {
  const t = (type || "").toLowerCase();
  const d = (detail || "").toLowerCase();
  if (t === "goal") return "⚽";
  if (t === "card") return d.includes("red") ? "🟥" : "🟨";
  if (t === "subst") return "↔";
  if (t === "var") return "📺";
  return "•";
}

function formatEventMinute(ev) {
  if (ev.extra) return `${ev.minute}+${ev.extra}'`;
  return `${ev.minute}'`;
}

function renderEventsTimeline(events, statsLoaded = false) {
  if (!events?.length) {
    const hint = statsLoaded
      ? '<p class="meta">Linha de tempo: toca ↻ Estatísticas para actualizar (inclui eventos).</p>'
      : "";
    return `<div class="match-section"><div class="match-section-title">Eventos</div><p class="meta">Sem eventos registados.</p>${hint}</div>`;
  }
  const items = events
    .map((ev) => {
      const who = [ev.player, ev.team].filter(Boolean).join(" · ");
      const assist = ev.assist ? ` (${ev.assist})` : "";
      return `<li class="event-item">
        <span class="event-min">${formatEventMinute(ev)}</span>
        <span class="event-icon">${eventIcon(ev.type, ev.detail)}</span>
        <span class="event-text"><strong>${ev.type}</strong>${ev.detail ? ` — ${ev.detail}` : ""}<br>${who}${assist}</span>
      </li>`;
    })
    .join("");
  return `
    <div class="match-section">
      <div class="match-section-title">Linha de tempo</div>
      <ul class="events-timeline">${items}</ul>
    </div>`;
}

function formatXgPair(homeVal, awayVal, homeSrc, awaySrc, bundleSrc) {
  const fmt = (v, src) => {
    if (v == null) return "—";
    if (src === "estimated") return `${v} (est.)`;
    return String(v);
  };
  const notes = {
    estimated: "xG estimado a partir de remates (sem API de xG).",
    mixed: "xG misto: API numa equipa, estimativa noutra.",
  };
  const note = notes[bundleSrc]
    ? `<div class="meta xg-estimate-note">${notes[bundleSrc]}</div>`
    : "";
  return {
    home: fmt(homeVal, homeSrc),
    away: fmt(awayVal, awaySrc),
    note,
  };
}

function liveSourceBadgeMeta(source, label) {
  const src = (source || "").toLowerCase();
  if (src === "api-football") return { cls: "api", text: label || "API-Football" };
  if (src === "espn") return { cls: "espn", text: label || "ESPN" };
  return { cls: "", text: label || "" };
}

function updateLiveSourceBadge(source, label) {
  if (!els.liveSourceBadge) return;
  const meta = liveSourceBadgeMeta(source, label);
  if (!meta.text) {
    els.liveSourceBadge.classList.add("hidden");
    els.liveSourceBadge.textContent = "";
    return;
  }
  els.liveSourceBadge.classList.remove("hidden", "api", "espn");
  if (meta.cls) els.liveSourceBadge.classList.add(meta.cls);
  els.liveSourceBadge.textContent = meta.text;
  els.liveSourceBadge.title = `Fonte dos jogos: ${meta.text}`;
}

function renderStatsHistory(history) {
  if (!history?.length || history.length < 2) return "";
  const last = history[history.length - 1];
  const maxXg = Math.max(
    ...history.map((h) => Math.max(h.home_xg || 0, h.away_xg || 0)),
    0.1
  );

  const xgBars = history
    .map((h) => {
      const hPct = Math.round(((h.home_xg || 0) / maxXg) * 100);
      const aPct = Math.round(((h.away_xg || 0) / maxXg) * 100);
      return `<div class="history-spark-bar home" style="height:${Math.max(20, hPct)}%" title="${h.minute ?? "?"}'"></div>
        <div class="history-spark-bar away" style="height:${Math.max(20, aPct)}%" title="${h.minute ?? "?"}'"></div>`;
    })
    .join("");

  const possEnd =
    last.home_possession_pct != null
      ? `${last.home_possession_pct}%`
      : "—";

  return `
    <div class="match-section">
      <div class="match-section-title">Evolução (${history.length} leituras)</div>
      <div class="stats-history-chart">
        <div class="history-spark">
          <span class="history-spark-label">xG</span>
          <div class="history-spark-track" style="align-items:flex-end;height:2.2rem">${xgBars}</div>
          <span class="history-spark-end">${(last.home_xg ?? "—")} / ${(last.away_xg ?? "—")}</span>
        </div>
        <div class="meta">Última posse casa: ${possEnd} · min ${last.minute ?? "—"}'</div>
      </div>
    </div>`;
}

function tmAlignmentClass(alignment) {
  if (alignment === "strong") return "tm-align-strong";
  if (alignment === "weak") return "tm-align-weak";
  if (alignment === "veto") return "tm-align-weak";
  return "tm-align-neutral";
}

function motAlignmentLabel(alignment) {
  if (alignment === "strong") return "Motivação forte";
  if (alignment === "veto") return "Veto";
  if (alignment === "weak") return "Sem motivação";
  return "Motivação parcial";
}

function renderMotivationSection(mot) {
  if (!mot) {
    return `
      <div class="match-section mot-section">
        <div class="match-section-title">Motivation Gate</div>
        <p class="meta">Auditores indisponíveis neste ciclo.</p>
      </div>`;
  }
  const votes = (mot.votes || [])
    .map(
      (v) =>
        `<li><strong>${v.category}</strong> — ${v.label}${v.supports_market === false ? " · ⚠" : ""}</li>`
    )
    .join("");
  const club = mot.clubelo
    ? `<p class="meta">ClubElo: ${mot.clubelo.home?.elo ?? "—"} vs ${mot.clubelo.away?.elo ?? "—"} (Δ ${mot.clubelo.diff ?? "—"})</p>`
    : "";
  const table = mot.table_stakes
    ? `<p class="meta">Classificação: ${mot.table_stakes.home?.label ?? "—"} · ${mot.table_stakes.away?.label ?? "—"}</p>`
    : "";
  const hist = mot.historical?.closing
    ? `<p class="meta">Fecho hist.: ${mot.historical.closing.today_odd ?? "—"} vs ${mot.historical.closing.closing_avg ?? "—"} (${mot.historical.closing.delta_pct > 0 ? "+" : ""}${mot.historical.closing.delta_pct ?? 0}%)</p>`
    : "";
  const style = mot.historical?.style
    ? `<p class="meta">Estilo: ${mot.historical.style}</p>`
    : "";
  return `
    <div class="match-section mot-section">
      <div class="match-section-head">
        <div class="match-section-title">Motivation Gate</div>
        <span class="tm-align-badge ${tmAlignmentClass(mot.alignment)}">${motAlignmentLabel(mot.alignment)}</span>
      </div>
      <p class="meta tm-summary">${mot.summary || ""}</p>
      <div class="tm-metrics">
        <span>Score ${mot.motivation_score}/6</span>
        <span>Stake ×${mot.stake_multiplier ?? 1}</span>
        ${mot.veto ? `<span class="tm-gap">Trap</span>` : ""}
      </div>
      ${club}
      ${table}
      ${hist}
      ${style}
      ${votes ? `<ul class="tm-signals">${votes}</ul>` : ""}
    </div>`;
}

function motivationListBadge(mot) {
  if (!mot) return "";
  if (mot.alignment === "strong") return `<span class="mot-list-badge">MG ★</span>`;
  if (mot.alignment === "veto" || mot.veto) return `<span class="mot-list-badge veto">MG ✕</span>`;
  if (mot.motivation_score >= 1) return `<span class="mot-list-badge neutral">MG</span>`;
  return "";
}

function renderTransfermarktSection(tm) {
  if (state.match.transfermarktLoading) {
    return `<div class="match-section"><p class="meta">A carregar inteligência Transfermarkt…</p></div>`;
  }
  if (!tm?.data_available) {
    return `
      <div class="match-section tm-section">
        <div class="match-section-title">Transfermarkt</div>
        <p class="meta">Sem dados em cache para este confronto. Actualiza <code>data/transfermarkt/*.jsonl</code>.</p>
      </div>`;
  }
  const blocks = [];
  if (tm.value_gap) {
    blocks.push(`
      <div class="tm-block">
        <div class="tm-block-title">Valor de plantel</div>
        <div class="tm-metrics">
          <span>${tm.value_gap.home_value_m}M vs ${tm.value_gap.away_value_m}M</span>
          <span class="tm-gap">Gap ${tm.value_gap.gap_pct > 0 ? "+" : ""}${tm.value_gap.gap_pct}%</span>
        </div>
        <p class="meta">${tm.value_gap.label}</p>
      </div>`);
  }
  if (tm.tactical) {
    blocks.push(`
      <div class="tm-block">
        <div class="tm-block-title">Treinadores & tática</div>
        <p class="meta">${tm.tactical.home_manager} (${tm.tactical.home_formation}) vs ${tm.tactical.away_manager} (${tm.tactical.away_formation})</p>
        <p class="meta">${tm.tactical.label}</p>
      </div>`);
  }
  if (tm.referee) {
    blocks.push(`
      <div class="tm-block">
        <div class="tm-block-title">Árbitro</div>
        <p class="meta">${tm.referee.label}</p>
        <p class="meta">Amarelos ${tm.referee.yellow_avg}/j · Penáltis ${tm.referee.penalty_avg}/j</p>
      </div>`);
  }
  const absRows = [];
  for (const side of [tm.home_absences, tm.away_absences]) {
    if (!side?.absences?.length) continue;
    const items = side.absences
      .slice(0, 3)
      .map(
        (a) =>
          `<li>${a.name} — ${a.status === "suspended" ? "suspenso" : "lesionado"} · ${a.days_out}d · ${a.market_value_m}M</li>`
      )
      .join("");
    absRows.push(`<div class="tm-abs-side"><strong>${side.team}</strong><ul>${items}</ul><p class="meta">${side.label}</p></div>`);
  }
  if (absRows.length) {
    blocks.push(`<div class="tm-block"><div class="tm-block-title">Lesões & suspensões</div>${absRows.join("")}</div>`);
  }
  const signals = (tm.signals || []).map((s) => `<li>${s}</li>`).join("");
  return `
    <div class="match-section tm-section">
      <div class="match-section-head">
        <div class="match-section-title">Transfermarkt</div>
        <span class="tm-align-badge ${tmAlignmentClass(tm.alignment)}">${tm.alignment === "strong" ? "Alinhado" : tm.alignment === "weak" ? "Atenção" : "Neutro"}</span>
      </div>
      <p class="meta tm-summary">${tm.summary || ""}</p>
      <div class="tm-blocks">${blocks.join("")}</div>
      ${signals ? `<ul class="tm-signals">${signals}</ul>` : ""}
    </div>`;
}

function renderExtendedMarkets(markets) {
  if (!markets?.length) {
    return `
      <div class="match-section">
        <div class="match-section-title">Oportunidades avançadas</div>
        <p class="meta">Handicap, cantos e golos de equipa — odds estimadas (confirma na casa antes de apostar).</p>
      </div>`;
  }
  const items = markets
    .map((m) => {
      const evCls = m.ev_pct >= 0 ? "pos" : "neg";
      const reasons = (m.reasoning || [])
        .slice(0, 2)
        .map((r) => `<li>${r}</li>`)
        .join("");
      return `
        <div class="extended-pick">
          <div class="extended-pick-head">
            <span>${m.label}</span>
            <span class="extended-ev ${evCls}">EV ${m.ev_pct > 0 ? "+" : ""}${m.ev_pct}%</span>
          </div>
          <div class="extended-meta">Odd ${m.odd} · modelo ${m.model_prob_pct}% vs mercado ${m.implied_prob_pct}%</div>
          ${reasons ? `<ul class="extended-reasons">${reasons}</ul>` : ""}
        </div>`;
    })
    .join("");
  return `
    <div class="match-section">
      <div class="match-section-title">Oportunidades avançadas</div>
      <p class="meta">Handicap, cantos, golos equipa — odds estimadas a partir do contexto live.</p>
      <div class="extended-markets-list">${items}</div>
    </div>`;
}

function renderStatsSection(stats, homeName, awayName) {
  if (!stats?.stats_available) {
    return `
      <div class="match-section">
        <div class="match-section-title">Estatísticas ao vivo</div>
        <p class="meta">${stats?.message || "Indisponível — jogo via ESPN ou liga sem cobertura."}</p>
      </div>`;
  }
  const hs = stats.home_stats || {};
  const as = stats.away_stats || {};
  const xgFmt = formatXgPair(hs.xg, as.xg, hs.xg_source, as.xg_source, stats.xg_source);
  const compares = [
    ["Chutes totais", hs.shots_total, as.shots_total],
    ["À baliza", hs.shots_on, as.shots_on],
    ["Fora", hs.shots_off, as.shots_off],
    ["Bloqueados", hs.shots_blocked, as.shots_blocked],
    ["Cantos", hs.corners, as.corners],
    ["Faltas", hs.fouls, as.fouls],
    ["Fora de jogo", hs.offsides, as.offsides],
    ["Defesas", hs.saves, as.saves],
    ["Passes %", hs.passes_pct, as.passes_pct],
  ]
    .map(([label, hv, av]) => renderStatCompare(label, hv, av, homeName, awayName))
    .filter(Boolean)
    .join("");

  const xgRow =
    hs.xg != null || as.xg != null
      ? (() => {
          const widths = statBarWidth(hs.xg, as.xg);
          return `
    <div class="stat-compare">
      <div class="stat-compare-head">
        <span class="stat-team home" title="${homeName}">${xgFmt.home}</span>
        <span class="stat-label">xG</span>
        <span class="stat-team away" title="${awayName}">${xgFmt.away}</span>
      </div>
      <div class="stat-dual-bar">
        <div class="stat-bar-home" style="width:${widths.home}%"></div>
        <div class="stat-bar-away" style="width:${widths.away}%"></div>
      </div>
    </div>`;
        })()
      : "";

  return `
    <div class="match-section">
      <div class="match-section-title">Estatísticas ao vivo</div>
      ${renderPossessionBar(hs.possession_pct, as.possession_pct, homeName, awayName)}
      ${xgRow}
      ${xgFmt.note}
      <div class="stats-grid-charts">${compares || '<p class="meta">Sem métricas detalhadas.</p>'}</div>
    </div>
      ${renderStatsHistory(stats.stats_history)}
      ${renderEventsTimeline(stats.events, true)}`;
}

function renderBettingSection(ctx) {
  const { ranked, skipReason, mode } = ctx;
  if (!ranked && !skipReason) {
    return `<div class="match-section"><p class="meta">Este jogo ainda não foi analisado pelo motor neste ciclo.</p></div>`;
  }
  let statusBadge = "";
  let statusClass = "watch";
  if (ranked?.should_bet) {
    statusBadge = "★ Dica recomendada";
    statusClass = "tip";
  } else if (skipReason) {
    statusBadge = "Sem dica";
    statusClass = "skip";
  } else if (ranked) {
    statusBadge = mode === "live" ? "Analisado — abaixo do limiar" : "Analisado";
    statusClass = "watch";
  }

  const rows = [];
  if (ranked) {
    rows.push(["Mercado", ranked.best_market || "—"]);
    if (ranked.odd != null) rows.push(["Odd", String(ranked.odd)]);
    rows.push(["EV", `${ranked.best_ev_pct > 0 ? "+" : ""}${ranked.best_ev_pct}%`]);
    rows.push(["Score", `${ranked.best_score} (mín. ${ranked.min_score})`]);
    if (ranked.stake_level) rows.push(["Stake", `${ranked.stake_level}/10`]);
    if (ranked.stake_display) rows.push(["Aposta", ranked.stake_display]);
    if (ranked.motivation?.summary) rows.push(["Motivação", ranked.motivation.summary]);
    if (ranked.competition_progress?.progress_pct != null) {
      rows.push(["Época", `${ranked.competition_progress.progress_pct}%`]);
    }
    if (ranked.block_reason) rows.push(["Bloqueio", ranked.block_reason]);
  }
  const markets =
    ranked?.top_markets?.length
      ? `<ul class="live-detail-markets">${ranked.top_markets.map((m) => `<li>${m}</li>`).join("")}</ul>`
      : "";
  const skipBlock = skipReason ? `<div class="meta warn">Motivo: ${skipReason}</div>` : "";

  return `
    <div class="match-section">
      <div class="match-section-head">
        <div class="match-section-title">Análise ${mode === "live" ? "in-play" : "pré-jogo"}</div>
        ${statusBadge ? `<span class="live-detail-status ${statusClass}">${statusBadge}</span>` : ""}
      </div>
      ${
        rows.length
          ? `<div class="live-detail-grid">${rows
              .map(([label, val]) => `<div class="row"><span class="label">${label}</span><span>${val}</span></div>`)
              .join("")}</div>`
          : ""
      }
      ${markets ? `<div class="meta" style="margin-top:0.5rem">Top mercados</div>${markets}` : ""}
      ${ranked?.summary ? `<div class="live-detail-summary">${ranked.summary}</div>` : ""}
      ${skipBlock}
    </div>`;
}

function renderMatchPage() {
  if (!els.matchPageBody) return;
  const ctx = getMatchContext(state.match.mode, state.match.key);
  if (!ctx) {
    closeMatchPage();
    return;
  }
  const { fx, ranked, mode } = ctx;
  const home = fx.home;
  const away = fx.away;
  const isLive = mode === "live";
  const minute = isLive
    ? fx.injury_time
      ? `${fx.minute}+${fx.injury_time}'`
      : `${fx.minute ?? "—"}'`
    : formatKickoff(fx.kickoff);
  const score = isLive ? fx.score || `${fx.home_score ?? 0}-${fx.away_score ?? 0}` : null;
  const statusShort = isLive && fx.status === "HT" ? " · Intervalo" : "";
  const env = ranked?.environment;
  const statsBlock = state.match.statsLoading
    ? `<div class="match-section"><p class="meta">A carregar estatísticas…</p></div>`
    : isLive
      ? renderStatsSection(state.match.stats, home, away)
      : `<div class="match-section"><p class="meta">Estatísticas ao vivo disponíveis quando o jogo começar.</p></div>`;

  els.matchPageBody.innerHTML = `
    <div class="match-hero card">
      <div class="match-name">${home} vs ${away}</div>
      <div class="meta">${fx.league || ""}${fx.stage ? ` · ${fx.stage}` : ""}</div>
      ${
        isLive
          ? `<div class="match-hero-score">
              <span class="live-detail-score">${score}</span>
              <span class="minute-pill">${minute}${statusShort}</span>
            </div>`
          : `<div class="meta" style="margin-top:0.35rem">Kickoff: ${minute}</div>`
      }
    </div>
    ${env ? renderEnvironmentBlock(env, ranked?.environment_impact) : ""}
    ${!isLive ? renderTransfermarktSection(state.match.transfermarkt) : ""}
    ${!isLive ? renderMotivationSection(ctx.ranked?.motivation) : ""}
    ${statsBlock}
    ${isLive ? renderExtendedMarkets(state.match.stats?.extended_markets) : ""}
    ${renderBettingSection(ctx)}`;
}

async function loadPrematchInsights(home, away, ranked = null) {
  if (ranked?.transfermarkt?.data_available) {
    state.match.transfermarkt = ranked.transfermarkt;
    state.match.transfermarktLoading = false;
    if (state.match.key) renderMatchPage();
    return;
  }
  state.match.transfermarktLoading = true;
  if (state.match.key) renderMatchPage();
  try {
    const params = new URLSearchParams({ home, away });
    if (ranked?.odd && ranked.best_market) {
      const fx = ranked;
      if (fx.odd) {
        /* odds parciais só se existirem no ranked — skip */
      }
    }
    const res = await fetch(`/api/match/prematch-insights?${params}`);
    state.match.transfermarkt = res.ok ? await res.json() : { data_available: false };
  } catch {
    state.match.transfermarkt = { data_available: false };
  } finally {
    state.match.transfermarktLoading = false;
    if (state.match.key) renderMatchPage();
  }
}

async function loadMatchStats(fixtureId, { force = false, withEvents = false } = {}) {
  if (!fixtureId) {
    state.match.stats = { stats_available: false, message: "ID do jogo indisponível (fonte ESPN)." };
    state.match.statsLoading = false;
    state.match.statsFixtureId = null;
    updateMatchStatsRefreshBtn();
    renderMatchPage();
    return;
  }
  if (
    !force &&
    state.match.statsFixtureId === fixtureId &&
    state.match.stats &&
    !state.match.statsLoading
  ) {
    return;
  }
  state.match.statsLoading = true;
  updateMatchStatsRefreshBtn();
  renderMatchPage();
  try {
    const params = new URLSearchParams({ fixture_id: String(fixtureId) });
    if (withEvents) params.set("events", "true");
    const ctx = getMatchContext(state.match.mode, state.match.key);
    if (ctx?.fx && state.match.mode === "live") {
      params.set("home_score", String(ctx.fx.home_score ?? 0));
      params.set("away_score", String(ctx.fx.away_score ?? 0));
      params.set("minute", String(ctx.fx.minute ?? 0));
      if (ctx.fx.injury_time) params.set("injury_time", String(ctx.fx.injury_time));
      if (ctx.fx.home) params.set("home", ctx.fx.home);
      if (ctx.fx.away) params.set("away", ctx.fx.away);
    }
    const res = await fetch(`/api/match/detail?${params}`);
    state.match.stats = res.ok
      ? await res.json()
      : { stats_available: false, message: "Não foi possível carregar estatísticas." };
    state.match.statsFixtureId = fixtureId;
  } catch {
    state.match.stats = { stats_available: false, message: "Erro de rede ao carregar estatísticas." };
    state.match.statsFixtureId = null;
  } finally {
    state.match.statsLoading = false;
    updateMatchStatsRefreshBtn();
    if (state.match.key) renderMatchPage();
  }
}

function updateMatchStatsRefreshBtn() {
  if (!els.matchStatsRefresh) return;
  const ctx = state.match.key ? getMatchContext(state.match.mode, state.match.key) : null;
  const show = state.match.mode === "live" && ctx?.fixtureId;
  els.matchStatsRefresh.classList.toggle("hidden", !show);
  els.matchStatsRefresh.disabled = !!state.match.statsLoading;
  els.matchStatsRefresh.textContent = state.match.statsLoading
    ? "A carregar…"
    : "↻ Estatísticas";
}

function openMatchPage(mode, key) {
  const ctx = getMatchContext(mode, key);
  if (!ctx) return;
  state.match.mode = mode;
  state.match.key = key;
  state.match.stats = null;
  state.match.transfermarkt = null;
  state.match.transfermarktLoading = false;
  state.match.returnTab = state.tab;
  if (mode === "live") {
    state.live.selectedKey = key;
    renderLiveFixtures(state.live.fixtures);
    renderRankingLive(state.live.ranked, state.lastTip);
  } else {
    state.prematch.selectedKey = key;
    renderPrematchFixtures(state.prematch.fixtures);
    renderRankingPrematch(state.prematch.ranked);
  }
  document.querySelectorAll(".panel:not(#panel-match)").forEach((p) => p.classList.remove("active"));
  els.panelMatch?.classList.remove("hidden");
  els.panelMatch?.classList.add("active");
  els.appShell?.classList.add("match-open");
  if (els.matchPageLabel) {
    els.matchPageLabel.textContent = mode === "live" ? "Ao vivo" : "Pré-jogo";
  }
  renderMatchPage();
  if (mode === "prematch") {
    loadPrematchInsights(ctx.fx.home, ctx.fx.away, ctx.ranked);
  }
  if (mode === "live" && ctx.fixtureId) {
    if (state.match.statsFixtureId !== ctx.fixtureId) {
      loadMatchStats(ctx.fixtureId);
    } else {
      updateMatchStatsRefreshBtn();
    }
  } else {
    updateMatchStatsRefreshBtn();
  }
}

function closeMatchPage() {
  const tab = state.match.returnTab || state.tab || "prematch";
  state.match.mode = null;
  state.match.key = null;
  state.match.stats = null;
  state.match.statsLoading = false;
  state.match.statsFixtureId = null;
  state.match.transfermarkt = null;
  state.match.transfermarktLoading = false;
  state.match.returnTab = null;
  els.panelMatch?.classList.add("hidden");
  els.panelMatch?.classList.remove("active");
  els.appShell?.classList.remove("match-open");
  switchTab(tab, { skipMatchClose: true });
}

function showError(el, message) {
  el.className = "card error";
  el.textContent = message;
}

function setPanelRefreshing(panel, on) {
  if (panel === "live") {
    els.liveBanner?.classList.toggle("refreshing", on);
    els.liveContent?.classList.toggle("refreshing", on);
    els.liveRefresh?.classList.toggle("hidden", !on);
  } else if (panel === "prematch") {
    els.prematchRefresh?.classList.toggle("hidden", !on);
  }
  const any = state.fetching.live || state.fetching.prematch || state.fetching.history;
  updateRefreshBallState(any);
}

let refreshBallHidden = false;
let refreshBallTimer = null;

function updateRefreshBallState(isFetching) {
  const btn = els.refreshBtn;
  if (!btn || refreshBallHidden) return;
  btn.classList.toggle("loading", isFetching);
  btn.classList.toggle("idle", !isFetching);
}

function hideRefreshBallBriefly() {
  const btn = els.refreshBtn;
  if (!btn || refreshBallHidden) return;

  refreshBallHidden = true;
  if (refreshBallTimer) clearTimeout(refreshBallTimer);
  btn.classList.remove("idle", "loading");
  btn.classList.add("ball-gone");

  refreshBallTimer = setTimeout(() => {
    btn.classList.remove("ball-gone");
    refreshBallHidden = false;
    refreshBallTimer = null;
    updateRefreshBallState(
      state.fetching.live || state.fetching.prematch || state.fetching.history,
    );
  }, 1000);
}

/* ── Pré-jogo ── */
function renderBestPrematch(best) {
  if (!best) { els.bestPrematch.classList.add("hidden"); return; }
  els.bestPrematch.classList.remove("hidden");
  els.bestPrematch.className = "card tip-hero";
  els.bestPrematch.innerHTML = `
    <div class="best-badge">★ Pick do dia</div>
    <div class="match-name">${best.home} vs ${best.away}</div>
    <div class="meta">${best.league} · ${formatKickoff(best.kickoff)}</div>
    <div class="pill-row">
      <span class="pill ${best.should_bet ? "yes" : ""}">${best.best_market} @ ${best.odd}</span>
      <span class="pill ${evClass(best.best_ev_pct)}">EV ${best.best_ev_pct > 0 ? "+" : ""}${best.best_ev_pct}%</span>
      ${best.stake_level ? `<span class="pill kelly">Stake ${best.stake_level}/10</span>` : ""}
      ${best.stake_display ? `<span class="pill kelly">${best.stake_display}</span>` : ""}
      ${best.motivation?.alignment === "strong" ? `<span class="pill yes">MG ★</span>` : ""}
      ${best.motivation?.veto ? `<span class="pill warn">MG veto</span>` : ""}
    </div>
    ${best.motivation?.summary ? `<div class="meta">${best.motivation.summary}</div>` : ""}
    ${best.environment ? `<div class="meta env-compact">${formatEnvCompact(best.environment)}</div>` : ""}`;
}

function findPrematchRanked(key) {
  return (state.prematch.ranked || []).find((r) => liveMatchKey(r.home, r.away) === key) || null;
}

function selectPrematchMatch(key) {
  openMatchPage("prematch", key);
}

function renderRankingPrematch(ranked) {
  if (!ranked?.length) { els.rankingPrematch.classList.add("hidden"); return; }
  els.rankingPrematch.classList.remove("hidden");
  const rows = ranked.map((r) => {
    const key = liveMatchKey(r.home, r.away);
    const sel = state.prematch.selectedKey === key ? " selected" : "";
    const envHint = r.environment ? `<div class="meta env-compact">${formatEnvCompact(r.environment)}</div>` : "";
    return `
    <tr class="prematch-row${r.rank === 1 ? " highlight" : ""}${sel}" data-prematch-key="${key}" role="button" tabindex="0">
      <td>${r.rank}${r.should_bet ? "★" : ""}</td>
      <td>${r.home} vs ${r.away}${envHint}</td>
      <td>${r.best_market}</td>
      <td class="${evClass(r.best_ev_pct)}">${r.best_ev_pct > 0 ? "+" : ""}${r.best_ev_pct}%</td>
      <td>${r.stake_level ? `${r.stake_level}/10` : "—"}${motivationListBadge(r.motivation)}</td>
    </tr>`;
  }).join("");
  els.tablePrematch.innerHTML = `
    <table><thead><tr><th>#</th><th>Jogo</th><th>Mercado</th><th>EV</th><th>Stake</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

function renderPrematchFixtures(fixtures, hoursWindow) {
  if (!els.prematchFixturesList) return;
  const label = hoursWindow ? ` (${hoursWindow}h)` : "";
  if (!fixtures?.length) {
    els.prematchFixturesList.innerHTML =
      `<li class="meta">Nenhum jogo nas próximas horas${label}.</li>`;
    return;
  }
  els.prematchFixturesList.innerHTML = fixtures.map((f) => {
    const key = liveMatchKey(f.home, f.away);
    const ko = f.kickoff ? formatKickoff(f.kickoff) : "hora a confirmar";
    const ranked = findPrematchRanked(key);
    const sel = state.prematch.selectedKey === key ? " selected" : "";
    const envHint = ranked?.environment
      ? `<div class="meta env-compact">${formatEnvCompact(ranked.environment)}</div>`
      : "";
    const tmHint =
      ranked?.transfermarkt?.alignment === "strong"
        ? `<span class="tm-list-badge">TM ★</span>`
        : ranked?.transfermarkt?.data_available
          ? `<span class="tm-list-badge neutral">TM</span>`
          : "";
    const motHint = motivationListBadge(ranked?.motivation);
    return `<li class="live-fixture-item prematch-fixture${sel}" data-prematch-key="${key}" role="button" tabindex="0">
      <span class="live-pulse" style="color:var(--accent)">◷</span>
      <div>
        <strong>${f.home} vs ${f.away}</strong>${tmHint}${motHint}
        <div class="meta">${f.league} · ${ko}</div>
        ${envHint}
      </div>
    </li>`;
  }).join("");
}

function renderPrematchStatus(data, staleMsg = "") {
  els.statusPrematch.className = `card status-card${staleMsg ? " status-stale" : ""}`;
  const win = data.hours_window || 12;
  const notice = data.notice ? `<div class="meta warn">${data.notice}</div>` : "";
  let html = `<strong>${data.total_found}</strong> jogos (${win}h) · <strong>${data.total_analyzed}</strong> analisados
    <div class="meta">Actualizado: ${formatKickoff(data.scanned_at)}</div>
    ${notice}`;
  if (!data.ranked?.length) html += "<div class='meta'>Nenhum jogo analisável com odds/stats.</div>";
  if (staleMsg) html += `<div class="meta">${staleMsg}</div>`;
  els.statusPrematch.innerHTML = html;
}

/* ── Live ── */
function liveMatchKey(home, away) {
  return `${home}|${away}`;
}

function findLiveRanked(key) {
  return (state.live.ranked || []).find((r) => liveMatchKey(r.home, r.away) === key) || null;
}

function findLiveFixture(key) {
  return (state.live.fixtures || []).find((f) => liveMatchKey(f.home, f.away) === key) || null;
}

function findLiveSkipped(key) {
  const ranked = findLiveRanked(key);
  if (ranked) return null;
  const label = key.replace("|", " vs ");
  const hit = (state.live.skipped || []).find((s) => {
    const m = (s.match || "").toLowerCase();
    const [home, away] = key.split("|");
    return m.includes(home.toLowerCase()) && m.includes(away.toLowerCase());
  });
  return hit?.reason || null;
}

function selectLiveMatch(key) {
  openMatchPage("live", key);
}

function setLiveScanData(data) {
  state.live.fixtures = data.fixtures?.length ? data.fixtures : state.live.fixtures;
  state.live.ranked = data.ranked || [];
  state.live.skipped = data.skipped || [];
  state.live.scannedAt = data.scanned_at || null;
  if (state.live.selectedKey) {
    const still = findLiveFixture(state.live.selectedKey) || findLiveRanked(state.live.selectedKey);
    if (!still) state.live.selectedKey = null;
  }
  renderLiveFixtures(state.live.fixtures);
  const liveN = state.live.fixtures?.length || 0;
  if (els.desktopLiveBadge) {
    els.desktopLiveBadge.textContent = String(liveN);
    els.desktopLiveBadge.classList.toggle("hidden", liveN === 0);
  }
  if (state.live.scannedAt) {
    updateDesktopStatus(`Ao vivo · ${liveN} jogos · ${formatKickoff(state.live.scannedAt)}`);
  }
  if (state.match.key && state.match.mode === "live") {
    renderMatchPage();
  }
}

function renderBestLive(best) {
  if (!best) { els.bestLive.classList.add("hidden"); return; }
  const minute = best.injury_time ? `${best.minute}+${best.injury_time}'` : `${best.minute}'`;
  els.bestLive.classList.remove("hidden");
  els.bestLive.className = "card tip-hero win-glow";
  els.bestLive.innerHTML = `
    <div class="best-badge">★ Live pick</div>
    <div class="match-name">${best.home} vs ${best.away}</div>
    <div class="score-line">
      <span class="score-big">${best.score}</span>
      <span class="minute-pill">${minute}</span>
    </div>
    <div class="meta">${best.league}</div>
    <div class="pill-row">
      <span class="pill ${best.should_bet ? "yes" : ""}">${best.best_market} @ ${best.odd}</span>
      <span class="pill ${evClass(best.best_ev_pct)}">EV ${best.best_ev_pct > 0 ? "+" : ""}${best.best_ev_pct}%</span>
      ${best.stake_level ? `<span class="pill kelly">Stake ${best.stake_level}/10</span>` : ""}
      ${best.stake_display ? `<span class="pill kelly">${best.stake_display}</span>` : ""}
    </div>
    ${best.environment ? `<div class="meta env-compact">${formatEnvCompact(best.environment)}</div>` : ""}`;
}

function renderRankingLive(ranked, lastTip = null) {
  if (!ranked?.length) {
    els.rankingLive.classList.add("hidden");
    renderLastTipNote(els.liveLastTip, null, { liveOnly: true });
    return;
  }
  els.rankingLive.classList.remove("hidden");
  renderLastTipNote(els.liveLastTip, lastTip, { liveOnly: true });
  const rows = ranked.map((r) => {
    const min = r.injury_time ? `${r.minute}+${r.injury_time}` : r.minute;
    const key = liveMatchKey(r.home, r.away);
    const sel = state.live.selectedKey === key ? " selected" : "";
    return `<tr class="live-row${sel} ${r.rank === 1 ? "highlight" : ""}" data-live-key="${key}" role="button" tabindex="0">
      <td>${r.rank}${r.should_bet ? "★" : ""}</td>
      <td>${min}' ${r.score}<br><small>${r.home} vs ${r.away}</small></td>
      <td>${r.best_market}</td>
      <td class="${evClass(r.best_ev_pct)}">${r.best_ev_pct > 0 ? "+" : ""}${r.best_ev_pct}%</td>
      <td>${r.stake_level ? `${r.stake_level}/10` : "—"}</td>
    </tr>`;
  }).join("");
  els.tableLive.innerHTML = `
    <table><thead><tr><th>#</th><th>Jogo</th><th>Mercado</th><th>EV</th><th>Stake</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

function renderLiveStatus(data, staleMsg = "") {
  els.statusLive.className = `card status-card${staleMsg ? " status-stale" : ""}`;
  if (data.total_live === 0) {
    els.statusLive.innerHTML = `Nenhum jogo ao vivo.<div class="meta">Actualizado: ${formatKickoff(data.scanned_at)}</div>`;
    return;
  }
  els.statusLive.innerHTML = `
    <strong>${data.total_live}</strong> ao vivo · <strong>${data.total_analyzed}</strong> analisados
    <div class="meta">Actualizado: ${formatKickoff(data.scanned_at)}</div>
    ${staleMsg ? `<div class="meta">${staleMsg}</div>` : ""}`;
}

function renderLiveFixtures(fixtures) {
  if (!els.liveFixturesList) return;
  els.liveFixtures?.classList.remove("hidden");
  if (!fixtures?.length) {
    els.liveFixturesList.innerHTML = '<li class="meta">Nenhum jogo ao vivo neste momento.</li>';
    return;
  }
  els.liveFixturesList.innerHTML = fixtures.map((f) => {
    const min = f.injury_time ? `${f.minute}'+${f.injury_time}` : `${f.minute}'`;
    const status = f.status === "HT" ? " · intervalo" : "";
    const key = liveMatchKey(f.home, f.away);
    const sel = state.live.selectedKey === key ? " selected" : "";
    const ranked = findLiveRanked(key);
    const tip = ranked?.should_bet ? " ★" : "";
    const envHint = ranked?.environment
      ? `<div class="meta env-compact">${formatEnvCompact(ranked.environment)}</div>`
      : "";
    return `<li class="live-fixture-item${sel}" data-live-key="${key}" role="button" tabindex="0">
      <span class="live-pulse">●</span>
      <div>
        <strong>${f.home} ${f.score} ${f.away}${tip}</strong>
        <div class="meta">${f.league} · ${min}${status}</div>
        ${envHint}
      </div>
    </li>`;
  }).join("");
}

/* ── Histórico ── */
function renderHistoryLearning(learning) {
  const box = els.historyLearning;
  if (!box) return;
  if (!learning?.resolved) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  const tune = learning.auto_tune || {};
  const suggestions = (learning.suggestions || []).slice(0, 3);
  const markets = (learning.by_market || []).slice(0, 4);
  const marketRows = markets
    .map(
      (m) =>
        `<span class="learning-chip">${m.market}: ${m.hit_rate_pct ?? "—"}% (${m.wins}G/${m.losses}R)</span>`,
    )
    .join("");
  const sugRows = suggestions.map((s) => `<li>${s}</li>`).join("");
  const tuneActive = learning.auto_tune_active && tune.active;
  const tuneAdjustments = (tune.adjustments || []).slice(0, 5);
  const tuneRows = tuneAdjustments.map((a) => `<li>${a}</li>`).join("");
  const tuneBadge = tuneActive
    ? `<span class="learning-tune-badge">Auto-tune ON</span>`
    : `<span class="learning-tune-badge off">Auto-tune OFF</span>`;
  const tuneBlock =
    tuneRows || tune.reason
      ? `<div class="learning-tune${tuneActive ? " active" : ""}">
          <div class="learning-tune-head">${tuneBadge}${tune.reason ? `<span class="learning-tune-reason">${tune.reason}</span>` : ""}</div>
          ${tuneRows ? `<ul class="learning-tune-list">${tuneRows}</ul>` : ""}
        </div>`
      : "";
  box.classList.remove("hidden");
  box.innerHTML = `
    <div class="learning-title">Aprendizagem (${learning.resolved} resolvidas · ${learning.hit_rate_pct ?? "—"}% global)</div>
    ${marketRows ? `<div class="learning-markets">${marketRows}</div>` : ""}
    ${tuneBlock}
    ${sugRows ? `<ul class="learning-suggestions">${sugRows}</ul>` : ""}
    ${learning.note ? `<p class="learning-note">${learning.note}</p>` : ""}`;
}

function renderHistoryStats(perf) {
  els.historyStats.className = "stats-grid";
  const hit = perf.hit_rate_pct != null ? `${perf.hit_rate_pct}%` : "—";
  const pnlClass = perf.total_pnl > 0 ? "positive" : perf.total_pnl < 0 ? "negative" : "";
  const roi = perf.roi_pct != null ? `${perf.roi_pct > 0 ? "+" : ""}${perf.roi_pct}%` : "—";
  els.historyStats.innerHTML = `
    <div class="stat-card hero">
      <div class="stat-value gold">${hit}</div>
      <div class="stat-label">Taxa de acerto</div>
    </div>
    <div class="stat-card">
      <div class="stat-value positive">${perf.wins}</div>
      <div class="stat-label">Green ✓</div>
    </div>
    <div class="stat-card">
      <div class="stat-value negative">${perf.losses}</div>
      <div class="stat-label">Red ✗</div>
    </div>
    <div class="stat-card">
      <div class="stat-value ${pnlClass}">${perf.total_pnl > 0 ? "+" : ""}${perf.total_pnl.toFixed(2)}€</div>
      <div class="stat-label">Lucro total</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${roi}</div>
      <div class="stat-label">ROI</div>
    </div>`;
}

function outcomeBadge(outcome) {
  const map = {
    win: { cls: "win", label: "GREEN" },
    loss: { cls: "loss", label: "RED" },
    pending: { cls: "pending", label: "PENDENTE" },
    void: { cls: "void", label: "VOID" },
  };
  return map[outcome] || map.pending;
}

function renderHistoryFeed() {
  const filter = state.historyFilter;
  const tips = state.historyTips.filter((t) => {
    if (filter === "all") return true;
    return t.outcome === filter;
  });

  els.historyEmpty.classList.toggle("hidden", tips.length > 0);
  renderLastTipNote(els.historyLastTip, state.lastTip);
  if (!tips.length) {
    els.historyFeed.innerHTML = "";
    return;
  }

  els.historyFeed.innerHTML = tips.map((t) => {
    const b = outcomeBadge(t.outcome);
    const mode = t.mode === "live" ? "LIVE" : "PRÉ";
    const scoreInfo = t.final_score
      ? `Resultado <strong>${t.final_score}</strong>`
      : t.score_at_tip
        ? `Ao vivo <strong>${t.score_at_tip}</strong> (${t.minute}')`
        : "";
    const pnl = t.pnl != null && t.outcome !== "pending"
      ? `<div class="tip-pnl ${t.pnl >= 0 ? "positive" : "negative"}">${t.pnl >= 0 ? "+" : ""}${Number(t.pnl).toFixed(2)}€</div>`
      : "";
    return `
      <article class="tip-card outcome-${t.outcome}">
        <div class="tip-card-header">
          <div class="tip-match">${t.home} vs ${t.away}</div>
          <span class="tip-badge ${b.cls}">${b.label}</span>
        </div>
        <div class="meta">${t.league || ""} · ${mode} · ${formatKickoff(t.logged_at)}</div>
        <div class="tip-details" style="margin-top:0.4rem">
          <span><strong>${t.market}</strong> @ ${t.odd}</span>
          <span>EV ${t.ev_pct > 0 ? "+" : ""}${t.ev_pct}%</span>
          ${t.stake_level ? `<span>Stake ${t.stake_level}/10</span>` : ""}
          ${scoreInfo ? `<span>${scoreInfo}</span>` : ""}
        </div>
        ${pnl}
      </article>`;
  }).join("");
}

async function loadHistory() {
  if (state.fetching.history) return;
  state.fetching.history = true;
  setPanelRefreshing("history", true);
  if (!state.hasData.history) {
    els.historyStats.className = "stats-grid loading";
    els.historyStats.textContent = "A carregar histórico…";
  }
  try {
    const res = await fetch("/api/tips/history?limit=80&auto_resolve=true");
    if (!res.ok) throw new Error("Histórico indisponível");
    const data = await res.json();
    state.hasData.history = true;
    state.historyTips = data.tips || [];
    state.lastTip = data.last_tip || null;
    renderHistoryStats(data.performance || { wins: 0, losses: 0, total_pnl: 0, hit_rate_pct: null, roi_pct: null });
    renderHistoryLearning(data.learning || null);
    renderHistoryFeed();
  } catch {
    if (!state.hasData.history) {
      els.historyStats.className = "stats-grid loading";
      els.historyStats.textContent = "Não foi possível carregar o histórico.";
    }
  } finally {
    state.fetching.history = false;
    setPanelRefreshing("history", false);
  }
}

/* ── Data loading ── */
function buildLiveListUrl() {
  const params = new URLSearchParams();
  if (state.settings.league) params.set("league", state.settings.league);
  const q = params.toString();
  return `/api/live/list${q ? `?${q}` : ""}`;
}

function buildLiveUrl() {
  const params = new URLSearchParams({ min_score: "0.55" });
  if (state.settings.bankroll) params.set("bankroll", String(state.settings.bankroll));
  if (state.settings.league) params.set("league", state.settings.league);
  return `/api/live?${params}`;
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) arr[i] = raw.charCodeAt(i);
  return arr;
}

async function setupPushSubscription() {
  if (!state.settings.notify || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    return;
  }
  try {
    const reg = await navigator.serviceWorker.ready;
    const keyRes = await fetch("/api/push/vapid-public-key");
    const keyData = keyRes.ok ? await keyRes.json() : {};
    if (!keyData.public_key) return;

    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(keyData.public_key),
      });
    }
    const payload = sub.toJSON();
    await fetch("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    /* push opcional — notificações locais continuam */
  }
}

async function notifyUser(title, body) {
  if (!state.settings.notify || !("Notification" in window)) return;
  if (Notification.permission === "default") await Notification.requestPermission();
  if (Notification.permission === "granted") new Notification(title, { body, icon: "/icons/icon-192.jpg" });
}

function checkLiveAlerts(ranked) {
  for (const r of ranked || []) {
    const key = `${r.home}|${r.away}`;
    const prev = state.liveSnapshots[key];
    if (prev && prev.score !== r.score) {
      notifyUser(`Golo! ${r.home} ${r.score} ${r.away}`, `${r.minute}' — era ${prev.score}`);
    }
    if (
      r.should_bet &&
      (!prev || !prev.should_bet || prev.best_market !== r.best_market)
    ) {
      notifyUser(`Oportunidade: ${r.home} vs ${r.away}`, `${r.best_market} EV ${r.best_ev_pct > 0 ? "+" : ""}${r.best_ev_pct}%`);
    }
    state.liveSnapshots[key] = {
      score: r.score,
      should_bet: r.should_bet,
      best_market: r.best_market,
    };
  }
}

async function loadPrematch() {
  if (state.fetching.prematch) return;
  const keepVisible = state.hasData.prematch;
  state.fetching.prematch = true;
  setPanelRefreshing("prematch", true);
  if (!keepVisible) {
    els.statusPrematch.className = "card status-card loading";
    els.statusPrematch.textContent = "A analisar oportunidades…";
    if (els.prematchFixturesList) {
      els.prematchFixturesList.innerHTML = '<li class="meta">A carregar lista…</li>';
    }
  }

  let listData = null;
  try {
    const listRes = await fetch("/api/scan/list?hours=12");
    if (listRes.ok) {
      listData = await listRes.json();
      renderPrematchFixtures(listData.fixtures, listData.hours_window);
    }
  } catch {
    /* lista rápida falhou */
  }

  try {
    const params = new URLSearchParams({ hours: "12" });
    if (state.settings.bankroll) params.set("bankroll", String(state.settings.bankroll));
    const res = await fetch(`/api/scan?${params}`);
    if (!res.ok) throw new Error("Servidor não respondeu");
    const data = await res.json();
    state.hasData.prematch = true;
    state.prematch.ranked = data.ranked || [];
    state.prematch.fixtures = data.fixtures?.length ? data.fixtures : listData?.fixtures || [];
    if (state.prematch.selectedKey) {
      const still = findPrematchRanked(state.prematch.selectedKey);
      if (!still) state.prematch.selectedKey = null;
    }
    renderPrematchStatus(data);
    renderPrematchFixtures(state.prematch.fixtures, data.hours_window || listData?.hours_window);
    renderBestPrematch(data.best);
    renderRankingPrematch(state.prematch.ranked);
    if (state.match.key && state.match.mode === "prematch") renderMatchPage();
    updateDesktopStatus(`Pré-jogo · ${formatKickoff(data.scanned_at)}`);
  } catch (err) {
    if (listData?.fixtures?.length) {
      renderPrematchStatus(
        {
          total_found: listData.total,
          total_analyzed: 0,
          hours_window: listData.hours_window,
          notice: listData.notice,
          scanned_at: listData.scanned_at,
          ranked: [],
        },
        "Análise lenta — lista de jogos actualizada"
      );
      renderBestPrematch(null);
      renderRankingPrematch([]);
    } else if (!keepVisible) {
      showError(els.statusPrematch, "Servidor desligado. Verifica se o robot está a correr.");
      renderPrematchFixtures([], 12);
    } else {
      renderPrematchStatus({ total_found: "—", total_analyzed: "—", scanned_at: new Date().toISOString(), ranked: [] }, "Falha — última análise mantida");
    }
  } finally {
    state.fetching.prematch = false;
    setPanelRefreshing("prematch", false);
  }
}

async function loadLive() {
  if (state.fetching.live) return;
  const keepVisible = state.hasData.live;
  state.fetching.live = true;
  setPanelRefreshing("live", true);
  if (!keepVisible) {
    els.statusLive.className = "card status-card loading";
    els.statusLive.textContent = "A analisar oportunidades…";
    renderLiveFixtures([]);
    els.liveFixturesList.innerHTML = '<li class="meta">A carregar lista…</li>';
  }

  let listData = null;
  try {
    const listRes = await fetch(buildLiveListUrl());
    if (listRes.ok) {
      listData = await listRes.json();
      state.hasData.live = true;
      els.liveCount.textContent = `${listData.total} jogo${listData.total !== 1 ? "s" : ""}`;
      state.live.fixtures = listData.fixtures || [];
      renderLiveFixtures(state.live.fixtures);
      updateLiveSourceBadge(listData.live_source, listData.live_source_label);
      renderLiveStatus({
        total_live: listData.total,
        total_analyzed: "…",
        scanned_at: listData.scanned_at,
        warning: listData.warning,
        source: listData.source,
      });
    }
  } catch {
    /* lista rápida falhou — tenta análise completa */
  }

  try {
    const res = await fetch(buildLiveUrl());
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || "Live indisponível");
    const data = await res.json();
    state.hasData.live = true;
    state.lastTip = data.last_tip || state.lastTip;
    els.liveCount.textContent = `${data.total_live} jogo${data.total_live !== 1 ? "s" : ""}`;
    updateLiveSourceBadge(data.live_source, data.live_source_label);
    renderLiveStatus(data);
    setLiveScanData({
      ...data,
      fixtures: data.fixtures?.length ? data.fixtures : listData?.fixtures,
    });
    checkLiveAlerts(data.ranked);
    renderBestLive(data.best);
    renderRankingLive(data.ranked, data.last_tip);

  } catch (err) {
    if (listData?.fixtures?.length) {
      renderLiveStatus(
        {
          total_live: listData.total,
          total_analyzed: 0,
          scanned_at: listData.scanned_at,
          warning: listData.warning,
          source: listData.source,
        },
        "Análise lenta — lista de jogos actualizada"
      );
      renderBestLive(null);
      renderRankingLive([]);

    } else if (!keepVisible) {
      showError(els.statusLive, err.message || "Erro live");
      renderLiveFixtures([]);
    } else {
      renderLiveStatus({ total_live: 0, total_analyzed: "—", scanned_at: new Date().toISOString() }, "Falha — última análise mantida");
    }
  } finally {
    state.fetching.live = false;
    setPanelRefreshing("live", false);
  }
}

function syncDesktopNav(tab) {
  if (!isDesktopApp) return;
  document.querySelectorAll(".desktop-nav-btn[data-tab]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
}

function updateDesktopStatus(text) {
  if (!isDesktopApp || !els.desktopStatusSync) return;
  els.desktopStatusSync.textContent = text;
}

function initDesktopMode() {
  if (!isDesktopApp) return;
  localStorage.setItem("sgm_desktop", "1");
  document.documentElement.classList.add("desktop-app");
  els.desktopSidebar?.classList.remove("hidden");
  els.desktopStatus?.classList.remove("hidden");
  document.querySelectorAll(".desktop-nav-btn[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
  document.getElementById("desktop-settings-btn")?.addEventListener("click", openDrawer);
  document.getElementById("desktop-refresh-btn")?.addEventListener("click", refreshCurrent);
  syncDesktopNav(state.tab);
}

function switchTab(tab, { skipMatchClose = false } = {}) {
  if (!skipMatchClose && state.match.key) {
    state.match.key = null;
    state.match.mode = null;
    state.match.stats = null;
    state.match.statsFixtureId = null;
    els.panelMatch?.classList.add("hidden");
    els.panelMatch?.classList.remove("active");
    els.appShell?.classList.remove("match-open");
  }
  state.tab = tab;
  document.querySelectorAll(".tab[data-tab]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.getElementById("panel-prematch").classList.toggle("active", tab === "prematch");
  document.getElementById("panel-live").classList.toggle("active", tab === "live");
  document.getElementById("panel-history").classList.toggle("active", tab === "history");
  scheduleAutoRefresh();
  syncDesktopNav(tab);
  if (tab === "history") loadHistory();
}

function refreshCurrent() {
  hideRefreshBallBriefly();
  if (state.match.key) {
    if (state.match.mode === "live") loadLive();
    else loadPrematch();
    return;
  }
  if (state.tab === "live") loadLive();
  else if (state.tab === "history") loadHistory();
  else loadPrematch();
}

function clearTimers() {
  clearInterval(state.timers.live);
  clearInterval(state.timers.prematch);
  state.timers.live = state.timers.prematch = null;
}

function scheduleAutoRefresh() {
  clearTimers();
  if (!state.settings.autoRefresh) return;
  state.timers.live = setInterval(() => {
    if (state.tab === "live" || (state.match.key && state.match.mode === "live")) loadLive();
  }, LIVE_INTERVAL);
  state.timers.prematch = setInterval(() => {
    if (state.tab === "prematch" || (state.match.key && state.match.mode === "prematch")) loadPrematch();
  }, PREMATCH_INTERVAL);
}

function openDrawer() {
  applySettingsToForm();
  els.drawer.classList.remove("hidden");
}
function closeDrawer() { els.drawer.classList.add("hidden"); }

document.querySelectorAll(".tab[data-tab]").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});
els.matchBack?.addEventListener("click", closeMatchPage);
els.matchStatsRefresh?.addEventListener("click", () => {
  const ctx = getMatchContext(state.match.mode, state.match.key);
  if (ctx?.fixtureId) loadMatchStats(ctx.fixtureId, { force: true, withEvents: true });
});
document.querySelectorAll("#history-filters .chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll("#history-filters .chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    state.historyFilter = chip.dataset.filter;
    renderHistoryFeed();
  });
});

function onLivePick(event) {
  const row = event.target.closest("[data-live-key]");
  if (!row) return;
  selectLiveMatch(row.dataset.liveKey);
}

function onPrematchPick(event) {
  const row = event.target.closest("[data-prematch-key]");
  if (!row) return;
  selectPrematchMatch(row.dataset.prematchKey);
}

els.prematchFixturesList?.addEventListener("click", onPrematchPick);
els.tablePrematch?.addEventListener("click", onPrematchPick);
els.tablePrematch?.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const row = e.target.closest("[data-prematch-key]");
  if (!row) return;
  e.preventDefault();
  selectPrematchMatch(row.dataset.prematchKey);
});
els.prematchFixturesList?.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const row = e.target.closest("[data-prematch-key]");
  if (!row) return;
  e.preventDefault();
  selectPrematchMatch(row.dataset.prematchKey);
});

els.liveFixturesList?.addEventListener("click", onLivePick);
els.tableLive?.addEventListener("click", onLivePick);
els.tableLive?.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const row = e.target.closest("[data-live-key]");
  if (!row) return;
  e.preventDefault();
  selectLiveMatch(row.dataset.liveKey);
});
els.liveFixturesList?.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const row = e.target.closest("[data-live-key]");
  if (!row) return;
  e.preventDefault();
  selectLiveMatch(row.dataset.liveKey);
});

els.refreshBtn?.addEventListener("click", refreshCurrent);
els.settingsBtn?.addEventListener("click", openDrawer);
els.drawerBackdrop?.addEventListener("click", closeDrawer);
els.saveSettings?.addEventListener("click", saveSettingsToStorage);

if ("serviceWorker" in navigator && !isDesktopApp) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

initDesktopMode();
els.refreshBtn?.classList.add("idle");

applyBranding().then(() => {
  applySettingsToForm();
  scheduleAutoRefresh();
  if (state.settings.notify) setupPushSubscription();
  loadPrematch();
  loadLive();
});