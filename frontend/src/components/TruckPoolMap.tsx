import { Lock, MapPin, Thermometer, Truck } from "lucide-react";
import { useMemo, useState } from "react";

import { api, ApiError, type PoolLot, type PoolView } from "../api/client";
import { cn, kg, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { refreshPools, setState, useAppState } from "../state/store";
import { Badge, Button, Panel, ProgressBar, Spinner } from "./ui";

const R = 128;
const C = 150;
const GRADE_FILL: Record<PoolLot["grade"], string> = { A: "#059669", B: "#d97706", C: "#e11d48" };

const COPY = {
  en: {
    title: "5-ton union truck pool",
    selectPool: "Select truck pool",
    loading: "Loading pools…",
    radar: "Radar of {n} micro-lots within {km} km of the union",
    grade: "Grade",
    dispatchLocked: "Dispatch locked",
    toFill: "{kg} to fill",
    pooledLots: "{n} micro-lots pooled",
    rosterFarmers: "{n} farmers in the union",
    freight: "Freight",
    freightDetail: "Tk 68/km + Tk 1,500/trip + bridge tolls, + Tk 0.10/kg pooling fee",
    thisLot: "This lot",
    lotNumbers: "{freight}/kg freight · {net}/kg net",
    destination: "Destination",
    destinationPending: "chosen when a farmer's decision matches this pool",
    truck: "Truck",
    dispatchLine: "{price}/kg · escrow {escrow} locked {amount} · ETA {eta} h",
    heat: "Truck temperature",
    heatCheck: "Check route",
    heatFailed: "Transit check failed",
    TransitChecked: "{temp} °C leaves {shelf} h of shelf life; {eta} h to the buyer is safe. Route kept.",
    TruckRerouted: "{temp} °C leaves {shelf} h of shelf life, too little for {eta} h to {from}. Rerouted to {to} ({neweta} h).",
    TransitAtRisk: "{temp} °C leaves {shelf} h of shelf life and no buyer is reachable in time. Unload at the nearest cold store.",
  },
  bn: {
    title: "৫ টনের ইউনিয়ন ট্রাক পুল",
    selectPool: "ট্রাক পুল বাছাই করুন",
    loading: "পুল লোড হচ্ছে…",
    radar: "ইউনিয়নের {km} কিমির মধ্যে {n}টি মাইক্রো-লটের রাডার",
    grade: "গ্রেড",
    dispatchLocked: "ডিসপ্যাচ লক হয়েছে",
    toFill: "আর {kg} বাকি",
    pooledLots: "{n}টি মাইক্রো-লট পুল হয়েছে",
    rosterFarmers: "ইউনিয়নে {n} জন কৃষক",
    freight: "ভাড়া",
    freightDetail: "প্রতি কিমি Tk 68 + প্রতি ট্রিপ Tk 1,500 + ব্রিজ টোল, + প্রতি কেজি Tk 0.10 পুলিং ফি",
    thisLot: "এই লট",
    lotNumbers: "{freight}/কেজি ভাড়া · {net}/কেজি নিট",
    destination: "গন্তব্য",
    destinationPending: "কৃষকের সিদ্ধান্ত এই পুলের সাথে মিললে ঠিক হবে",
    truck: "ট্রাক",
    dispatchLine: "{price}/কেজি · এসক্রো {escrow} লক {amount} · ETA {eta} ঘণ্টা",
    heat: "ট্রাকের তাপমাত্রা",
    heatCheck: "রুট যাচাই",
    heatFailed: "পরিবহন যাচাই ব্যর্থ",
    TransitChecked: "{temp} °C-এ ফসল আর {shelf} ঘণ্টা ভালো থাকবে; ক্রেতা পর্যন্ত {eta} ঘণ্টা নিরাপদ। রুট বহাল।",
    TruckRerouted: "{temp} °C-এ ফসল আর {shelf} ঘণ্টা ভালো থাকবে, {from} পর্যন্ত {eta} ঘণ্টার জন্য যথেষ্ট নয়। ট্রাক {to}-এ ঘোরানো হলো ({neweta} ঘণ্টা)।",
    TransitAtRisk: "{temp} °C-এ ফসল আর {shelf} ঘণ্টা ভালো থাকবে; সময়মতো কোনো ক্রেতার কাছে পৌঁছানো যাবে না। নিকটতম হিমাগারে নামান।",
  },
};

function fmt(s: string, vars: Record<string, string | number>): string {
  return s.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ""));
}

const TRANSIT_EVENTS = { TransitChecked: 1, TruckRerouted: 1, TransitAtRisk: 1 };

function transitLine(template: string, d: Record<string, unknown>): string {
  return fmt(template, { temp: String(d.transit_temp_c), shelf: Number(d.shelf_life_hours).toFixed(1), eta: Number(d.eta_hours).toFixed(1),
                        from: String(d.from_buyer ?? ""), to: String(d.to_buyer ?? ""), neweta: Number(d.new_eta_hours ?? 0).toFixed(1) });
}

function angleOf(farmerId: string): number {
  let h = 0;
  for (const ch of farmerId) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return ((h % 3600) / 3600) * Math.PI * 2;
}

function LotDot({ lot, radiusKm }: { lot: PoolLot; radiusKm: number }) {
  const c = useCopy(COPY);
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
        <title>{`${lot.farmer_id}: ${lot.weight_kg} kg ${c.grade}-${lot.grade}, ${lot.distance_km} km`}</title>
      </circle>
    </g>
  );
}

