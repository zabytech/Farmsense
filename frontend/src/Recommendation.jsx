import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import {
  ConfidenceBar,
  DropIcon,
  BugIcon,
  LeafIcon,
  SunIcon,
  PhoneIcon,
  RefreshIcon,
  LoadingCard,
  ErrorCard,
} from "../components/ui.jsx";

/* ── Helpers ───────────────────────────────────────────────── */

function urgencyOf(rec) {
  const text = `${rec?.time_window ?? ""} ${rec?.action ?? ""} ${rec?.urgency ?? ""}`.toLowerCase();
  const hours = text.match(/(\d+)\s*(hours?|hrs?|h\b)/);
  const days = text.match(/(\d+)\s*days?/);
  if (hours) return Number(hours[1]) <= 6 ? "high" : "medium";
  if (days) return Number(days[1]) <= 1 ? "high" : "low";
  if (/urgent|immediately|right now|asap/.test(text)) return "high";
  if (/irrigate|water|spray|pest|fertiliz|treat/.test(text)) return "medium";
  return "low";
}

function actionIcon(action) {
  const a = String(action || "").toLowerCase();
  if (/irrigat|water|watering/.test(a)) return <DropIcon size={52} className="hero-icon" />;
  if (/pest|insect|disease|spray|fung|blight|rot/.test(a)) return <BugIcon size={52} className="hero-icon" />;
  if (/harvest|sun|dry|wait|monitor|no action/.test(a)) return <SunIcon size={52} className="hero-icon" />;
  return <LeafIcon size={52} className="hero-icon" />;
}

function soilStatus(moisture) {
  const m = Number(moisture);
  if (!Number.isFinite(m)) return null;
  if (m < 30) return "very dry";
  if (m < 45) return "a bit dry";
  if (m < 60) return "just right";
  if (m < 75) return "a bit wet";
  return "too wet";
}

function confidenceOf(rec) {
  const n = Number(rec?.confidence_pct ?? rec?.confidence);
  return Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : 0;
}

function factorsOf(rec) {
  const rf = rec?.reasoning_factors;
  if (!rf) return [];
  if (Array.isArray(rf)) return rf.map(String);
  if (typeof rf === "object") return Object.entries(rf).map(([k, v]) => `${k}: ${v}`);
  return [String(rf)];
}

/* ── Screen ─────────────────────────────────────────────────── */

