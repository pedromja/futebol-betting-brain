const CFG_KEY = "sgm_settings";
const LIVE_INTERVAL = 45_000;
const PREMATCH_INTERVAL = 300_000;

const state = {
  tab: "prematch",
  settings: loadSettings(),
  liveSnapshots: {},
  prematchSnapshots: {},
  tipOutcomeSnapshots: {},
  historyAlertsReady: false,
  timers: { live: null, prematch: null, historyPoll: null },
  fetching: { live: false, prematch: false, history: false },
  hasData: { live: false, prematch: false, history: false },
  historyTips: [],
  historyFilter: "all",
  historyModeFilter: "all",
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
  bots: {
    list: [],
    catalog: null,
    filter: "all",
    wizardStep: 1,
    editingId: null,
    draft: null,
    lastHits: [],
    snapshots: {},
    performance: {},
    perfGlobal: null,
    historyId: null,
    historyData: null,
  },
  outcomeCorrect: null,
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
  historyVerifyQueue: document.getElementById("history-verify-queue"),
  historyLastTip: document.getElementById("history-last-tip"),
  historyFeed: document.getElementById("history-feed"),
  historyEmpty: document.getElementById("history-empty"),
  historyFilters: document.getElementById("history-filters"),
  historyModeScope: document.getElementById("history-mode-scope"),
  liveLastTip: document.getElementById("live-last-tip"),
  panelMatch: document.getElementById("panel-match"),
  matchPageBody: document.getElementById("match-page-body"),
  matchBack: document.getElementById("match-back"),
  matchStatsRefresh: document.getElementById("match-stats-refresh"),
  matchPageLabel: document.getElementById("match-page-label"),
  appShell: document.querySelector(".app-shell"),
  mainContent: document.getElementById("main-content"),
  pwaWatermark: document.getElementById("pwa-watermark"),
  desktopSidebar: document.getElementById("desktop-sidebar"),
  desktopStatus: document.getElementById("desktop-status"),
  desktopStatusSync: document.getElementById("desktop-status-sync"),
  desktopLiveBadge: document.getElementById("desktop-live-badge"),
  screenTitle: document.getElementById("screen-title"),
  pwaLiveChip: document.getElementById("pwa-live-chip"),
  pwaLiveCount: document.getElementById("pwa-live-count"),
  historyTabBadge: document.getElementById("history-tab-badge"),
  panelBots: document.getElementById("panel-bots"),
  botsList: document.getElementById("bots-list"),
  botsCountLabel: document.getElementById("bots-count-label"),
  botsNewBtn: document.getElementById("bots-new-btn"),
  botsFilters: document.getElementById("bots-filters"),
  botsTemplates: document.getElementById("bots-templates"),
  botsHits: document.getElementById("bots-hits"),
  botsPerfSummary: document.getElementById("bots-perf-summary"),
  botsHistoryPanel: document.getElementById("bots-history-panel"),
  outcomeCorrectModal: document.getElementById("outcome-correct-modal"),
  outcomeCorrectBackdrop: document.getElementById("outcome-correct-backdrop"),
  outcomeCorrectSub: document.getElementById("outcome-correct-sub"),
  outcomeCorrectOutcome: document.getElementById("outcome-correct-outcome"),
  outcomeCorrectScore: document.getElementById("outcome-correct-score"),
  outcomeCorrectNote: document.getElementById("outcome-correct-note"),
  outcomeCorrectCancel: document.getElementById("outcome-correct-cancel"),
  outcomeCorrectSave: document.getElementById("outcome-correct-save"),
  botWizard: document.getElementById("bot-wizard"),
  botWizardBackdrop: document.getElementById("bot-wizard-backdrop"),
  botWizardBody: document.getElementById("bot-wizard-body"),
  botWizardTitle: document.getElementById("bot-wizard-title"),
  botWizardSub: document.getElementById("bot-wizard-sub"),
  botWizardSteps: document.getElementById("bot-wizard-steps"),
  botWizardCancel: document.getElementById("bot-wizard-cancel"),
  botWizardPrev: document.getElementById("bot-wizard-prev"),
  botWizardNext: document.getElementById("bot-wizard-next"),
  botWizardSave: document.getElementById("bot-wizard-save"),
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
  if (state.settings.notify) {
    setupPushSubscription();
    loadHistory({ quiet: true });
  }
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
    const brandName = b.app_name_full || b.app_name || "SindGreenMentor";
    const shortName = b.short_name || "SindGrEeN";
    const appleTitle = document.querySelector('meta[name="apple-mobile-web-app-title"]');
    if (appleTitle) appleTitle.content = shortName;
    if (!isDesktopApp && els.screenTitle) {
      els.screenTitle.textContent = brandName;
    }
    if (isDesktopApp) {
      const deskTitle = document.getElementById("desktop-brand-title");
      if (deskTitle) deskTitle.textContent = brandName;
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
  const travel = env.travel || {};
  const travelLine =
    travel.distance_km > 0
      ? `<span class="env-compact-travel">${travel.distance_km} km · ${travel.hours}h viagem</span>`
      : "";
  const venue = env.stadium || env.venue || env.city || "";
  const venueNote = env.venue_correction
    ? `<p class="env-venue-correction">Jogo em <strong>${env.stadium || env.venue}</strong> (casa: ${env.venue_correction.usual_home})</p>`
    : "";
  const impactHint =
    impact?.home || impact?.away
      ? `<span class="env-compact-impact">Modelo ajustado ao contexto</span>`
      : "";
  return `
    <div class="env-section env-section-compact">
      <div class="env-section-title">Clima</div>
      ${venueNote}
      ${venue ? `<div class="meta env-venue">${venue}</div>` : ""}
      <div class="meta env-compact">${formatEnvCompact(env)}</div>
      ${travelLine}
      ${impactHint}
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
  if (!mot) return "";
  return `
    <div class="match-section mot-section mot-section-compact">
      <div class="match-section-head">
        <div class="match-section-title">Motivação</div>
        <span class="tm-align-badge ${tmAlignmentClass(mot.alignment)}">${motAlignmentLabel(mot.alignment)}</span>
      </div>
      ${mot.summary ? `<p class="meta tm-summary">${mot.summary}</p>` : ""}
      <div class="tm-metrics">
        <span>Score ${mot.motivation_score}/6</span>
        <span>Stake ×${mot.stake_multiplier ?? 1}</span>
        ${mot.veto ? `<span class="tm-gap">Trap</span>` : ""}
      </div>
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
  if (state.match.transfermarktLoading || !tm?.data_available) return "";
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
  if (!markets?.length) return "";
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
    ? isLive
      ? `<div class="match-section"><p class="meta">A carregar estatísticas…</p></div>`
      : ""
    : isLive
      ? renderStatsSection(state.match.stats, home, away)
      : "";

  const heroBlock = `
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
    </div>`;

  const envBlock = env ? renderEnvironmentBlock(env, ranked?.environment_impact) : "";
  const tmBlock = !isLive ? renderTransfermarktSection(state.match.transfermarkt) : "";
  const motBlock = !isLive ? renderMotivationSection(ctx.ranked?.motivation) : "";
  const extBlock = isLive ? renderExtendedMarkets(state.match.stats?.extended_markets) : "";
  const betBlock = renderBettingSection(ctx);

  els.matchPageBody.classList.add("match-page-body-split");
  els.matchPageBody.innerHTML = `
    ${heroBlock}
    <div class="match-page-main">
      ${envBlock}
      ${statsBlock}
      ${extBlock}
    </div>
    <aside class="match-page-aside">
      ${betBlock}
      ${motBlock}
      ${tmBlock}
    </aside>`;
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
    const league = ranked?.league || ranked?.fixture?.league;
    const stage = ranked?.stage || ranked?.fixture?.stage;
    if (league) params.set("league", league);
    if (stage) params.set("stage", stage);
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
  updateWatermark();
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
  updateWatermark(tab);
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
  if (!best) {
    els.bestPrematch.classList.add("hidden");
    updateWatermark("prematch");
    return;
  }
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
  updateWatermark("prematch");
}

function findPrematchRanked(key) {
  return (state.prematch.ranked || []).find((r) => liveMatchKey(r.home, r.away) === key) || null;
}

function selectPrematchMatch(key) {
  openMatchPage("prematch", key);
}

function renderRankingPrematch(ranked) {
  if (!ranked?.length) {
    els.rankingPrematch.classList.add("hidden");
    updateWatermark("prematch");
    return;
  }
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
  updateWatermark("prematch");
}

function renderPrematchFixtures(fixtures, hoursWindow) {
  if (!els.prematchFixturesList) return;
  const label = hoursWindow ? ` (${hoursWindow}h)` : "";
  if (!fixtures?.length) {
    els.prematchFixturesList.innerHTML =
      `<li class="meta">Nenhum jogo nas próximas horas${label}.</li>`;
    updateWatermark("prematch");
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
  updateWatermark("prematch");
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
  updateWatermark("prematch");
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
  if (!best) {
    els.bestLive.classList.add("hidden");
    updateWatermark("live");
    return;
  }
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
  updateWatermark("live");
}

function renderRankingLive(ranked, lastTip = null) {
  if (!ranked?.length) {
    els.rankingLive.classList.add("hidden");
    renderLastTipNote(els.liveLastTip, null, { liveOnly: true });
    updateWatermark("live");
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
  updateWatermark("live");
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
  updateWatermark("live");
}

function renderLiveFixtures(fixtures) {
  if (!els.liveFixturesList) return;
  els.liveFixtures?.classList.remove("hidden");
  if (!fixtures?.length) {
    els.liveFixturesList.innerHTML = '<li class="meta">Nenhum jogo ao vivo neste momento.</li>';
    updateWatermark("live");
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
  updateWatermark("live");
}

/* ── Histórico ── */
function renderHistoryLearning(learning) {
  const box = els.historyLearning;
  if (!box) return;
  if (!learning?.resolved) {
    box.classList.add("hidden");
    box.innerHTML = "";
    updateWatermark("history");
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
  const tuneAdjustments = (tune.adjustments || []).slice(0, 6);
  const tuneRows = tuneAdjustments.map((a) => `<li>${a}</li>`).join("");
  const tuneBadge = tuneActive
    ? `<span class="learning-tune-badge">Auto-tune ON</span>`
    : `<span class="learning-tune-badge off">Auto-tune OFF</span>`;
  const recent = learning.recent || {};
  const recentTxt =
    recent.hit_rate_pct != null ? ` · recente ${recent.hit_rate_pct}%` : "";
  const evGap = learning.ev_gap_pct;
  const evTxt = evGap != null && evGap > 2 ? ` · EV reds +${evGap}pp` : "";
  const tuneMetrics = (tune.metrics || {});
  const metricsLine = [
    tuneMetrics.recent_hit_rate_pct != null ? `Forma ${tuneMetrics.recent_hit_rate_pct}%` : "",
    tuneMetrics.ev_gap_pct != null && tuneMetrics.ev_gap_pct > 2
      ? `EV +${tuneMetrics.ev_gap_pct}pp nos reds`
      : "",
  ]
    .filter(Boolean)
    .join(" · ");
  const tuneBlock =
    tuneRows || tune.reason || metricsLine
      ? `<div class="learning-tune${tuneActive ? " active" : ""}">
          <div class="learning-tune-head">${tuneBadge}${tune.reason ? `<span class="learning-tune-reason">${tune.reason}</span>` : ""}</div>
          ${metricsLine ? `<div class="learning-tune-metrics">${metricsLine}</div>` : ""}
          ${tuneRows ? `<ul class="learning-tune-list">${tuneRows}</ul>` : ""}
        </div>`
      : "";
  box.classList.remove("hidden");
  box.innerHTML = `
    <div class="learning-title">Aprendizagem (${learning.resolved} resolvidas · ${learning.hit_rate_pct ?? "—"}% global${recentTxt}${evTxt})</div>
    ${marketRows ? `<div class="learning-markets">${marketRows}</div>` : ""}
    ${tuneBlock}
    ${sugRows ? `<ul class="learning-suggestions">${sugRows}</ul>` : ""}
    ${learning.note ? `<p class="learning-note">${learning.note}</p>` : ""}`;
  updateWatermark("history");
}

function renderHistoryModeColumn(mode, perf, { title, iconClass, theme }) {
  const p = perf || {};
  const hit = p.hit_rate_pct != null ? `${p.hit_rate_pct}%` : "—";
  const pnl = Number(p.total_pnl) || 0;
  const pnlClass = pnl > 0 ? "positive" : pnl < 0 ? "negative" : "";
  const roi = p.roi_pct != null ? `${p.roi_pct > 0 ? "+" : ""}${p.roi_pct}%` : "—";
  const pending = p.pending || 0;
  return `
    <section class="history-mode-col ${theme}" aria-label="Estatísticas ${title}">
      <div class="history-mode-head">
        <span class="history-mode-icon ${iconClass}" aria-hidden="true"></span>
        <span class="history-mode-title">${title}</span>
        ${pending ? `<span class="history-mode-pending">${pending} pend.</span>` : ""}
      </div>
      <div class="history-mode-hit">${hit}</div>
      <div class="history-mode-hit-label">Taxa acerto</div>
      <div class="history-mode-mini-grid">
        <div class="history-mini-stat">
          <span class="history-mini-val positive">${p.wins || 0}</span>
          <span class="history-mini-lbl">Green</span>
        </div>
        <div class="history-mini-stat">
          <span class="history-mini-val negative">${p.losses || 0}</span>
          <span class="history-mini-lbl">Red</span>
        </div>
        <div class="history-mini-stat">
          <span class="history-mini-val ${pnlClass}">${pnl > 0 ? "+" : ""}${pnl.toFixed(2)}€</span>
          <span class="history-mini-lbl">Lucro</span>
        </div>
        <div class="history-mini-stat">
          <span class="history-mini-val">${roi}</span>
          <span class="history-mini-lbl">ROI</span>
        </div>
      </div>
    </section>`;
}

function renderHistoryStats(perf, byMode) {
  const split = byMode || {};
  const prematch = split.prematch || perf;
  const live = split.live || {
    wins: 0,
    losses: 0,
    pending: 0,
    hit_rate_pct: null,
    total_pnl: 0,
    roi_pct: null,
  };
  els.historyStats.className = "history-stats-split";
  els.historyStats.innerHTML = `
    <div class="history-stats-columns">
      ${renderHistoryModeColumn("prematch", prematch, {
        title: "Pré-jogo",
        iconClass: "mode-icon-prematch",
        theme: "theme-prematch",
      })}
      ${renderHistoryModeColumn("live", live, {
        title: "Ao vivo",
        iconClass: "mode-icon-live",
        theme: "theme-live",
      })}
    </div>`;
  updateWatermark("history");
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

function renderPostMatchReview(review) {
  if (!review) return "";
  const status = review.status || "";
  const note = review.context_note || "";
  const sources = (review.sources || []).join(", ");
  const enriched = status === "enriched";
  const needs = review.needs_verification || status === "initial_only";
  const ft = review.ft_stats || {};
  const xg = ft.xg || {};
  const cards = ft.cards || {};
  let statsLine = "";
  if (enriched && (xg.total != null || cards.yellow != null)) {
    const bits = [];
    if (xg.total != null) bits.push(`xG ${xg.total}${xg.source ? ` (${xg.source})` : ""}`);
    if (cards.yellow != null) bits.push(`${cards.yellow} amarelos`);
    statsLine = bits.length ? `<span class="post-review-stats">${bits.join(" · ")}</span>` : "";
  }
  const manual = status === "manual";
  const cls = manual ? "manual" : enriched ? "enriched" : needs ? "verify" : "initial";
  const label = manual
    ? "Corrigido manualmente"
    : enriched
      ? "Pós-jogo confirmado"
      : needs
        ? "Verificar manualmente"
        : "Avaliação inicial";
  const promptBtn = needs && review.verify_prompt
    ? `<button type="button" class="chip post-review-copy" data-copy-prompt="${encodeURIComponent(review.verify_prompt)}">Copiar prompt</button>`
    : "";
  return `<div class="post-review post-review-${cls}">
    <div class="post-review-head">
      <span class="post-review-label">${label}</span>
      ${sources ? `<span class="meta post-review-src">${sources}</span>` : ""}
      ${promptBtn}
    </div>
    ${note ? `<p class="post-review-note">${note}</p>` : ""}
    ${statsLine}
  </div>`;
}

function renderOutcomeCorrectBtn(entry, kind) {
  const id = entry.id || tipKey(entry);
  if (!id) return "";
  return `<button type="button" class="tip-correct-btn" data-correct-kind="${kind}" data-correct-id="${encodeURIComponent(id)}" title="Corrigir GREEN/RED">✎</button>`;
}

function openOutcomeCorrectModal(entry, kind) {
  state.outcomeCorrect = {
    kind,
    entryId: entry.id || tipKey(entry),
    entry,
  };
  if (els.outcomeCorrectSub) {
    const title = kind === "bot"
      ? `${entry.bot_name || "Bot"} — ${entry.home} vs ${entry.away}`
      : `${entry.home} vs ${entry.away}`;
    els.outcomeCorrectSub.textContent = `${title} · ${entry.market} @ ${entry.odd}`;
  }
  if (els.outcomeCorrectOutcome) {
    els.outcomeCorrectOutcome.value = entry.outcome || "pending";
  }
  if (els.outcomeCorrectScore) {
    els.outcomeCorrectScore.value = entry.final_score || "";
  }
  if (els.outcomeCorrectNote) {
    els.outcomeCorrectNote.value = entry.manual_correction?.note || "";
  }
  els.outcomeCorrectModal?.classList.remove("hidden");
  els.outcomeCorrectModal?.setAttribute("aria-hidden", "false");
}

function closeOutcomeCorrectModal() {
  state.outcomeCorrect = null;
  els.outcomeCorrectModal?.classList.add("hidden");
  els.outcomeCorrectModal?.setAttribute("aria-hidden", "true");
}

async function saveOutcomeCorrection() {
  const draft = state.outcomeCorrect;
  if (!draft?.entryId) return;
  const outcome = els.outcomeCorrectOutcome?.value || "pending";
  const finalScore = els.outcomeCorrectScore?.value?.trim() || null;
  const note = els.outcomeCorrectNote?.value?.trim() || null;
  try {
    const res = await fetch("/api/outcome/correct", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: draft.kind,
        entry_id: draft.entryId,
        outcome,
        final_score: finalScore,
        note,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.error || "Erro ao corrigir resultado");
      return;
    }
    closeOutcomeCorrectModal();
    if (draft.kind === "bot") {
      await loadBots();
      if (state.bots.historyId) await loadBotHistory(state.bots.historyId);
    }
    await loadHistory();
  } catch {
    alert("Falha de rede ao guardar correcção.");
  }
}

function renderVerifyQueue(items) {
  const el = els.historyVerifyQueue;
  if (!el) return;
  if (!items?.length) {
    el.classList.add("hidden");
    el.innerHTML = "";
    return;
  }
  el.classList.remove("hidden");
  const rows = items.slice(0, 5).map((item) => {
    const title = item.kind === "bot"
      ? `${item.bot_name || "Bot"} — ${item.home} vs ${item.away}`
      : `${item.home} vs ${item.away}`;
    return `<li class="verify-queue-item">
      <div class="verify-queue-main">
        <strong>${title}</strong>
        <span class="meta">${item.market} · ${String(item.outcome || "").toUpperCase()} · FT ${item.final_score || "?"}</span>
      </div>
      <button type="button" class="chip post-review-copy" data-copy-prompt="${encodeURIComponent(item.prompt || "")}">Copiar prompt</button>
    </li>`;
  }).join("");
  el.innerHTML = `
    <p class="section-title">Verificação manual (${items.length})</p>
    <p class="meta">Sem stats FT automáticas — confirma em SofaScore/Flashscore.</p>
    <ul class="verify-queue-list">${rows}</ul>`;
}

function isLiveTip(tip) {
  return String(tip?.mode || "").toLowerCase() === "live";
}

function renderTipModeChip(tip, { prominent = false } = {}) {
  const live = isLiveTip(tip);
  const cls = prominent ? "tip-mode-chip prominent" : "tip-mode-chip";
  if (live) {
    return `<span class="${cls} tip-mode-live" title="Aposta registada ao vivo">
      <span class="tip-mode-dot" aria-hidden="true"></span>AO VIVO</span>`;
  }
  return `<span class="${cls} tip-mode-prematch" title="Aposta registada pré-jogo">
    <span class="tip-mode-icon" aria-hidden="true">◷</span>PRÉ-JOGO</span>`;
}

function renderPendingLiveStrip(tip) {
  if (!isLiveTip(tip) || tip.outcome !== "pending") return "";
  if (!tip.score_at_tip && tip.minute == null) return "";
  const minute = tip.minute != null
    ? (tip.injury_time ? `${tip.minute}+${tip.injury_time}'` : `${tip.minute}'`)
    : "";
  return `<div class="tip-pending-live-strip">
    <span class="tip-pending-live-score">${tip.score_at_tip || "—"}</span>
    ${minute ? `<span class="tip-pending-live-minute">${minute}</span>` : ""}
    <span class="tip-pending-live-label">em jogo</span>
  </div>`;
}

function historyFilterCounts(tips) {
  const buckets = {
    all: { total: 0, prematch: 0, live: 0 },
    win: { total: 0, prematch: 0, live: 0 },
    loss: { total: 0, prematch: 0, live: 0 },
    pending: { total: 0, prematch: 0, live: 0 },
  };
  for (const tip of tips) {
    const outcome = String(tip.outcome || "pending").toLowerCase();
    const key = outcome === "win" || outcome === "loss" || outcome === "pending" ? outcome : "pending";
    const live = isLiveTip(tip);
    buckets.all.total += 1;
    if (live) buckets.all.live += 1;
    else buckets.all.prematch += 1;
    buckets[key].total += 1;
    if (live) buckets[key].live += 1;
    else buckets[key].prematch += 1;
  }
  return buckets;
}

function renderFilterModeSplit(prematch, live) {
  if (!prematch && !live) return "";
  return `<span class="filter-chip-modes" aria-hidden="true">
    ${prematch ? `<span class="filter-mode-pre">◷${prematch}</span>` : ""}
    ${live ? `<span class="filter-mode-live">●${live}</span>` : ""}
  </span>`;
}

function renderHistoryFilters() {
  const bar = els.historyFilters;
  if (!bar) return;
  const counts = historyFilterCounts(state.historyTips);
  const chips = [
    { id: "all", label: "Todas" },
    { id: "win", label: "Green ✓" },
    { id: "loss", label: "Red ✗" },
    { id: "pending", label: "Pendentes" },
  ];
  bar.innerHTML = chips
    .map(({ id, label }) => {
      const c = counts[id];
      const active = state.historyFilter === id ? " active" : "";
      return `<button type="button" class="chip filter-chip${active}" data-filter="${id}">
        <span class="filter-chip-main">
          <span class="filter-chip-label">${label}</span>
          <span class="filter-chip-count">${c.total}</span>
        </span>
        ${renderFilterModeSplit(c.prematch, c.live)}
      </button>`;
    })
    .join("");

  const scope = els.historyModeScope;
  if (scope) {
    scope.querySelectorAll(".chip-mode-scope").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.modeScope === state.historyModeFilter);
    });
  }
}

function tipMatchesHistoryFilters(tip) {
  if (state.historyModeFilter !== "all") {
    const live = isLiveTip(tip);
    if (state.historyModeFilter === "live" && !live) return false;
    if (state.historyModeFilter === "prematch" && live) return false;
  }
  if (state.historyFilter === "all") return true;
  return String(tip.outcome || "pending").toLowerCase() === state.historyFilter;
}

function renderHistoryFeed() {
  const tips = state.historyTips.filter(tipMatchesHistoryFilters);

  const hasAnyTips = state.historyTips.length > 0;
  els.historyEmpty.classList.toggle("hidden", tips.length > 0);
  if (!tips.length && hasAnyTips) {
    els.historyEmpty.textContent = "Nenhuma tip com estes filtros.";
    els.historyEmpty.classList.remove("hidden");
  } else if (!hasAnyTips) {
    els.historyEmpty.textContent =
      "Ainda sem tips registadas. O robot grava automaticamente cada dica recomendada.";
  }
  renderLastTipNote(els.historyLastTip, state.lastTip);
  if (!tips.length) {
    els.historyFeed.innerHTML = "";
    updateWatermark("history");
    return;
  }

  els.historyFeed.innerHTML = tips.map((t) => {
    const b = outcomeBadge(t.outcome);
    const pending = t.outcome === "pending";
    const live = isLiveTip(t);
    const modeClass = live ? "mode-live" : "mode-prematch";
    const scoreInfo = t.final_score
      ? `Resultado <strong>${t.final_score}</strong>`
      : !pending && t.score_at_tip
        ? `Ao vivo <strong>${t.score_at_tip}</strong> (${t.minute}')`
        : "";
    const pnl = t.pnl != null && !pending
      ? `<div class="tip-pnl ${t.pnl >= 0 ? "positive" : "negative"}">${t.pnl >= 0 ? "+" : ""}${Number(t.pnl).toFixed(2)}€</div>`
      : "";
    const badges = pending
      ? `<div class="tip-card-badges">${renderTipModeChip(t, { prominent: true })}<span class="tip-badge ${b.cls}">${b.label}</span>${renderOutcomeCorrectBtn(t, "tip")}</div>`
      : `<div class="tip-card-badges">${renderTipModeChip(t)}<span class="tip-badge ${b.cls}">${b.label}</span>${renderOutcomeCorrectBtn(t, "tip")}</div>`;
    return `
      <article class="tip-card outcome-${t.outcome} ${modeClass}${pending ? " tip-pending-mode" : ""}" data-tip-id="${encodeURIComponent(t.id || tipKey(t))}">
        <div class="tip-card-header">
          <div class="tip-match">${t.home} vs ${t.away}</div>
          ${badges}
        </div>
        ${renderPendingLiveStrip(t)}
        <div class="meta">${t.league || ""} · ${formatKickoff(t.logged_at)}</div>
        <div class="tip-details" style="margin-top:0.4rem">
          <span><strong>${t.market}</strong> @ ${t.odd}</span>
          <span>EV ${t.ev_pct > 0 ? "+" : ""}${t.ev_pct}%</span>
          ${t.stake_level ? `<span>Stake ${t.stake_level}/10</span>` : ""}
          ${scoreInfo ? `<span>${scoreInfo}</span>` : ""}
        </div>
        ${pnl}
        ${renderPostMatchReview(t.review)}
      </article>`;
  }).join("");
  updateWatermark("history");
}

function tipKey(tip) {
  return tip.id || `${tip.home}|${tip.away}|${tip.market}|${tip.logged_at}`;
}

function updatePendingBadges(tips = state.historyTips) {
  const pending = (tips || []).filter(
    (t) => String(t.outcome || "pending").toLowerCase() === "pending"
  ).length;
  if (els.historyTabBadge) {
    els.historyTabBadge.textContent = String(pending);
    els.historyTabBadge.classList.toggle("hidden", pending === 0);
  }
}

async function loadHistory({ quiet = false } = {}) {
  if (state.fetching.history) return;
  state.fetching.history = true;
  if (!quiet) setPanelRefreshing("history", true);
  if (!quiet && !state.hasData.history) {
    els.historyStats.className = "history-stats-split loading";
    els.historyStats.textContent = "A carregar histórico…";
    updateWatermark("history");
  }
  try {
    const res = await fetch("/api/tips/history?limit=80&auto_resolve=true");
    if (!res.ok) throw new Error("Histórico indisponível");
    const data = await res.json();
    state.hasData.history = true;
    state.historyTips = data.tips || [];
    state.lastTip = data.last_tip || null;
    checkPendingTipAlerts(state.historyTips);
    updatePendingBadges(state.historyTips);
    if (quiet) return;
    renderHistoryStats(
      data.performance || { wins: 0, losses: 0, total_pnl: 0, hit_rate_pct: null, roi_pct: null },
      data.performance_by_mode,
    );
    renderHistoryLearning(data.learning || null);
    renderHistoryFilters();
    renderHistoryFeed();
    try {
      const vq = await fetch("/api/review/verify-queue?limit=10");
      if (vq.ok) {
        const vdata = await vq.json();
        renderVerifyQueue(vdata.items || []);
      }
    } catch {
      /* ignore */
    }
  } catch {
    if (!quiet && !state.hasData.history) {
      els.historyStats.className = "history-stats-split loading";
      els.historyStats.textContent = "Não foi possível carregar o histórico.";
    }
  } finally {
    state.fetching.history = false;
    if (!quiet) setPanelRefreshing("history", false);
  }
}

/* ── Bots configuráveis ── */
function emptyBotDraft() {
  return {
    name: "",
    description: "",
    mode: "prematch",
    active: true,
    notify: true,
    leagues: [],
    markets: [],
    min_score: null,
    min_ev_pct: null,
    max_stake_level: null,
    minutes_before: null,
    conditions: [],
    conditions_logic: "and",
    condition_groups: [],
    groups_logic: "or",
    template: null,
  };
}

function botConditionCount(bot) {
  const flat = (bot.conditions || []).length;
  const grouped = (bot.condition_groups || []).reduce(
    (n, g) => n + (g.conditions || []).length,
    0,
  );
  return flat + grouped;
}

function renderBotConditionGroups(groups) {
  if (!groups?.length) return "";
  const gLogic = state.bots.catalog?.logic_options?.group_logic || {};
  return groups
    .map((g, gi) => {
      const items = (g.conditions || [])
        .map(
          (c) =>
            `<li class="bot-cond-item bot-cond-group-item"><span>${c.label || c.field} ${c.operator} ${c.value}</span></li>`,
        )
        .join("");
      const logicLabel = gLogic[g.logic] || g.logic || "AND";
      return `<div class="bot-cond-group">
        <p class="bot-cond-group-title">${g.label || `Grupo ${gi + 1}`} <span class="meta">(${logicLabel})</span></p>
        <ul class="bot-cond-list">${items}</ul>
      </div>`;
    })
    .join("");
}

function botModeLabel(mode) {
  return mode === "live" ? "● Live" : "◷ Pré-jogo";
}

function botMatchesFilter(bot) {
  const f = state.bots.filter;
  if (f === "active" && !bot.active) return false;
  if (f === "inactive" && bot.active) return false;
  if (f === "prematch" && bot.mode !== "prematch") return false;
  if (f === "live" && bot.mode !== "live") return false;
  return true;
}

function formatBotPerfLine(perf) {
  if (!perf?.total) return "";
  const resolved = perf.resolved || 0;
  if (!resolved && !perf.pending) return "";
  const hit = perf.hit_rate_pct != null ? `${perf.hit_rate_pct}%` : "—";
  const pnlNum = Number(perf.total_pnl || 0);
  const pnl = `${pnlNum >= 0 ? "+" : ""}€${pnlNum.toFixed(2)}`;
  const roi = perf.roi_pct != null ? ` · ROI ${perf.roi_pct}%` : "";
  const pending = perf.pending ? ` · ${perf.pending} pend.` : "";
  return `${perf.wins || 0}G ${perf.losses || 0}R · ${hit} · ${pnl}${roi}${pending}`;
}

function renderBotsPerfSummary() {
  const el = els.botsPerfSummary;
  if (!el) return;
  const global = state.bots.perfGlobal;
  if (!global?.total_signals) {
    el.classList.add("hidden");
    el.innerHTML = "";
    return;
  }
  const perf = global.performance || {};
  const line = formatBotPerfLine(perf);
  el.classList.remove("hidden");
  el.innerHTML = `
    <p class="bots-perf-summary-title">Performance dos bots</p>
    <p class="bot-card-perf">${line || "Sem sinais resolvidos"}</p>
    <p class="meta">${global.total_signals} sinal${global.total_signals !== 1 ? "is" : ""} registado${global.total_signals !== 1 ? "s" : ""}</p>`;
}

function renderBotHistoryPanel() {
  const panel = els.botsHistoryPanel;
  if (!panel) return;
  if (!state.bots.historyId || !state.bots.historyData) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }
  const d = state.bots.historyData;
  const perfLine = formatBotPerfLine(d.performance);
  const signals = d.signals || [];
  const items = signals.map((t) => {
    const b = outcomeBadge(t.outcome);
    const pending = t.outcome === "pending";
    const live = isLiveTip(t);
    const modeClass = live ? "mode-live" : "mode-prematch";
    const pnl = t.pnl != null && !pending
      ? `<div class="tip-pnl ${t.pnl >= 0 ? "positive" : "negative"}">${t.pnl >= 0 ? "+" : ""}${Number(t.pnl).toFixed(2)}€</div>`
      : "";
    return `
      <article class="tip-card outcome-${t.outcome} ${modeClass}">
        <div class="tip-card-header">
          <div class="tip-match">${t.home} vs ${t.away}</div>
          <div class="tip-card-badges">
            <span class="tip-badge ${b.cls}">${b.label}</span>
            ${renderOutcomeCorrectBtn(t, "bot")}
          </div>
        </div>
        <div class="meta">${t.league || ""} · ${formatKickoff(t.logged_at)}</div>
        <div class="tip-details" style="margin-top:0.4rem">
          <span><strong>${t.market}</strong> @ ${t.odd}</span>
          <span>EV ${t.ev_pct > 0 ? "+" : ""}${t.ev_pct}%</span>
          ${t.final_score ? `<span>FT ${t.final_score}</span>` : ""}
        </div>
        ${pnl}
        ${renderPostMatchReview(t.review)}
      </article>`;
  }).join("");
  panel.classList.remove("hidden");
  panel.innerHTML = `
    <div class="bots-history-head">
      <div>
        <p class="section-title">${d.bot_name || "Bot"}</p>
        ${perfLine ? `<p class="bot-card-perf">${perfLine}</p>` : ""}
      </div>
      <button type="button" class="chip" id="bots-history-close">Fechar</button>
    </div>
    <div class="tips-feed bots-history-feed">${items || '<p class="meta">Sem sinais registados.</p>'}</div>`;
  document.getElementById("bots-history-close")?.addEventListener("click", () => {
    state.bots.historyId = null;
    state.bots.historyData = null;
    renderBotHistoryPanel();
  });
}

async function loadBotHistory(botId) {
  if (state.bots.historyId === botId) {
    state.bots.historyId = null;
    state.bots.historyData = null;
    renderBotHistoryPanel();
    return;
  }
  try {
    const res = await fetch(`/api/bots/${botId}/history?limit=30`);
    if (!res.ok) return;
    state.bots.historyId = botId;
    state.bots.historyData = await res.json();
    renderBotHistoryPanel();
  } catch {
    /* ignore */
  }
}

function renderBotsList() {
  if (!els.botsList) return;
  const bots = (state.bots.list || []).filter(botMatchesFilter);
  if (els.botsCountLabel) {
    els.botsCountLabel.textContent = `${state.bots.list.length}/40 bots`;
  }
  if (!state.bots.list.length) {
    els.botsList.innerHTML = `<p class="meta bots-empty">Ainda sem bots. Cria um ou importa um template.</p>`;
    updateWatermark("bots");
    return;
  }
  if (!bots.length) {
    els.botsList.innerHTML = `<p class="meta">Nenhum bot com este filtro.</p>`;
    updateWatermark("bots");
    return;
  }
  els.botsList.innerHTML = bots
    .map((bot) => {
      const hit = (state.bots.lastHits || []).find((h) => h.bot_id === bot.id);
      const hitN = hit?.total || 0;
      const condN = botConditionCount(bot);
      const leagueTxt = (bot.leagues || []).join(", ") || "Todas as ligas";
      const mktTxt = (bot.markets || []).join(", ") || "Todos os mercados";
      const perf = state.bots.performance?.[bot.id];
      const perfLine = formatBotPerfLine(perf);
      const histActive = state.bots.historyId === bot.id ? " active" : "";
      return `<article class="bot-card card" data-bot-id="${bot.id}">
        <div class="bot-card-main">
          <div class="bot-card-head">
            <strong class="bot-card-name">${bot.name}</strong>
            <span class="bot-card-mode">${botModeLabel(bot.mode)}</span>
          </div>
          <p class="meta bot-card-desc">${bot.description || mktTxt}</p>
          <p class="meta bot-card-meta">${leagueTxt}${bot.minutes_before ? ` · ${bot.minutes_before}min antes` : ""} · ${condN} cond.</p>
          ${perfLine ? `<p class="bot-card-perf">${perfLine}</p>` : ""}
          ${hitN ? `<p class="bot-card-hit">${hitN} jogo${hitN !== 1 ? "s" : ""} neste ciclo</p>` : ""}
        </div>
        <div class="bot-card-actions">
          <button type="button" class="bot-icon-btn bot-history-btn${histActive}" data-bot-history="${bot.id}" title="Histórico PnL">◎</button>
          <button type="button" class="bot-icon-btn" data-bot-edit="${bot.id}" title="Editar">✎</button>
          <button type="button" class="bot-icon-btn" data-bot-copy="${bot.id}" title="Duplicar">⧉</button>
          <button type="button" class="bot-toggle ${bot.active ? "on" : ""}" data-bot-toggle="${bot.id}" aria-pressed="${bot.active}" title="${bot.active ? "Desactivar" : "Activar"}"></button>
        </div>
      </article>`;
    })
    .join("");
  updateWatermark("bots");
}

function renderBotsTemplates() {
  if (!els.botsTemplates) return;
  const templates = state.bots.catalog?.templates || [];
  if (!templates.length) {
    els.botsTemplates.classList.add("hidden");
    return;
  }
  els.botsTemplates.classList.remove("hidden");
  els.botsTemplates.innerHTML = `
    <p class="bots-templates-title">Templates rápidos</p>
    <div class="bots-templates-row">${templates
      .map(
        (t) =>
          `<button type="button" class="chip bots-template-btn" data-template-id="${t.id}">${t.name}</button>`
      )
      .join("")}</div>`;
}

function renderBotsHits(hits) {
  if (!els.botsHits) return;
  state.bots.lastHits = hits || [];
  renderBotsList();
  if (!hits?.length) {
    els.botsHits.classList.add("hidden");
    return;
  }
  els.botsHits.classList.remove("hidden");
  const items = hits
    .map((h) => {
      const top = h.matches?.[0];
      if (!top) return "";
      return `<li><strong>${h.bot_name}</strong> — ${top.home} vs ${top.away} · ${top.best_market} (EV ${top.best_ev_pct > 0 ? "+" : ""}${top.best_ev_pct}%)</li>`;
    })
    .filter(Boolean)
    .join("");
  els.botsHits.innerHTML = `<p class="section-title">Alertas dos bots</p><ul class="bots-hits-list">${items}</ul>`;
}

function checkBotNotifyHits(hits) {
  if (!state.settings.notify || !hits?.length) return;
  for (const hit of hits) {
    if (!hit.notify) continue;
    const top = hit.matches?.[0];
    if (!top) continue;
    const snapKey = `${hit.bot_id}|${top.home}|${top.away}|${top.best_market}`;
    const prev = state.bots.snapshots[snapKey];
    const sig = `${top.best_score}|${top.best_ev_pct}`;
    if (prev === sig) continue;
    state.bots.snapshots[snapKey] = sig;
    notifyUser(
      `Bot: ${hit.bot_name}`,
      `${top.home} vs ${top.away} · ${top.best_market} EV ${top.best_ev_pct > 0 ? "+" : ""}${top.best_ev_pct}%`,
      { url: `/?tab=${hit.mode === "live" ? "live" : "prematch"}` },
    );
  }
}

async function loadBotsCatalog() {
  if (state.bots.catalog) return state.bots.catalog;
  try {
    const res = await fetch("/api/bots/catalog");
    state.bots.catalog = res.ok ? await res.json() : { categories: [], markets: [], templates: [] };
  } catch {
    state.bots.catalog = { categories: [], markets: [], templates: [] };
  }
  renderBotsTemplates();
  return state.bots.catalog;
}

async function loadBots() {
  await loadBotsCatalog();
  try {
    const res = await fetch("/api/bots?include_performance=true");
    const data = res.ok ? await res.json() : { bots: [] };
    state.bots.list = data.bots || [];
    state.bots.performance = data.performance?.by_bot || {};
    state.bots.perfGlobal = data.performance || null;
  } catch {
    state.bots.list = [];
    state.bots.performance = {};
    state.bots.perfGlobal = null;
  }
  renderBotsPerfSummary();
  renderBotsList();
  if (state.bots.historyId) {
    await loadBotHistory(state.bots.historyId);
  }
}

function setWizardStep(step) {
  state.bots.wizardStep = step;
  els.botWizardSteps?.querySelectorAll(".bot-step").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.step) <= step);
    el.classList.toggle("done", Number(el.dataset.step) < step);
  });
  els.botWizardPrev?.classList.toggle("hidden", step <= 1);
  els.botWizardNext?.classList.toggle("hidden", step >= 3);
  els.botWizardSave?.classList.toggle("hidden", step < 3);
  const subs = ["Nome, modo e alertas", "Mercados, ligas e limiares", "Condições (todas em AND)"];
  if (els.botWizardSub) els.botWizardSub.textContent = subs[step - 1] || "";
  renderWizardStep();
}

