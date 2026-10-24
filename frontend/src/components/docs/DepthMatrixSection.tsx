import { CheckCircle2, CircleDashed, Play } from "lucide-react";
import { useState } from "react";

import {
  api,
  ApiError,
  type CompressReport,
  type LocalModelsReport,
  type PoolView,
  type PromptRegistryListing,
  type RagQueryReport,
} from "../../api/client";
import { cn, tk } from "../../lib/format";
import { Badge, Button, Spinner } from "../ui";

type Status = "Live" | "Partial";

const MATRIX: { category: string; implementation: string; evidence: string; status: Status; note?: string }[] = [
  { category: "Prompt engineering", implementation: "Versioned XML system prompts, Bangla few-shots, CoT schema, DSPy-style optimiser", evidence: "GET /prompts/registry", status: "Live" },
  { category: "Token optimisation", implementation: "LLMLingua-2-style keep/drop, lossless JSON compaction, semantic dedup, cache payloads", evidence: "POST /optimization/compress", status: "Live" },
  { category: "Retrieval & RAG", implementation: "Contextual chunks, BM25 + dense hybrid, RRF, BGE-style reranker, HyDE dialect rewrite, CRAG", evidence: "POST /rag/query", status: "Live" },
  { category: "Knowledge graph", implementation: "NetworkX GraphRAG over upazila → crop → storage → corridor → market → rule", evidence: "POST /rag/graph-traverse", status: "Live", note: "Neo4j-compatible Cypher emitted; no Neo4j server deployed" },
  { category: "Agent orchestration", implementation: "LangGraph StateGraph supervisor, 4 typed agents, re-plan loop", evidence: "POST /agents/orchestrate", status: "Live", note: "CrewAI not used" },
  { category: "MCP servers", implementation: "3 custom servers, 13 tools, JSON-RPC 2.0, Streamable HTTP / SSE / stdio", evidence: "POST /mcp/call", status: "Live" },
  { category: "Workflow automation", implementation: "n8n cron/webhook jobs, durable event-sourced 5-ton truck pools", evidence: "/automation/*", status: "Live", note: "n8n workflow JSON is importable; no n8n instance deployed" },
  { category: "Guardrails & privacy", implementation: "Presidio-compatible BD PII scrubber with vault, ΔΠ and DAE circuit-breakers", evidence: "POST /guardrails/verify", status: "Live" },
  { category: "Model routing", implementation: "Cheap-to-reasoning router over Ollama, Gemini Flash, DeepSeek-R1, Claude Sonnet 5.5", evidence: "GET /optimization/route", status: "Live" },
  { category: "Local / on-device LLMs", implementation: "Ollama / llama.cpp / vLLM runtime manager, Q4_K_M telemetry, offline fallback", evidence: "GET /edge/local-models", status: "Partial", note: "Live generation needs a local runtime with the models pulled" },
  { category: "Fine-tuning", implementation: "krishi-bangla-lora-v1 QLoRA spec + 3,200-example generated SFT dataset", evidence: "GET /edge/lora-dataset", status: "Partial", note: "Adapter not trained yet" },
  { category: "Multimodal", implementation: "Optical grader (classical CV on photos, sweep simulation), Bangla dialect voice + SSML", evidence: "POST /edge/grade-crop", status: "Partial", note: "No trained YOLO weights; audio STT needs a Whisper model" },
  { category: "Real-time explainability", implementation: "WebSocket stream of every thought, MCP call, CRAG grade and guardrail", evidence: "WS /ws/agent-trace", status: "Live" },
  { category: "Evaluation", implementation: "Measured RAGAS-style metrics + seeded 100-case regression suite", evidence: "/evals/*", status: "Live", note: "Deterministic rubric judge; no LLM judge" },
  { category: "Frontend & visual", implementation: "React + Three.js digital twin, split-screen judge mode, live trace", evidence: "this app", status: "Live" },
  { category: "AI development lifecycle", implementation: "AGENTS.md / CLAUDE.md spec-driven build in 6 verified steps", evidence: "AGENTS.md", status: "Live", note: "BMAD-METHOD not used" },
];

