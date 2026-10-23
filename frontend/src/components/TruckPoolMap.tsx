import { Lock, MapPin, Truck } from "lucide-react";
import { useMemo } from "react";

import type { PoolLot, PoolView } from "../api/client";
import { cn, kg, tk } from "../lib/format";
import { setState, useAppState } from "../state/store";
import { Badge, Panel, ProgressBar } from "./ui";

const R = 128;
const C = 150;

function angleOf(farmerId: string): number {
  let h = 0;
  for (const ch of farmerId) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return ((h % 3600) / 3600) * Math.PI * 2;
}

function LotDot({ lot, radiusKm }: { lot: PoolLot; radiusKm: number }) {
  const a = angleOf(lot.farmer_id);
  const r = (Math.min(lot.distance_km, radiusKm) / radiusKm) * R;
  const x = C + r * Math.cos(a);
  const y = C + r * Math.sin(a);
  const size = 3 + Math.sqrt(lot.weight_kg) / 6;
  const fill = lot.grade === "A" ? "#3fa97c" : lot.grade === "B" ? "#e58f2b" : "#f2545b";
  return (
    <g>
      <line x1={C} y1={C} x2={x} y2={y} stroke={fill} strokeOpacity={0.18} strokeDasharray="2 3" />
      {lot.source === "farmer" && (
        <circle cx={x} cy={y} r={size + 6} fill="none" stroke="#3fa97c" strokeWidth={1.5} className="animate-pulse-soft" />
      )}
      <circle cx={x} cy={y} r={size} fill={fill} fillOpacity={0.9} stroke="#0a1913" strokeWidth={1}>
        <title>{`${lot.farmer_id}: ${lot.weight_kg} kg Grade-${lot.grade}, ${lot.distance_km} km`}</title>
      </circle>
    </g>
  );
}

export function TruckPoolMap({ className }: { className?: string }) {
  const pools = useAppState((s) => s.pools);
  const focusId = useAppState((s) => s.focusPoolId);
  const pool: PoolView | undefined = useMemo(() => pools.find((p) => p.pool_id === focusId) ?? pools[0], [pools, focusId]);

  return (
    <Panel
      className={className}
      icon={<Truck className="size-4 text-amber-300" />}
      title={pool ? `5-Ton Union Truck Pool · ${pool.upazila}, ${pool.district}` : "5-Ton Union Truck Pool"}
      actions={
        <select
          value={pool?.pool_id ?? ""}
          onChange={(e) => setState({ focusPoolId: e.target.value })}
          className="rounded-md bg-ink-800 px-1.5 py-0.5 text-[11px] text-slate-200 ring-1 ring-ink-600"
          aria-label="Select truck pool"
        >
          {pools.map((p) => <option key={p.pool_id} value={p.pool_id}>{p.pool_id}</option>)}
        </select>
      }
      bodyClassName="flex flex-col gap-2"
    >
      {!pool ? (
        <div className="py-10 text-center text-xs text-slate-500">Loading pools…</div>
      ) : (
        <>
          <div className="relative mx-auto w-full max-w-[300px]">
            <svg viewBox="0 0 300 300" className="w-full" role="img" aria-label={`Radar of ${pool.smallholders} micro-lots within ${pool.union_radius_km} km`}>
              <defs>
                <radialGradient id="radarBg" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#122a21" />
                  <stop offset="100%" stopColor="#0b1b15" />
                </radialGradient>
                <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#3fa97c" stopOpacity="0" />
                  <stop offset="100%" stopColor="#3fa97c" stopOpacity="0.35" />
                </linearGradient>
              </defs>
              <circle cx={C} cy={C} r={R} fill="url(#radarBg)" stroke="#21443a" />
              {[1, 2, 3, 4].map((ring) => (
                <circle key={ring} cx={C} cy={C} r={(R * ring) / 5} fill="none" stroke="#21443a" strokeDasharray="3 4" />
              ))}
              <line x1={C - R} y1={C} x2={C + R} y2={C} stroke="#21443a" />
              <line x1={C} y1={C - R} x2={C} y2={C + R} stroke="#21443a" />
              <g className="origin-center animate-sweep" style={{ transformOrigin: "150px 150px" }}>
                <path d={`M ${C} ${C} L ${C + R} ${C} A ${R} ${R} 0 0 0 ${C + R * Math.cos(-0.6)} ${C + R * Math.sin(-0.6)} Z`} fill="url(#sweep)" />
              </g>
              {pool.lots.map((lot) => <LotDot key={lot.farmer_id} lot={lot} radiusKm={pool.union_radius_km} />)}
              <circle cx={C} cy={C} r={9} fill={pool.status === "DISPATCHED" ? "#cf7616" : "#158a60"} />
              <text x={C} y={C + 3.5} textAnchor="middle" fontSize="9" fontWeight="700" fill="#0a1913">5T</text>
              <text x={C + R - 4} y={C - 4} textAnchor="end" fontSize="9" fill="#7d9285">{pool.union_radius_km} km</text>
            </svg>
            <div className="absolute left-1 top-1 flex items-center gap-1 text-[10px] text-slate-400">
              <MapPin className="size-3" /> {pool.union}
            </div>
          </div>

          <div>
            <div className="mb-1 flex items-baseline justify-between text-xs">
              <span className="font-mono font-semibold text-slate-100">{kg(pool.loaded_kg)} / {kg(pool.capacity_kg)}</span>
              {pool.status === "DISPATCHED" ? (
                <Badge tone="amber"><Lock className="size-3" /> DISPATCH LOCKED</Badge>
              ) : (
                <span className="text-slate-400">{kg(pool.remaining_kg)} to fill</span>
              )}
            </div>
            <ProgressBar value={pool.loaded_kg} max={pool.capacity_kg} tone={pool.status === "DISPATCHED" ? "amber" : "emerald"} />
            <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px]">
              <Badge tone="emerald">{pool.smallholders} micro-lots pooled</Badge>
              <Badge tone="slate">{pool.roster_size} registered smallholders in union</Badge>
              <Badge tone="slate">{pool.crop}</Badge>
            </div>
          </div>

          {pool.dispatch && (
            <div className={cn("rounded-lg border border-amber-400/30 bg-amber-500/10 p-2 text-[11px] text-amber-100")}>
              <div className="font-semibold">Truck {pool.dispatch.truck_booking_id} → {pool.dispatch.buyer_name}</div>
              <div className="font-mono text-amber-200/80">
                {tk(pool.dispatch.contract_price_tk_per_kg)}/kg · escrow {pool.dispatch.escrow_id} locked {tk(pool.dispatch.escrow_amount_tk, 0)} · ETA {pool.dispatch.eta_hours.toFixed(1)} h
              </div>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
