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
};

const els = {
  statusPrematch: document.getElementById("status-prematch"),
  bestPrematch: document.getElementById("best-prematch"),
  tablePrematch: document.getElementById("table-prematch"),
  rankingPrematch: document.getElementById("ranking-prematch"),
  prematchRefresh: document.getElementById("prematch-refresh"),
  statusLive: document.getElementById("status-live"),
  bestLive: document.getElementById("best-live"),
  tableLive: document.getElementById("table-live"),
  rankingLive: document.getElementById("ranking-live"),
  skippedLive: document.getElementById("skipped-live"),
  skippedList: document.getElementById("skipped-list"),
  liveFixtures: document.getElementById("live-fixtures"),
  liveFixturesList: document.getElementById("live-fixtures-list"),
  liveContent: document.getElementById("live-content"),
  liveBanner: document.getElementById("live-banner"),
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
  historyFeed: document.getElementById("history-feed"),
  historyEmpty: document.getElementById("history-empty"),
};

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
  } catch { /* defaults */ }
}

function formatKickoff(iso) {
  try {
    return new Date(iso).toLocaleString("pt-PT", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso || "—"; }
}

function evClass(pct) { return pct >= 0 ? "ev-pos" : "ev-neg"; }

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
  els.refreshBtn?.classList.toggle("spinning", any);
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
    </div>`;
}

function renderRankingPrematch(ranked) {
  if (!ranked?.length) { els.rankingPrematch.classList.add("hidden"); return; }
  els.rankingPrematch.classList.remove("hidden");
  const rows = ranked.map((r) => `
    <tr class="${r.rank === 1 ? "highlight" : ""}">
      <td>${r.rank}${r.should_bet ? "★" : ""}</td>
      <td>${r.home} vs ${r.away}</td>
      <td>${r.best_market}</td>
      <td class="${evClass(r.best_ev_pct)}">${r.best_ev_pct > 0 ? "+" : ""}${r.best_ev_pct}%</td>
      <td>${r.stake_level ? `${r.stake_level}/10` : "—"}</td>
    </tr>`).join("");
  els.tablePrematch.innerHTML = `
    <table><thead><tr><th>#</th><th>Jogo</th><th>Mercado</th><th>EV</th><th>Stake</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

function renderPrematchStatus(data, staleMsg = "") {
  els.statusPrematch.className = `card status-card${staleMsg ? " status-stale" : ""}`;
  let html = `<strong>${data.total_found}</strong> jogos · <strong>${data.total_analyzed}</strong> analisados
    <div class="meta">Actualizado: ${formatKickoff(data.scanned_at)}</div>`;
  if (!data.ranked?.length) html += "<div class='meta'>Nenhum jogo analisável.</div>";
  if (staleMsg) html += `<div class="meta">${staleMsg}</div>`;
  els.statusPrematch.innerHTML = html;
}

/* ── Live ── */
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
    </div>`;
}

function renderRankingLive(ranked) {
  if (!ranked?.length) { els.rankingLive.classList.add("hidden"); return; }
  els.rankingLive.classList.remove("hidden");
  const rows = ranked.map((r) => {
    const min = r.injury_time ? `${r.minute}+${r.injury_time}` : r.minute;
    return `<tr class="live-row ${r.rank === 1 ? "highlight" : ""}">
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
  const warn = data.warning
    ? `<div class="meta warn">${data.warning}</div>`
    : data.source === "espn"
      ? `<div class="meta">Fonte: ESPN (API-Football indisponível)</div>`
      : "";
  if (data.total_live === 0) {
    els.statusLive.innerHTML = `Nenhum jogo ao vivo.${warn}<div class="meta">Actualizado: ${formatKickoff(data.scanned_at)}</div>`;
    return;
  }
  els.statusLive.innerHTML = `
    <strong>${data.total_live}</strong> ao vivo · <strong>${data.total_analyzed}</strong> analisados
    <div class="meta">Actualizado: ${formatKickoff(data.scanned_at)}</div>
    ${warn}
    ${staleMsg ? `<div class="meta">${staleMsg}</div>` : ""}`;
}

