import { CheckCircle2, FlaskConical, Play, RefreshCw, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api, ApiError, type RagasReport, type RegressionCase, type RegressionReport } from "../../api/client";
import { cn } from "../../lib/format";
import { Badge, Button, ProgressBar, Spinner } from "../ui";

const LABELS: Record<string, string> = {
  faithfulness: "Faithfulness",
  answer_relevancy: "Answer relevancy",
  context_precision: "Context precision",
  context_recall: "Context recall",
  mcp_json_schema_validity: "MCP JSON schema validity",
  pii_redaction_recall: "PII redaction recall",
};

function MetricBar({ name, value, target, method, n }: { name: string; value: number; target: number; method: string; n: number }) {
  const meets = value >= target;
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-slate-200">{LABELS[name] ?? name}</span>
        <span className="font-mono">
          <span className={meets ? "text-emerald-300" : "text-amber-300"}>{(value * 100).toFixed(1)}%</span>
          <span className="text-slate-500"> / target {(target * 100).toFixed(1)}%</span>
        </span>
      </div>
      <div className="relative mt-1 h-2 rounded-full bg-ink-700">
        <div className={cn("h-full rounded-full", meets ? "bg-emerald-400" : "bg-amber-400")} style={{ width: `${Math.min(100, value * 100)}%` }} />
        <div className="absolute -top-0.5 h-3 w-0.5 bg-slate-200" style={{ left: `${target * 100}%` }} title={`target ${target}`} />
      </div>
      <div className="mt-0.5 text-[10px] text-slate-500">{method} · n={n}</div>
    </div>
  );
}

function CaseRow({ c }: { c: RegressionCase }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-white/5">
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex w-full items-center gap-2 py-1 text-left hover:bg-white/5">
        {c.passed ? <CheckCircle2 className="size-3.5 shrink-0 text-emerald-400" /> : <XCircle className="size-3.5 shrink-0 text-red-400" />}
        <span className="w-20 shrink-0 font-mono text-[10px] text-slate-500">{c.case_id}</span>
        <span className="min-w-0 flex-1 truncate text-[11px] text-slate-200">{c.title}</span>
        {c.judge && <Badge tone="violet">judge {c.judge.score.toFixed(2)}</Badge>}
        <span className="w-14 shrink-0 text-right font-mono text-[10px] text-slate-400">{c.latency_ms.toFixed(1)} ms</span>
      </button>
      {open && (
        <div className="space-y-1 pb-2 pl-7 font-mono text-[10px] text-slate-400">
          <div className="text-emerald-200">proof: {c.proof}</div>
          <div>expected: {JSON.stringify(c.expected)}</div>
          <div>actual:&nbsp;&nbsp; {JSON.stringify(c.actual)}</div>
        </div>
      )}
    </div>
  );
}

export function EvalsSection() {
  const [metrics, setMetrics] = useState<RagasReport | null>(null);
  const [metricsBusy, setMetricsBusy] = useState(false);
  const [report, setReport] = useState<RegressionReport | null>(null);
  const [shown, setShown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const loadMetrics = async (refresh: boolean) => {
    setMetricsBusy(true);
    try {
      setMetrics(await api.evalMetrics(refresh));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMetricsBusy(false);
    }
  };

  useEffect(() => {
    void loadMetrics(false);
    return () => window.clearInterval(timer.current);
  }, []);

  const run = async () => {
    setBusy(true);
    setError(null);
    setShown(0);
    window.clearInterval(timer.current);
    try {
      const result = await api.runRegression(20);
      setReport(result);
      timer.current = window.setInterval(() => {
        setShown((n) => {
          if (n >= result.cases.length) {
            window.clearInterval(timer.current);
            return n;
          }
          return n + 1;
        });
      }, 35);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const visible = report?.cases.slice(0, shown) ?? [];
  const done = report && shown >= report.cases.length;
  return (
    <div className="grid gap-3 xl:grid-cols-[380px_1fr]">
      <div className="panel space-y-3 p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-100"><FlaskConical className="size-4 text-violet-300" /> Measured RAGAS-style metrics</div>
          <Button onClick={() => loadMetrics(true)} disabled={metricsBusy}>{metricsBusy ? <Spinner /> : <RefreshCw className="size-3.5" />} Recompute</Button>
        </div>
        {!metrics && !error && <div className="flex items-center gap-2 text-xs text-slate-400"><Spinner /> computing over the eval set…</div>}
        {metrics?.metrics.map((m) => <MetricBar key={m.name} name={m.name} value={m.value} target={m.target} method={m.method} n={m.sample_size} />)}
        {metrics && (
          <div className="space-y-1 border-t border-ink-700 pt-2 text-[10px] text-slate-500">
            <div>PII precision {(metrics.pii_redaction_precision * 100).toFixed(1)}% · computed in {metrics.duration_ms.toFixed(0)} ms</div>
            {metrics.notes.map((n) => <div key={n}>• {n}</div>)}
          </div>
        )}
      </div>

      <div className="panel flex min-h-[420px] flex-col gap-2 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary" onClick={run} disabled={busy}>{busy ? <Spinner /> : <Play className="size-3.5" />} Run Live Regression Suite</Button>
          {report && (
            <>
              <Badge tone={report.failed === 0 ? "emerald" : "red"} className="text-sm">
                {done ? `${report.pass_rate_pct}% PASS` : `running ${shown}/${report.total_cases}`}
              </Badge>
              <span className="text-[11px] text-slate-400">{report.passed}/{report.total_cases} passed · suite {report.duration_ms.toFixed(0)} ms · seed {report.seed}</span>
            </>
          )}
          {error && <span className="text-xs text-red-300">{error}</span>}
        </div>
        {report && (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
            {report.categories.map((cat) => {
              const seen = visible.filter((c) => c.category === cat.category);
              return (
                <div key={cat.category} className="rounded-lg bg-ink-800 p-2 ring-1 ring-ink-600">
                  <div className="truncate text-[10.5px] font-semibold text-slate-200" title={cat.title}>{cat.title}</div>
                  <div className="my-1 font-mono text-xs text-emerald-300">{seen.filter((c) => c.passed).length}/{cat.total}</div>
                  <ProgressBar value={seen.length} max={cat.total} tone={seen.some((c) => !c.passed) ? "red" : "emerald"} className="h-1.5" />
                  <div className="mt-1 text-[10px] text-slate-500">avg {cat.avg_latency_ms} ms</div>
                </div>
              );
            })}
          </div>
        )}
        <div className="scroll-thin max-h-[420px] flex-1 overflow-y-auto rounded-lg bg-black/40 p-2">
          {!report && <div className="py-10 text-center text-xs text-slate-500">100 seeded scenarios: 5 categories × 20 cases, each checked against an independently recomputed expectation.</div>}
          {visible.map((c) => <CaseRow key={c.case_id} c={c} />)}
        </div>
      </div>
    </div>
  );
}
