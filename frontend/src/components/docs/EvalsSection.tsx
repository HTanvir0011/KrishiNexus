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
    <div className="min-w-0">
      <div className="flex items-baseline justify-between gap-3 text-[13px]">
        <span className="font-medium text-slate-900">{LABELS[name] ?? name}</span>
        <span className="shrink-0 tabular-nums">
          <span className={cn("num", meets ? "text-emerald-700" : "text-amber-700")}>{(value * 100).toFixed(1)}%</span>
          <span className="text-slate-500"> / target {(target * 100).toFixed(1)}%</span>
        </span>
      </div>
      <div className="relative mt-2 h-2 rounded-full bg-slate-100" aria-hidden>
        <div className={cn("h-full rounded-full", meets ? "bg-emerald-600" : "bg-amber-500")} style={{ width: `${Math.min(100, value * 100)}%` }} />
        <div className="absolute -top-[3px] h-3.5 w-0.5 -translate-x-1/2 rounded-full bg-slate-900" style={{ left: `${target * 100}%` }} title={`target ${target}`} />
      </div>
      <div className="mt-1 text-[12px] text-slate-500">{method} · n = <span className="tabular-nums">{n}</span></div>
    </div>
  );
}

function CaseRow({ c }: { c: RegressionCase }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-slate-100 last:border-b-0">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-slate-50">
        {c.passed ? <CheckCircle2 className="size-4 shrink-0 text-emerald-600" /> : <XCircle className="size-4 shrink-0 text-rose-600" />}
        <span className="w-16 shrink-0 font-mono text-[11.5px] text-slate-500 sm:w-20">{c.case_id}</span>
        <span className="min-w-0 flex-1 truncate text-[13px] text-slate-900">{c.title}</span>
        {/* Phones keep the width for the title; the judge score shows from 640 px up. */}
        {c.judge && <Badge tone="violet" className="max-sm:hidden">judge <span className="tabular-nums">{c.judge.score.toFixed(2)}</span></Badge>}
        <span className="w-14 shrink-0 text-right font-mono text-[11.5px] tabular-nums text-slate-500">{c.latency_ms.toFixed(1)} ms</span>
      </button>
      {open && (
        <div className="space-y-1 pr-2 pb-2.5 pl-8 font-mono text-[11.5px] break-all text-slate-600">
          <div className="text-emerald-700">proof: {c.proof}</div>
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
    <div className="space-y-4">
      <div className="surface p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em] text-slate-900">
            <FlaskConical className="size-4 text-violet-700" /> Measured RAGAS-style metrics
          </h3>
          <Button onClick={() => loadMetrics(true)} disabled={metricsBusy}>{metricsBusy ? <Spinner /> : <RefreshCw className="size-3.5" />} Recompute</Button>
        </div>
        {!metrics && !error && <div className="mt-4 flex items-center gap-2 text-[13px] text-slate-500"><Spinner /> Computing over the eval set…</div>}
        {metrics && (
          <>
            <div className="mt-5 grid gap-x-8 gap-y-5 md:grid-cols-2">
              {metrics.metrics.map((m) => <MetricBar key={m.name} name={m.name} value={m.value} target={m.target} method={m.method} n={m.sample_size} />)}
            </div>
            <div className="mt-5 space-y-1 border-t border-slate-100 pt-3 text-[12px] text-slate-500">
              <div className="tabular-nums">PII precision {(metrics.pii_redaction_precision * 100).toFixed(1)}% · computed in <span className="font-mono">{metrics.duration_ms.toFixed(0)} ms</span></div>
              {metrics.notes.map((n) => <div key={n}>• {n}</div>)}
            </div>
          </>
        )}
      </div>

      <div className="surface p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary" onClick={run} disabled={busy}>{busy ? <Spinner /> : <Play className="size-3.5" />} Run live regression suite</Button>
          {report && (
            <>
              <Badge tone={report.failed === 0 ? "emerald" : "red"}>
                <span className="tabular-nums">{done ? `${report.pass_rate_pct}% passed` : `Running ${shown}/${report.total_cases}`}</span>
              </Badge>
              <span className="text-[12px] tabular-nums text-slate-500">
                {report.passed}/{report.total_cases} passed · suite <span className="font-mono">{report.duration_ms.toFixed(0)} ms</span> · seed {report.seed}
              </span>
            </>
          )}
          {error && <span className="text-[13px] text-rose-600">{error}</span>}
        </div>
        {report && (
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
            {report.categories.map((cat) => {
              const seen = visible.filter((c) => c.category === cat.category);
              return (
                <div key={cat.category} className="min-w-0 rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200 ring-inset">
                  <div className="truncate text-[12px] font-medium text-slate-700" title={cat.title}>{cat.title}</div>
                  <div className="num my-1 text-[15px] text-emerald-700">{seen.filter((c) => c.passed).length}/{cat.total}</div>
                  <ProgressBar value={seen.length} max={cat.total} tone={seen.some((c) => !c.passed) ? "red" : "emerald"} className="h-1.5" />
                  <div className="mt-1.5 font-mono text-[11px] tabular-nums text-slate-500">avg {cat.avg_latency_ms} ms</div>
                </div>
              );
            })}
          </div>
        )}
        <div className="scroll-thin mt-4 max-h-[420px] overflow-y-auto rounded-lg bg-white p-1 ring-1 ring-slate-200 ring-inset">
          {!report && <div className="px-4 py-10 text-center text-[13px] text-slate-500">100 seeded scenarios: 5 categories × 20 cases, each checked against an independently recomputed expectation.</div>}
          {visible.map((c) => <CaseRow key={c.case_id} c={c} />)}
        </div>
      </div>
    </div>
  );
}
