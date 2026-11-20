import { ArrowRight, Award, CheckCircle2, Download, KeyRound, Smartphone } from "lucide-react";
import { useState } from "react";

import { api } from "../api/client";
import { AppDownload } from "../components/AppDownload";
import site from "../data/site.json";
import { useCopy } from "../lib/i18n";
import { Link } from "../lib/router";
import { useAppState } from "../state/store";
import type { RahimFacts } from "./data";
import { HaorCard } from "./HaorCard";
import { LandingVideo } from "./LandingVideo";
import { LiveDecisionCard } from "./LiveDecisionCard";
import { PipelineSection } from "./PipelineSection";
import { QuotaCard } from "./QuotaCard";
import { RouteGraphic } from "./RouteGraphic";
import { SyndicateCard } from "./SyndicateCard";
import { TeamSection } from "./TeamSection";
import { useLive } from "./useLive";

const COPY = {
  en: {
    track: "AgriSphere AI · FarmMarket track",
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
    problem: "The problem in 30 seconds",
    problemLabel: "Video: the problem KrishiNexus solves, in 30 seconds",
    demoTitle: "Watch the demo",
    demoLede: "Three minutes on the live site: a farmer asks in his dialect, the agents decide, a buyer bids, a driver delivers and the payment is released.",
    demoLabel: "Video: KrishiNexus OS demo",
    captions: "English captions are on; the player's menu turns them off.",
    appTitle: "Take KrishiNexus to the field",
    appLede: "The Android app uses the same account: ask in Bangla by voice, grade a crop with the phone's camera, sell, deliver and get paid.",
    guide: "How to install it, step by step",
    footer: { team: "Team", guide: "User guide", docs: "Whitepaper", app: "Get the Android app" },
    congress: "International AI Builders Congress 2026 · AgriSphere AI → FarmMarket · Showcase on 26 December 2026 at Daffodil International University.",
  },
  bn: {
    track: "এগ্রিস্ফিয়ার এআই · ফার্মমার্কেট ট্র্যাক",
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
    problem: "৩০ সেকেন্ডে সমস্যাটি",
    problemLabel: "ভিডিও: কৃষিনেক্সাস যে সমস্যার সমাধান করে, ৩০ সেকেন্ডে",
    demoTitle: "ডেমো দেখুন",
    demoLede: "চালু সাইটে তিন মিনিট: কৃষক নিজের ভাষায় প্রশ্ন করেন, এজেন্টরা সিদ্ধান্ত দেয়, ক্রেতা দর দেন, চালক পৌঁছে দেন, আর টাকা ছাড় হয়।",
    demoLabel: "ভিডিও: কৃষিনেক্সাস ওএস ডেমো",
    captions: "ইংরেজি ক্যাপশন চালু আছে; প্লেয়ারের মেনু থেকে বন্ধ করা যায়।",
    appTitle: "কৃষিনেক্সাস মাঠে নিয়ে যান",
    appLede: "অ্যান্ড্রয়েড অ্যাপে একই অ্যাকাউন্ট চলে: মুখে বাংলায় প্রশ্ন, ফোনের ক্যামেরায় ফসল গ্রেডিং, বিক্রি, ডেলিভারি আর টাকা পাওয়া।",
    guide: "কীভাবে ইনস্টল করবেন, ধাপে ধাপে",
    footer: { team: "দল", guide: "ব্যবহার নির্দেশিকা", docs: "শ্বেতপত্র", app: "অ্যান্ড্রয়েড অ্যাপ নিন" },
    congress: "ইন্টারন্যাশনাল এআই বিল্ডার্স কংগ্রেস ২০২৬ · এগ্রিস্ফিয়ার এআই → ফার্মমার্কেট · প্রদর্শনী ২৬ ডিসেম্বর ২০২৬, ড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি।",
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
        <li className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-[13px] font-medium text-emerald-800 ring-1 ring-inset ring-emerald-700/15">
          <Award className="size-4" aria-hidden /> {c.track}
        </li>
      </ul>
      <p className="m-0 mt-2 text-[12.5px] text-slate-500">{c.measured}</p>
    </div>
  );
}