function renderSkipped(skipped) {
  if (!skipped?.length) { els.skippedLive.classList.add("hidden"); return; }
  els.skippedLive.classList.remove("hidden");
  els.skippedList.innerHTML = skipped.slice(0, 6).map((s) => `<li>${s.match}: ${s.reason}</li>`).join("");
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
    return `<li class="live-fixture-item">
      <span class="live-pulse">●</span>
      <div>
        <strong>${f.home} ${f.score} ${f.away}</strong>
        <div class="meta">${f.league} · ${min}${status}</div>
      </div>
    </li>`;
  }).join("");
}

/* ── Histórico ── */
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
    renderHistoryStats(data.performance || { wins: 0, losses: 0, total_pnl: 0, hit_rate_pct: null, roi_pct: null });
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
    if (r.should_bet && (!prev || !prev.should_bet)) {
      notifyUser(`Oportunidade: ${r.home} vs ${r.away}`, `${r.best_market} EV ${r.best_ev_pct > 0 ? "+" : ""}${r.best_ev_pct}%`);
    }
    state.liveSnapshots[key] = { score: r.score, should_bet: r.should_bet };
  }
}

async function loadPrematch() {
  if (state.fetching.prematch) return;
  const keepVisible = state.hasData.prematch;
  state.fetching.prematch = true;
  setPanelRefreshing("prematch", true);
  if (!keepVisible) {
    els.statusPrematch.className = "card status-card loading";
    els.statusPrematch.textContent = "A analisar jogos…";
  }
  try {
    const params = new URLSearchParams({ hours: "12" });
    if (state.settings.bankroll) params.set("bankroll", String(state.settings.bankroll));
    const res = await fetch(`/api/scan?${params}`);
    if (!res.ok) throw new Error("Servidor não respondeu");
    const data = await res.json();
    state.hasData.prematch = true;
    renderPrematchStatus(data);
    renderBestPrematch(data.best);
    renderRankingPrematch(data.ranked);
  } catch (err) {
    if (!keepVisible) showError(els.statusPrematch, "Servidor desligado. Verifica se o robot está a correr.");
    else renderPrematchStatus({ total_found: "—", total_analyzed: "—", scanned_at: new Date().toISOString(), ranked: [] }, `Falha — última análise mantida`);
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
      renderLiveFixtures(listData.fixtures);
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
    els.liveCount.textContent = `${data.total_live} jogo${data.total_live !== 1 ? "s" : ""}`;
    renderLiveStatus(data);
    renderLiveFixtures(data.fixtures?.length ? data.fixtures : listData?.fixtures);
    checkLiveAlerts(data.ranked);
    renderBestLive(data.best);
    renderRankingLive(data.ranked);
    renderSkipped(data.skipped);
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
      renderSkipped([]);
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

function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab[data-tab]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.getElementById("panel-prematch").classList.toggle("active", tab === "prematch");
  document.getElementById("panel-live").classList.toggle("active", tab === "live");
  document.getElementById("panel-history").classList.toggle("active", tab === "history");
  scheduleAutoRefresh();
  if (tab === "history") loadHistory();
}

function refreshCurrent() {
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
  state.timers.live = setInterval(() => { if (state.tab === "live") loadLive(); }, LIVE_INTERVAL);
  state.timers.prematch = setInterval(() => { if (state.tab === "prematch") loadPrematch(); }, PREMATCH_INTERVAL);
}

function openDrawer() {
  applySettingsToForm();
  els.drawer.classList.remove("hidden");
}
function closeDrawer() { els.drawer.classList.add("hidden"); }

document.querySelectorAll(".tab[data-tab]").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});
document.querySelectorAll("#history-filters .chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll("#history-filters .chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    state.historyFilter = chip.dataset.filter;
    renderHistoryFeed();
  });
});

els.refreshBtn?.addEventListener("click", refreshCurrent);
els.settingsBtn?.addEventListener("click", openDrawer);
els.drawerBackdrop?.addEventListener("click", closeDrawer);
els.saveSettings?.addEventListener("click", saveSettingsToStorage);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

applyBranding().then(() => {
  applySettingsToForm();
  scheduleAutoRefresh();
  loadPrematch();
  loadLive();
});