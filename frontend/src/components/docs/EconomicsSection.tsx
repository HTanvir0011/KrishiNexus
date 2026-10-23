import { Calculator } from "lucide-react";
import { useMemo, useState } from "react";

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
    <label className="block">
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-slate-200">{label}</span>
        <span className="num text-emerald-300">{format(value)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full accent-emerald-400" />
      <div className="text-[10px] text-slate-500">{hint}</div>
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

  return (
    <div className="grid gap-3 lg:grid-cols-[360px_1fr]">
      <div className="panel space-y-4 p-3">
        <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-100"><Calculator className="size-4 text-emerald-400" /> Levers</div>
        <Slider label="Active 5-ton pooled trucks / month" value={trucks} min={10} max={10_000} step={10} onChange={setTrucks}
          format={(v) => v.toLocaleString()} hint="Each truck carries 12.5 smallholder micro-lots of 400 kg" />
        <Slider label="B2B marketplace take-rate" value={takeRate} min={2.5} max={4} step={0.1} onChange={setTakeRate}
          format={(v) => `${v.toFixed(1)}%`} hint="Charged on the escrow-locked truck contract value" />
        <Slider label="Subscribed BCSA cold storages" value={storages} min={0} max={400} step={5} onChange={setStorages}
          format={(v) => v.toLocaleString()} hint="$150/mo SaaS + Tk 0.25/kg smallholder quota brokerage" />
        <Slider label="Underwritten smallholder profiles" value={profiles} min={0} max={1_000_000} step={5_000} onChange={setProfiles}
          format={(v) => v.toLocaleString()} hint="$1.50 per profile per season to partner banks / iFarmer" />
      </div>
      <div className="space-y-3">
        <div className="panel grid grid-cols-2 gap-4 p-4 md:grid-cols-3">
          <Stat label="Annual recurring revenue" value={usd(model.arr)} tone="emerald"
            hint={`marketplace ${usd(model.marketplace)} · storage ${usd(model.storageRevenue)} · credit API ${usd(model.creditRevenue)}`} />
          <Stat label="Smallholders served / yr" value={model.farmers.toLocaleString()} tone="sky" hint="unique farmers, 2 lots each" />
          <Stat label="Net farmer income uplift" value={usd(model.uplift)} tone="emerald" hint="at the +32% / $947 per season benchmark" />
          <Stat label="Spoilage prevented" value={`${Math.round(model.spoilageTons).toLocaleString()} t/yr`} tone="amber"
            hint={`${ASSUMPTIONS.baselineLossPct}% → ${ASSUMPTIONS.platformLossPct}% loss on routed volume`} />
          <Stat label="Platform volume" value={`${Math.round(model.tonsPerYear).toLocaleString()} t/yr`} tone="slate"
            hint={`${(model.share * 100).toFixed(2)}% of national perishables`} />
          <Stat label="Food CPI spread (weighted)" value={`${model.spread.toFixed(1)}%`} tone="red"
            hint={`116% baseline → 34% on platform volume`} />
        </div>
        <div className="panel p-3 text-[11px] leading-relaxed text-slate-400">
          <div className="mb-1 font-semibold text-slate-300">Model assumptions (illustrative, not forecasts)</div>
          Truck load {ASSUMPTIONS.truckKg.toLocaleString()} kg at Tk {ASSUMPTIONS.avgPriceTkPerKg}/kg, Tk {ASSUMPTIONS.fxTkPerUsd}/USD;
          {` ${ASSUMPTIONS.brokeredTonsPerStorage} t brokered per storage per season; credit fee over ${ASSUMPTIONS.creditSeasonsPerYear} seasons;`}
          {` farmer uplift uses the BAU +32% / $${ASSUMPTIONS.upliftUsdPerFarmerSeason} seasonal benchmark for one season;`}
          {` national marketed perishables assumed at ${(ASSUMPTIONS.nationalPerishablesTons / 1e6).toFixed(0)} M t/yr; weighted spread = 116% × (1 − share) + 34% × share.`}
        </div>
      </div>
    </div>
  );
}