type Tab = "prompts" | "compress" | "rag" | "guardrails" | "local" | "workflows" | "aidlc";
// The three core layers lead the row and the compression tester opens first.
const TABS: { id: Tab; label: string }[] = [
  { id: "compress", label: "LLMLingua-2" }, { id: "rag", label: "GraphRAG + CRAG" }, { id: "guardrails", label: "PII & ΔΠ breaker" },
  { id: "prompts", label: "XML prompts & DSPy" }, { id: "local", label: "Ollama & LoRA" }, { id: "workflows", label: "n8n + Temporal" },
  { id: "aidlc", label: "AI-DLC" },
];

/** Light code block shared by every JSON, diff and compressed-text view. */
const CODE = "scroll-thin overflow-auto rounded-lg bg-slate-50 p-3 font-mono text-[12px] leading-relaxed text-slate-800 ring-1 ring-slate-200 ring-inset";

const WEATHER_JSON = JSON.stringify({
  latitude: 25.07, longitude: 91.39,
  hourly: Array.from({ length: 168 }, (_, h) => ({
    time: new Date(Date.UTC(2026, 3, 10, h)).toISOString().slice(0, 16), temperature_c: Number((26 + (h % 24) / 6).toFixed(1)),
    relative_humidity_pct: 78 + (h % 5), precipitation_mm: h % 17 === 0 ? 4.2 : 0, wind_gusts_kmh: null,
  })),
}, null, 2);
const DAM_TEXT = "Bogura wholesale market report: Cardinal Potato grower price Tk 11/kg, Faria Tk 14/kg, Bepari Tk 17/kg, Aratdar takes 62.35% of Bepari marketing cost, retail Dhaka Karwan Bazar Tk 28/kg. Cold storage fee Tk 8.50/kg at 48-50F and 92-95% RH.";
const GUARD_BODY = {
  raw_text: "আমার নাম করিম, NID 1992269485738, ফোন 01712345678, বিকাশ 01898765432। ফড়িয়া ১০ টাকা কেজি আলু চাচ্ছে।",
  crop: "Cardinal Potato", quantity_kg: 5000, spot_price_bdt: 10, expected_future_price_bdt: 78, storage_tariff_bdt: 8.5,
  handling_cost_bdt: 3.5, lambda_rot: 0.015,
};

function useRunner<T>() {
  const [data, setData] = useState<T | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<T>) => {
    setBusy(true);
    setError(null);
    try {
      setData(await fn());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return { data, busy, error, run };
}

function RunButton({ busy, onClick, label = "Run live" }: { busy: boolean; onClick: () => void; label?: string }) {
  return <Button variant="primary" onClick={onClick} disabled={busy}>{busy ? <Spinner /> : <Play className="size-3.5" />} {label}</Button>;
}

function PromptsTester() {
  const r = useRunner<PromptRegistryListing>();
  const [agent, setAgent] = useState("coldchain_arbitrage");
  const view = r.data?.agents.find((a) => a.agent === agent);
  return (
    <div className="space-y-3">
      <RunButton busy={r.busy} onClick={() => r.run(api.promptsRegistry)} label="Load prompt registry" />
      {r.error && <div className="text-[13px] text-rose-600">{r.error}</div>}
      {r.data && (
        <>
          <div className="flex flex-wrap gap-1.5">
            {r.data.agents.map((a) => (
              <button key={a.agent} type="button" onClick={() => setAgent(a.agent)} aria-pressed={agent === a.agent}
                className={cn("rounded-md px-2.5 py-1 text-[12.5px] ring-1 ring-inset transition-colors max-sm:min-h-10",
                  agent === a.agent ? "bg-emerald-50 text-emerald-800 ring-emerald-700/25" : "bg-white text-slate-700 ring-slate-200 hover:bg-slate-50")}>
                {a.agent} <span className="font-mono tabular-nums text-emerald-700">{a.optimization.baseline_score.toFixed(2)}→{a.optimization.optimized_score.toFixed(2)}</span>
              </button>
            ))}
          </div>
          {view && (
            <div className="text-[12.5px] text-slate-600">{view.optimization.method} · {view.optimization.trials_evaluated} candidates · active {view.active_version}</div>
          )}
          <pre className={cn(CODE, "max-h-72")}>
            {view?.optimization.diff.map((line, i) => (
              <div key={i} className={line.startsWith("+") ? "text-emerald-700" : line.startsWith("-") ? "text-rose-600" : "text-slate-500"}>{line}</div>
            ))}
          </pre>
        </>
      )}
    </div>
  );
}

function CompressTester() {
  const [text, setText] = useState(WEATHER_JSON);
  const r = useRunner<CompressReport>();
  const c = r.data?.compression;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap gap-1.5">
          <Button onClick={() => setText(WEATHER_JSON)}>168-hour weather JSON</Button>
          <Button onClick={() => setText(DAM_TEXT)}>DAM price text</Button>
          <RunButton busy={r.busy} onClick={() => r.run(() => api.compress(text))} label="Compress" />
        </div>
        <textarea value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} aria-label="Context to compress"
          className={cn(CODE, "block h-52 w-full resize-y")} />
      </div>
      <div className="min-w-0 space-y-2 text-[13px]">
        {r.error && <div className="text-rose-600">{r.error}</div>}
        {c && (
          <>
            <div className="flex flex-wrap gap-1.5">
              <Badge tone="violet"><span className="tabular-nums">{c.original_tokens} → {c.compressed_tokens}</span> tokens</Badge>
              <Badge tone="emerald"><span className="tabular-nums">{c.reduction_factor}x</span> reduction</Badge>
              <Badge tone={c.all_numbers_preserved ? "emerald" : "red"}>numbers preserved: {String(c.all_numbers_preserved)}</Badge>
              <Badge tone="sky">dedup <span className="tabular-nums">{r.data?.deduplication.input_chunks}→{r.data?.deduplication.kept_chunks}</span></Badge>
            </div>
            <div className="text-[12.5px] text-slate-600">Cache eligible: {Object.entries(r.data?.cache.cache_eligible ?? {}).map(([k, v]) => `${k} ${v ? "yes" : "no"}`).join(" · ")}</div>
            <pre className={cn(CODE, "max-h-48 whitespace-pre-wrap wrap-anywhere")}>{c.compressed_text}</pre>
          </>
        )}
      </div>
    </div>
  );
}