function renderWizardStep() {
  const d = state.bots.draft || emptyBotDraft();
  const cat = state.bots.catalog || {};
  const step = state.bots.wizardStep;
  if (!els.botWizardBody) return;

  if (step === 1) {
    els.botWizardBody.innerHTML = `
      <label class="field"><span>Nome *</span><input id="bot-f-name" type="text" value="${d.name || ""}" placeholder="ex: Over pré Liga PT" /></label>
      <label class="field"><span>Descrição</span><input id="bot-f-desc" type="text" value="${d.description || ""}" placeholder="Opcional" /></label>
      <div class="field"><span>Modo</span>
        <div class="bot-mode-row">
          <label class="chip-mode-scope"><input type="radio" name="bot-mode" value="prematch" ${d.mode !== "live" ? "checked" : ""} /> ◷ Pré-jogo</label>
          <label class="chip-mode-scope"><input type="radio" name="bot-mode" value="live" ${d.mode === "live" ? "checked" : ""} /> ● Ao vivo</label>
        </div>
      </div>
      <label class="field checkbox"><input id="bot-f-notify" type="checkbox" ${d.notify ? "checked" : ""} /><span>Notificar quando o bot encontrar jogos</span></label>
      <label class="field checkbox"><input id="bot-f-active" type="checkbox" ${d.active !== false ? "checked" : ""} /><span>Activar ao guardar</span></label>`;
    return;
  }

  if (step === 2) {
    const markets = (cat.markets || []).map((m) => {
      const on = (d.markets || []).includes(m);
      return `<label class="bot-market-chip"><input type="checkbox" data-bot-market="${m}" ${on ? "checked" : ""} /> ${m}</label>`;
    }).join("");
    els.botWizardBody.innerHTML = `
      <label class="field"><span>Ligas (vírgula, vazio = todas)</span><input id="bot-f-leagues" type="text" value="${(d.leagues || []).join(", ")}" placeholder="Primeira Liga, World" /></label>
      <div class="field"><span>Mercados preferidos</span><div class="bot-markets-grid">${markets}</div></div>
      <div class="bot-filters-grid">
        <label class="field"><span>Score mín.</span><input id="bot-f-min-score" type="number" step="0.01" min="0.5" max="0.9" value="${d.min_score ?? ""}" placeholder="0.55" /></label>
        <label class="field"><span>EV mín. %</span><input id="bot-f-min-ev" type="number" step="0.5" value="${d.min_ev_pct ?? ""}" placeholder="5" /></label>
        <label class="field bot-f-timing ${d.mode === "live" ? "hidden" : ""}"><span>Máx. min antes kickoff</span><input id="bot-f-mins-before" type="number" min="5" step="5" value="${d.minutes_before ?? ""}" placeholder="120" /></label>
        <label class="field"><span>Stake máx. (1-10)</span><input id="bot-f-max-stake" type="number" min="1" max="10" value="${d.max_stake_level ?? ""}" placeholder="10" /></label>
      </div>`;
    return;
  }

  const categories = (cat.categories || []).filter((c) => {
    if (!c.modes) return true;
    return c.modes.includes(d.mode);
  });
  const logicOpts = cat.logic_options?.conditions_logic || { and: "Todas (AND)", or: "Qualquer (OR)" };
  const groupsLogicOpts = cat.logic_options?.groups_logic || { and: "Todos (AND)", or: "Qualquer (OR)" };
  const condLogic = d.conditions_logic || "and";
  const groupsLogic = d.groups_logic || "or";
  const hasGroups = (d.condition_groups || []).length > 0;
  const logicSel = Object.entries(logicOpts)
    .map(([k, label]) => `<option value="${k}"${condLogic === k ? " selected" : ""}>${label}</option>`)
    .join("");
  const groupsLogicSel = Object.entries(groupsLogicOpts)
    .map(([k, label]) => `<option value="${k}"${groupsLogic === k ? " selected" : ""}>${label}</option>`)
    .join("");
  const conds = (d.conditions || []).map((c, i) =>
    `<li class="bot-cond-item"><span>${c.label || c.field} ${c.operator} ${c.value}</span><button type="button" data-rm-cond="${i}" class="bot-cond-rm">×</button></li>`
  ).join("");
  const groupsHtml = renderBotConditionGroups(d.condition_groups);
  els.botWizardBody.innerHTML = `
    <div class="bot-cond-logic-row">
      <label class="field bot-cond-logic-field">
        <span>Combinação das condições</span>
        <select id="bot-cond-logic">${logicSel}</select>
      </label>
      ${hasGroups ? `<label class="field bot-cond-logic-field">
        <span>Entre grupos</span>
        <select id="bot-groups-logic">${groupsLogicSel}</select>
      </label>` : ""}
    </div>
    ${hasGroups ? `<p class="meta">Grupos do template — (perder OU empatar) AND (cantos).</p>${groupsHtml}` : ""}
    <p class="meta">${hasGroups ? "Condições extra:" : "Condições abaixo aplicam a lógica escolhida."}</p>
    <ul class="bot-cond-list">${conds || '<li class="meta">Sem condições extra — usa só os filtros do passo 2.</li>'}</ul>
    <div class="bot-cond-add">
      <p class="bot-cond-add-title">Adicionar condição</p>
      <div class="bot-cat-grid">${categories.map((c) =>
        `<button type="button" class="bot-cat-btn" data-cat-id="${c.id}">${c.label}</button>`
      ).join("")}</div>
      <div id="bot-cond-form" class="bot-cond-form hidden"></div>
    </div>`;
}

