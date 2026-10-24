import { ArrowRight, CheckCircle2, ExternalLink, KeyRound } from "lucide-react";

import { api } from "../api/client";
import { useCopy } from "../lib/i18n";
import { Link } from "../lib/router";
import { useAppState } from "../state/store";
import { HaorCard } from "./HaorCard";
import { LiveDecisionCard } from "./LiveDecisionCard";
import { PipelineSection } from "./PipelineSection";
import { TEAM } from "./presets";
import { QuotaCard } from "./QuotaCard";
import { SyndicateCard } from "./SyndicateCard";
import { useLive } from "./useLive";

const COPY = {
  en: {
    eyebrow: "AGRISPHERE AI · FARMMARKET TRACK",
    title: "Cut the 116% syndicate markup. Open the hoarded cold stores. Harvest before the flood.",
    lede: "KrishiNexus OS listens to a farmer's question in their own dialect and four agents answer it: they grade the crop, route it past five middlemen on a pooled 5-ton truck, find space in cold stores where traders and plant owners hold 77.32% of capacity, and send a Sentinel-1 radar harvest alert 72 hours before a haor embankment breaks.",
    os: "Open live OS workspace",
    docs: "Inspect 13 MCP tools and evals",
    faithfulness: "RAG faithfulness",
    regression: "seeded regression",
    keys: "paid API keys required",
    computing: "computing",
    measured: "Measured on this backend just now, not typed in.",
    leakTitle: "Where the money and the harvest leak",
    leakLede: "Three live views of the failures KrishiNexus targets. Every figure is an MCP tool call you can repeat in the whitepaper.",
    team: "The team",
    congress: "International AI Builders Congress 2026 · AgriSphere AI → FarmMarket · Showcase on 26 December 2026 at Daffodil International University.",
    source: "Source on GitHub",
  },
  bn: {
    eyebrow: "এগ্রিস্ফিয়ার এআই · ফার্মমার্কেট ট্র্যাক",
    title: "সিন্ডিকেটের ১১৬% মুনাফা কাটুন। দখলে থাকা হিমাগার খুলুন। বন্যার আগেই ধান তুলুন।",
    lede: "কৃষিনেক্সাস ওএস কৃষকের নিজের আঞ্চলিক ভাষায় প্রশ্ন শোনে, আর চার এজেন্ট উত্তর দেয়: ফসল গ্রেড করে, পাঁচ মধ্যস্বত্বভোগীকে এড়িয়ে ৫ টনের যৌথ ট্রাকে পাঠায়, যেসব হিমাগারের ৭৭.৩২% জায়গা ব্যবসায়ী ও মালিকদের দখলে সেখানে জায়গা খুঁজে দেয়, আর হাওরের বাঁধ ভাঙার ৭২ ঘণ্টা আগে সেন্টিনেল-১ রাডারের সতর্কবার্তা পাঠায়।",
    os: "লাইভ ওএস খুলুন",
    docs: "১৩টি এমসিপি টুল ও ইভাল দেখুন",
    faithfulness: "আরএজি ফেইথফুলনেস",
    regression: "সিডেড রিগ্রেশন",
    keys: "পেইড এপিআই কী লাগে না",
    computing: "হিসাব হচ্ছে",
    measured: "এই ব্যাকএন্ডে এইমাত্র মাপা, হাতে লেখা নয়।",
    leakTitle: "টাকা আর ফসল কোথায় হারায়",
    leakLede: "কৃষিনেক্সাস যে তিনটি সমস্যার সমাধান করে, তার লাইভ চিত্র। প্রতিটি সংখ্যা একটি এমসিপি টুল কল, যা শ্বেতপত্রে আবার চালানো যায়।",
    team: "দল",
    congress: "ইন্টারন্যাশনাল এআই বিল্ডার্স কংগ্রেস ২০২৬ · এগ্রিস্ফিয়ার এআই → ফার্মমার্কেট · প্রদর্শনী ২৬ ডিসেম্বর ২০২৬, ড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি।",
    source: "গিটহাবে সোর্স",
  },
};

function MetricPill({ value, label, live }: { value: string; label: string; live: boolean }) {
  return (
    <li className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-[13px] text-slate-700 shadow-sm ring-1 ring-inset ring-slate-200">
      <CheckCircle2 className={live ? "size-4 text-emerald-700" : "size-4 text-slate-400"} aria-hidden />
      <span className="num text-slate-900">{value}</span> {label}
    </li>
  );
}