function RagTester() {
  const [query, setQuery] = useState("মুন্সিগঞ্জে কার্ডিনাল আলু কোল্ড স্টোরেজে কত তাপমাত্রায় রাখলে পচবে না এবং সিন্ডিকেট ছাড়া কোথায় বেচব?");
  const r = useRunner<RagQueryReport>();
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Farmer question" lang="bn"
          className="voice min-w-0 flex-1 rounded-lg bg-white px-3 py-1.5 text-[15px] text-slate-900 ring-1 ring-slate-300 ring-inset" />
        <RunButton busy={r.busy} onClick={() => r.run(() => api.ragQuery(query, "Munshiganj", "Cardinal Potato"))} label="Query" />
      </div>
      {r.error && <div className="text-[13px] text-rose-600">{r.error}</div>}
      {r.data && (
        <div className="grid gap-4 text-[13px] lg:grid-cols-2">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap gap-1.5">
              <Badge tone="violet">{r.data.rewrite.detected_dialect}</Badge>
              {r.data.rewrite.intents.map((i) => <Badge key={i} tone="sky">{i}</Badge>)}
              <Badge tone={r.data.crag.verdict === "CORRECT" ? "emerald" : "amber"}>CRAG {r.data.crag.verdict} <span className="tabular-nums">{r.data.crag.confidence.toFixed(2)}</span></Badge>
            </div>
            <div className="text-[12.5px] text-slate-600">HyDE formal query: {r.data.rewrite.formal_query}</div>
            <div className="scroll-thin overflow-x-auto rounded-lg ring-1 ring-slate-200 ring-inset">
              <table className="w-full font-mono text-[12px] tabular-nums">
                <thead className="bg-slate-50 text-slate-500 [&_th]:px-2.5 [&_th]:py-1.5 [&_th]:font-medium">
                  <tr><th className="text-left">chunk</th><th>BM25</th><th>vector</th><th>rerank</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100 [&_td]:px-2.5 [&_td]:py-1.5">{r.data.retrieval.slice(0, 5).map((c) => (
                  <tr key={c.chunk_id}><td className="text-slate-800">{c.chunk_id}</td><td className="text-center text-slate-600">{c.bm25_rank ?? "-"}</td>
                    <td className="text-center text-slate-600">{c.vector_rank ?? "-"}</td><td className="text-center text-emerald-700">{c.rerank_score.toFixed(3)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          </div>
          <div className="min-w-0 space-y-2">
            {r.data.graph?.paths.slice(0, 2).map((p) => (
              <div key={p.narrative} className="rounded-md bg-slate-50 p-2.5 text-[12.5px] text-slate-700 ring-1 ring-slate-200 ring-inset">{p.narrative}</div>
            ))}
            <div className="rounded-lg bg-emerald-50 p-3 leading-relaxed text-emerald-900 ring-1 ring-emerald-700/20 ring-inset">{r.data.answer_summary}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function GuardrailsTester() {
  const r = useRunner<Record<string, unknown>>();
  const d = r.data as { overall_verdict?: string; tripped?: string[]; pii?: { anonymized_text: string }; arbitrage?: { delta_pi_bdt: number; verdict: string; rationale: string[]; micro_credit?: { credit_limit_bdt: number } } } | null;
  return (
    <div className="space-y-3 text-[13px]">
      <div lang="bn" className="voice rounded-lg bg-slate-50 p-3 text-[15px] text-slate-800 ring-1 ring-slate-200 ring-inset">{GUARD_BODY.raw_text}</div>
      <RunButton busy={r.busy} onClick={() => r.run(() => api.guardrailsVerify(GUARD_BODY))} label="Verify (5,000 kg at Tk 10/kg)" />
      {r.error && <div className="text-rose-600">{r.error}</div>}
      {d && (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5"><Badge tone={d.overall_verdict === "BLOCKED" ? "red" : "emerald"}>{d.overall_verdict}</Badge>{d.tripped?.map((t) => <Badge key={t} tone="amber">{t}</Badge>)}</div>
          <div lang="bn" className="voice rounded-lg bg-emerald-50 p-3 text-[15px] text-emerald-900 ring-1 ring-emerald-700/20 ring-inset">{d.pii?.anonymized_text}</div>
          {d.arbitrage && <div className="font-mono text-[12.5px] tabular-nums text-slate-800">ΔΠ = {tk(d.arbitrage.delta_pi_bdt, 0)} · {d.arbitrage.verdict} · credit {tk(d.arbitrage.micro_credit?.credit_limit_bdt ?? 0, 0)}</div>}
          {d.arbitrage?.rationale.map((line) => <div key={line} className="text-[12.5px] text-slate-600">• {line}</div>)}
        </div>
      )}
    </div>
  );
}

function LocalTester() {
  const r = useRunner<LocalModelsReport>();
  return (
    <div className="space-y-3 text-[13px]">
      <RunButton busy={r.busy} onClick={() => r.run(async () => (await api.localModels()).data)} label="Probe local runtimes" />
      {r.error && <div className="text-rose-600">{r.error}</div>}
      {r.data && (
        <>
          <div className="flex flex-wrap gap-1.5">{r.data.runtimes.map((rt) => <Badge key={rt.runtime} tone={rt.reachable ? "emerald" : "slate"}>{rt.runtime} {rt.reachable ? "live" : "not running"}</Badge>)}</div>
          <div className="scroll-thin overflow-x-auto">
            <table className="w-full min-w-[480px] text-[12.5px]">
              <tbody className="divide-y divide-slate-100">{r.data.models.map((m) => (
                <tr key={m.key}><td className="py-2 pr-3 font-medium text-slate-900">{m.display_name}</td><td className="pr-3 text-slate-600">{m.role}</td>
                  <td className="font-mono tabular-nums text-slate-700">{m.telemetry.vram_mb} MB · {m.telemetry.decode_tokens_per_s} tok/s (modelled)</td></tr>
              ))}</tbody>
            </table>
          </div>
          <div className="text-[12.5px] text-slate-700">LoRA {r.data.lora_adapter.name}: <Badge tone="amber">{r.data.lora_adapter.status}</Badge> rank {r.data.lora_adapter.rank} · {r.data.lora_adapter.dataset.total_examples.toLocaleString()} SFT examples</div>
        </>
      )}
    </div>
  );
}

function WorkflowsTester() {
  const r = useRunner<PoolView[]>();
  return (
    <div className="space-y-3 text-[13px]">
      <RunButton busy={r.busy} onClick={() => r.run(async () => (await api.truckPools()).data)} label="Read durable pool state" />
      {r.error && <div className="text-rose-600">{r.error}</div>}
      {r.data && (
        <div className="divide-y divide-slate-100">
          {r.data.map((p) => (
            <div key={p.pool_id} className="flex flex-wrap items-center gap-2 py-2">
              <span className="font-mono text-slate-900">{p.pool_id}</span><Badge tone={p.status === "DISPATCHED" ? "amber" : "emerald"}>{p.status}</Badge>
              <span className="tabular-nums text-slate-600">{p.loaded_kg.toLocaleString()} / 5,000 kg · {p.smallholders} lots</span>
              {p.dispatch && <span className="font-mono text-[12px] text-amber-700">escrow {p.dispatch.escrow_id}</span>}
            </div>
          ))}
        </div>
      )}
      <div className="text-[12.5px] text-slate-600">n8n jobs: Daily DAM Price Sync (0 6 * * * Asia/Dhaka) and Hourly SAR Flood Check (0 * * * *); import JSON from GET /automation/n8n/workflows.</div>
    </div>
  );
}

const STEPS = [
  "Step 1 · MCP foundation: 3 servers, 13 tools, JSON-RPC 2.0, anomaly injection",
  "Step 2 · Hybrid GraphRAG, CRAG, token optimisation, PII + ΔΠ guardrails",
  "Step 3 · LangGraph supervisor, 4 agents, XML prompt registry, durable automation",
  "Step 4 · Rural edge: Bangla dialect voice, optical grading, local LLM runtime",
  "Step 5 · React + Three.js frontend with split-screen judge mode",
  "Step 6 · /docs portal, measured metrics and 100-case regression suite",
];

function AidlcSteps() {
  return (
    <div className="space-y-3 text-[13.5px] leading-relaxed text-slate-700">
      <p className="max-w-[760px]">AGENTS.md (mirrored as CLAUDE.md) is the single specification the coding agent reads before every step: mission, non-negotiable rules (no placeholders, strict typing, Bangladeshi seed data) and the target file tree. Each step ends with a verification gate before the next begins.</p>
      <ol className="space-y-1.5">{STEPS.map((s) => <li key={s} className="flex gap-2"><CheckCircle2 className="mt-[3px] size-4 shrink-0 text-emerald-600" />{s}</li>)}</ol>
    </div>
  );
}

export function DepthMatrixSection() {
  const [tab, setTab] = useState<Tab>("compress");
  return (
    <div className="space-y-4">
      <p className="max-w-[760px] text-[15px] leading-relaxed text-slate-600">
        The congress judges AI depth with its 110-point AI Depth Score rubric; each row below links one rubric area to an endpoint you can call live, and the testers underneath call them for you.
      </p>
      <div className="surface overflow-hidden">
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-[13px]">
            <thead className="border-b border-slate-200 bg-slate-50 text-[12px] text-slate-500 [&_th]:px-4 [&_th]:py-2.5 [&_th]:font-medium">
              <tr><th>Rubric area</th><th>Implementation</th><th>Live evidence</th><th>Status</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {MATRIX.map((row) => (
                <tr key={row.category} className="align-top [&>td]:px-4 [&>td]:py-3">
                  <td className="font-medium text-slate-900">{row.category}</td>
                  <td className="text-slate-600">
                    {row.implementation}
                    {row.note && <div className={cn("mt-1 text-[12px]", row.status === "Partial" ? "text-amber-700" : "text-slate-500")}>{row.note}</div>}
                  </td>
                  <td className="font-mono text-[12px] whitespace-nowrap text-sky-700">{row.evidence}</td>
                  <td>{row.status === "Live"
                    ? <Badge tone="emerald"><CheckCircle2 className="size-3" /> Live</Badge>
                    : <Badge tone="amber"><CircleDashed className="size-3" /> Partial</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="surface min-w-0">
        {/* The inset shadow is the tab rail's hairline, so the active underline can sit on it inside the scroll box. */}
        <div role="tablist" aria-label="Live AI layer testers" className="scroll-thin flex overflow-x-auto px-2 shadow-[inset_0_-1px_0_var(--color-slate-200)]">
          {TABS.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
              className={cn("shrink-0 border-b-2 px-3 py-3 text-[13.5px] font-medium whitespace-nowrap transition-colors",
                tab === t.id ? "border-emerald-700 text-emerald-800" : "border-transparent text-slate-600 hover:text-slate-900")}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="p-4 sm:p-5">
          {tab === "prompts" && <PromptsTester />}
          {tab === "compress" && <CompressTester />}
          {tab === "rag" && <RagTester />}
          {tab === "guardrails" && <GuardrailsTester />}
          {tab === "local" && <LocalTester />}
          {tab === "workflows" && <WorkflowsTester />}
          {tab === "aidlc" && <AidlcSteps />}
        </div>
      </div>
    </div>
  );
}
