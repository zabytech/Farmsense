import { useEffect, useState } from "react";

/* ── Loading spinner ─────────────────────────────────────── */
export function Spinner() {
  return <div className="spinner" role="status" aria-label="Loading" />;
}

export function LoadingCard({ label = "Please wait…" }) {
  return (
    <div className="glass card center-card">
      <Spinner />
      <p className="muted">{label}</p>
    </div>
  );
}

/* ── Friendly error state with retry ─────────────────────── */
export function ErrorCard({ message, onRetry }) {
  return (
    <div className="glass card center-card error-card">
      <svg viewBox="0 0 24 24" className="sad-leaf" aria-hidden="true">
        <path
          d="M17 8C8 10 5.9 16.17 3.82 21.34l1.89.66.95-2.3c.48.17.98.3 1.34.3C19 20 22 3 22 3c-1 2-8 2.25-13 3.25S2 11.5 2 13.5s1.75 3.75 1.75 3.75C7 8 17 8 17 8z"
          fill="currentColor"
        />
      </svg>
      <p className="error-text">{message || "Something went wrong. Please try again."}</p>
      {onRetry && (
        <button className="btn btn-primary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

/* ── Animated confidence bar (0–100) ──────────────────────── */
export function ConfidenceBar({ value }) {
  const v = Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  const [w, setW] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setW(v), 120);
    return () => clearTimeout(t);
  }, [v]);
  return (
    <div className="cbar" role="meter" aria-valuenow={v} aria-valuemin={0} aria-valuemax={100}>
      <div className="cbar-fill" style={{ width: `${w}%` }} />
    </div>
  );
}

/* ── Small inline SVG icons ───────────────────────────────── */
const iconProps = { viewBox: "0 0 24 24", "aria-hidden": "true" };

export function SproutIcon({ size = 28, className = "" }) {
  return (
    <svg className={className} width={size} height={size} {...iconProps}>
      <path d="M12 22v-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
      <path d="M12 14C12 9.5 8.8 7 4 7c0 4.5 3.2 7 8 7z" fill="currentColor" />
      <path d="M12 12c0-4.5 3.2-7 8-7 0 4.5-3.2 7-8 7z" fill="currentColor" opacity="0.75" />
    </svg>
  );
}

export function DropIcon({ size = 24, className = "" }) {
  return (
    <svg className={className} width={size} height={size} {...iconProps}>
      <path d="M12 2.7s6.5 7.2 6.5 12a6.5 6.5 0 0 1-13 0C5.5 9.9 12 2.7 12 2.7z" fill="currentColor" />
    </svg>
  );
}

export function BugIcon({ size = 24, className = "" }) {
  return (
    <svg className={className} width={size} height={size} {...iconProps}>
      <ellipse cx="12" cy="13" rx="5.5" ry="7" fill="currentColor" />
      <path d="M12 6V3M8 7 5.5 4.5M16 7l2.5-2.5M6.5 12H3M21 12h-3.5M7 17l-3 2.5M17 17l3 2.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function LeafIcon({ size = 24, className = "" }) {
  return (
    <svg className={className} width={size} height={size} {...iconProps}>
      <path d="M17 8C8 10 5.9 16.17 3.82 21.34l1.89.66.95-2.3c.48.17.98.3 1.34.3C19 20 22 3 22 3c-1 2-8 2.25-13 3.25S2 11.5 2 13.5s1.75 3.75 1.75 3.75C7 8 17 8 17 8z" fill="currentColor" />
    </svg>
  );
}

export function SunIcon({ size = 24, className = "" }) {
  return (
    <svg className={className} width={size} height={size} {...iconProps}>
      <circle cx="12" cy="12" r="4.5" fill="currentColor" />
      <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function PhoneIcon({ size = 22, className = "" }) {
  return (
    <svg className={className} width={size} height={size} {...iconProps}>
      <rect x="6" y="2.5" width="12" height="19" rx="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M10.5 18.5h3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function ChartIcon({ size = 24, className = "" }) {
  return (
    <svg className={className} width={size} height={size} {...iconProps}>
      <path d="M3 20h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M5 16l4-5 3.5 3L19 7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <circle cx="19" cy="7" r="2" fill="currentColor" />
    </svg>
  );
}

export function CameraIcon({ size = 40, className = "" }) {
  return (
    <svg className={className} width={size} height={size} {...iconProps}>
      <rect x="2.5" y="6.5" width="19" height="14" rx="3.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8 6.5 9.5 4h5L16 6.5" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" fill="none" />
      <circle cx="12" cy="13.5" r="4" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="12" cy="13.5" r="1.4" fill="currentColor" />
    </svg>
  );
}

export function RefreshIcon({ size = 20, className = "" }) {
  return (
    <svg className={className} width={size} height={size} {...iconProps}>
      <path d="M20 12a8 8 0 1 1-2.34-5.66" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
      <path d="M20 3v4.5h-4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}
