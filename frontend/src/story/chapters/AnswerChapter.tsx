import { Volume2 } from "lucide-react";
import { useState } from "react";

import { cn, tk } from "../../lib/format";
import { speak } from "../../lib/speech";
import type { RahimFacts, Sourced } from "../data";
import { hasBanglaVoice } from "../Hero";
import { ChapterHeading, SourceNote, StoryButton } from "../parts";

export function AnswerChapter({ rahim }: { rahim: Sourced<RahimFacts> }) {
  const r = rahim.data;
  const [notice, setNotice] = useState<string | null>(null);
  const best = r.decision === "SELL_POOLED_B2B" ? "pool" : r.decision.startsWith("STORE") ? "store" : "faria";
  const rows = [
    {
      key: "faria", title: "Sell to the Faria now", value: r.spotValue, tone: "bg-red-400",
      note: r.blocked ? `Blocked: ${tk(r.offer, 0)} is below the ${tk(r.floor, 0)} it costs to grow a kilo.` : "Above what it costs to grow.",
    },
    {
      key: "store", title: `Keep them in cold storage for ${r.horizonDays} days`, value: r.storageValue, tone: "bg-sky-400",
      note: `After rent and handling, with the farm-gate price expected at ${tk(r.futurePrice)} by then.`,
    },
    {
      key: "pool", title: "Join the pooled truck", value: r.lotValueB2b, tone: "bg-mustard-400",
      note: `${tk(r.b2bNet)} a kilo after freight.`,
    },
  ];
  const max = Math.max(...rows.map((row) => row.value), 1);

  const play = (lang: "bn-BD" | "en-US") => {
    if (lang === "bn-BD" && !hasBanglaVoice()) {
      setNotice("This device has no Bangla voice installed, so the answer is shown but not spoken.");
      return;
    }
    setNotice(speak(lang === "bn-BD" ? r.spokenBn : r.english, lang) ? null : "Speech playback is not available in this browser.");
  };

  return (
    <>
      <ChapterHeading index={3}>Rahim's answer</ChapterHeading>
      <p className="text-[18px] leading-relaxed text-slate-200">What each choice is worth for his {r.quantityKg} kg:</p>
      <ul className="m-0 mt-5 list-none space-y-5 p-0">
        {rows.map((row) => (
          <li key={row.key}>
            <div className="flex items-baseline justify-between gap-4">
              <span className={cn("text-[17px]", row.key === best ? "font-semibold text-slate-50" : "text-slate-200")}>
                {row.title}
                {row.key === best && <span className="ml-2 rounded-full bg-mustard-400 px-2 py-0.5 text-[12px] font-semibold text-ink-900">Best for Rahim</span>}
              </span>
              <span className={cn("num text-[24px]", row.key === "faria" && r.blocked ? "text-red-300 line-through decoration-2" : "text-slate-50")}>
                {tk(row.value, 0)}
              </span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-slate-50/[0.07]">
              <div className={cn("h-full rounded-full", row.tone)} style={{ width: `${Math.max(2, (row.value / max) * 100)}%` }} />
            </div>
            <p className="m-0 mt-1.5 text-[14px] text-slate-400">{row.note}</p>
          </li>
        ))}
      </ul>

      <blockquote className="m-0 mt-9 border-l-2 border-mustard-400 pl-5">
        <p lang="bn" className="voice m-0 text-[clamp(19px,1.6vw,23px)] leading-[1.8] text-slate-50">{r.spokenBn}</p>
        <p className="m-0 mt-4 text-[16px] leading-relaxed text-slate-300">{r.english}</p>
      </blockquote>
      <div className="mt-6 flex flex-wrap gap-3">
        <StoryButton onClick={() => play("bn-BD")}><Volume2 className="size-[18px]" aria-hidden /> Play the answer</StoryButton>
        <StoryButton variant="ghost" onClick={() => play("en-US")}>Listen in English</StoryButton>
      </div>
      {notice && <p className="mt-3 text-[14px] text-slate-400" role="status">{notice}</p>}
      {r.credit?.eligible && (
        <p className="mt-6 text-[16px] text-slate-300">
          The same answer offers working capital: a credit score of {r.credit.score} ({r.credit.band.toLowerCase()}) unlocks
          {" "}{tk(r.credit.amount, 0)} at {r.credit.rate}% for {r.credit.tenor} months.
        </p>
      )}
      <SourceNote status={rahim.status} />
    </>
  );
}
