import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const UPGRADE_TYPES = ["capability", "safety", "efficiency", "market"];
const UPGRADE_SHORT_LABELS = {
  capability: "CAP",
  safety: "SAF",
  efficiency: "EFF",
  market: "MKT",
};

function clamp(value, low, high) {
  return Math.max(low, Math.min(value, high));
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function formatCompactMoney(value) {
  if (!Number.isFinite(value)) return "$0";
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}k`;
  return `$${Math.round(value)}`;
}

function moneyValueClass(value) {
  const digits = Math.abs(Math.round(value || 0)).toString().length;
  if (digits >= 12) return "metric-value-xs";
  if (digits >= 11) return "metric-value-sm";
  if (digits >= 10) return "metric-value-md";
  return "metric-value-lg";
}

function scoreClass(score) {
  if (score >= 82) return "score-outstanding";
  if (score >= 68) return "score-strong";
  if (score >= 55) return "score-stable";
  if (score >= 42) return "score-risky";
  return "score-critical";
}

function nextUpgradeCost(model, upgradeType) {
  const currentLevel = model?.[upgradeType] ?? 1;
  const baseCosts = {
    capability: 700_000,
    safety: 550_000,
    efficiency: 600_000,
    market: 650_000,
  };
  return Math.round(baseCosts[upgradeType] * (1 + 0.16 * (currentLevel - 1)));
}

function sparklinePoints(values, width = 280, height = 84, left = 26, right = 272, top = 10, bottom = 70) {
  if (!values.length) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  return values
    .map((value, index) => {
      const x = left + (index / Math.max(1, values.length - 1)) * (right - left);
      const normalized = (value - min) / range;
      const y = bottom - normalized * (bottom - top);
      return `${x},${y}`;
    })
    .join(" ");
}

function Sparkline({ values, color, title }) {
  const chartValues = values.length ? values : [0, 0];
  const points = sparklinePoints(chartValues);
  const latest = chartValues[chartValues.length - 1] ?? 0;
  const min = Math.min(...chartValues);
  const max = Math.max(...chartValues);
  const latestQuarter = Math.max(1, chartValues.length);
  return (
    <article className="spark-card">
      <div className="spark-head">
        <span>{title}</span>
        <strong>{Number(latest).toFixed(1)}</strong>
      </div>
      <svg viewBox="0 0 280 84" preserveAspectRatio="none" className="spark-svg" role="img" aria-label={title}>
        <line className="spark-axis" x1="26" y1="10" x2="26" y2="70" />
        <line className="spark-axis" x1="26" y1="70" x2="272" y2="70" />
        <polyline points={points} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
        <text className="spark-axis-text" x="2" y="14">{max.toFixed(1)}</text>
        <text className="spark-axis-text" x="2" y="71">{min.toFixed(1)}</text>
        <text className="spark-axis-text" x="24" y="82">Q1</text>
        <text className="spark-axis-text" x="252" y="82">Q{latestQuarter}</text>
      </svg>
      <p className="spark-axis-note">Y: metric value · X: quarter</p>
    </article>
  );
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",  // Include cookies
    ...options,
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const payload = await response.json();
      detail = payload?.detail || detail;
    } catch {
      detail = `${response.status} ${response.statusText}`;
    }
    throw new Error(detail);
  }

  return response.json();
}

function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [showAuthUI, setShowAuthUI] = useState(false);
  const [authMode, setAuthMode] = useState("login");  // "login" or "register"
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [game, setGame] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");
  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [seenEventKey, setSeenEventKey] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyItems, setHistoryItems] = useState([]);
  const [epilogueLoading, setEpilogueLoading] = useState(false);
  const [epilogueRequestedForGame, setEpilogueRequestedForGame] = useState(null);

  useEffect(() => {
    void checkAuth();
  }, []);

  async function checkAuth() {
    try {
      setAuthLoading(true);
      const data = await fetchJson(`${API_BASE}/auth/me`);
      setUser(data);
      setShowAuthUI(false);
      void createGame();
    } catch (err) {
      setUser(null);
      setShowAuthUI(true);
      setLoading(false);
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleAuth(e) {
    e.preventDefault();
    if (!authUsername || !authPassword) {
      setError("Username and password required");
      return;
    }
    try {
      setActionLoading(true);
      setError("");
      const endpoint = authMode === "login" ? "/auth/login" : "/auth/register";
      await fetchJson(`${API_BASE}${endpoint}`, {
        method: "POST",
        body: JSON.stringify({ username: authUsername, password: authPassword }),
      });
      setAuthUsername("");
      setAuthPassword("");
      await checkAuth();
    } catch (err) {
      setError(err.message || "Authentication failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleLogout() {
    try {
      await fetchJson(`${API_BASE}/auth/logout`, { method: "POST" });
      setUser(null);
      setGame(null);
      setShowAuthUI(true);
    } catch (err) {
      setError(err.message || "Logout failed");
    }
  }

  async function createGame() {
    try {
      setLoading(true);
      setError("");
      setEventModalOpen(false);
      setSeenEventKey(null);
      setEpilogueLoading(false);
      setEpilogueRequestedForGame(null);
      const data = await fetchJson(`${API_BASE}/games`, {
        method: "POST",
        body: JSON.stringify({ company_name: "NovaForge AI" }),
      });
      setGame(data);
    } catch (err) {
      setError(err.message || "Could not start game session");
    } finally {
      setLoading(false);
    }
  }

  async function applyUpgrade(modelIndex, upgradeType) {
    if (!game || actionLoading || eventModalOpen) return;
    try {
      setActionLoading(true);
      setError("");
      const data = await fetchJson(`${API_BASE}/games/${game.game_id}/upgrades`, {
        method: "POST",
        body: JSON.stringify({
          upgrades: [{ model_index: modelIndex, upgrade_type: upgradeType }],
        }),
      });
      setGame(data);
    } catch (err) {
      setError(err.message || "Upgrade failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function runQuarter() {
    if (!game || actionLoading || eventModalOpen) return;
    try {
      setActionLoading(true);
      setError("");
      const data = await fetchJson(`${API_BASE}/games/${game.game_id}/quarters/run`, {
        method: "POST",
      });
      setGame(data);
    } catch (err) {
      setError(err.message || "Quarter simulation failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function decideFunding(accept) {
    if (!game || actionLoading || eventModalOpen) return;
    try {
      setActionLoading(true);
      setError("");
      const data = await fetchJson(`${API_BASE}/games/${game.game_id}/funding`, {
        method: "POST",
        body: JSON.stringify({ accept }),
      });
      setGame(data);
    } catch (err) {
      setError(err.message || "Funding decision failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function requestEpilogue(gameId) {
    try {
      setEpilogueLoading(true);
      const data = await fetchJson(`${API_BASE}/games/${gameId}/epilogue`, {
        method: "POST",
      });
      setGame(data);
    } catch (err) {
      setError(err.message || "Epilogue generation failed");
    } finally {
      setEpilogueLoading(false);
    }
  }

  async function openHistory() {
    try {
      setHistoryOpen(true);
      setHistoryLoading(true);
      setError("");
      const data = await fetchJson(`${API_BASE}/history?limit=15`);
      setHistoryItems(data.items || []);
    } catch (err) {
      setError(err.message || "Failed to load history");
      setHistoryItems([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  const budgetUsedRatio = useMemo(() => {
    if (!game?.budget?.cap) return 0;
    return Math.min(100, Math.round((game.budget.spent / game.budget.cap) * 100));
  }, [game]);

  useEffect(() => {
    const eventKey = game?.state?.active_event?.key;
    if (!eventKey) return;
    if (eventKey !== seenEventKey) {
      setEventModalOpen(true);
      setSeenEventKey(eventKey);
    }
  }, [game, seenEventKey]);

  useEffect(() => {
    const needsEpilogue = game?.status === "completed" || game?.status === "leader";
    if (!game || !needsEpilogue || game.epilogue) return;
    if (epilogueRequestedForGame === game.game_id) return;
    setEpilogueRequestedForGame(game.game_id);
    void requestEpilogue(game.game_id);
  }, [game, epilogueRequestedForGame]);

  if (authLoading) {
    return (
      <main className="shell">
        <div className="loading-panel">AUTHENTICATING...</div>
      </main>
    );
  }

  if (showAuthUI) {
    return (
      <main className="shell">
        <div className="auth-panel">
          <h1>NOVAFORGE AI</h1>
          <p className="auth-subtitle">
            {authMode === "login" ? "LOGIN TO CONTINUE" : "CREATE NEW ACCOUNT"}
          </p>
          {error ? <div className="error-banner">{error}</div> : null}
          <form className="auth-form" onSubmit={handleAuth}>
            <input
              type="text"
              placeholder="USERNAME"
              value={authUsername}
              onChange={(e) => setAuthUsername(e.target.value)}
              className="auth-input"
              disabled={actionLoading}
            />
            <input
              type="password"
              placeholder="PASSWORD"
              value={authPassword}
              onChange={(e) => setAuthPassword(e.target.value)}
              className="auth-input"
              disabled={actionLoading}
            />
            <button type="submit" className="btn primary" disabled={actionLoading}>
              {actionLoading ? "PROCESSING..." : authMode === "login" ? "LOGIN" : "REGISTER"}
            </button>
          </form>
          <button
            className="btn ghost auth-toggle"
            onClick={() => {
              setAuthMode(authMode === "login" ? "register" : "login");
              setError("");
            }}
            disabled={actionLoading}
          >
            {authMode === "login" ? "CREATE ACCOUNT" : "BACK TO LOGIN"}
          </button>
        </div>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="shell">
        <div className="loading-panel">BOOTING AI COMMAND CORE...</div>
      </main>
    );
  }

  if (!game) {
    return (
      <main className="shell">
        <div className="loading-panel">
          FAILED TO INITIALIZE SESSION.
          <button onClick={() => void createGame()} className="btn primary">
            RETRY
          </button>
        </div>
      </main>
    );
  }

  const state = game.state;
  const pending = game.pending_round?.quarter_outcome;
  const isCompleted = game.status === "completed";
  const isLeader = game.status === "leader";
  const isShutdown = game.status === "shutdown";
  const isGameOver = game.status !== "active";
  const history = game.history || [];
  const modelMetrics = game.model_metrics || [];
  const activeEvent = state.active_event;
  const isPausedByEvent = eventModalOpen && !!activeEvent;
  const isReputationLow = state.reputation < 58;
  const isComplianceLow = state.compliance < 58;

  const revenueTrend = history.map((h) => h.revenue / 1_000_000);
  const profitTrend = history.map((h) => h.net_profit / 1_000_000);
  const reputationTrend = history.map((h) => h.reputation);
  const complianceTrend = history.map((h) => h.compliance);
  const pressureTrend = history.map((h) => h.competitive_pressure * 10);
  const rivalValuationTrend = history.map((h) => (h.rival_valuation ?? 0) / 1_000_000);
  const leaderboard = game.leaderboard || [];
  const rivalStatus = game.rival_status || "not-run";
  const finalStats = game.final_stats;
  const epilogue = game.epilogue;
  const isPausedByOverlay = isPausedByEvent || isCompleted || isLeader || isShutdown;
  const roundedValuationMillions = finalStats
    ? Math.round(finalStats.valuation / 10_000) / 100
    : 0;

  return (
    <main className={`shell ${isShutdown ? "danger-mode" : ""} ${isPausedByOverlay ? "paused" : ""}`}>
      <div className="ambient-grid" />
      <div className="ambient-glow" />

      <header className="topbar">
        <div className="title-block">
          <p className="kicker">PIXEL STRATEGY // AI FOUNDRY</p>
          <h1>
            {state.name}
            <span className="blink-dot" />
          </h1>
          <p className="subtitle">
            YEAR {state.year} · Q{state.quarter} · STATUS {game.status.toUpperCase()}
          </p>
        </div>
        <div className="title-controls">
          <div className={`ai-badge ${isShutdown ? "danger" : ""}`}>
            {isShutdown ? "AI CORE OFFLINE" : "AI CORE ONLINE"}
          </div>
          <div className="title-actions">
            <button className="btn ghost" onClick={() => void handleLogout()} disabled={actionLoading}>
              LOGOUT
            </button>
            <button className="btn ghost" onClick={() => void openHistory()} disabled={actionLoading}>
              HISTORY
            </button>
            <button className="btn ghost" onClick={() => void createGame()} disabled={actionLoading || isPausedByOverlay}>
              NEW RUN
            </button>
          </div>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="dashboard-grid">
        <section className="metrics-grid panel-metrics">
          <article className="metric-card metric-card-primary">
            <label>CASH</label>
            <h2 className={moneyValueClass(state.cash)}>{formatMoney(state.cash)}</h2>
          </article>
          <article className="metric-card metric-card-primary">
            <label>VALUATION</label>
            <h2 className={moneyValueClass(state.valuation)}>{formatMoney(state.valuation)}</h2>
          </article>
          <article className={`metric-card metric-card-secondary ${isReputationLow ? "metric-card-danger" : ""}`}>
            <label>REPUTATION</label>
            <h2>{state.reputation.toFixed(1)}</h2>
          </article>
          <article className={`metric-card metric-card-secondary ${isComplianceLow ? "metric-card-danger" : ""}`}>
            <label>COMPLIANCE</label>
            <h2>{state.compliance.toFixed(1)}</h2>
          </article>
        </section>

        <section className="budget-card panel-budget">
          <div className="budget-line">
            <span>R&D ENERGY BUDGET</span>
            <strong>
              {formatMoney(game.budget.spent)} / {formatMoney(game.budget.cap)}
            </strong>
          </div>
          <div className="budget-track">
            <div className="budget-fill" style={{ width: `${budgetUsedRatio}%` }} />
          </div>
          <p>{formatMoney(game.budget.remaining)} REMAINING THIS QUARTER</p>
        </section>

        <section className="models-grid panel-models">
          {state.models.map((model, modelIndex) => (
            <article className="model-card" key={model.name}>
              <h3>{model.name}</h3>
              <p className="model-levels">
                CAP {model.capability} · SAF {model.safety} · EFF {model.efficiency} · MKT {model.market}
              </p>
              <p className="model-age">LIVE FOR {model.quarters_live} QUARTERS</p>
              <div className="upgrade-buttons">
                {UPGRADE_TYPES.map((upgradeType) => {
                  const upgradeCost = nextUpgradeCost(model, upgradeType);
                  const unaffordable = upgradeCost > game.budget.remaining;
                  return (
                  <button
                    key={upgradeType}
                    className="btn upgrade"
                    onClick={() => void applyUpgrade(modelIndex, upgradeType)}
                    disabled={actionLoading || !!pending || isGameOver || isPausedByOverlay || unaffordable}
                    title={`Upgrade ${upgradeType} for ${formatMoney(upgradeCost)}`}
                  >
                    <span className="upgrade-label">+ {UPGRADE_SHORT_LABELS[upgradeType]}</span>
                    <span className="upgrade-cost">{formatCompactMoney(upgradeCost)}</span>
                  </button>
                  );
                })}
              </div>
            </article>
          ))}
        </section>

        <section className="ops-grid panel-ops">
          <article className="log-card">
            <h3>COMMAND LOG</h3>
            {game.budget.actions.length === 0 ? (
              <p>NO UPGRADES ISSUED THIS QUARTER.</p>
            ) : (
              <ul>
                {game.budget.actions.slice(-5).map((entry) => (
                  <li key={entry}>{entry.toUpperCase()}</li>
                ))}
              </ul>
            )}
          </article>

          <article className="warnings-card">
            <h3>STRATEGY SIGNALS</h3>
            <ul>
              {(game.challenge_flags || []).map((flag) => (
                <li key={flag}>{flag.toUpperCase()}</li>
              ))}
            </ul>
          </article>

          <article className="leaderboard-card">
            <h3>LEADERBOARD (YOU VS RIVAL)</h3>
            <p className="leaderboard-note">Ranked by valuation.</p>
            <p className="leaderboard-note">Rival status: {rivalStatus.toUpperCase()}</p>
            <table>
              <thead>
                <tr>
                  <th>RANK</th>
                  <th>TEAM</th>
                  <th>VALUATION</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map((entry, index) => (
                  <tr key={entry.name} className={entry.isPlayer ? "player-row" : "rival-row"}>
                    <td>#{entry.rank || index + 1}</td>
                    <td>{entry.isPlayer ? `${entry.name} (YOU)` : entry.name}</td>
                    <td>{formatCompactMoney(entry.valuation)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </article>
        </section>

        <section className="analytics-grid panel-analytics">
          <Sparkline values={revenueTrend} color="#61c7ff" title="REVENUE TREND (M)" />
          <Sparkline values={profitTrend} color="#89deff" title="PROFIT TREND (M)" />
          <Sparkline values={reputationTrend} color="#6dffce" title="REPUTATION" />
          <Sparkline values={complianceTrend} color="#73b7ff" title="COMPLIANCE" />
          <Sparkline values={pressureTrend} color="#ffab8f" title="COMPETITIVE PRESSURE x10" />
          <Sparkline values={rivalValuationTrend} color="#ff7fc8" title="RIVAL VALUATION (M)" />
        </section>

        <section className="model-metrics-grid panel-model-metrics">
          {modelMetrics.map((metric) => (
            <article className="model-metric-card" key={metric.name}>
              <h3>{metric.name}</h3>
              <div className="metric-row">
                <span>Performance</span>
                <strong>{metric.performance.toFixed(1)}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill bar-performance" style={{ width: `${clamp(metric.performance, 0, 100)}%` }} />
              </div>
              <div className="metric-row">
                <span>Reliability</span>
                <strong>{metric.reliability.toFixed(1)}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill bar-reliability" style={{ width: `${clamp(metric.reliability, 0, 100)}%` }} />
              </div>
              <div className="metric-row">
                <span>Risk</span>
                <strong>{metric.risk.toFixed(1)}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill bar-risk" style={{ width: `${clamp(metric.risk, 0, 100)}%` }} />
              </div>
            </article>
          ))}
        </section>

        <section className="action-panel panel-action">
          {isShutdown ? (
            <div className="shutdown-card">
              <h3>COMPANY SHUTDOWN</h3>
              <p>
                Reputation and compliance both dropped below 50. Regulators and customers forced
                a shutdown.
              </p>
              <p>
                FINAL HEALTH: REP {state.reputation.toFixed(1)} / COMP {state.compliance.toFixed(1)}
              </p>
              <button className="btn primary" onClick={() => void createGame()} disabled={actionLoading || isPausedByOverlay}>
                START NEW RUN
              </button>
            </div>
          ) : isCompleted || isLeader ? null : !pending ? (
            <button
              className="btn primary"
              onClick={() => void runQuarter()}
              disabled={actionLoading || isGameOver || isPausedByOverlay}
            >
              {actionLoading ? "SIMULATING..." : "RUN QUARTER"}
            </button>
          ) : (
            <div className="report-card">
              <h3>BOARD EVALUATION REPORT</h3>
              <div className="report-grid">
                <p>REVENUE: <strong>{formatMoney(pending.revenue)}</strong></p>
                <p>NET PROFIT: <strong>{formatMoney(pending.net_profit)}</strong></p>
                <p>INCIDENTS: <strong>{pending.incidents}</strong></p>
                <p>RUNWAY: <strong>{pending.runway_quarters.toFixed(1)} QUARTERS</strong></p>
                <p>
                  SCORE:
                  <strong className={scoreClass(pending.score)}>
                    {` ${pending.score.toFixed(1)} (${pending.band})`}
                  </strong>
                </p>
                <p>DILUTION: <strong>{(pending.dilution * 100).toFixed(2)}%</strong></p>
              </div>
              <p className="funding-offer">
                OFFER: {formatMoney(pending.raise_amount)} AT {formatMoney(pending.pre_money)} PRE-MONEY
              </p>
              <div className="funding-actions">
                <button className="btn primary" onClick={() => void decideFunding(true)} disabled={actionLoading || isPausedByOverlay}>
                  ACCEPT FUNDING
                </button>
                <button className="btn ghost" onClick={() => void decideFunding(false)} disabled={actionLoading || isPausedByOverlay}>
                  DECLINE FUNDING
                </button>
              </div>
            </div>
          )}
        </section>
      </div>

      {isPausedByEvent ? (
        <div className="event-modal-backdrop" role="dialog" aria-modal="true" aria-label="Quarterly world event">
          <article className="event-modal">
            <p className="event-kicker">NEW WORLD EVENT</p>
            <h2>{activeEvent.title}</h2>
            <p>{activeEvent.description}</p>
            <p className="event-impact-line">Impact: {activeEvent.impact}</p>
            <button className="btn primary" onClick={() => setEventModalOpen(false)}>
              ACKNOWLEDGE EVENT
            </button>
          </article>
        </div>
      ) : null}

      {isShutdown ? (
        <div className="shutdown-modal-backdrop" role="dialog" aria-modal="true" aria-label="Company shutdown">
          <article className="shutdown-modal">
            <p className="event-kicker">END OF RUN</p>
            <h2>COMPANY SHUTDOWN</h2>
            <p>Reputation and compliance dropped below the survival threshold.</p>
            <p className="event-impact-line">
              Final health: REP {state.reputation.toFixed(1)} / COMP {state.compliance.toFixed(1)}
            </p>
            <button className="btn primary" onClick={() => void createGame()} disabled={actionLoading}>
              START NEW RUN
            </button>
          </article>
        </div>
      ) : null}

      {isCompleted || isLeader ? (
        <div className="completion-modal-backdrop" role="dialog" aria-modal="true" aria-label="Run complete">
          <article className="completion-modal">
            <p className="completion-kicker">END OF RUN</p>
            <h2>{isLeader ? "VICTORY - MARKET LEADER" : "RUN COMPLETE"}</h2>
            {finalStats ? (
              <div className="completion-stats-grid">
                <div className="completion-stat-card">
                  <span>VALUATION</span>
                  <strong>{roundedValuationMillions.toFixed(2)}</strong>
                </div>
                <div className="completion-stat-card">
                  <span>REPUTATION</span>
                  <strong>{finalStats.reputation.toFixed(1)}</strong>
                </div>
                <div className="completion-stat-card">
                  <span>COMPLIANCE</span>
                  <strong>{finalStats.compliance.toFixed(1)}</strong>
                </div>
              </div>
            ) : null}
            <div className="completion-epilogue-box">
              {epilogue ? <p>{epilogue}</p> : <p>EPILOGUE LOADING...</p>}
            </div>
            <button className="btn primary" onClick={() => void createGame()} disabled={actionLoading}>
              START NEW RUN
            </button>
          </article>
        </div>
      ) : null}

      {historyOpen ? (
        <div className="history-modal-backdrop" role="dialog" aria-modal="true" aria-label="Run history">
          <article className="history-modal">
            <div className="history-modal-head">
              <h2>RUN HISTORY</h2>
              <button className="btn ghost" onClick={() => setHistoryOpen(false)}>
                CLOSE
              </button>
            </div>
            {historyLoading ? (
              <p className="history-empty">Loading history...</p>
            ) : historyItems.length === 0 ? (
              <p className="history-empty">No past runs yet.</p>
            ) : (
              <div className="history-table-wrap">
                <table className="history-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Company</th>
                      <th>Valuation</th>
                      <th>Reputation</th>
                      <th>Compliance</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyItems.map((item, idx) => (
                      <tr key={`${item.finished_at}-${idx}`}>
                        <td>{new Date(item.finished_at).toLocaleString()}</td>
                        <td>{item.company_name}</td>
                        <td>{formatCompactMoney(item.valuation)}</td>
                        <td>{Number(item.reputation).toFixed(1)}</td>
                        <td>{Number(item.compliance).toFixed(1)}</td>
                        <td>{String(item.status || "").toUpperCase()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </div>
      ) : null}
    </main>
  );
}

export default App;
