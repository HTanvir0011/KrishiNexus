import { Calculator, CalendarRange, Scale } from "lucide-react";
import { useMemo, useState } from "react";

import { cn } from "../../lib/format";
import { Stat } from "../ui";

const ASSUMPTIONS = {
  fxTkPerUsd: 122,
  truckKg: 5_000,
  avgPriceTkPerKg: 40,
  avgLotKg: 400,
  lotsPerFarmerPerYear: 2,
  saasUsdPerMonth: 150,
  brokeredTonsPerStorage: 400,
  brokerageTkPerKg: 0.25,
  creditFeeUsdPerSeason: 1.5,
  creditSeasonsPerYear: 2,
  upliftUsdPerFarmerSeason: 947,
  baselineLossPct: 25,
  platformLossPct: 8,
  nationalPerishablesTons: 20_000_000,
  baselineSpreadPct: 116,
  platformSpreadPct: 34,
};

/** One pooled truck's economics. The pooling fee is the backend's (dam_market_mcp.POOLING_FEE_TK_PER_KG); the rest are
 *  planning assumptions for the pilot to test, not measured costs. */
const UNIT = {
  poolingFeeTkPerKg: 0.10,
  paymentRailsPct: 1.0,
  coordinationTkPerTruck: 800,
  cloudAndSmsTkPerTruck: 200,
  coordinatorTkPerMonth: 30_000,
  kiosksPerDistrict: 2,
  kioskTk: 45_000,
  kioskLifeMonths: 24,
  connectivityTkPerMonth: 4_000,
  farmerGainTkPerKg: 5,
};

const PILOT = [
  { when: "Dec 2026", what: "Field validation in Shibganj, Bogura: 5 farmers and a DAE agriculture officer use the app on a phone and the kiosk (docs/field-test-kit.md); every answer is rated in the app." },
  { when: "Jan–Mar 2027", what: "Potato-harvest pilot in one union: one kiosk, one co-op, one cold storage and one buyer. Target: break-even truck volume by March." },
  { when: "Apr–May 2027", what: "Boro harvest in the Sunamganj haor: flood alerts and early-harvest windows for the same co-op model." },
  { when: "From Jul 2027", what: "A second district only if the pilot meets its targets: farmers net at least Tk 5/kg more, 70% of answers rated useful, and break-even reached." },
];

const tkFmt = (v: number) => `Tk ${Math.round(v).toLocaleString("en-IN")}`;

