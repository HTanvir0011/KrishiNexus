import { Truck } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties } from "react";

import { mcpCall } from "../api/client";
import { Badge, SourceChip } from "../components/ui";
import { cn, kg, pct, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { LADDER_SNAPSHOT, ladderFrom, type DetectOutput, type Ladder, type RahimFacts } from "./data";
import { useLive } from "./useLive";

const COPY = {
  en: {
    title: "Five hands, or one truck",
    sub: "Rahim's Cardinal potato from Mithapukur to Dhaka, taka per kilo",
    today: "Today, through five middlemen",
    markup: (p: string) => `${p} markup`,
    share: (p: string) => `Rahim keeps ${p} of what a Dhaka shopper pays.`,
    gate: "Farm gate",
    retail: "Dhaka retail",
    tiers: "Middlemen between the farm gate and Dhaka retail",
    withUs: "With KrishiNexus, one pooled 5-ton truck",
    field: "His field",
    net: "net to Rahim",
    waiting: "Press run above: the agents route his 400 kg and the truck sets off.",
    routed: (hub: string, freight: string) => `Straight to ${hub}, after ${freight}/kg freight.`,
    gain: (x: string) => `+${x}/kg on the Faria's offer`,
  },
  bn: {
    title: "পাঁচ হাত, নাকি এক ট্রাক",
    sub: "মিঠাপুকুর থেকে ঢাকা, রহিমের কার্ডিনাল আলু, কেজিপ্রতি টাকা",
    today: "আজ, পাঁচ মধ্যস্বত্বভোগীর হাত ঘুরে",
    markup: (p: string) => `${p} মার্কআপ`,
    share: (p: string) => `ঢাকার ক্রেতা যা দেন, রহিম পান তার ${p}।`,
    gate: "খামার",
    retail: "ঢাকা খুচরা",
    tiers: "খামার থেকে ঢাকার খুচরা বাজার পর্যন্ত মধ্যস্বত্বভোগীরা",
    withUs: "কৃষিনেক্সাসে, এক যৌথ ৫-টন ট্রাক",
    field: "তাঁর খেত",
    net: "রহিমের হাতে",
    waiting: "উপরে চালান চাপুন: এজেন্টরা তাঁর ৪০০ কেজির পথ ঠিক করবে, আর ট্রাক রওনা দেবে।",
    routed: (hub: string, freight: string) => `সরাসরি ${hub}-এ, কেজিতে ${freight} ভাড়ার পরে।`,
    gain: (x: string) => `ফড়িয়ার দামের চেয়ে কেজিতে +${x}`,
  },
};

/**
 * The landing page's one authored moment. The syndicate road is drawn from the live markup tool, one middleman at a
 * time; when the agents in the card above route Rahim's lot, a truck drives the direct road and his real net lands at
 * the buyer. `runId` changes on every run, so the drive replays.
 */
export function RouteGraphic({ decision, runId }: { decision: RahimFacts | null; runId: number }) {
  const c = useCopy(COPY);
  const live = useLive<Ladder>(
    "route|Cardinal Potato|Mithapukur",
    async () => ladderFrom(await mcpCall<DetectOutput>("detect_syndicate_markup_anomaly",
      { crop: "Cardinal Potato", upazila: "Mithapukur", retail_hub: "Dhaka Karwan Bazar" })),
    () => LADDER_SNAPSHOT,
  );
  const l = live.data;

  // The drive plays when its lane is on screen: after a run the card above grows and can push this lane below the
  // fold, and a moment nobody sees is wasted. Until then the lane keeps its waiting state.
  const lane = useRef<HTMLDivElement>(null);
  const [shownRun, setShownRun] = useState(0);
  useEffect(() => {
    const el = lane.current;
    if (!decision || shownRun === runId || !el) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) {
        setShownRun(runId);
        observer.disconnect();
      }
    }, { threshold: 0.6 });
    observer.observe(el);
    return () => observer.disconnect();
  }, [decision, runId, shownRun]);
  const routed = decision && shownRun === runId ? decision : null;

  return (
    <section className="surface overflow-hidden" aria-labelledby="route-title">
      <header className="flex flex-wrap items-start justify-between gap-2 px-5 pt-4">
        <div className="min-w-0">
          <h2 id="route-title" className="m-0 text-[15px] font-semibold text-slate-900">{c.title}</h2>
          <p className="m-0 text-[12.5px] text-slate-500">{c.sub}</p>
        </div>
      </header>

      <div className="space-y-6 px-5 pt-4 pb-5">
        {/* The road through five hands, drawn from the farm gate. */}
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[12.5px] font-medium text-slate-700">{c.today}</span>
            {l && <Badge tone="red">{c.markup(pct(l.markupPct, 0))}</Badge>}
          </div>
          <div className="mt-2 grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3">
            <RoadEnd price={l ? tk(l.grower) : "-"} label={c.gate} />
            <div className="relative h-16">
              <span aria-hidden className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 rounded-full bg-slate-200" />
              {l && <span aria-hidden className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 origin-left animate-draw rounded-full bg-rose-400" style={{ animationDuration: "1.1s" }} />}
              {l && (
                <ol aria-label={c.tiers} className="m-0 list-none p-0">
                  {l.tiers.map((t, i) => {
                    const delay = { animationDelay: `${220 + i * 160}ms` };
                    return (
                      <li key={t.tier} className="absolute top-1/2" style={{ left: `${((i + 1) / (l.tiers.length + 1)) * 100}%` }}>
                        <span className="num absolute bottom-3 left-1/2 -translate-x-1/2 animate-fade-in text-[11.5px] whitespace-nowrap text-rose-600 max-sm:text-[10.5px]" style={delay}>
                          +{t.margin.toFixed(2)}
                        </span>
                        <span aria-hidden className="absolute top-0 left-0 block size-2.5 -translate-x-1/2 -translate-y-1/2">
                          <span className="block size-full animate-pop rounded-full bg-white ring-2 ring-rose-500" style={delay} />
                        </span>
                        <span className="absolute top-3 left-1/2 -translate-x-1/2 text-[11px] whitespace-nowrap text-slate-500 max-sm:sr-only">{t.tier}</span>
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>
            <RoadEnd price={l ? tk(l.retail) : "-"} label={c.retail} align="right" />
          </div>
          {l && <p className="m-0 mt-1 text-[12.5px] text-slate-600">{c.share(pct(l.farmerSharePct))}</p>}
        </div>

        {/* The direct road: waits for the agents, then the truck drives it. */}
        <div ref={lane}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[12.5px] font-medium text-slate-700">{c.withUs}</span>
            {routed && (
              <span key={shownRun} className="animate-fade-in" style={{ animationDelay: "1.3s" }}>
                <Badge tone="emerald">{c.gain(tk(routed.b2bNet - routed.offer))}</Badge>
              </span>
            )}
          </div>
          <div key={shownRun} className="mt-2 grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3">
            <RoadEnd price={kg(routed?.quantityKg ?? 400)} label={c.field} />
            <div className="relative h-10">
              <span aria-hidden className={cn("absolute inset-x-0 top-1/2 -translate-y-1/2 rounded-full",
                routed ? "h-0.5 bg-slate-200" : "border-t-2 border-dashed border-slate-300")} />
              {routed && <span aria-hidden className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 origin-left animate-draw rounded-full bg-emerald-500" style={{ animationDuration: "1.2s" }} />}
              {/* A full-width carrier holds the truck at its right end; sliding the carrier drives the truck along the road. */}
              <span aria-hidden className={cn("pointer-events-none absolute inset-y-0 left-0 flex w-full items-center justify-end", routed && "animate-drive")}
                style={routed ? undefined : { transform: "translateX(calc(-100% + 1.25rem))" }}>
                <span className={cn("grid size-5 place-items-center rounded-md", routed ? "bg-emerald-700 text-white shadow-sm" : "bg-slate-200 text-slate-500")}>
                  <Truck className="size-3.5" />
                </span>
              </span>
            </div>
            {routed
              ? <RoadEnd price={tk(routed.b2bNet)} label={c.net} align="right" tone="emerald" className="animate-pop" style={{ animationDelay: "1.2s" }} />
              : <RoadEnd price="?" label={c.net} align="right" />}
          </div>
          <p className="m-0 mt-1 text-[12.5px] text-slate-600">
            {routed ? c.routed(routed.bestHub, tk(routed.freight)) : c.waiting}
          </p>
        </div>
      </div>
      <footer className="border-t border-slate-200 bg-slate-50/70 px-5 py-3">
        <SourceChip status={live.status} tool={live.status === "live" ? "detect_syndicate_markup_anomaly" : undefined} ms={live.ms} />
      </footer>
    </section>
  );
}

function RoadEnd({ price, label, align, tone, className, style }: {
  price: string;
  label: string;
  align?: "right";
  tone?: "emerald";
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={cn("min-w-0", align === "right" && "text-right", className)} style={style}>
      <div className={cn("num text-[15px] leading-tight whitespace-nowrap", tone === "emerald" ? "text-emerald-700" : "text-slate-900")}>{price}</div>
      <div className="text-[11.5px] whitespace-nowrap text-slate-500">{label}</div>
    </div>
  );
}
