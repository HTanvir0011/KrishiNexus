import { useMemo } from "react";

/** Seeded PRNG so the mosaic is identical on every load (no unseeded randomness). */
function mulberry32(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const GREENS = ["#173828", "#1b4130", "#204a35", "#143022", "#245039", "#1a3c2b"];
const RIVER = "M-60 640 C 160 560, 300 700, 470 600 S 760 420, 1080 470";

interface Plot { x: number; y: number; w: number; h: number; fill: string }

/**
 * Aerial delta at night: long narrow plots between bunds, a river, dim mustard and water patches.
 * With `highlight`, one plot near (560, 390) is lit mustard inside a dashed 5 km union ring.
 */
export function MosaicSvg({ highlight = false, className }: { highlight?: boolean; className?: string }) {
  const { plots, rahim, neighbours } = useMemo(() => {
    const rand = mulberry32(20261226);
    const angle = (-11 * Math.PI) / 180;
    const dx = 560 - 500, dy = 390 - 400;
    const target = { x: 500 + dx * Math.cos(-angle) - dy * Math.sin(-angle), y: 400 + dx * Math.sin(-angle) + dy * Math.cos(-angle) };
    const list: Plot[] = [];
    let best = Infinity;
    let chosen: Plot | null = null;
    for (let row = -2; row < 13; row++) {
      for (let col = -2; col < 16; col++) {
        const bx = col * 78 + (row % 2) * 24, by = row * 70;
        const strips = 2 + Math.floor(rand() * 4);
        const vertical = rand() > 0.45;
        for (let s = 0; s < strips; s++) {
          const w = vertical ? 74 / strips : 74, h = vertical ? 66 : 66 / strips;
          const x = vertical ? bx + s * w : bx, y = vertical ? by : by + s * h;
          const roll = rand();
          const fill = roll < 0.07 ? "#6f5f22" : roll < 0.12 ? "#16343b" : GREENS[Math.floor(rand() * GREENS.length)];
          const plot = { x, y, w, h, fill };
          list.push(plot);
          const d = Math.hypot(x + w / 2 - target.x, y + h / 2 - target.y);
          if (d < best && w > 14 && h > 14) {
            best = d;
            chosen = plot;
          }
        }
      }
    }
    const near = mulberry32(7);
    const around = chosen
      ? Array.from({ length: 8 }, () => {
        const a = near() * Math.PI * 2, r = 50 + near() * 120;
        return { x: chosen!.x + chosen!.w / 2 + Math.cos(a) * r - 9, y: chosen!.y + chosen!.h / 2 + Math.sin(a) * r - 6 };
      })
      : [];
    return { plots: list, rahim: chosen, neighbours: around };
  }, []);

  return (
    <svg className={className} viewBox="0 0 1000 800" preserveAspectRatio="xMidYMid slice" aria-hidden>
      <g transform="rotate(-11 500 400)">
        {plots.map((p, i) => (
          <rect key={i} x={p.x + 0.8} y={p.y + 0.8} width={Math.max(p.w - 1.6, 1)} height={Math.max(p.h - 1.6, 1)} fill={p.fill} rx={1} />
        ))}
      </g>
      <path d={RIVER} stroke="#1d4a55" strokeWidth={34} fill="none" opacity={0.9} />
      <path d={RIVER} stroke="#6fa8b5" strokeWidth={2} fill="none" opacity={0.35} />
      {highlight && rahim && (
        <g transform="rotate(-11 500 400)">
          <rect x={rahim.x + 0.8} y={rahim.y + 0.8} width={rahim.w - 1.6} height={rahim.h - 1.6} fill="#edb723" rx={1} />
          <circle cx={rahim.x + rahim.w / 2} cy={rahim.y + rahim.h / 2} r={190} fill="none" stroke="#efebdd" strokeOpacity={0.4}
            strokeWidth={1.2} strokeDasharray="3 7" />
          {neighbours.map((n, i) => (
            <rect key={i} x={n.x} y={n.y} width={18} height={12} fill="none" stroke="#edb723" strokeWidth={1.4} rx={1} />
          ))}
        </g>
      )}
    </svg>
  );
}
