/**
 * Animated farm scene behind the app:
 * a softly pulsing sun, drifting clouds, falling leaves,
 * rolling hills and swaying grass — all pure CSS animation.
 */

const LEAVES = [
  { left: "5%", size: 26, dur: 16, delay: 0 },
  { left: "16%", size: 18, dur: 21, delay: 3 },
  { left: "30%", size: 30, dur: 15, delay: 7 },
  { left: "44%", size: 20, dur: 19, delay: 1 },
  { left: "58%", size: 26, dur: 17, delay: 5 },
  { left: "70%", size: 16, dur: 22, delay: 9 },
  { left: "82%", size: 28, dur: 16, delay: 2 },
  { left: "93%", size: 20, dur: 18, delay: 6 },
];

function GrassBlades() {
  return (
    <svg className="grass" viewBox="0 0 1440 140" preserveAspectRatio="none" aria-hidden="true">
      {Array.from({ length: 26 }).map((_, i) => {
        const x = i * 58 + 12;
        const h = 45 + ((i * 37) % 55);
        const lean = i % 2 === 0 ? 10 : -10;
        return (
          <path
            key={i}
            className="blade"
            style={{ animationDelay: `${(i % 7) * 0.45}s` }}
            d={`M ${x} 140 Q ${x + lean} ${140 - h * 0.55} ${x + lean * 1.6} ${140 - h} Q ${x + lean * 0.4} ${140 - h * 0.45} ${x} 140 Z`}
            fill={i % 3 === 0 ? "rgba(22,84,48,0.30)" : "rgba(22,84,48,0.38)"}
          />
        );
      })}
    </svg>
  );
}

export default function Background() {
  return (
    <div className="farm-bg" aria-hidden="true">
      <div className="bg-sky" />
      <div className="bg-sun" />
      <div className="cloud cloud-1" />
      <div className="cloud cloud-2" />
      <div className="cloud cloud-3" />
      {LEAVES.map((l, i) => (
        <div
          key={i}
          className="leaf"
          style={{
            left: l.left,
            width: l.size,
            height: l.size,
            animationDuration: `${l.dur}s`,
            animationDelay: `${l.delay}s`,
          }}
        >
          <svg viewBox="0 0 24 24" width={l.size} height={l.size}>
            <path
              d="M17 8C8 10 5.9 16.17 3.82 21.34l1.89.66.95-2.3c.48.17.98.3 1.34.3C19 20 22 3 22 3c-1 2-8 2.25-13 3.25S2 11.5 2 13.5s1.75 3.75 1.75 3.75C7 8 17 8 17 8z"
              fill="rgba(23,92,51,0.45)"
            />
          </svg>
        </div>
      ))}
      <div className="hill hill-back" />
      <div className="hill hill-front" />
      <GrassBlades />
    </div>
  );
}
