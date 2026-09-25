import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { api } from "../api.js";
import { ConfidenceBar, LoadingCard, ErrorCard, DropIcon } from "../components/ui.jsx";

/* The trend may arrive as plain numbers or as objects — handle both. */
function normalizeTrend(trend) {
  if (!Array.isArray(trend)) return [];
  return trend
    .map((item, i) => {
      if (typeof item === "number") return { label: `${i + 1}`, value: item };
      const o = item ?? {};
      const label = o.date ?? o.timestamp ?? o.day ?? o.label ?? `${i + 1}`;
      const value = o.soil_moisture ?? o.soil_moisture_pct ?? o.moisture ?? o.value ?? o.reading;
      return {
        label: String(label).slice(0, 10),
        value: typeof value === "number" ? value : null,
      };
    })
    .filter((p) => p.value !== null);
}

function normalizePast(list) {
  if (!Array.isArray(list)) return [];
  return list
    .map((r) => {
      const o = r ?? {};
      const date = o.date ?? o.created_at ?? o.timestamp ?? o.time;
      const action = o.action ?? o.title ?? o.recommendation ?? o.advice ?? "Advice";
      const conf = o.confidence_pct ?? o.confidence;
      const n = Number(conf);
      return {
        date: date ? String(date) : "",
        action: String(action),
        confidence: Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : null,
      };
    })
    .slice()
    .reverse(); // most recent first
}

function fmtDate(d) {
  if (!d) return "Earlier";
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return d;
  return dt.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function History({ farmerId }) {
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    api
      .getHistory(farmerId)
      .then(setHistory)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [farmerId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <LoadingCard label="Loading your farm's history…" />;
  if (error) return <ErrorCard message={error} onRetry={load} />;

  const trend = normalizeTrend(history?.soil_moisture_trend);
  const past = normalizePast(history?.past_recommendations);

  return (
    <div className="screen">
      <div className="glass card intro-card">
        <h1>Your farm's story</h1>
        <p className="muted">How the soil moisture has changed, and the advice we gave you.</p>
      </div>

      <section className="glass card chart-card">
        <div className="card-kicker">
          <DropIcon size={16} /> Soil moisture over time
        </div>
        {trend.length > 1 ? (
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={trend} margin={{ top: 10, right: 10, bottom: 0, left: -18 }}>
                <CartesianGrid stroke="rgba(13,59,38,0.12)" strokeDasharray="4 4" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#2e5540" }} tickLine={false} />
                <YAxis
                  tick={{ fontSize: 11, fill: "#2e5540" }}
                  tickLine={false}
                  domain={["dataMin - 5", "dataMax + 5"]}
                />
                <Tooltip
                  contentStyle={{
                    background: "rgba(255,255,255,0.92)",
                    border: "1px solid rgba(13,59,38,0.15)",
                    borderRadius: 12,
                    fontSize: 13,
                  }}
                  formatter={(v) => [`${Math.round(v)}%`, "Moisture"]}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#1e8c4e"
                  strokeWidth={3}
                  dot={{ r: 3, fill: "#1e8c4e" }}
                  activeDot={{ r: 5 }}
                  isAnimationActive={true}
                  animationDuration={1200}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : trend.length === 1 ? (
          <p className="muted">We have one reading so far — the line chart will appear as more readings come in.</p>
        ) : (
          <p className="muted">No moisture readings yet. Check back after your first day with FarmSense.</p>
        )}
      </section>

      <section className="glass card">
        <div className="card-kicker">Past advice</div>
        {past.length > 0 ? (
          <ul className="history-list">
            {past.map((p, i) => (
              <li key={i} className="history-item">
                <div className="hi-main">
                  <span className="hi-date">{fmtDate(p.date)}</span>
                  <span className="hi-action">{p.action}</span>
                </div>
                {p.confidence !== null && (
                  <div className="hi-confidence">
                    <ConfidenceBar value={p.confidence} />
                    <span className="confidence-num small">{p.confidence}%</span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">You have not received any advice yet — your first recommendation will appear here.</p>
        )}
      </section>
    </div>
  );
}
