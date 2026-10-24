import { ChevronRight, FileCode2 } from "lucide-react";
import { Fragment, useMemo, useState } from "react";

import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { useAppState } from "../state/store";
import { PIPELINE, timingsFor } from "./pipeline";

const COPY = {
  en: {
    title: "One question, nine LangGraph nodes",
    lede: "Every answer runs this graph in `backend/agents/supervisor.py`. Pick a node to see the state it reads and writes, the MCP tools it calls and how long it took in the last run you watched.",
    reads: "Reads from the agent state", writes: "Writes to the agent state", tools: "MCP tools", files: "Source",
    noTools: "None: works on the agent state only.",
    timing: "Last run",
    notYet: "Run a farmer decision above (or in the live OS) to time each node.",
    replan: "A conditional edge sends Supervisor review back to Cold-chain arbitrage when the chosen chamber is out of band, at most twice.",
  },
  bn: {
    title: "একটি প্রশ্ন, নয়টি ল্যাংগ্রাফ নোড",
    lede: "প্রতিটি উত্তর `backend/agents/supervisor.py`-এর এই গ্রাফ দিয়ে চলে। একটি নোড বেছে দেখুন সেটি কী পড়ে, কী লেখে, কোন এমসিপি টুল ডাকে এবং শেষবার কত সময় নিয়েছে।",
    reads: "এজেন্ট স্টেট থেকে পড়ে", writes: "এজেন্ট স্টেটে লেখে", tools: "এমসিপি টুল", files: "সোর্স",
    noTools: "নেই: শুধু এজেন্ট স্টেট নিয়ে কাজ করে।",
    timing: "শেষ রান",
    notYet: "প্রতিটি নোডের সময় মাপতে উপরে (বা লাইভ ওএস-এ) একটি সিদ্ধান্ত চালান।",
    replan: "নির্বাচিত চেম্বার সঠিক তাপমাত্রায় না থাকলে সুপারভাইজার কোল্ড-চেইন এজেন্টকে আবার পাঠায়, সর্বোচ্চ দুবার।",
  },
};

export function PipelineSection() {
  const c = useCopy(COPY);
  const [selected, setSelected] = useState("crag_retrieval");
  const traces = useAppState((s) => s.traces);
  const sessionId = useAppState((s) => s.activeSessionId);
  const timings = useMemo(() => timingsFor(sessionId ? traces.filter((e) => e.session_id === sessionId) : []), [traces, sessionId]);
  const node = PIPELINE.find((n) => n.id === selected) ?? PIPELINE[0];
  const t = timings[node.id];

  return (
    <section aria-labelledby="pipeline-title">
      <h2 id="pipeline-title" className="m-0 text-[28px] font-semibold tracking-[-0.02em] text-slate-900">{c.title}</h2>
      <p className="m-0 mt-2 max-w-[44rem] text-[15px] text-slate-600">{c.lede.split("`").map((part, i) => (i % 2 ? <code key={i} className="font-mono text-[13px] text-slate-800">{part}</code> : part))}</p>

      <div className="scroll-thin mt-6 overflow-x-auto pb-2">
        <ol className="m-0 flex min-w-max list-none items-center gap-1 p-0" aria-label="LangGraph nodes in run order">
          {PIPELINE.map((n, i) => (
            <Fragment key={n.id}>
              <li>
                <button type="button" onClick={() => setSelected(n.id)} aria-pressed={selected === n.id}
                  className={cn("flex min-h-11 items-center gap-2 rounded-lg px-3 text-[13.5px] font-medium ring-1 ring-inset transition-colors",
                    selected === n.id ? "bg-emerald-700 text-white ring-emerald-700" : "bg-white text-slate-800 ring-slate-200 hover:bg-slate-50")}>
                  <span className={cn("num grid size-5 place-items-center rounded-full text-[11px]",
                    selected === n.id ? "bg-white/20 text-white" : timings[n.id] ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-500")}>{i + 1}</span>
                  {n.short}
                </button>
              </li>
              {i < PIPELINE.length - 1 && <li aria-hidden className="text-slate-300"><ChevronRight className="size-4" /></li>}
            </Fragment>
          ))}
        </ol>
      </div>

      <div className="surface mt-3 grid gap-6 p-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <h3 className="m-0 text-[18px] font-semibold text-slate-900">{node.title}</h3>
          <p className="m-0 mt-1 text-[14.5px] text-slate-700">{node.does}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Fields label={c.reads} items={node.reads} />
            <Fields label={c.writes} items={node.writes} accent />
          </div>
          <div className="mt-4">
            <div className="mb-1.5 text-[12.5px] font-medium text-slate-500">{c.tools}</div>
            {node.tools.length ? (
              <div className="flex flex-wrap gap-1.5">
                {node.tools.map((tool) => <code key={tool} className="rounded-md bg-sky-50 px-2 py-0.5 font-mono text-[12px] text-sky-800 ring-1 ring-inset ring-sky-600/15">{tool}</code>)}
              </div>
            ) : <p className="m-0 text-[13px] text-slate-500">{c.noTools}</p>}
          </div>
          {node.id === "supervisor_review" && <p className="m-0 mt-4 text-[13px] text-slate-600">{c.replan}</p>}
        </div>
        <div className="min-w-0 space-y-4 lg:border-l lg:border-slate-200 lg:pl-6">
          <div>
            <div className="mb-1.5 text-[12.5px] font-medium text-slate-500">{c.timing}</div>
            {t ? (
              <dl className="m-0 grid grid-cols-3 gap-2">
                <Metric label="Node time" value={t.wallMs !== null ? `${Math.round(t.wallMs)} ms` : "-"} />
                <Metric label="Traced MCP calls" value={String(t.mcpCalls)} />
                <Metric label="Traced MCP time" value={`${Math.round(t.mcpMs)} ms`} />
              </dl>
            ) : <p className="m-0 text-[13px] text-slate-500">{c.notYet}</p>}
          </div>
          <div>
            <div className="mb-1.5 text-[12.5px] font-medium text-slate-500">{c.files}</div>
            <ul className="m-0 list-none space-y-1 p-0">
              {node.files.map((file) => (
                <li key={file} className="flex min-w-0 items-center gap-1.5 font-mono text-[12px] text-slate-700">
                  <FileCode2 className="size-3.5 shrink-0 text-slate-400" aria-hidden /><span className="truncate">{file}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

function Fields({ label, items, accent = false }: { label: string; items: string[]; accent?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="mb-1.5 text-[12.5px] font-medium text-slate-500">{label}</div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <code key={item} className={cn("rounded-md px-2 py-0.5 font-mono text-[12px] ring-1 ring-inset",
            accent ? "bg-emerald-50 text-emerald-800 ring-emerald-700/15" : "bg-slate-50 text-slate-700 ring-slate-200")}>{item}</code>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-200">
      <dt className="text-[12px] text-slate-500">{label}</dt>
      <dd className="num m-0 text-[17px] text-slate-900">{value}</dd>
    </div>
  );
}