export default function StoryPage() {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  // Rahim's latest routed decision, shared by the live card (which runs the agents) and the route graphic (which drives it).
  const [rahim, setRahim] = useState<{ facts: RahimFacts; run: number } | null>(null);
  return (
    <main>
      <section className="relative isolate">
        <div className="hero-ground" aria-hidden />
        <div className="mx-auto grid max-w-[1280px] items-start gap-10 px-4 pt-10 pb-16 sm:px-6 sm:pt-16 lg:grid-cols-12 lg:gap-12">
        <div className="min-w-0 lg:col-span-7 lg:pt-6">
          {/* Bangla conjuncts need more room between lines than Latin capitals. */}
          <h1 className={`m-0 mt-2 max-w-[22ch] text-[clamp(34px,4.6vw,56px)] font-semibold text-slate-900 ${lang === "bn" ? "leading-[1.32]" : "leading-[1.08] tracking-[-0.025em]"}`}>
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
          <LandingVideo name="problem-30s" label={c.problemLabel} className="mt-8 max-w-[640px]"
            title={<h2 className="m-0 mb-2 text-[15px] font-semibold text-slate-900">{c.problem}</h2>}>
            {c.captions}
          </LandingVideo>
        </div>
        <div className="min-w-0 space-y-4 lg:col-span-5">
          <LiveDecisionCard onRahim={(facts) => setRahim((prev) => ({ facts, run: (prev?.run ?? 0) + 1 }))} />
          <RouteGraphic decision={rahim?.facts ?? null} runId={rahim?.run ?? 0} />
        </div>
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

      <LandingVideo name="krishinexus-demo" label={c.demoLabel} className="mx-auto max-w-[960px] px-4 pt-16 sm:px-6"
        title={<>
          <h2 className="m-0 text-[28px] font-semibold tracking-[-0.02em] text-slate-900">{c.demoTitle}</h2>
          <p className="m-0 mt-2 mb-6 max-w-[44rem] text-[15px] text-slate-600">{c.demoLede}</p>
        </>}>
        {c.captions}
      </LandingVideo>

      <div className="mx-auto max-w-[1280px] px-4 py-16 sm:px-6">
        <PipelineSection />
      </div>

      <section aria-labelledby="app-heading" className="border-t border-slate-200">
        <div className="mx-auto grid max-w-[1280px] items-center gap-x-6 gap-y-4 px-4 py-14 sm:px-6 md:grid-cols-[auto_minmax(0,1fr)]">
          <span className="grid size-14 place-items-center rounded-2xl bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-700/15" aria-hidden>
            <Smartphone className="size-7" />
          </span>
          <div className="min-w-0">
            <h2 id="app-heading" className="m-0 text-[24px] font-semibold tracking-[-0.02em] text-slate-900">{c.appTitle}</h2>
            <p className="m-0 mt-1.5 max-w-[48rem] text-[15px] text-slate-600">{c.appLede}</p>
            <AppDownload className="mt-4" />
            <Link to="/guide#app" className="inline-flex min-h-11 items-center gap-1.5 text-[14px] font-semibold text-emerald-700 no-underline hover:text-emerald-800">
              {c.guide} <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        </div>
      </section>

      <TeamSection />

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-6 text-[13px] text-slate-500 sm:px-6">
          <p className="m-0 max-w-[60rem]">{c.congress}</p>
          <nav aria-label="Footer" className="flex flex-wrap items-center gap-x-5">
            {/* /team/ is a static page written at build time, so it is a normal link, not a client route. */}
            <a href={lang === "bn" ? "/team/bn/" : "/team/"} className="inline-flex min-h-11 items-center font-medium text-slate-700 no-underline hover:text-slate-900">{c.footer.team}</a>
            <Link to="/guide" className="inline-flex min-h-11 items-center font-medium text-slate-700 no-underline hover:text-slate-900">{c.footer.guide}</Link>
            <Link to="/docs" className="inline-flex min-h-11 items-center font-medium text-slate-700 no-underline hover:text-slate-900">{c.footer.docs}</Link>
            <a href={site.apk} className="inline-flex min-h-11 items-center gap-1 font-medium text-slate-700 no-underline hover:text-slate-900">
              <Download className="size-3.5" aria-hidden /> {c.footer.app}
            </a>
          </nav>
        </div>
      </footer>
    </main>
  );
}
