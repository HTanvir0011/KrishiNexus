/** Arc gauge, fill ring and score dial in the KrishiNexus palette. Numbers use the condensed `.num` face. */

const TRACK = "rgb(157 176 163 / 0.22)";

function arcPoint(cx: number, cy: number, r: number, t: number): [number, number] {
  const angle = Math.PI - t * Math.PI;
  return [cx + r * Math.cos(angle), cy - r * Math.sin(angle)];
}

function arcPath(cx: number, cy: number, r: number, from: number, to: number): string {
  const [x1, y1] = arcPoint(cx, cy, r, from);
  const [x2, y2] = arcPoint(cx, cy, r, to);
  return `M${x1.toFixed(2)} ${y1.toFixed(2)} A${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

/** Half-circle gauge with a target band (e.g. 48–50 °F) in flag green and a mustard needle. */
export function ArcGauge({ value, min, max, band, unit, label, alarm = false, className }: {
  value: number;
  min: number;
  max: number;
  band: [number, number];
  unit: string;
  label: string;
  alarm?: boolean;
  className?: string;
}) {
  const clamp = (v: number) => Math.min(1, Math.max(0, (v - min) / (max - min)));
  const [nx, ny] = arcPoint(130, 140, 80, clamp(value));
  return (
    <svg viewBox="0 0 260 165" className={className} role="img" aria-label={label}>
      <path d={arcPath(130, 140, 100, 0, 1)} stroke={TRACK} strokeWidth={14} fill="none" strokeLinecap="round" />
      <path d={arcPath(130, 140, 100, clamp(band[0]), clamp(band[1]))} stroke="#006a4e" strokeWidth={14} fill="none" />
      <line x1={130} y1={140} x2={nx} y2={ny} stroke={alarm ? "#f2545b" : "#edb723"} strokeWidth={3} strokeLinecap="round"
        style={{ transition: "all 0.6s cubic-bezier(0.2, 0.8, 0.2, 1)" }} />
      <circle cx={130} cy={140} r={6} fill={alarm ? "#f2545b" : "#edb723"} />
      <text x={30} y={162} fill="#9db0a3" fontSize={12} textAnchor="middle">{min}{unit}</text>
      <text x={230} y={162} fill="#9db0a3" fontSize={12} textAnchor="middle">{max}{unit}</text>
    </svg>
  );
}

/** Fill ring, e.g. a 5-ton truck at 3,550 of 5,000 kg. */
export function Ring({ value, max, label, className }: { value: number; max: number; label: string; className?: string }) {
  const r = 54;
  const circumference = 2 * Math.PI * r;
  const fraction = Math.min(1, Math.max(0, value / max));
  return (
    <svg viewBox="0 0 132 132" className={className} role="img" aria-label={label}>
      <circle cx={66} cy={66} r={r} stroke={TRACK} strokeWidth={12} fill="none" />
      <circle cx={66} cy={66} r={r} stroke="#edb723" strokeWidth={12} fill="none" strokeLinecap="round"
        strokeDasharray={`${(fraction * circumference).toFixed(1)} ${circumference.toFixed(1)}`} transform="rotate(-90 66 66)"
        style={{ transition: "stroke-dasharray 0.7s ease-out" }} />
      <text x={66} y={70} textAnchor="middle" fill="#efebdd" fontSize={30} fontWeight={600} style={{ fontStretch: "75%" }}>
        {Math.round(fraction * 100)}%
      </text>
    </svg>
  );
}

/** 300–850 agri-credit dial: leaf above 750, turmeric above 650, sun red below. */
export function ScoreDial({ score, className }: { score: number; className?: string }) {
  const t = Math.min(1, Math.max(0, (score - 300) / 550));
  const color = score >= 750 ? "#3fa97c" : score >= 650 ? "#e58f2b" : "#f2545b";
  return (
    <svg viewBox="0 0 200 120" className={className} role="img" aria-label={`Credit score ${score} of 850`}>
      <path d={arcPath(100, 100, 80, 0, 1)} fill="none" stroke={TRACK} strokeWidth={14} strokeLinecap="round" />
      <path d={arcPath(100, 100, 80, 0, t)} fill="none" stroke={color} strokeWidth={14} strokeLinecap="round" />
      <text x={100} y={92} textAnchor="middle" fontSize={34} fontWeight={600} fill="#efebdd" style={{ fontStretch: "75%" }}>{score}</text>
      <text x={100} y={113} textAnchor="middle" fontSize={11} fill="#9db0a3">300 to 850</text>
    </svg>
  );
}
