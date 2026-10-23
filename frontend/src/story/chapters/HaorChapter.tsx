import { useState } from "react";

import { api, ApiError, mcpCall } from "../../api/client";
import { cn } from "../../lib/format";
import { pushAlert } from "../../state/store";
import type { AbdulFacts, Sourced } from "../data";
import { ChapterHeading, SourceNote, StoryButton } from "../parts";
import { ABDUL } from "../presets";

interface HaorRisk {
  embankment_breach_probability_pct: number;
  alert_level: string;
  recommended_harvest_within_hours: number;
  boro_at_risk_tons: number;
  upstream_rainfall_72h_mm: number;
  voice_alert_bn: string;
}

const ALERT_TONE: Record<string, string> = {
  GREEN: "bg-emerald-600 text-slate-50",
  YELLOW: "bg-mustard-400 text-ink-900",
  ORANGE: "bg-amber-400 text-ink-900",
  RED: "bg-red-500 text-slate-50",
};

const ADVICE: Record<string, string> = {
  GREEN: "Harvest on the normal schedule.",
  YELLOW: "Get the harvester and labour ready.",
  ORANGE: "Start harvesting the mature plots.",
  RED: "Harvest the mature plots now.",
};

export function HaorChapter({ abdul, radar, onRadar, onFlood }: {
  abdul: Sourced<AbdulFacts>;
  radar: number;
  onRadar: (x: number) => void;
  onFlood: (level: number) => void;
}) {
  const a = abdul.data;
  const [sim, setSim] = useState<HaorRisk | null>(null);
  const [busy, setBusy] = useState(false);

  const simulate = async () => {
    setBusy(true);
    try {
      if (sim) {
        await api.clearAnomalies();
        setSim(null);
        onFlood(0);
      } else {
        await api.simulateFlashFlood("Tahirpur");
        const risk = await mcpCall<HaorRisk>("calculate_haor_flash_flood_risk", { upazila: "Tahirpur", sar_water_backscatter_db: -19.5 });
        setSim(risk);
        onFlood(Math.min(1, risk.embankment_breach_probability_pct / 100));
      }
    } catch (error) {
      pushAlert("danger", "The flood simulation needs the backend", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const level = a.alertLevel ?? "GREEN";
  return (
    <>
      <ChapterHeading index={4}>Abdul's question</ChapterHeading>
      <p className="text-[17px] text-slate-400">Abdul grows four acres of Boro rice in Tahirpur, beside the Tanguar haor.</p>
      <p lang="bn" className="voice m-0 mt-2 text-[clamp(40px,4.6vw,64px)] leading-[1.25] text-slate-50">{ABDUL.question}</p>
      <p className="m-0 mt-2 text-[19px] text-slate-50">“{ABDUL.english}”<span className="ml-2 text-[14px] text-slate-400">{ABDUL.dialect}</span></p>
      <p className="mt-6 text-[18px] leading-relaxed text-slate-200">
        In April 2017 a flash flood from the Meghalaya hills took 65% of Sunamganj's Boro crop within days. Monsoon cloud hides the haor
        from ordinary satellites. Radar sees through it: on a radar image, black is open water.
      </p>

      <label className="mt-6 block max-w-[26rem]">
        <span className="label block text-[14px] text-slate-400">Radar divider: cloud on the left, radar on the right. You can also drag the line on the map.</span>
        <input type="range" min={0} max={100} value={Math.round(radar * 100)} onChange={(e) => onRadar(Number(e.target.value) / 100)}
          className="mt-2 w-full accent-mustard-400" aria-label="Radar divider position" />
      </label>

      <div className="card mt-6 p-5">
        <div className="flex flex-wrap items-center gap-3">
          <span className={cn("rounded-full px-3 py-1 text-[13px] font-semibold", ALERT_TONE[sim?.alert_level ?? level] ?? ALERT_TONE.GREEN)}>
            Alert {(sim?.alert_level ?? level).toLowerCase()}
          </span>
          <span className="num text-[34px] leading-none text-slate-50">
            {(sim ? sim.embankment_breach_probability_pct : a.breachPct ?? 0).toFixed(1)}%
          </span>
          <span className="text-[15px] text-slate-400">chance the embankment breaks in 72 hours</span>
        </div>
        {sim ? (
          <>
            <p className="mt-4 mb-0 text-[16px] leading-relaxed text-slate-200">
              With {Math.round(sim.upstream_rainfall_72h_mm)} mm of rain upstream: {ADVICE[sim.alert_level] ?? ADVICE.RED} The agents recommend
              harvesting within {Math.round(sim.recommended_harvest_within_hours)} hours, because{" "}
              {Math.round(sim.boro_at_risk_tons).toLocaleString("en-IN")} t of Boro is at risk.
            </p>
            <p lang="bn" className="voice mt-3 mb-0 text-[19px] leading-[1.75] text-slate-50">{sim.voice_alert_bn}</p>
          </>
        ) : (
          <>
            <p className="mt-4 mb-0 text-[16px] leading-relaxed text-slate-200">Today, with {a.rain72h.toFixed(0)} mm of rain forecast upstream: {ADVICE[level] ?? ADVICE.GREEN}</p>
            <p lang="bn" className="voice mt-3 mb-0 text-[19px] leading-[1.75] text-slate-50">{a.advice}</p>
          </>
        )}
        <StoryButton variant="ghost" className="mt-5" onClick={() => void simulate()} disabled={busy}>
          {sim ? "Clear the simulation" : "Simulate the April 2017 flood"}
        </StoryButton>
        <p className="label mt-2 mb-0 text-[13px] text-slate-500">
          The radar here is a simulated Sentinel-1 pass; this build has no live Copernicus feed. The simulation adds 320 mm of upstream rain on the backend.
        </p>
      </div>
      <SourceNote status={abdul.status} />
    </>
  );
}