function readWizardDraft() {
  const d = { ...(state.bots.draft || emptyBotDraft()) };
  const name = document.getElementById("bot-f-name");
  if (name) {
    d.name = name.value.trim();
    d.description = document.getElementById("bot-f-desc")?.value.trim() || "";
    d.mode = document.querySelector('input[name="bot-mode"]:checked')?.value || "prematch";
    d.notify = !!document.getElementById("bot-f-notify")?.checked;
    d.active = !!document.getElementById("bot-f-active")?.checked;
  }
  const leagues = document.getElementById("bot-f-leagues");
  if (leagues) {
    d.leagues = leagues.value.split(",").map((s) => s.trim()).filter(Boolean);
    d.markets = [...document.querySelectorAll("[data-bot-market]:checked")].map((el) => el.dataset.botMarket);
    const ms = document.getElementById("bot-f-min-score")?.value;
    const me = document.getElementById("bot-f-min-ev")?.value;
    const mb = document.getElementById("bot-f-mins-before")?.value;
    const mx = document.getElementById("bot-f-max-stake")?.value;
    d.min_score = ms ? parseFloat(ms) : null;
    d.min_ev_pct = me ? parseFloat(me) : null;
    d.minutes_before = mb ? parseInt(mb, 10) : null;
    d.max_stake_level = mx ? parseInt(mx, 10) : null;
  }
  const condLogic = document.getElementById("bot-cond-logic");
  if (condLogic) d.conditions_logic = condLogic.value || "and";
  const groupsLogic = document.getElementById("bot-groups-logic");
  if (groupsLogic) d.groups_logic = groupsLogic.value || "or";
  state.bots.draft = d;
  return d;
}

