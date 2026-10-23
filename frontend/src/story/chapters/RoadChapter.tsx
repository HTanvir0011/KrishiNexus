import { Ring } from "../../components/gauges";
import { cn, kg, tk } from "../../lib/format";
import type { Ladder, RahimFacts, Sourced } from "../data";
import type { RouteMode } from "../landscape/Landscape";
import { ChapterHeading, SourceNote } from "../parts";

export function RoadChapter({ ladder, rahim, mode, onMode, focus, onFocus }: {
  ladder: Sourced<Ladder>;
  rahim: Sourced<RahimFacts>;
  mode: RouteMode;
  onMode: (mode: RouteMode) => void;
  focus: number | null;
  onFocus: (index: number | null) => void;
}) {
  const l = ladder.data;
  const r = rahim.data;
  const date = new Date(`${l.marketDate}T00:00:00+06:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

  return (
    <>
      <ChapterHeading index={2}>The road to Dhaka</ChapterHeading>
      <p className="text-[18px] leading-relaxed text-slate-200">
        The Faria offers Rahim {tk(r.offer)} a kilo. Today the farm-gate price in Mithapukur is {tk(l.grower)}, and in Karwan Bazar the
        same potato sells for {tk(l.retail)}.
      </p>

      <div role="radiogroup" aria-label="How the potatoes travel" className="mt-6 inline-flex flex-wrap rounded-full border border-slate-50/15 p-1">
        {([["syndicate", "Through five traders"], ["pooled", "In a pooled truck"]] as const).map(([value, label]) => (
          <button key={value} type="button" role="radio" aria-checked={mode === value} onClick={() => onMode(value)}
            className={cn("min-h-11 rounded-full px-5 text-[15px] font-semibold transition-colors",
              mode === value ? "bg-slate-50 text-ink-900" : "text-slate-300 hover:text-slate-50")}>
            {label}
          </button>
        ))}
      </div>

      {mode === "syndicate" ? (
        <>
          <ol className="m-0 mt-6 list-none space-y-1 p-0" aria-label="Margin each trader adds per kilo">
            {l.tiers.map((t, i) => (
              <li key={t.tier}>
                <button type="button" aria-pressed={focus === i} onClick={() => onFocus(focus === i ? null : i)}
                  onMouseEnter={() => onFocus(i)} onMouseLeave={() => onFocus(null)}
                  className={cn("grid w-full grid-cols-[1fr_auto] items-baseline gap-x-4 rounded-xl px-3 py-2.5 text-left transition-colors",
                    focus === i ? "bg-slate-50/[0.06]" : "hover:bg-slate-50/[0.04]")}>
                  <span className="text-[16px]">
                    <span className="font-semibold text-slate-50">{t.tier}</span>
                    <span className="text-slate-400">, {t.role}</span>
                    {t.tier === "Aratdar" && (
                      <span className="mt-0.5 block text-[14px] text-slate-400">
                        Takes {l.aratdarSharePct.toFixed(2)}% of the Bepari's marketing cost and spends Tk 0 on grading.
                      </span>
                    )}
                  </span>
                  <span className="num text-[22px] text-red-300">+{tk(t.margin)}</span>
                </button>
              </li>
            ))}
          </ol>
          <p className="mt-5 text-[19px] leading-relaxed text-slate-50">
            Rahim keeps {l.farmerSharePct.toFixed(1)}% of what a Dhaka shopper pays. From farm gate to shop the price rises
            {" "}{l.markupPct.toFixed(0)}%.
          </p>
        </>
      ) : r.pool ? (
        <div className="mt-6 flex flex-wrap items-center gap-6">
          <Ring className="w-[124px]" value={r.pool.after} max={r.pool.capacity}
            label={`Truck ${kg(r.pool.after)} of ${kg(r.pool.capacity)} after Rahim joins`} />
          <p className="m-0 max-w-[26rem] flex-1 text-[18px] leading-relaxed text-slate-200">
            {r.pool.neighbours} neighbours within 5 km are loading a 5-ton truck: {kg(r.pool.current)} so far, {kg(r.pool.after)} with
            Rahim's lot. It skips the Faria and the Bepari and goes straight to the {r.bestHub}. After {tk(r.freight)} a kilo of freight,
            Rahim gets <span className="font-semibold text-mustard-300">{tk(r.b2bNet)} a kilo</span>.
          </p>
        </div>
      ) : (
        <p className="mt-6 text-[18px] text-slate-200">No union truck is forming near Rahim today; the agents would open a new pool.</p>
      )}
      <SourceNote status={ladder.status}>DAM-modelled prices for {date}.</SourceNote>
    </>
  );
}