function usd(value: number): string {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

function Slider({ label, value, min, max, step, onChange, format, hint }: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; format: (v: number) => string; hint: string;
}) {
  return (
    <label className="block min-w-0">
      <div className="flex items-baseline justify-between gap-3 text-[13px]">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="num shrink-0 text-emerald-700">{format(value)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full accent-emerald-700" />
      <div className="mt-0.5 text-[12px] text-slate-500">{hint}</div>
    </label>
  );
}

export function EconomicsSection() {
  const [trucks, setTrucks] = useState(500);
  const [takeRate, setTakeRate] = useState(2.5);
  const [storages, setStorages] = useState(80);
  const [profiles, setProfiles] = useState(100_000);

  const model = useMemo(() => {
    const a = ASSUMPTIONS;
    const loadUsd = (a.truckKg * a.avgPriceTkPerKg) / a.fxTkPerUsd;
    const marketplace = trucks * 12 * loadUsd * (takeRate / 100);
    const storageRevenue = storages * (a.saasUsdPerMonth * 12 + (a.brokeredTonsPerStorage * 1000 * a.brokerageTkPerKg) / a.fxTkPerUsd);
    const creditRevenue = profiles * a.creditFeeUsdPerSeason * a.creditSeasonsPerYear;
    const tonsPerYear = (trucks * 12 * a.truckKg) / 1000;
    const farmers = Math.round((trucks * 12 * (a.truckKg / a.avgLotKg)) / a.lotsPerFarmerPerYear);
    const share = Math.min(1, tonsPerYear / a.nationalPerishablesTons);
    return {
      arr: marketplace + storageRevenue + creditRevenue,
      marketplace, storageRevenue, creditRevenue, farmers,
      uplift: farmers * a.upliftUsdPerFarmerSeason,
      spoilageTons: tonsPerYear * ((a.baselineLossPct - a.platformLossPct) / 100),
      tonsPerYear, share,
      spread: a.baselineSpreadPct * (1 - share) + a.platformSpreadPct * share,
    };
  }, [trucks, takeRate, storages, profiles]);

  // Per pooled truck, at the take-rate on the slider: revenue, variable cost, contribution and a district's break-even.
  const unit = useMemo(() => {
    const u = UNIT;
    const contract = ASSUMPTIONS.truckKg * ASSUMPTIONS.avgPriceTkPerKg;
    const revenue = contract * (takeRate / 100) + ASSUMPTIONS.truckKg * u.poolingFeeTkPerKg;
    const variable = contract * (u.paymentRailsPct / 100) + u.coordinationTkPerTruck + u.cloudAndSmsTkPerTruck;
    const contribution = revenue - variable;
    const fixed = u.coordinatorTkPerMonth + (u.kiosksPerDistrict * u.kioskTk) / u.kioskLifeMonths + u.connectivityTkPerMonth;
    const breakEvenTrucks = contribution > 0 ? Math.ceil(fixed / contribution) : Infinity;
    const farmerGain = ASSUMPTIONS.truckKg * u.farmerGainTkPerKg;
    return { contract, revenue, variable, contribution, fixed, breakEvenTrucks, farmerGain };
  }, [takeRate]);

  // The take-rate floor (2.5%) and minimum 10 trucks keep marketplace revenue, and so ARR, above zero.
  const parts = [
    { label: "Marketplace", value: model.marketplace, fill: "bg-emerald-600" },
    { label: "Storage SaaS + brokerage", value: model.storageRevenue, fill: "bg-sky-600" },
    { label: "Credit API", value: model.creditRevenue, fill: "bg-violet-600" },
  ];
  // Farmers wear the design system's farmer accent; platform revenue stays neutral.
  const bars = [
    { label: "Farmer income uplift", value: model.uplift, fill: "bg-amber-600" },
    { label: "Platform ARR", value: model.arr, fill: "bg-slate-500" },
  ];
  const scale = Math.max(model.uplift, model.arr);

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <div className="surface min-w-0 p-4 sm:p-5 xl:self-start">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em] text-slate-900"><Calculator className="size-4 text-emerald-700" /> Levers</h3>
        <div className="mt-4 grid gap-5 sm:grid-cols-2 xl:grid-cols-1">
          <Slider label="Active 5-ton pooled trucks / month" value={trucks} min={10} max={10_000} step={10} onChange={setTrucks}
            format={(v) => v.toLocaleString()} hint="Each truck carries 12.5 smallholder micro-lots of 400 kg" />
          <Slider label="B2B marketplace take-rate" value={takeRate} min={2.5} max={4} step={0.1} onChange={setTakeRate}
            format={(v) => `${v.toFixed(1)}%`} hint="Charged on the escrow-locked truck contract value" />
          <Slider label="Subscribed BCSA cold storages" value={storages} min={0} max={400} step={5} onChange={setStorages}
            format={(v) => v.toLocaleString()} hint="$150/mo SaaS + Tk 0.25/kg smallholder quota brokerage" />
          <Slider label="Underwritten smallholder profiles" value={profiles} min={0} max={1_000_000} step={5_000} onChange={setProfiles}
            format={(v) => v.toLocaleString()} hint="$1.50 per profile per season to partner banks / iFarmer" />
        </div>
      </div>

      <div className="min-w-0 space-y-4">
        <div className="surface grid grid-cols-2 gap-x-4 gap-y-5 p-4 sm:p-5 md:grid-cols-3">
          <Stat label="Annual recurring revenue" value={usd(model.arr)} tone="emerald" hint="three revenue lines" />
          <Stat label="Smallholders served / yr" value={model.farmers.toLocaleString()} tone="sky" hint="unique farmers, 2 lots each" />
          <Stat label="Net farmer income uplift" value={usd(model.uplift)} tone="emerald" hint="at the +32% / $947 per season benchmark" />
          <Stat label="Spoilage prevented" value={`${Math.round(model.spoilageTons).toLocaleString()} t/yr`} tone="amber"
            hint={`${ASSUMPTIONS.baselineLossPct}% → ${ASSUMPTIONS.platformLossPct}% loss on routed volume`} />
          <Stat label="Platform volume" value={`${Math.round(model.tonsPerYear).toLocaleString()} t/yr`} tone="slate"
            hint={`${(model.share * 100).toFixed(2)}% of national perishables`} />
          <Stat label="Food CPI spread (weighted)" value={`${model.spread.toFixed(1)}%`} tone="red"
            hint={`116% baseline → 34% on platform volume`} />
        </div>

        <div className="surface space-y-5 p-4 sm:p-5">
          <figure>
            <figcaption className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <span className="text-[14px] font-semibold text-slate-900">ARR composition</span>
              <span className="text-[13px] text-slate-500">Total <span className="num text-slate-900">{usd(model.arr)}</span></span>
            </figcaption>
            <div className="mt-3 flex h-3 gap-0.5 overflow-hidden rounded-r-[4px]" role="img"
              aria-label={`ARR composition: ${parts.map((p) => `${p.label} ${usd(p.value)}`).join(", ")}`}>
              {parts.filter((p) => p.value > 0).map((p) => (
                <div key={p.label} className={cn("h-full", p.fill)} style={{ width: `${(p.value / model.arr) * 100}%` }} title={`${p.label}: ${usd(p.value)}`} />
              ))}
            </div>
            <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[13px]">
              {parts.map((p) => (
                <li key={p.label} className="flex items-center gap-2">
                  <span className={cn("size-2.5 shrink-0 rounded-[3px]", p.fill)} aria-hidden />
                  <span className="text-slate-600">{p.label}</span>
                  <span className="num text-slate-900">{usd(p.value)}</span>
                </li>
              ))}
            </ul>
          </figure>

          <figure className="border-t border-slate-100 pt-5">
            <figcaption className="text-[14px] font-semibold text-slate-900">Smallholder surplus against platform revenue</figcaption>
            <div className="mt-3 space-y-3">
              {bars.map((b) => (
                <div key={b.label}>
                  <div className="flex items-baseline justify-between gap-3 text-[13px]">
                    <span className="text-slate-600">{b.label}</span>
                    <span className="num text-slate-900">{usd(b.value)}</span>
                  </div>
                  <div className="mt-1.5 h-3">
                    <div className={cn("h-full min-w-[3px] rounded-r-[4px]", b.fill)} style={{ width: `${(b.value / scale) * 100}%` }} title={`${b.label}: ${usd(b.value)}`} />
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[13px] text-slate-600">
              Farmers keep <span className="num text-slate-900">{((model.uplift / (model.uplift + model.arr)) * 100).toFixed(1)}%</span> of the
              combined value: farmer uplift plus platform ARR.
            </p>
          </figure>
        </div>

        <div className="surface p-4 sm:p-5">
          <h3 className="flex items-center gap-2 text-[15px] font-semibold text-slate-900"><Scale className="size-4 text-emerald-700" aria-hidden /> One pooled truck, and when a district breaks even</h3>
          <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-[13.5px] sm:grid-cols-2">
            {[
              ["Truck contract (5,000 kg × Tk 40)", tkFmt(unit.contract)],
              [`Platform revenue (${takeRate.toFixed(1)}% take-rate + Tk 0.10/kg pooling fee)`, tkFmt(unit.revenue)],
              [`Variable cost (payment rails ${UNIT.paymentRailsPct}%, coordination, cloud and SMS)`, tkFmt(unit.variable)],
              ["Contribution per truck", tkFmt(unit.contribution)],
              ["District fixed cost per month (coordinator, 2 kiosks over 24 months, connectivity)", tkFmt(unit.fixed)],
              ["Break-even per district", Number.isFinite(unit.breakEvenTrucks)
                ? `${unit.breakEvenTrucks} trucks/month (${(unit.breakEvenTrucks * 5).toLocaleString()} t, about ${Math.round((unit.breakEvenTrucks * ASSUMPTIONS.truckKg) / ASSUMPTIONS.avgLotKg)} lots of 400 kg)`
                : "not at this take-rate"],
              [`Farmers' extra income per truck (at Tk ${UNIT.farmerGainTkPerKg}/kg)`, tkFmt(unit.farmerGain)],
              ["Farmers gain per Tk 1 the platform earns", `Tk ${(unit.farmerGain / unit.revenue).toFixed(1)}`],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-1.5">
                <dt className="text-slate-600">{label}</dt>
                <dd className="num m-0 max-w-[60%] text-right font-semibold text-slate-900">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="m-0 mt-3 text-[12.5px] leading-relaxed text-slate-500">
            Planning assumptions for the pilot to test, not measured costs. The Tk 5/kg farmer gain is deliberately below the
            demo&apos;s own modelled cases (Tk 10–18/kg over the Faria offer); the pooling fee is the backend&apos;s Tk 0.10/kg.
          </p>
        </div>

        <div className="surface p-4 sm:p-5">
          <h3 className="flex items-center gap-2 text-[15px] font-semibold text-slate-900"><CalendarRange className="size-4 text-emerald-700" aria-hidden /> Pilot plan (proposed, not started)</h3>
          <ol className="m-0 mt-3 grid list-none gap-3 p-0">
            {PILOT.map((step, i) => (
              <li key={step.when} className="grid grid-cols-[28px_minmax(0,1fr)] gap-2 text-[13.5px]">
                <span className="num grid size-6 place-items-center rounded-full bg-emerald-50 text-[12px] font-semibold text-emerald-800 ring-1 ring-emerald-700/20 ring-inset">{i + 1}</span>
                <span className="min-w-0"><span className="font-semibold text-slate-900">{step.when}.</span> <span className="text-slate-700">{step.what}</span></span>
              </li>
            ))}
          </ol>
        </div>

        <div className="rounded-lg bg-slate-50 p-4 text-[12.5px] leading-relaxed text-slate-600 ring-1 ring-slate-200 ring-inset">
          <div className="mb-1 text-[13px] font-semibold text-slate-900">Model assumptions (illustrative, not forecasts)</div>
          Truck load {ASSUMPTIONS.truckKg.toLocaleString()} kg at Tk {ASSUMPTIONS.avgPriceTkPerKg}/kg, Tk {ASSUMPTIONS.fxTkPerUsd}/USD;
          {` ${ASSUMPTIONS.brokeredTonsPerStorage} t brokered per storage per season; credit fee over ${ASSUMPTIONS.creditSeasonsPerYear} seasons;`}
          {` farmer uplift uses the BAU +32% / $${ASSUMPTIONS.upliftUsdPerFarmerSeason} seasonal benchmark for one season;`}
          {` national marketed perishables assumed at ${(ASSUMPTIONS.nationalPerishablesTons / 1e6).toFixed(0)} M t/yr; weighted spread = 116% × (1 − share) + 34% × share.`}
        </div>
      </div>
    </div>
  );
}
