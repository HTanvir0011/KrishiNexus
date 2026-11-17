import { Activity, CloudRain, MessageSquare, RefreshCw, RotateCcw, ThumbsDown, ThumbsUp, Truck, Wallet, X, Zap } from "lucide-react";
import { useCallback } from "react";

import { api } from "../api/client";
import { Badge, Button, Panel, ProgressBar, Spinner, Stat } from "../components/ui";
import { kg, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { setState } from "../state/store";
import { TABLE, TD, TH, useAdmin, when } from "./useAdmin";

const COPY = {
  en: {
    pools: "Truck pools", resetPools: "Reset truck pools", confirmResetPools: "Re-seed every truck pool? Farmers' joined lots are removed.",
    poolHeaders: ["Pool", "Crop", "Fill", "Smallholders", "Status / buyer"], open: "Open", dispatched: "Dispatched", poolsReset: "Truck pools re-seeded",
    escrows: "Escrows", simulated: "Simulated escrows: no money moves and no wallet API is called.",
    escrowHeaders: ["Escrow", "Farmer", "Buyer", "Lot", "Amount", "Wallet", "Locked"], noEscrows: "No escrow has been locked yet.", belowFloor: "below cost floor",
    anomalies: "Anomalies", inject: "Inject for a demo", powerCut: "Power cut · BCSA-MUN-01", flood: "Flash flood · Tahirpur", clearAll: "Clear all",
    anomalyHeaders: ["Anomaly", "Target", "Started", "Expires", ""], noAnomalies: "No active anomalies.", injected: "Anomaly injected", cleared: "Cleared",
    powerCutLabel: "Cold-chamber power cut", floodLabel: "Haor flash flood",
    activity: "Agent activity", activityLede: "The latest agent trace events, newest first.", refresh: "Refresh",
    traceHeaders: ["Time", "Agent", "Step", "Tool", "Summary", "ms"], noActivity: "No agent activity yet. Run a farmer request.",
  },
  bn: {
    pools: "ট্রাক পুল", resetPools: "ট্রাক পুল রিসেট", confirmResetPools: "সব ট্রাক পুল নতুন করে শুরু করবেন? কৃষকদের যোগ করা লট মুছে যাবে।",
    poolHeaders: ["পুল", "ফসল", "ভরাট", "কৃষক", "অবস্থা / ক্রেতা"], open: "খোলা", dispatched: "রওনা", poolsReset: "ট্রাক পুল নতুন করে শুরু",
    escrows: "এসক্রো", simulated: "সিমুলেটেড এসক্রো: কোনো টাকা লেনদেন হয় না।",
    escrowHeaders: ["এসক্রো", "কৃষক", "ক্রেতা", "লট", "টাকা", "ওয়ালেট", "সময়"], noEscrows: "এখনও কোনো এসক্রো লক হয়নি।", belowFloor: "খরচের নিচে",
    anomalies: "দুর্ঘটনা", inject: "ডেমোর জন্য চালু করুন", powerCut: "বিদ্যুৎ বিভ্রাট · BCSA-MUN-01", flood: "আকস্মিক বন্যা · তাহিরপুর", clearAll: "সব মুছুন",
    anomalyHeaders: ["ঘটনা", "লক্ষ্য", "শুরু", "শেষ", ""], noAnomalies: "কোনো সক্রিয় দুর্ঘটনা নেই।", injected: "চালু হয়েছে", cleared: "মুছে ফেলা হয়েছে",
    powerCutLabel: "হিমাগারে বিদ্যুৎ বিভ্রাট", floodLabel: "হাওরে আকস্মিক বন্যা",
    activity: "এজেন্ট কার্যক্রম", activityLede: "সর্বশেষ এজেন্ট ট্রেস, নতুনটি আগে।", refresh: "রিফ্রেশ",
    traceHeaders: ["সময়", "এজেন্ট", "ধাপ", "টুল", "সারাংশ", "ms"], noActivity: "এখনও কোনো কার্যক্রম নেই। একটি কৃষক অনুরোধ চালান।",
  },
};

const loadPools = async () => (await api.truckPools()).data;

export function PoolsSection() {
  const c = useCopy(COPY);
  const { data: pools, busy, run } = useAdmin(loadPools);
  return (
    <Panel title={c.pools} icon={<Truck className="size-4 text-amber-600" aria-hidden />}
      actions={
        <Button variant="quiet" disabled={busy !== null}
          onClick={() => window.confirm(c.confirmResetPools) && void run("reset", async () => setState({ pools: await api.resetPools() }), c.poolsReset)}>
          <RotateCcw className="size-4" aria-hidden /> {c.resetPools}
        </Button>
      }>
      {!pools ? <Spinner /> : (
        <div className="scroll-thin -mx-1 overflow-x-auto">
          <table className={TABLE}>
            <thead><tr className="border-b border-slate-200">{c.poolHeaders.map((h) => <th key={h} scope="col" className={TH}>{h}</th>)}</tr></thead>
            <tbody>
              {pools.map((p) => (
                <tr key={p.pool_id} className="border-b border-slate-100">
                  <td className={TD}>
                    <div className="font-mono text-[12.5px] font-semibold text-slate-900">{p.pool_id}</div>
                    <div className="text-[12px] text-slate-500">{p.district} · {p.upazila} · {p.union}</div>
                  </td>
                  <td className={TD}>{p.crop}</td>
                  <td className={`${TD} min-w-[160px]`}>
                    <ProgressBar value={p.loaded_kg} max={p.capacity_kg} tone={p.status === "DISPATCHED" ? "emerald" : "amber"} />
                    <div className="mt-1 text-[12px] text-slate-600">{kg(p.loaded_kg)} / {kg(p.capacity_kg)} · {p.fill_pct.toFixed(0)}%</div>
                  </td>
                  <td className={TD}>{p.smallholders} · {p.lots.length} lots</td>
                  <td className={TD}>
                    <Badge tone={p.status === "DISPATCHED" ? "emerald" : "amber"}>{p.status === "DISPATCHED" ? c.dispatched : c.open}</Badge>
                    {p.dispatch && <div className="mt-1 text-[12px] text-slate-600">{p.dispatch.buyer_name} · {tk(p.dispatch.escrow_amount_tk)}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

export function EscrowsSection() {
  const c = useCopy(COPY);
  const { data: escrows } = useAdmin(api.adminEscrows);
  return (
    <Panel title={c.escrows} icon={<Wallet className="size-4 text-emerald-700" aria-hidden />}>
      <p className="m-0 mb-3 rounded-lg bg-amber-100/70 px-3 py-2 text-[13px] text-amber-900 ring-1 ring-inset ring-amber-600/20">{c.simulated}</p>
      {!escrows ? <Spinner /> : escrows.length === 0 ? <p className="m-0 text-[14px] text-slate-600">{c.noEscrows}</p> : (
        <div className="scroll-thin -mx-1 overflow-x-auto">
          <table className={TABLE}>
            <thead><tr className="border-b border-slate-200">{c.escrowHeaders.map((h) => <th key={h} scope="col" className={TH}>{h}</th>)}</tr></thead>
            <tbody>
              {escrows.map((e) => (
                <tr key={e.escrow_id} className="border-b border-slate-100">
                  <td className={`${TD} font-mono text-[12px]`}>{e.escrow_id}</td>
                  <td className={`${TD} font-mono text-[12px]`}>{e.farmer_id}</td>
                  <td className={TD}>{e.buyer_name}</td>
                  <td className={TD}>{kg(e.weight_kg)}</td>
                  <td className={TD}>
                    <span className="num">{tk(e.amount_tk)}</span>
                    {e.below_cost_floor && <Badge tone="red" className="ml-1.5">{c.belowFloor}</Badge>}
                  </td>
                  <td className={TD}>{e.wallet} {e.wallet_masked}</td>
                  <td className={TD}>{when(e.locked_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

export function AnomaliesSection() {
  const c = useCopy(COPY);
  const { data: anomalies, busy, run } = useAdmin(api.anomalies);
  return (
    <Panel title={c.anomalies} icon={<Zap className="size-4 text-rose-600" aria-hidden />}
      actions={anomalies && anomalies.length > 0 && (
        <Button variant="quiet" disabled={busy !== null} onClick={() => void run("clear-all", api.clearAnomalies, c.cleared)}>{c.clearAll}</Button>
      )}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-medium text-slate-600">{c.inject}:</span>
        <Button variant="ghost" disabled={busy !== null} onClick={() => void run("cut", () => api.simulatePowerCut("BCSA-MUN-01"), c.injected)}>
          <Zap className="size-4 text-rose-600" aria-hidden /> {c.powerCut}
        </Button>
        <Button variant="ghost" disabled={busy !== null} onClick={() => void run("flood", () => api.simulateFlashFlood("Tahirpur"), c.injected)}>
          <CloudRain className="size-4 text-sky-600" aria-hidden /> {c.flood}
        </Button>
      </div>
      {!anomalies ? <Spinner /> : anomalies.length === 0 ? <p className="m-0 text-[14px] text-slate-600">{c.noAnomalies}</p> : (
        <div className="scroll-thin -mx-1 overflow-x-auto">
          <table className={TABLE}>
            <thead><tr className="border-b border-slate-200">{c.anomalyHeaders.map((h, i) => <th key={i} scope="col" className={TH}>{h}</th>)}</tr></thead>
            <tbody>
              {anomalies.map((a) => (
                <tr key={a.anomaly_id} className="border-b border-slate-100">
                  <td className={TD}>
                    <Badge tone={a.anomaly_type === "haor_flash_flood" ? "sky" : "red"}>{a.anomaly_type === "haor_flash_flood" ? c.floodLabel : c.powerCutLabel}</Badge>
                    <div className="mt-1 font-mono text-[11.5px] text-slate-500">{a.anomaly_id}</div>
                  </td>
                  <td className={TD}>{a.target}</td>
                  <td className={TD}>{when(a.activated_at)}</td>
                  <td className={TD}>{when(a.expires_at)}</td>
                  <td className={TD}>
                    <Button variant="quiet" className="min-h-9" disabled={busy !== null} aria-label={`${c.cleared}: ${a.anomaly_id}`}
                      onClick={() => void run(`clear-${a.anomaly_id}`, () => api.clearAnomaly(a.anomaly_id), c.cleared)}>
                      <X className="size-4" aria-hidden />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

export function ActivitySection() {
  const c = useCopy(COPY);
  const load = useCallback(async () => (await api.traceHistory(150)).slice().reverse(), []);
  const { data: events, busy, reload, run } = useAdmin(load);
  return (
    <Panel title={c.activity} icon={<Activity className="size-4 text-sky-600" aria-hidden />}
      actions={
        <Button variant="quiet" disabled={busy !== null} onClick={() => void run("refresh", reload, c.refresh)}>
          <RefreshCw className="size-4" aria-hidden /> {c.refresh}
        </Button>
      }>
      <p className="m-0 mb-3 text-[13px] text-slate-600">{c.activityLede}</p>
      {!events ? <Spinner /> : events.length === 0 ? <p className="m-0 text-[14px] text-slate-600">{c.noActivity}</p> : (
        <div className="scroll-thin -mx-1 max-h-[70vh] overflow-auto">
          <table className={TABLE}>
            <thead className="sticky top-0 bg-white"><tr className="border-b border-slate-200">{c.traceHeaders.map((h) => <th key={h} scope="col" className={TH}>{h}</th>)}</tr></thead>
            <tbody>
              {events.map((e) => (
                <tr key={`${e.session_id}#${e.seq}`} className="border-b border-slate-100">
                  <td className={`${TD} whitespace-nowrap text-[12px]`}>{when(e.timestamp)}</td>
                  <td className={TD}>{e.agent_name}</td>
                  <td className={TD}><Badge>{e.step_type}</Badge></td>
                  <td className={`${TD} font-mono text-[12px]`}>{e.tool_name ?? "—"}</td>
                  <td className={`${TD} max-w-[420px] text-[12.5px] text-slate-700`}>{e.payload_summary}</td>
                  <td className={`${TD} num text-right`}>{Math.round(e.latency_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

const FEEDBACK_COPY = {
  en: {
    title: "Feedback", total: "Answers rated", useful: "Rated useful", byRole: "By role", none: "No feedback yet. Farmers rate each decision in the farmer app.",
    headers: ["When", "Rating", "Comment", "Who", "Session"], yes: "Useful", no: "Not useful", hidden: (n: number) => `${n} personal detail hidden`,
  },
  bn: {
    title: "মতামত", total: "মোট মতামত", useful: "কাজে লেগেছে", byRole: "ভূমিকা অনুযায়ী", none: "এখনও কোনো মতামত নেই। কৃষক অ্যাপে প্রতিটি সিদ্ধান্তে মতামত দেন।",
    headers: ["সময়", "মত", "মন্তব্য", "কে", "সেশন"], yes: "কাজে লেগেছে", no: "কাজে লাগেনি", hidden: (n: number) => `${n}টি ব্যক্তিগত তথ্য লুকানো`,
  },
};

export function FeedbackSection() {
  const c = useCopy(FEEDBACK_COPY);
  const { data, busy, reload, run } = useAdmin(api.adminFeedback);
  return (
    <Panel title={c.title} icon={<MessageSquare className="size-4 text-emerald-700" aria-hidden />}
      actions={<Button variant="quiet" disabled={busy !== null} onClick={() => void run("refresh", reload, "Refreshed")}><RefreshCw className="size-4" aria-hidden /></Button>}>
      {!data ? <Spinner /> : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
            <Stat label={c.total} value={data.total} />
            <Stat label={c.useful} value={data.useful_pct === null ? "—" : `${data.useful_pct}%`} tone="emerald" hint={`${data.useful} / ${data.total}`} />
            <Stat label={c.byRole} value={Object.keys(data.by_role).length} hint={Object.entries(data.by_role).map(([role, n]) => `${role} ${n}`).join(" · ")} />
          </div>
          {data.items.length === 0 ? <p className="m-0 text-[14px] text-slate-600">{c.none}</p> : (
            <div className="scroll-thin -mx-1 overflow-x-auto">
              <table className={TABLE}>
                <thead><tr className="border-b border-slate-200">{c.headers.map((h) => <th key={h} scope="col" className={TH}>{h}</th>)}</tr></thead>
                <tbody>
                  {data.items.map((f) => (
                    <tr key={f.feedback_id} className="border-b border-slate-100">
                      <td className={`${TD} whitespace-nowrap text-[12px]`}>{when(f.at)}</td>
                      <td className={TD}>
                        <Badge tone={f.useful ? "emerald" : "red"}>
                          {f.useful ? <ThumbsUp className="mr-1 inline size-3" aria-hidden /> : <ThumbsDown className="mr-1 inline size-3" aria-hidden />}
                          {f.useful ? c.yes : c.no}
                        </Badge>
                      </td>
                      <td className={`${TD} max-w-[380px] text-[13px] text-slate-700`}>
                        {f.comment || "—"}
                        {f.pii_hidden > 0 && <div className="text-[11.5px] text-amber-700">{c.hidden(f.pii_hidden)}</div>}
                      </td>
                      <td className={`${TD} text-[12.5px]`}>{f.user_id ? <span className="font-mono">{f.user_id}</span> : "visitor"}{f.role ? ` · ${f.role}` : ""}</td>
                      <td className={`${TD} font-mono text-[11.5px] text-slate-500`}>{f.session_id ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
