import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const UPGRADE_TYPES = ["capability", "safety", "efficiency", "market"];

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

function scoreClass(score) {
  if (score >= 82) return "score-outstanding";
  if (score >= 68) return "score-strong";
  if (score >= 55) return "score-stable";
  if (score >= 42) return "score-risky";
  return "score-critical";
}

function sparklinePoints(values, width = 280, height = 84, padding = 8) {
  if (!values.length) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  return values
    .map((value, index) => {
      const x = padding + (index / Math.max(1, values.length - 1)) * (width - padding * 2);
      const normalized = (value - min) / range;
      const y = height - padding - normalized * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");
}

function Sparkline({ values, color, title }) {
  const chartValues = values.length ? values : [0, 0];
  const points = sparklinePoints(chartValues);
  const latest = chartValues[chartValues.length - 1] ?? 0;
  return (
    <article className="spark-card">
      <div className="spark-head">
        <span>{title}</span>
        <strong>{Number(latest).toFixed(1)}</strong>
      </div>
      <svg viewBox="0 0 280 84" preserveAspectRatio="none" className="spark-svg" role="img" aria-label={title}>
        <polyline points={points} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    </article>
  );
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
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
  const [game, setGame] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void createGame();
  }, []);

  async function createGame() {
    try {
      setLoading(true);
      setError("");
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
    if (!game || actionLoading) return;
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
    if (!game || actionLoading) return;
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
    if (!game || actionLoading) return;
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

  const budgetUsedRatio = useMemo(() => {
    if (!game?.budget?.cap) return 0;
    return Math.min(100, Math.round((game.budget.spent / game.budget.cap) * 100));
  }, [game]);

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
  const isShutdown = game.status === "shutdown";
  const isGameOver = game.status !== "active";
  const history = game.history || [];
  const modelMetrics = game.model_metrics || [];

  const revenueTrend = history.map((h) => h.revenue / 1_000_000);
  const profitTrend = history.map((h) => h.net_profit / 1_000_000);
  const reputationTrend = history.map((h) => h.reputation);
  const complianceTrend = history.map((h) => h.compliance);
  const pressureTrend = history.map((h) => h.competitive_pressure * 10);

  return (
    <main className={`shell ${isShutdown ? "danger-mode" : ""}`}>
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
          <button className="btn ghost" onClick={() => void createGame()} disabled={actionLoading}>
            NEW RUN
          </button>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="metrics-grid">
        <article className="metric-card">
          <label>CASH</label>
          <h2>{formatMoney(state.cash)}</h2>
        </article>
        <article className="metric-card">
          <label>VALUATION</label>
          <h2>{formatMoney(state.valuation)}</h2>
        </article>
        <article className="metric-card">
          <label>REPUTATION</label>
          <h2>{state.reputation.toFixed(1)}</h2>
        </article>
        <article className="metric-card">
          <label>COMPLIANCE</label>
          <h2>{state.compliance.toFixed(1)}</h2>
        </article>
      </section>

      <section className="budget-card">
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

      <section className="models-grid">
        {state.models.map((model, modelIndex) => (
          <article className="model-card" key={model.name}>
            <h3>{model.name}</h3>
            <p className="model-levels">
              CAP {model.capability} · SAF {model.safety} · EFF {model.efficiency} · MKT {model.market}
            </p>
            <p className="model-age">LIVE FOR {model.quarters_live} QUARTERS</p>
            <div className="upgrade-buttons">
              {UPGRADE_TYPES.map((upgradeType) => (
                <button
                  key={upgradeType}
                  className="btn upgrade"
                  onClick={() => void applyUpgrade(modelIndex, upgradeType)}
                  disabled={actionLoading || !!pending || isGameOver}
                >
                  + {upgradeType.toUpperCase()}
                </button>
              ))}
            </div>
          </article>
        ))}
      </section>

      <section className="log-card">
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
      </section>

      <section className="warnings-card">
        <h3>STRATEGY SIGNALS</h3>
        <ul>
          {(game.challenge_flags || []).map((flag) => (
            <li key={flag}>{flag.toUpperCase()}</li>
          ))}
        </ul>
      </section>

      <section className="analytics-grid">
        <Sparkline values={revenueTrend} color="#61c7ff" title="REVENUE TREND (M)" />
        <Sparkline values={profitTrend} color="#89deff" title="PROFIT TREND (M)" />
        <Sparkline values={reputationTrend} color="#6dffce" title="REPUTATION" />
        <Sparkline values={complianceTrend} color="#73b7ff" title="COMPLIANCE" />
        <Sparkline values={pressureTrend} color="#ffab8f" title="COMPETITIVE PRESSURE x10" />
      </section>

      <section className="model-metrics-grid">
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
              <span>Balance</span>
              <strong>{metric.balance.toFixed(1)}</strong>
            </div>
            <div className="bar-track">
              <div className="bar-fill bar-balance" style={{ width: `${clamp(metric.balance, 0, 100)}%` }} />
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

      <section className="action-panel">
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
            <button className="btn primary" onClick={() => void createGame()} disabled={actionLoading}>
              START NEW RUN
            </button>
          </div>
        ) : !pending ? (
          <button
            className="btn primary"
            onClick={() => void runQuarter()}
            disabled={actionLoading || isGameOver}
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
              <button className="btn primary" onClick={() => void decideFunding(true)} disabled={actionLoading}>
                ACCEPT FUNDING
              </button>
              <button className="btn ghost" onClick={() => void decideFunding(false)} disabled={actionLoading}>
                DECLINE FUNDING
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

export default App;