function openBotWizard(bot = null, template = null) {
  if (template) {
    state.bots.draft = {
      ...emptyBotDraft(),
      ...template,
      name: `${template.name} (cópia)`,
      template: template.id,
      conditions: [...(template.conditions || [])],
      condition_groups: (template.condition_groups || []).map((g) => ({
        ...g,
        conditions: [...(g.conditions || [])],
      })),
      conditions_logic: template.conditions_logic || "and",
      groups_logic: template.groups_logic || "or",
    };
    state.bots.editingId = null;
  } else if (bot) {
    state.bots.draft = {
      ...bot,
      conditions: [...(bot.conditions || [])],
      condition_groups: (bot.condition_groups || []).map((g) => ({
        ...g,
        conditions: [...(g.conditions || [])],
      })),
    };
    state.bots.editingId = bot.id;
  } else {
    state.bots.draft = emptyBotDraft();
    state.bots.editingId = null;
  }
  if (els.botWizardTitle) {
    els.botWizardTitle.textContent = state.bots.editingId ? "Editar bot" : "Novo bot";
  }
  els.botWizard?.classList.remove("hidden");
  els.botWizard?.setAttribute("aria-hidden", "false");
  setWizardStep(1);
}

function closeBotWizard() {
  els.botWizard?.classList.add("hidden");
  els.botWizard?.setAttribute("aria-hidden", "true");
  state.bots.draft = null;
  state.bots.editingId = null;
}