function HeroMetrics() {
  const c = useCopy(COPY);
  const metrics = useLive("metrics", () => api.evalMetrics(), () => null);
  const regression = useLive("regression", () => api.runRegression(20), () => null);
  const faithfulness = metrics.data?.metrics.find((m) => m.name === "faithfulness");
  return (
    <div className="mt-8">
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        <MetricPill live={metrics.status === "live"} label={c.faithfulness}
          value={faithfulness ? faithfulness.value.toFixed(2) : metrics.status === "loading" ? c.computing : "-"} />
        <MetricPill live={regression.status === "live"} label={c.regression}
          value={regression.data ? `${regression.data.passed}/${regression.data.total_cases}` : regression.status === "loading" ? c.computing : "-"} />
        <li className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-[13px] text-slate-700 shadow-sm ring-1 ring-inset ring-slate-200">
          <KeyRound className="size-4 text-emerald-700" aria-hidden /><span className="num text-slate-900">0</span> {c.keys}
        </li>
      </ul>
      <p className="m-0 mt-2 text-[12.5px] text-slate-500">{c.measured}</p>
    </div>
  );
}

export default function StoryPage() {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  return (
    <main>
      <section className="mx-auto grid max-w-[1280px] items-start gap-10 px-4 pt-10 pb-16 sm:px-6 sm:pt-16 lg:grid-cols-12 lg:gap-12">
        <div className="min-w-0 lg:col-span-7 lg:pt-6">
          <span className="inline-flex rounded-full bg-emerald-50 px-3 py-1 text-[12px] font-semibold tracking-[0.06em] text-emerald-800 ring-1 ring-inset ring-emerald-700/15">
            {c.eyebrow}
          </span>
          {/* Bangla conjuncts need more room between lines than Latin capitals. */}
          <h1 className={`m-0 mt-5 max-w-[22ch] text-[clamp(34px,4.6vw,56px)] font-semibold text-slate-900 ${lang === "bn" ? "leading-[1.32]" : "leading-[1.08] tracking-[-0.025em]"}`}>
            {c.title}
          </h1>
          <p className="m-0 mt-5 max-w-[60ch] text-[17px] leading-relaxed text-slate-600">{c.lede}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/os" className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-emerald-700 px-5 text-[15px] font-semibold text-white no-underline shadow-sm transition-colors hover:bg-emerald-800">
              {c.os} <ArrowRight className="size-4" aria-hidden />
            </Link>
            <Link to="/docs" className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-white px-5 text-[15px] font-semibold text-slate-800 no-underline ring-1 ring-inset ring-slate-300 transition-colors hover:bg-slate-50">
              {c.docs}
            </Link>
          </div>
          <HeroMetrics />
        </div>
        <div className="min-w-0 lg:col-span-5">
          <LiveDecisionCard />
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white/60">
        <div className="mx-auto max-w-[1280px] px-4 py-16 sm:px-6">
          <h2 className="m-0 text-[28px] font-semibold tracking-[-0.02em] text-slate-900">{c.leakTitle}</h2>
          <p className="m-0 mt-2 max-w-[44rem] text-[15px] text-slate-600">{c.leakLede}</p>
          <div className="mt-8 grid gap-5 lg:grid-cols-3">
            <SyndicateCard className="lg:col-span-2" />
            <QuotaCard />
            <HaorCard className="lg:col-span-3" />
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-[1280px] px-4 py-16 sm:px-6">
        <PipelineSection />
      </div>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-[1280px] px-4 py-10 sm:px-6">
          <h2 className="m-0 text-[15px] font-semibold text-slate-900">{c.team}</h2>
          <ul className="m-0 mt-4 grid list-none gap-x-6 gap-y-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
            {TEAM.map((member) => (
              <li key={member.name} className="text-[14px]">
                <span className="font-medium text-slate-900">{member.name}</span>
                <span className="block text-[13px] text-slate-500">{member.role} · {member.country}</span>
              </li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-5 text-[13px] text-slate-500">
            <p className="m-0 max-w-[60rem]">{c.congress}</p>
            <a href="https://github.com/HTanvir0011/KrishiNexus" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-emerald-700 no-underline hover:text-emerald-800">
              {c.source} <ExternalLink className="size-3.5" aria-hidden />
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}
