import { useState } from "react";

import { mcpCall, type Crop } from "../api/client";
import { Badge, SourceChip } from "../components/ui";
import { cn, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { LADDER_SNAPSHOT, ladderFrom, SNAPSHOT_DATE, type DetectOutput, type Ladder } from "./data";
import { useLive } from "./useLive";

const CROPS: Crop[] = ["Cardinal Potato", "Diamant Potato", "Green Chili", "Brinjal", "Boro Rice"];
const ORIGINS = [
  { upazila: "Mithapukur", district: "Rangpur" },
  { upazila: "Shibganj", district: "Bogura" },
  { upazila: "Sariakandi", district: "Bogura" },
  { upazila: "Tongibari", district: "Munshiganj" },
  { upazila: "Jhikargacha", district: "Jessore" },
  { upazila: "Ranisankail", district: "Thakurgaon" },
];
const HUB = "Dhaka Karwan Bazar";

const COPY = {
  en: {
    title: "The five-tier syndicate",
    sub: "Farm gate to Dhaka retail, in taka per kilo",
    crop: "Crop",
    origin: "Grown in",
    gate: "Farm gate",
    retail: "Dhaka retail",
    markup: "producer-to-retail markup",
    share: (pct: string) => `The farmer keeps ${pct} of what a Dhaka shopper pays.`,
    aratdar: (share: string, take: string, grading: string) =>
      `The Aratdar takes ${share} of the Bepari's marketing cost (${take}/kg) and spends ${grading} on grading.`,
    fair: (fair: string, excess: string) => `A fair markup for this crop is ${fair}; ${excess}/kg above it is extraction.`,
  },
  bn: {
    title: "পাঁচ স্তরের সিন্ডিকেট",
    sub: "খামার থেকে ঢাকার খুচরা বাজার, কেজিপ্রতি টাকায়",
    crop: "ফসল",
    origin: "উৎপাদন এলাকা",
    gate: "খামার",
    retail: "ঢাকা খুচরা",
    markup: "উৎপাদক থেকে খুচরা পর্যন্ত মার্কআপ",
    share: (pct: string) => `ঢাকার ক্রেতা যা দেন, কৃষক পান তার ${pct}।`,
    aratdar: (share: string, take: string, grading: string) =>
      `আড়তদার বেপারির বিপণন খরচের ${share} নেন (${take}/কেজি), অথচ গ্রেডিংয়ে খরচ করেন ${grading}।`,
    fair: (fair: string, excess: string) => `এই ফসলে ন্যায্য মার্কআপ ${fair}; এর উপরে ${excess}/কেজি হলো বাড়তি আদায়।`,
  },
};

const SEVERITY_TONE: Record<string, "red" | "amber" | "emerald"> = { CRITICAL: "red", SEVERE: "red", ELEVATED: "amber", NORMAL: "emerald" };

export function SyndicateCard({ className }: { className?: string }) {
  const c = useCopy(COPY);
  const [crop, setCrop] = useState<Crop>("Cardinal Potato");
  const [upazila, setUpazila] = useState("Mithapukur");
  const live = useLive<Ladder>(
    `${crop}|${upazila}`,
    async () => ladderFrom(await mcpCall<DetectOutput>("detect_syndicate_markup_anomaly", { crop, upazila, retail_hub: HUB })),
    () => (crop === "Cardinal Potato" && upazila === "Mithapukur" ? LADDER_SNAPSHOT : null),
  );
  const l = live.data;
  const max = l ? l.retail * 1.12 : 1;
  const bars = l
    ? [
        { key: c.gate, from: 0, to: l.grower, label: l.grower.toFixed(2), kind: "farmer" as const },
        ...l.tiers.map((t) => ({ key: t.tier, from: t.buy, to: t.sell, label: `+${t.margin.toFixed(2)}`, kind: t.tier === "Aratdar" ? ("aratdar" as const) : ("tier" as const) })),
        { key: c.retail, from: 0, to: l.retail, label: l.retail.toFixed(2), kind: "retail" as const },
      ]
    : [];

  return (
    <article className={cn("surface flex min-w-0 flex-col p-5", className)}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="m-0 text-[17px] font-semibold tracking-[-0.01em] text-slate-900">{c.title}</h3>
          <p className="m-0 text-[13px] text-slate-500">{c.sub}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select label={c.crop} value={crop} onChange={(v) => setCrop(v as Crop)} options={CROPS.map((v) => ({ value: v, label: v }))} />
          <Select label={c.origin} value={upazila} onChange={setUpazila} options={ORIGINS.map((o) => ({ value: o.upazila, label: `${o.upazila}, ${o.district}` }))} />
        </div>
      </header>

      {live.error && <p className="mt-4 text-[13px] text-rose-600">{live.error}</p>}
      {!l && !live.error && (
        <p className="mt-4 text-[13px] text-slate-500">{live.status === "loading" ? "Calling detect_syndicate_markup_anomaly…" : `Start the backend to price ${crop} from ${upazila}; the cached snapshot covers Cardinal potato from Mithapukur only.`}</p>
      )}

      {l && (
        <>
          <div className="mt-5 flex flex-wrap items-end gap-x-6 gap-y-2">
            <div>
              <div className="num text-[44px] leading-none text-rose-600">{l.markupPct.toFixed(0)}%</div>
              <div className="text-[13px] text-slate-600">{c.markup}</div>
            </div>
            <Badge tone={SEVERITY_TONE[l.severity] ?? "amber"}>{l.severity.toLowerCase()}</Badge>
            <p className="m-0 max-w-[30rem] text-[14px] text-slate-700">{c.share(`${l.farmerSharePct.toFixed(1)}%`)}</p>
          </div>

          <div className="mt-6 grid grid-cols-7 gap-1.5 sm:gap-3" role="img"
            aria-label={`Price ladder: farm gate ${tk(l.grower)}, retail ${tk(l.retail)}; ${l.tiers.map((t) => `${t.tier} adds ${tk(t.margin)}`).join(", ")}`}>
            {bars.map((bar) => (
              <div key={bar.key} className="flex min-w-0 flex-col">
                <div className="relative h-44 border-b border-slate-300">
                  <div className={cn("absolute inset-x-0 rounded-t-[4px]",
                    bar.kind === "farmer" && "bg-emerald-600",
                    bar.kind === "tier" && "bg-rose-400",
                    bar.kind === "aratdar" && "bg-rose-600",
                    bar.kind === "retail" && "bg-slate-300")}
                    style={{ bottom: `${(bar.from / max) * 100}%`, height: `${Math.max(1.5, ((bar.to - bar.from) / max) * 100)}%` }}>
                    {bar.kind === "retail" && (
                      <div className="absolute inset-x-0 bottom-0 bg-emerald-600" style={{ height: `${(l.grower / l.retail) * 100}%` }} />
                    )}
                  </div>
                  <div className={cn("num absolute inset-x-0 text-center text-[11.5px] sm:text-[12.5px]",
                    bar.kind === "farmer" ? "text-emerald-700" : bar.kind === "retail" ? "text-slate-900" : "text-rose-600")}
                    style={{ bottom: `calc(${(bar.to / max) * 100}% + 4px)` }}>
                    {bar.label}
                  </div>
                </div>
                <div className={cn("mt-1.5 text-center text-[11.5px] leading-tight sm:text-[12.5px]", bar.kind === "aratdar" ? "font-semibold text-rose-700" : "text-slate-600")}>{bar.key}</div>
              </div>
            ))}
          </div>

          <div className="mt-5 grid gap-2 text-[13px] text-slate-700 sm:grid-cols-2">
            <p className="m-0 rounded-lg bg-rose-100/60 px-3 py-2 ring-1 ring-inset ring-rose-600/10">
              {c.aratdar(`${l.aratdarSharePct.toFixed(2)}%`, tk(l.aratdarTake), tk(l.gradingSpend, 0))}
            </p>
            <p className="m-0 rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-200">
              {c.fair(`${l.fairMarkupPct.toFixed(0)}%`, tk(l.excessTkPerKg))}
            </p>
          </div>
        </>
      )}

      <footer className="mt-auto pt-4">
        <SourceChip status={live.error ? "live" : live.status} tool={live.status === "cached" ? `detect_syndicate_markup_anomaly · run of ${SNAPSHOT_DATE}` : "detect_syndicate_markup_anomaly"} ms={live.ms} />
      </footer>
    </article>
  );
}

export function Select({ label, value, onChange, options }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="flex flex-col gap-0.5 text-[12px] text-slate-500">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="min-h-9 rounded-lg border border-slate-300 bg-white px-2.5 text-[14px] text-slate-900 shadow-sm max-sm:min-h-11">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}