export default function Recommendation({ farmerId }) {
  const [rec, setRec] = useState(null);
  const [env, setEnv] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [whyOpen, setWhyOpen] = useState(false);
  const [smsState, setSmsState] = useState("idle"); // idle | sending | done | failed

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setSmsState("idle");
    setWhyOpen(false);
    try {
      const data = await api.getRecommendation(farmerId);
      setRec(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
    // Environment is context only — its failure must never block the advice.
    api
      .getEnvironment(farmerId)
      .then(setEnv)
      .catch(() => setEnv(null));
  }, [farmerId]);

  useEffect(() => {
    load();
  }, [load]);

  const sendSms = async () => {
    setSmsState("sending");
    try {
      const res = await api.sendSms(farmerId);
      const s = String(res?.status ?? "").toLowerCase();
      if (["sent", "queued", "success", "ok", "delivered", "scheduled", "pending"].includes(s)) {
        setSmsState("done");
      } else {
        setSmsState("failed");
      }
    } catch {
      setSmsState("failed");
    }
  };

  if (loading) return <LoadingCard label="Getting your farm's advice…" />;
  if (error) return <ErrorCard message={error} onRetry={load} />;
  if (!rec) return <ErrorCard message="No advice was found for your farm." onRetry={load} />;

  const urgency = urgencyOf(rec);
  const factors = factorsOf(rec);
  const confidence = confidenceOf(rec);
  const soil = soilStatus(env?.soil_moisture_pct ?? rec?.soil_moisture_pct);
  const temp = Number(env?.temperature);
  const humidity = Number(env?.humidity);

  return (
    <div className="screen">
      {/* Environment summary — small, contextual, never competing */}
      {(Number.isFinite(temp) || Number.isFinite(humidity) || soil) && (
        <div className="env-strip glass" aria-label="Current conditions at your farm">
          <span className="env-item">
            <SunIcon size={16} />
            {Number.isFinite(temp) ? `${Math.round(temp)}°` : "—"}
          </span>
          {Number.isFinite(humidity) && <span className="env-divider">•</span>}
          {Number.isFinite(humidity) && <span className="env-item">Humidity {Math.round(humidity)}%</span>}
          {soil && (
            <>
              <span className="env-divider">•</span>
              <span className="env-item">
                <DropIcon size={14} /> Soil: {soil}
              </span>
            </>
          )}
        </div>
      )}

      {/* 1 — The action: biggest, boldest element */}
      <section className={`glass card hero urgency-${urgency}`} aria-label="Recommended action">
        <div className="hero-emoji">{actionIcon(rec.action)}</div>
        <h1 className="action">{rec.action || "All looks good"}</h1>
        {rec.time_window ? <div className="window-pill">{rec.time_window}</div> : null}
        <span className={`urgency-dot u-${urgency}`} title={urgency === "high" ? "Needs attention soon" : urgency === "medium" ? "Do this today" : "Can wait"} />
      </section>

      {/* 2 — Plain language explanation */}
      {rec.plain_language_message ? (
        <section className="glass card message-card">
          <p className="plain-message">{rec.plain_language_message}</p>
        </section>
      ) : null}

      {/* 3 — Confidence */}
      <section className="glass card confidence-card">
        <div className="confidence-head">
          <span>How sure we are</span>
          <span className="confidence-num">{confidence}%</span>
        </div>
        <ConfidenceBar value={confidence} />
        <p className="hint">{confidence >= 75 ? "We are quite confident about this advice." : "This is our best guess for now — it will improve as we learn about your farm."}</p>
      </section>

      {/* 4 — Consequence if ignored */}
      {rec.consequence_if_ignored ? (
        <section className="glass card consequence-card" aria-label="What happens if you wait">
          <div className="card-kicker">If you wait too long</div>
          <p className="consequence-text">{rec.consequence_if_ignored}</p>
        </section>
      ) : null}

      {/* 5a — Fertilizer tip (only when present) */}
      {rec.fertilizer_tip ? (
        <section className="glass card tip-card">
          <div className="card-kicker">Fertilizer tip</div>
          <p className="tip-text">{rec.fertilizer_tip}</p>
        </section>
      ) : null}

      {/* 5b — Pest & disease advice (only when present) */}
      {rec.pest_disease_advice ? (
        <section className="glass card pest-card">
          <div className="card-kicker">Pest & disease care</div>
          <p className="tip-text">{rec.pest_disease_advice}</p>
        </section>
      ) : null}

      {/* Why? — transparency, tucked away */}
      {factors.length > 0 && (
        <section className="glass card why-card">
          <button type="button" className="why-toggle" onClick={() => setWhyOpen((o) => !o)} aria-expanded={whyOpen}>
            <span>Why this advice?</span>
            <span className={`chev ${whyOpen ? "open" : ""}`}>▾</span>
          </button>
          {whyOpen && (
            <ul className="why-list fade-slide">
              {factors.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* SMS */}
      <section className="glass card sms-card">
        {smsState === "idle" && (
          <button type="button" className="btn btn-primary" onClick={sendSms}>
            <PhoneIcon size={22} /> Send this to my phone (SMS)
          </button>
        )}
        {smsState === "sending" && (
          <button type="button" className="btn btn-primary" disabled>
            <span className="mini-spinner light" /> Sending…
          </button>
        )}
        {smsState === "done" && <p className="sms-ok">Message sent — check your phone.</p>}
        {smsState === "failed" && (
          <div className="sms-fail">
            <p className="error-text">We could not send the message right now.</p>
            <button type="button" className="btn btn-secondary" onClick={sendSms}>
              Try again
            </button>
          </div>
        )}
      </section>

      <button type="button" className="btn btn-ghost refresh-btn" onClick={load}>
        <RefreshIcon size={18} /> Refresh advice
      </button>
    </div>
  );
}