function buildConditionValueInput(field) {
  if (field.type === "number") {
    return `<input id="bot-cond-value" type="number" step="any" />`;
  }
  if (field.type === "boolean") {
    return `<select id="bot-cond-value"><option value="true">Sim</option><option value="false">Não</option></select>`;
  }
  if (field.type === "market") {
    return `<select id="bot-cond-value">${(state.bots.catalog?.markets || []).map((m) => `<option value="${m}">${m}</option>`).join("")}</select>`;
  }
  if (field.type === "enum" && field.options) {
    return `<select id="bot-cond-value">${field.options.map((o) => `<option value="${o}">${o}</option>`).join("")}</select>`;
  }
  return `<input id="bot-cond-value" type="text" placeholder="valor" />`;
}

function showConditionForm(categoryId) {
  const cat = (state.bots.catalog?.categories || []).find((c) => c.id === categoryId);
  const form = document.getElementById("bot-cond-form");
  if (!cat || !form || !cat.fields?.length) return;

  const fieldOpts = cat.fields
    .map((f, i) => `<option value="${i}">${f.label}${f.unit ? ` (${f.unit})` : ""}</option>`)
    .join("");

  form.classList.remove("hidden");
  form.innerHTML = `
    <p class="meta">${cat.description || cat.label}</p>
    <div class="bot-cond-form-row">
      <select id="bot-cond-field">${fieldOpts}</select>
      <select id="bot-cond-op"></select>
      <span id="bot-cond-value-wrap"></span>
      <button type="button" id="bot-cond-add-btn" class="btn-primary">Adicionar</button>
    </div>`;

  const fieldSel = document.getElementById("bot-cond-field");
  const opSel = document.getElementById("bot-cond-op");
  const valueWrap = document.getElementById("bot-cond-value-wrap");

  const syncField = () => {
    const field = cat.fields[parseInt(fieldSel?.value || "0", 10)];
    if (!field || !opSel || !valueWrap) return;
    const ops = field.operators || ["eq"];
    opSel.innerHTML = ops
      .map((o) => `<option value="${o}">${state.bots.catalog?.operators?.[o] || o}</option>`)
      .join("");
    valueWrap.innerHTML = buildConditionValueInput(field);
  };

  fieldSel?.addEventListener("change", syncField);
  syncField();

  document.getElementById("bot-cond-add-btn")?.addEventListener("click", () => {
    readWizardDraft();
    const field = cat.fields[parseInt(fieldSel?.value || "0", 10)];
    if (!field) return;
    const op = document.getElementById("bot-cond-op")?.value || "eq";
    let val = document.getElementById("bot-cond-value")?.value;
    if (val === "true") val = true;
    if (val === "false") val = false;
    if (field.type === "number" && val !== "") val = parseFloat(val);
    const opLabel = state.bots.catalog?.operators?.[op] || op;
    const label = `${field.label} ${opLabel} ${val}`;
    state.bots.draft.conditions.push({
      category: cat.id,
      field: field.id,
      operator: op,
      value: val,
      label,
    });
    setWizardStep(3);
  });
}

