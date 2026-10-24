import { Lock, MapPin, Truck } from "lucide-react";
import { useMemo } from "react";

import type { PoolLot, PoolView } from "../api/client";
import { cn, kg, tk } from "../lib/format";
import { setState, useAppState } from "../state/store";
import { Badge, Panel, ProgressBar } from "./ui";

const R = 128;
const C = 150;
const GRADE_FILL: Record<PoolLot["grade"], string> = { A: "#059669", B: "#d97706", C: "#e11d48" };

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
  const fill = GRADE_FILL[lot.grade];
  return (
    <g>
      <line x1={C} y1={C} x2={x} y2={y} stroke={fill} strokeOpacity={0.25} strokeDasharray="2 3" />
      {lot.source === "farmer" && <circle cx={x} cy={y} r={size + 6} fill="none" stroke="#047857" strokeWidth={1.5} className="animate-pulse-soft" />}
      <circle cx={x} cy={y} r={size} fill={fill} stroke="#ffffff" strokeWidth={1.5}>
        <title>{`${lot.farmer_id}: ${lot.weight_kg} kg Grade-${lot.grade}, ${lot.distance_km} km`}</title>
      </circle>
    </g>
  );
}

export function TruckPoolMap({ className }: { className?: string }) {
  const pools = useAppState((s) => s.pools);
  const focusId = useAppState((s) => s.focusPoolId);
  const voice = useAppState((s) => s.lastVoice);
  const pool: PoolView | undefined = useMemo(() => pools.find((p) => p.pool_id === focusId) ?? pools[0], [pools, focusId]);
  const plan = voice?.orchestration?.state.syndicate_bypass_plan;
  const leg = plan?.pool && pool && plan.pool.pool_id === pool.pool_id ? plan : null;
  const destination = pool?.dispatch?.buyer_name ?? leg?.best_hub_name ?? null;

  return (
    <Panel className={className} icon={<Truck className="size-4 text-amber-600" aria-hidden />}
      title={pool ? `5-ton union truck pool · ${pool.upazila}, ${pool.district}` : "5-ton union truck pool"}
      actions={
        <select value={pool?.pool_id ?? ""} onChange={(e) => setState({ focusPoolId: e.target.value })} aria-label="Select truck pool"
          className="min-h-8 rounded-lg border border-slate-300 bg-white px-2 text-[12.5px] text-slate-800">
          {pools.map((p) => <option key={p.pool_id} value={p.pool_id}>{p.pool_id}</option>)}
        </select>
      }
      bodyClassName="flex flex-col gap-3">
      {!pool ? (
        <div className="py-10 text-center text-[13px] text-slate-500">Loading pools…</div>
      ) : (
        <>
          <div className="relative mx-auto w-full max-w-[280px]">
            <svg viewBox="0 0 300 300" className="w-full" role="img" aria-label={`Radar of ${pool.smallholders} micro-lots within ${pool.union_radius_km} km of the union`}>
              <defs>
                <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#047857" stopOpacity="0" />
                  <stop offset="100%" stopColor="#047857" stopOpacity="0.18" />
                </linearGradient>
              </defs>
              <circle cx={C} cy={C} r={R} fill="#f8faf7" stroke="#cbd5e1" />
              {[1, 2, 3, 4].map((ring) => <circle key={ring} cx={C} cy={C} r={(R * ring) / 5} fill="none" stroke="#e2e8f0" strokeDasharray="3 4" />)}
              <line x1={C - R} y1={C} x2={C + R} y2={C} stroke="#e2e8f0" />
              <line x1={C} y1={C - R} x2={C} y2={C + R} stroke="#e2e8f0" />
              <g className="animate-sweep" style={{ transformOrigin: "150px 150px" }}>
                <path d={`M ${C} ${C} L ${C + R} ${C} A ${R} ${R} 0 0 0 ${C + R * Math.cos(-0.6)} ${C + R * Math.sin(-0.6)} Z`} fill="url(#sweep)" />
              </g>
              {pool.lots.map((lot) => <LotDot key={lot.farmer_id} lot={lot} radiusKm={pool.union_radius_km} />)}
              <circle cx={C} cy={C} r={11} fill={pool.status === "DISPATCHED" ? "#d97706" : "#047857"} />
              <text x={C} y={C + 3.5} textAnchor="middle" fontSize="9" fontWeight="700" fill="#ffffff">5T</text>
              <text x={C + R - 4} y={C - 5} textAnchor="end" fontSize="10" fill="#64748b">{pool.union_radius_km} km</text>
            </svg>
            <div className="absolute top-0 left-0 flex items-center gap-1 text-[12px] text-slate-600"><MapPin className="size-3.5" aria-hidden /> {pool.union}</div>
          </div>
          <div className="flex justify-center gap-3 text-[12px] text-slate-600">
            {(["A", "B", "C"] as const).map((g) => (
              <span key={g} className="flex items-center gap-1"><span className="size-2.5 rounded-full" style={{ background: GRADE_FILL[g] }} /> Grade-{g}</span>
            ))}
          </div>

          <div>
            <div className="mb-1 flex items-baseline justify-between text-[13px]">
              <span className="num text-slate-900">{kg(pool.loaded_kg)} / {kg(pool.capacity_kg)}</span>
              {pool.status === "DISPATCHED"
                ? <Badge tone="amber"><Lock className="size-3" aria-hidden /> Dispatch locked</Badge>
                : <span className="text-slate-600">{kg(pool.remaining_kg)} to fill</span>}
            </div>
            <ProgressBar value={pool.loaded_kg} max={pool.capacity_kg} tone={pool.status === "DISPATCHED" ? "amber" : "emerald"} />
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone="emerald">{pool.smallholders} micro-lots pooled</Badge>
              <Badge tone="slate">{pool.roster_size} farmers in the union</Badge>
              <Badge tone="slate">{pool.crop}</Badge>
            </div>
          </div>

          <dl className="m-0 grid gap-2 rounded-lg bg-slate-50 p-3 text-[12.5px] ring-1 ring-inset ring-slate-200">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Freight</dt>
              <dd className="m-0 text-right text-slate-800">Tk 68/km + Tk 1,500/trip + bridge tolls, + Tk 0.10/kg pooling fee</dd>
            </div>
            {leg && (
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">This lot</dt>
                <dd className="num m-0 text-right text-slate-900">{tk(leg.pooled_transport_tk_per_kg)}/kg freight · {tk(leg.b2b_net_tk_per_kg)}/kg net</dd>
              </div>
            )}
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Destination</dt>
              <dd className={cn("m-0 text-right", destination ? "text-slate-900" : "text-slate-500")}>{destination ?? "chosen when a farmer's decision matches this pool"}</dd>
            </div>
          </dl>

          {pool.dispatch && (
            <div className="rounded-lg bg-amber-100/60 p-3 text-[12.5px] text-amber-900 ring-1 ring-inset ring-amber-600/25">
              <div className="font-semibold">Truck {pool.dispatch.truck_booking_id} → {pool.dispatch.buyer_name}</div>
              <div className="num font-medium text-amber-800">
                {tk(pool.dispatch.contract_price_tk_per_kg)}/kg · escrow {pool.dispatch.escrow_id} locked {tk(pool.dispatch.escrow_amount_tk, 0)} · ETA {pool.dispatch.eta_hours.toFixed(1)} h
              </div>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
