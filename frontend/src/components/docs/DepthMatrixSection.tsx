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
const TABS: { id: Tab; label: string }[] = [
  { id: "prompts", label: "XML prompts & DSPy" }, { id: "compress", label: "LLMLingua-2" }, { id: "rag", label: "GraphRAG + CRAG" },
  { id: "guardrails", label: "PII & ΔΠ breaker" }, { id: "local", label: "Ollama & LoRA" }, { id: "workflows", label: "n8n + Temporal" },
  { id: "aidlc", label: "AI-DLC" },
];

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
    <div className="space-y-2">
      <RunButton busy={r.busy} onClick={() => r.run(api.promptsRegistry)} label="Load prompt registry" />
      {r.error && <div className="text-xs text-red-300">{r.error}</div>}
      {r.data && (
        <>
          <div className="flex flex-wrap gap-1">
            {r.data.agents.map((a) => (
              <button key={a.agent} type="button" onClick={() => setAgent(a.agent)}
                className={cn("rounded-md px-2 py-1 text-[11px] ring-1", agent === a.agent ? "bg-emerald-500/20 ring-emerald-400/50" : "bg-ink-800 ring-ink-600")}>
                {a.agent} <span className="font-mono text-emerald-300">{a.optimization.baseline_score.toFixed(2)}→{a.optimization.optimized_score.toFixed(2)}</span>
              </button>
            ))}
          </div>
          {view && (
            <div className="text-[11px] text-slate-400">{view.optimization.method} · {view.optimization.trials_evaluated} candidates · active {view.active_version}</div>
          )}
          <pre className="scroll-thin max-h-72 overflow-auto rounded-lg bg-black/40 p-2 font-mono text-[10.5px] leading-relaxed">
            {view?.optimization.diff.map((line, i) => (
              <div key={i} className={line.startsWith("+") ? "text-emerald-300" : line.startsWith("-") ? "text-red-300" : "text-slate-500"}>{line}</div>
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
    <div className="grid gap-2 lg:grid-cols-2">
      <div className="space-y-2">
        <div className="flex gap-1.5">
          <Button onClick={() => setText(WEATHER_JSON)}>168-hour weather JSON</Button>
          <Button onClick={() => setText(DAM_TEXT)}>DAM price text</Button>
          <RunButton busy={r.busy} onClick={() => r.run(() => api.compress(text))} label="Compress" />
        </div>
        <textarea value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} aria-label="Context to compress"
          className="h-48 w-full rounded-lg bg-black/40 p-2 font-mono text-[10px] text-slate-300 ring-1 ring-ink-600" />
      </div>
      <div className="space-y-2 text-xs">
        {r.error && <div className="text-red-300">{r.error}</div>}
        {c && (
          <>
            <div className="flex flex-wrap gap-1.5">
              <Badge tone="violet">{c.original_tokens} → {c.compressed_tokens} tokens</Badge>
              <Badge tone="emerald">{c.reduction_factor}x reduction</Badge>
              <Badge tone={c.all_numbers_preserved ? "emerald" : "red"}>numbers preserved: {String(c.all_numbers_preserved)}</Badge>
              <Badge tone="sky">dedup {r.data?.deduplication.input_chunks}→{r.data?.deduplication.kept_chunks}</Badge>
            </div>
            <div className="text-[11px] text-slate-400">Cache eligible: {Object.entries(r.data?.cache.cache_eligible ?? {}).map(([k, v]) => `${k} ${v ? "yes" : "no"}`).join(" · ")}</div>
            <pre className="scroll-thin max-h-40 overflow-auto rounded-lg bg-black/40 p-2 font-mono text-[10px] text-emerald-100 whitespace-pre-wrap">{c.compressed_text}</pre>
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
    <div className="space-y-2">
      <div className="flex gap-1.5">
        <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Farmer question"
          className="bn min-w-0 flex-1 rounded-lg bg-ink-800 px-2 py-1.5 text-xs ring-1 ring-ink-600" />
        <RunButton busy={r.busy} onClick={() => r.run(() => api.ragQuery(query, "Munshiganj", "Cardinal Potato"))} label="Query" />
      </div>
      {r.error && <div className="text-xs text-red-300">{r.error}</div>}
      {r.data && (
        <div className="grid gap-2 text-xs lg:grid-cols-2">
          <div className="space-y-1.5">
            <div className="flex flex-wrap gap-1">
              <Badge tone="violet">{r.data.rewrite.detected_dialect}</Badge>
              {r.data.rewrite.intents.map((i) => <Badge key={i} tone="sky">{i}</Badge>)}
              <Badge tone={r.data.crag.verdict === "CORRECT" ? "emerald" : "amber"}>CRAG {r.data.crag.verdict} {r.data.crag.confidence.toFixed(2)}</Badge>
            </div>
            <div className="text-[11px] text-slate-400">HyDE formal query: {r.data.rewrite.formal_query}</div>
            <table className="w-full font-mono text-[10.5px]">
              <thead className="text-slate-500"><tr><th className="text-left">chunk</th><th>BM25</th><th>vector</th><th>rerank</th></tr></thead>
              <tbody>{r.data.retrieval.slice(0, 5).map((c) => (
                <tr key={c.chunk_id}><td className="text-slate-300">{c.chunk_id}</td><td className="text-center">{c.bm25_rank ?? "-"}</td>
                  <td className="text-center">{c.vector_rank ?? "-"}</td><td className="text-center text-emerald-300">{c.rerank_score.toFixed(3)}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <div className="space-y-1.5">
            {r.data.graph?.paths.slice(0, 2).map((p) => <div key={p.narrative} className="rounded bg-ink-800 p-1.5 text-[10.5px] text-slate-300">{p.narrative}</div>)}
            <div className="rounded-lg bg-emerald-950/40 p-2 text-[11px] leading-relaxed text-emerald-50 ring-1 ring-emerald-500/30">{r.data.answer_summary}</div>
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
    <div className="space-y-2 text-xs">
      <div className="bn rounded-lg bg-black/30 p-2 text-slate-300">{GUARD_BODY.raw_text}</div>
      <RunButton busy={r.busy} onClick={() => r.run(() => api.guardrailsVerify(GUARD_BODY))} label="Verify (5,000 kg at Tk 10/kg)" />
      {r.error && <div className="text-red-300">{r.error}</div>}
      {d && (
        <div className="space-y-1.5">
          <div className="flex flex-wrap gap-1"><Badge tone={d.overall_verdict === "BLOCKED" ? "red" : "emerald"}>{d.overall_verdict}</Badge>{d.tripped?.map((t) => <Badge key={t} tone="amber">{t}</Badge>)}</div>
          <div className="bn rounded-lg bg-black/30 p-2 text-emerald-100">{d.pii?.anonymized_text}</div>
          {d.arbitrage && <div className="font-mono text-[11px] text-slate-300">ΔΠ = {tk(d.arbitrage.delta_pi_bdt, 0)} · {d.arbitrage.verdict} · credit {tk(d.arbitrage.micro_credit?.credit_limit_bdt ?? 0, 0)}</div>}
          {d.arbitrage?.rationale.map((line) => <div key={line} className="text-[11px] text-slate-400">• {line}</div>)}
        </div>
      )}
    </div>
  );
}

function LocalTester() {
  const r = useRunner<LocalModelsReport>();
  return (
    <div className="space-y-2 text-xs">
      <RunButton busy={r.busy} onClick={() => r.run(async () => (await api.localModels()).data)} label="Probe local runtimes" />
      {r.error && <div className="text-red-300">{r.error}</div>}
      {r.data && (
        <>
          <div className="flex flex-wrap gap-1">{r.data.runtimes.map((rt) => <Badge key={rt.runtime} tone={rt.reachable ? "emerald" : "slate"}>{rt.runtime} {rt.reachable ? "live" : "not running"}</Badge>)}</div>
          <table className="w-full text-[11px]">
            <tbody>{r.data.models.map((m) => (
              <tr key={m.key} className="border-b border-ink-700"><td className="py-1 text-slate-200">{m.display_name}</td><td className="text-slate-400">{m.role}</td>
                <td className="font-mono text-slate-300">{m.telemetry.vram_mb} MB · {m.telemetry.decode_tokens_per_s} tok/s (modelled)</td></tr>
            ))}</tbody>
          </table>
          <div className="text-[11px] text-slate-300">LoRA {r.data.lora_adapter.name}: <Badge tone="amber">{r.data.lora_adapter.status}</Badge> rank {r.data.lora_adapter.rank} · {r.data.lora_adapter.dataset.total_examples.toLocaleString()} SFT examples</div>
        </>
      )}
    </div>
  );
}

function WorkflowsTester() {
  const r = useRunner<PoolView[]>();
  return (
    <div className="space-y-2 text-xs">
      <RunButton busy={r.busy} onClick={() => r.run(async () => (await api.truckPools()).data)} label="Read durable pool state" />
      {r.error && <div className="text-red-300">{r.error}</div>}
      {r.data && r.data.map((p) => (
        <div key={p.pool_id} className="flex flex-wrap items-center gap-2 border-b border-ink-700 py-1">
          <span className="font-mono text-slate-200">{p.pool_id}</span><Badge tone={p.status === "DISPATCHED" ? "amber" : "emerald"}>{p.status}</Badge>
          <span className="text-slate-400">{p.loaded_kg.toLocaleString()} / 5,000 kg · {p.smallholders} lots</span>
          {p.dispatch && <span className="font-mono text-[10px] text-amber-200">escrow {p.dispatch.escrow_id}</span>}
        </div>
      ))}
      <div className="text-[11px] text-slate-400">n8n jobs: Daily DAM Price Sync (0 6 * * * Asia/Dhaka) and Hourly SAR Flood Check (0 * * * *); import JSON from GET /automation/n8n/workflows.</div>
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

function AidlcPanel() {
  return (
    <div className="space-y-2 text-xs text-slate-300">
      <p>AGENTS.md (mirrored as CLAUDE.md) is the single specification the coding agent reads before every step: mission, non-negotiable rules (no placeholders, strict typing, Bangladeshi seed data) and the target file tree. Each step ends with a verification gate before the next begins.</p>
      <ol className="space-y-1">{STEPS.map((s) => <li key={s} className="flex gap-2"><CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-400" />{s}</li>)}</ol>
    </div>
  );
}

export function DepthMatrixSection() {
  const [tab, setTab] = useState<Tab>("prompts");
  return (
    <div className="space-y-3">
      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-xs">
          <thead className="text-[10px] uppercase tracking-wider text-slate-500">
            <tr><th className="px-3 py-2">Category</th><th>Implementation</th><th>Live evidence</th><th className="pr-3">Status</th></tr>
          </thead>
          <tbody className="divide-y divide-ink-700">
            {MATRIX.map((row) => (
              <tr key={row.category}>
                <td className="px-3 py-1.5 font-medium text-slate-100">{row.category}</td>
                <td className="py-1.5 text-slate-300">{row.implementation}{row.note && <div className="text-[10px] text-amber-300/80">{row.note}</div>}</td>
                <td className="font-mono text-[10.5px] text-sky-300">{row.evidence}</td>
                <td className="pr-3">{row.status === "Live"
                  ? <Badge tone="emerald"><CheckCircle2 className="size-3" /> Live</Badge>
                  : <Badge tone="amber"><CircleDashed className="size-3" /> Partial</Badge>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="panel p-3">
        <div className="mb-3 flex flex-wrap gap-1" role="tablist">
          {TABS.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
              className={cn("rounded-lg px-2.5 py-1 text-xs font-medium", tab === t.id ? "bg-emerald-500 text-ink-950" : "bg-ink-800 text-slate-300 hover:bg-ink-700")}>
              {t.label}
            </button>
          ))}
        </div>
        {tab === "prompts" && <PromptsTester />}
        {tab === "compress" && <CompressTester />}
        {tab === "rag" && <RagTester />}
        {tab === "guardrails" && <GuardrailsTester />}
        {tab === "local" && <LocalTester />}
        {tab === "workflows" && <WorkflowsTester />}
        {tab === "aidlc" && <AidlcPanel />}
      </div>
    </div>
  );
}