async function saveBotFromWizard() {
  readWizardDraft();
  const d = state.bots.draft;
  if (!d?.name?.trim()) {
    alert("Indica um nome para o bot.");
    setWizardStep(1);
    return;
  }
  const payload = { ...d, name: d.name.trim() };
  const id = state.bots.editingId;
  const url = id ? `/api/bots/${id}` : "/api/bots";
  const method = id ? "PUT" : "POST";
  try {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.error || "Erro ao guardar bot");
      return;
    }
    closeBotWizard();
    await loadBots();
  } catch {
    alert("Falha de rede ao guardar bot.");
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

async function ensureNotifyPermission() {
  if (!("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const result = await Notification.requestPermission();
  return result === "granted";
}

async function notifyUser(title, body, { url = "/?tab=history" } = {}) {
  if (!state.settings.notify) return;
  const granted = await ensureNotifyPermission();
  if (!granted) return;
  const options = {
    body,
    icon: "/icons/icon-192.jpg",
    badge: "/icons/icon-192.jpg",
    data: { url },
  };
  try {
    if ("serviceWorker" in navigator) {
      const reg = await navigator.serviceWorker.ready;
      if (reg.showNotification) {
        await reg.showNotification(title, options);
        return;
      }
    }
  } catch {
    /* fallback abaixo */
  }
  if ("Notification" in window) new Notification(title, options);
}

async function setupPushSubscription() {
  if (!state.settings.notify || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    return;
  }
  if (!(await ensureNotifyPermission())) return;
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

function checkPendingTipAlerts(tips) {
  for (const tip of tips || []) {
    const key = tipKey(tip);
    const outcome = String(tip.outcome || "pending").toLowerCase();
    const prev = state.tipOutcomeSnapshots[key];
    if (
      state.historyAlertsReady
      && prev === "pending"
      && (outcome === "win" || outcome === "loss")
    ) {
      const label = outcome === "win" ? "Green ✓" : "Red ✗";
      const score = tip.final_score ? ` · ${tip.final_score}` : "";
      notifyUser(
        `${label} ${tip.home} vs ${tip.away}`,
        `${tip.market}${score}`,
        { url: "/?tab=history" },
      );
    }
    state.tipOutcomeSnapshots[key] = outcome;
  }
  state.historyAlertsReady = true;
}

function checkPrematchAlerts(ranked) {
  for (const r of ranked || []) {
    const key = `${r.home}|${r.away}`;
    const prev = state.prematchSnapshots[key];
    if (
      r.should_bet
      && (!prev || !prev.should_bet || prev.best_market !== r.best_market)
    ) {
      notifyUser(
        `Pré-jogo: ${r.home} vs ${r.away}`,
        `${r.best_market} EV ${r.best_ev_pct > 0 ? "+" : ""}${r.best_ev_pct}%`,
        { url: "/?tab=prematch" },
      );
    }
    state.prematchSnapshots[key] = {
      should_bet: r.should_bet,
      best_market: r.best_market,
    };
  }
}

function checkLiveAlerts(ranked) {
  for (const r of ranked || []) {
    const key = `${r.home}|${r.away}`;
    const prev = state.liveSnapshots[key];
    if (prev && prev.score !== r.score) {
      notifyUser(`Golo! ${r.home} ${r.score} ${r.away}`, `${r.minute}' — era ${prev.score}`, {
        url: "/?tab=live",
      });
    }
    if (
      r.should_bet &&
      (!prev || !prev.should_bet || prev.best_market !== r.best_market)
    ) {
      notifyUser(`Ao vivo: ${r.home} vs ${r.away}`, `${r.best_market} EV ${r.best_ev_pct > 0 ? "+" : ""}${r.best_ev_pct}%`, {
        url: "/?tab=live",
      });
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
    updateWatermark("prematch");
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
    checkPrematchAlerts(data.ranked);
    renderBotsHits(data.bot_hits);
    checkBotNotifyHits(data.bot_hits);
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
    updateWatermark("live");
  }

  let listData = null;
  try {
    const listRes = await fetch(buildLiveListUrl());
    if (listRes.ok) {
      listData = await listRes.json();
      state.hasData.live = true;
      els.liveCount.textContent = `${listData.total} jogo${listData.total !== 1 ? "s" : ""}`;
      updatePwaLiveChip(listData.total);
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
    updatePwaLiveChip(data.total_live);
    updateLiveSourceBadge(data.live_source, data.live_source_label);
    renderLiveStatus(data);
    setLiveScanData({
      ...data,
      fixtures: data.fixtures?.length ? data.fixtures : listData?.fixtures,
    });
    checkLiveAlerts(data.ranked);
    renderBotsHits(data.bot_hits);
    checkBotNotifyHits(data.bot_hits);
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

function loadDesktopStyles() {
  if (document.getElementById("desktop-css")) return;
  const link = document.createElement("link");
  link.id = "desktop-css";
  link.rel = "stylesheet";
  link.href = "/desktop.css";
  document.head.appendChild(link);
}

function parseLiveCount(value) {
  const m = String(value ?? "").match(/(\d+)/);
  return m ? parseInt(m[1], 10) : 0;
}

function fixturesListHasGames(listEl) {
  return !!listEl?.querySelector(".live-fixture-item, .prematch-fixture");
}

function panelHasWrittenContent(tab = state.tab) {
  if (state.match.key) return true;

  if (tab === "prematch") {
    if (!els.bestPrematch?.classList.contains("hidden")) return true;
    if (!els.rankingPrematch?.classList.contains("hidden")) return true;
    if (fixturesListHasGames(els.prematchFixturesList)) return true;
    return false;
  }

  if (tab === "live") {
    if (!els.bestLive?.classList.contains("hidden")) return true;
    if (!els.rankingLive?.classList.contains("hidden")) return true;
    if (fixturesListHasGames(els.liveFixturesList)) return true;
    return false;
  }

  if (tab === "bots") {
    return state.bots.list.length > 0;
  }

  if (tab === "history") {
    if (els.historyStats?.classList.contains("loading")) return false;
    if (state.historyTips?.length > 0) return true;
    if (
      !els.historyLearning?.classList.contains("hidden")
      && (els.historyLearning?.textContent || "").trim().length > 0
    ) {
      return true;
    }
    if (state.hasData.history && !els.historyStats?.classList.contains("loading")) {
      return true;
    }
    return false;
  }

  return false;
}

function updateWatermark(tab = state.tab) {
  if (!els.mainContent) return;
  const show = !panelHasWrittenContent(tab);
  els.mainContent.classList.toggle("show-watermark", show);
}

function updatePwaLiveChip(count, tab = state.tab) {
  if (isDesktopApp || !els.pwaLiveCount) return;
  const n = Number.isFinite(count) ? Math.max(0, Math.floor(count)) : parseLiveCount(count);
  els.pwaLiveCount.textContent = String(n);
  els.pwaLiveChip?.classList.toggle("has-games", n > 0);
  els.pwaLiveChip?.classList.toggle("active", tab === "live");
}

function updateScreenChrome(tab = state.tab) {
  if (isDesktopApp) return;
  updatePwaLiveChip(parseLiveCount(els.liveCount?.textContent), tab);
}

function initPwaMode() {
  document.documentElement.classList.add("pwa-app");
  updateScreenChrome(state.tab);
  updateWatermark(state.tab);
  els.pwaLiveChip?.addEventListener("click", () => switchTab("live"));
}

function initDesktopMode() {
  if (!isDesktopApp) return;
  loadDesktopStyles();
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
  updateWatermark(state.tab);
}

function applyUrlTab() {
  const tab = new URLSearchParams(location.search).get("tab");
  if (tab === "prematch" || tab === "live" || tab === "history" || tab === "bots") {
    switchTab(tab, { skipMatchClose: true });
  }
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
  document.getElementById("panel-bots")?.classList.toggle("active", tab === "bots");
  if (tab === "bots") loadBots();
  scheduleAutoRefresh();
  syncDesktopNav(tab);
  updateScreenChrome(tab);
  updateWatermark(tab);
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
  clearInterval(state.timers.historyPoll);
  state.timers.live = state.timers.prematch = state.timers.historyPoll = null;
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
  if (state.settings.notify) {
    state.timers.historyPoll = setInterval(() => loadHistory({ quiet: true }), 120_000);
  }
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
els.historyFilters?.addEventListener("click", (event) => {
  const chip = event.target.closest(".filter-chip[data-filter]");
  if (!chip) return;
  state.historyFilter = chip.dataset.filter;
  renderHistoryFilters();
  renderHistoryFeed();
});

els.botsNewBtn?.addEventListener("click", () => openBotWizard());
els.botWizardCancel?.addEventListener("click", closeBotWizard);
els.botWizardBackdrop?.addEventListener("click", closeBotWizard);
els.botWizardPrev?.addEventListener("click", () => {
  readWizardDraft();
  setWizardStep(Math.max(1, state.bots.wizardStep - 1));
});
els.botWizardNext?.addEventListener("click", () => {
  readWizardDraft();
  if (state.bots.wizardStep === 1 && !state.bots.draft?.name?.trim()) {
    alert("Indica um nome para o bot.");
    return;
  }
  setWizardStep(Math.min(3, state.bots.wizardStep + 1));
});
els.botWizardSave?.addEventListener("click", saveBotFromWizard);

els.botsFilters?.addEventListener("click", (e) => {
  const btn = e.target.closest(".bots-filter");
  if (!btn) return;
  state.bots.filter = btn.dataset.botsFilter || "all";
  els.botsFilters.querySelectorAll(".bots-filter").forEach((b) => {
    b.classList.toggle("active", b === btn);
  });
  renderBotsList();
});

els.botsTemplates?.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-template-id]");
  if (!btn) return;
  const tpl = (state.bots.catalog?.templates || []).find((t) => t.id === btn.dataset.templateId);
  if (tpl) openBotWizard(null, tpl);
});

els.botsList?.addEventListener("click", async (e) => {
  const toggle = e.target.closest("[data-bot-toggle]");
  if (toggle) {
    const id = toggle.dataset.botToggle;
    await fetch(`/api/bots/${id}/toggle`, { method: "PATCH" });
    await loadBots();
    return;
  }
  const edit = e.target.closest("[data-bot-edit]");
  if (edit) {
    const bot = state.bots.list.find((b) => b.id === edit.dataset.botEdit);
    if (bot) openBotWizard(bot);
    return;
  }
  const copy = e.target.closest("[data-bot-copy]");
  if (copy) {
    const bot = state.bots.list.find((b) => b.id === copy.dataset.botCopy);
    if (bot) {
      const { id: _id, created_at: _c, updated_at: _u, ...rest } = bot;
      openBotWizard({ ...rest, name: `${bot.name} (cópia)` });
    }
    return;
  }
  const hist = e.target.closest("[data-bot-history]");
  if (hist) {
    await loadBotHistory(hist.dataset.botHistory);
  }
});

els.botWizardBody?.addEventListener("click", (e) => {
  const cat = e.target.closest("[data-cat-id]");
  if (cat) showConditionForm(cat.dataset.catId);
  const rm = e.target.closest("[data-rm-cond]");
  if (rm) {
    readWizardDraft();
    const idx = parseInt(rm.dataset.rmCond, 10);
    state.bots.draft.conditions.splice(idx, 1);
    setWizardStep(3);
  }
});

els.historyModeScope?.addEventListener("click", (event) => {
  const btn = event.target.closest(".chip-mode-scope[data-mode-scope]");
  if (!btn) return;
  state.historyModeFilter = btn.dataset.modeScope;
  renderHistoryFilters();
  renderHistoryFeed();
});

els.outcomeCorrectCancel?.addEventListener("click", closeOutcomeCorrectModal);
els.outcomeCorrectBackdrop?.addEventListener("click", closeOutcomeCorrectModal);
els.outcomeCorrectSave?.addEventListener("click", saveOutcomeCorrection);

els.mainContent?.addEventListener("click", async (e) => {
  const correctBtn = e.target.closest("[data-correct-id]");
  if (correctBtn) {
    const kind = correctBtn.dataset.correctKind || "tip";
    const entryId = decodeURIComponent(correctBtn.dataset.correctId || "");
    let entry = null;
    if (kind === "bot") {
      entry = (state.bots.historyData?.signals || []).find(
        (s) => (s.id || tipKey(s)) === entryId,
      );
    } else {
      entry = (state.historyTips || []).find((t) => (t.id || tipKey(t)) === entryId);
    }
    if (entry) openOutcomeCorrectModal(entry, kind);
    return;
  }
  const btn = e.target.closest("[data-copy-prompt]");
  if (!btn) return;
  const text = decodeURIComponent(btn.dataset.copyPrompt || "");
  if (!text) return;
  const original = btn.textContent;
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = "Copiado!";
  } catch {
    window.prompt("Copia este texto:", text);
  }
  setTimeout(() => {
    btn.textContent = original;
  }, 2000);
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

if (isDesktopApp) {
  initDesktopMode();
} else {
  initPwaMode();
}
els.refreshBtn?.classList.add("idle");

applyBranding().then(() => {
  applySettingsToForm();
  applyUrlTab();
  scheduleAutoRefresh();
  if (state.settings.notify) setupPushSubscription();
  loadPrematch();
  loadLive();
  if (state.settings.notify) loadHistory({ quiet: true });
});