export function TruckPoolMap({ className }: { className?: string }) {
  const c = useCopy(COPY);
  const pools = useAppState((s) => s.pools);
  const focusId = useAppState((s) => s.focusPoolId);
  const voice = useAppState((s) => s.lastVoice);
  const pool: PoolView | undefined = useMemo(() => pools.find((p) => p.pool_id === focusId) ?? pools[0], [pools, focusId]);
  const plan = voice?.orchestration?.state.syndicate_bypass_plan;
  const leg = plan?.pool && pool && plan.pool.pool_id === pool.pool_id ? plan : null;
  const destination = pool?.dispatch?.buyer_name ?? leg?.best_hub_name ?? null;
  const [heatC, setHeatC] = useState(38);
  const [checking, setChecking] = useState(false);
  const [heatError, setHeatError] = useState<string | null>(null);
  const check = [...(pool?.recent_events ?? [])].reverse().find((e) => e.event_type in TRANSIT_EVENTS);
  const checkHeat = async () => {
    if (!pool) return;
    setChecking(true);
    setHeatError(null);
    try {
      await api.transitCheck(pool.pool_id, heatC);
      await refreshPools();
    } catch (error) {
      setHeatError(`${c.heatFailed}: ${error instanceof ApiError ? error.message : String(error)}`);
    } finally {
      setChecking(false);
    }
  };

  return (
    <Panel className={className} icon={<Truck className="size-4 text-amber-600" aria-hidden />}
      title={pool ? `${c.title} · ${pool.upazila}, ${pool.district}` : c.title}
      actions={
        <select value={pool?.pool_id ?? ""} onChange={(e) => setState({ focusPoolId: e.target.value })} aria-label={c.selectPool}
          className="min-h-8 rounded-lg border border-slate-300 bg-white px-2 text-[12.5px] text-slate-800">
          {pools.map((p) => <option key={p.pool_id} value={p.pool_id}>{p.pool_id}</option>)}
        </select>
      }
      bodyClassName="flex flex-col gap-3">
      {!pool ? (
        <div className="py-10 text-center text-[13px] text-slate-500">{c.loading}</div>
      ) : (
        <>
          <div className="relative mx-auto w-full max-w-[280px]">
            <svg viewBox="0 0 300 300" className="w-full" role="img" aria-label={fmt(c.radar, { n: pool.smallholders, km: pool.union_radius_km })}>
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
              <span key={g} className="flex items-center gap-1"><span className="size-2.5 rounded-full" style={{ background: GRADE_FILL[g] }} /> {c.grade}-{g}</span>
            ))}
          </div>

          <div>
            <div className="mb-1 flex items-baseline justify-between text-[13px]">
              <span className="num text-slate-900">{kg(pool.loaded_kg)} / {kg(pool.capacity_kg)}</span>
              {pool.status === "DISPATCHED"
                ? <Badge tone="amber"><Lock className="size-3" aria-hidden /> {c.dispatchLocked}</Badge>
                : <span className="text-slate-600">{fmt(c.toFill, { kg: kg(pool.remaining_kg) })}</span>}
            </div>
            <ProgressBar value={pool.loaded_kg} max={pool.capacity_kg} tone={pool.status === "DISPATCHED" ? "amber" : "emerald"} />
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone="emerald">{fmt(c.pooledLots, { n: pool.smallholders })}</Badge>
              <Badge tone="slate">{fmt(c.rosterFarmers, { n: pool.roster_size })}</Badge>
              <Badge tone="slate">{pool.crop}</Badge>
            </div>
          </div>

          <dl className="m-0 grid gap-2 rounded-lg bg-slate-50 p-3 text-[12.5px] ring-1 ring-inset ring-slate-200">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">{c.freight}</dt>
              <dd className="m-0 text-right text-slate-800">{c.freightDetail}</dd>
            </div>
            {leg && (
              <div className="flex justify-between gap-3">
                <dt className="text-slate-500">{c.thisLot}</dt>
                <dd className="num m-0 text-right text-slate-900">{fmt(c.lotNumbers, { freight: tk(leg.pooled_transport_tk_per_kg), net: tk(leg.b2b_net_tk_per_kg) })}</dd>
              </div>
            )}
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">{c.destination}</dt>
              <dd className={cn("m-0 text-right", destination ? "text-slate-900" : "text-slate-500")}>{destination ?? c.destinationPending}</dd>
            </div>
          </dl>

          {pool.dispatch && (
            <div className="rounded-lg bg-amber-100/60 p-3 text-[12.5px] text-amber-900 ring-1 ring-inset ring-amber-600/25">
              <div className="font-semibold">{c.truck} {pool.dispatch.truck_booking_id} → {pool.dispatch.buyer_name}</div>
              <div className="num font-medium text-amber-800">
                {fmt(c.dispatchLine, { price: tk(pool.dispatch.contract_price_tk_per_kg), escrow: pool.dispatch.escrow_id, amount: tk(pool.dispatch.escrow_amount_tk, 0), eta: pool.dispatch.eta_hours.toFixed(1) })}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-1.5"><Thermometer className="size-3.5" aria-hidden /> {c.heat}
                  <input type="number" min={-5} max={55} value={heatC} onChange={(e) => setHeatC(Number(e.target.value))}
                    className="num w-16 rounded-md bg-white px-1.5 py-0.5 text-slate-900 ring-1 ring-inset ring-amber-600/30" /> °C
                </label>
                <Button onClick={() => void checkHeat()} disabled={checking}>{checking ? <Spinner /> : null} {c.heatCheck}</Button>
              </div>
              {check && <p role="status" className="m-0 mt-1.5">{transitLine(c[check.event_type as keyof typeof TRANSIT_EVENTS], check.data)}</p>}
              {heatError && <p role="alert" className="m-0 mt-1.5 text-rose-700">{heatError}</p>}
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
