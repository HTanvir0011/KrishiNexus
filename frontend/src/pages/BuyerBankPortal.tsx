import { Banknote, Building2, Fingerprint, Landmark, Lock, Satellite, ShieldCheck, Truck } from "lucide-react";
import { useMemo, useState } from "react";

import { api, ApiError, type PoolView } from "../api/client";
import { Badge, Button, Panel, ProgressBar, Spinner } from "../components/ui";
import { cn, kg, shortHash, tk } from "../lib/format";
import { pushAlert, refreshPools, setState, useAppState } from "../state/store";

function ScoreGauge({ score }: { score: number }) {
  const t = (score - 300) / 550;
  const angle = Math.PI * (1 - t);
  const x = 100 + 80 * Math.cos(angle);
  const y = 100 - 80 * Math.sin(angle);
  const color = score >= 750 ? "#34d399" : score >= 650 ? "#fbbf24" : "#f87171";
  return (
    <svg viewBox="0 0 200 120" className="w-full max-w-[240px]" role="img" aria-label={`Credit score ${score} of 850`}>
      <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#1d3036" strokeWidth="14" strokeLinecap="round" />
      <path d={`M 20 100 A 80 80 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}`} fill="none" stroke={color} strokeWidth="14" strokeLinecap="round" />
      <text x="100" y="92" textAnchor="middle" fontSize="30" fontWeight="700" fill="#f1f5f9" fontFamily="JetBrains Mono, monospace">{score}</text>
      <text x="100" y="112" textAnchor="middle" fontSize="10" fill="#64748b">300 – 850</text>
    </svg>
  );
}

function gradeMix(pool: PoolView): string {
  const a = pool.lots.filter((l) => l.grade === "A").reduce((s, l) => s + l.weight_kg, 0);
  return `${Math.round((a / Math.max(1, pool.loaded_kg)) * 100)}% Grade-A`;
}

export function BuyerBankPortal({ className }: { className?: string }) {
  const pools = useAppState((s) => s.pools);
  const voice = useAppState((s) => s.lastVoice);
  const [busy, setBusy] = useState(false);
  const state = voice?.orchestration?.state;
  const credit = state?.climate_credit_report;
  const cert = state?.optical_grade_cert;
  const cold = state?.cold_storage_arbitrage_plan;
  const loads = useMemo(() => [...pools].sort((a, b) => Number(b.status === "DISPATCHED") - Number(a.status === "DISPATCHED") || b.fill_pct - a.fill_pct), [pools]);

  const underwrite = async () => {
    setBusy(true);
    try {
      const result = await api.voiceInteract({
        text: "আমার কাছে ৪০০ কেজি কার্ডিনাল আলু আছে, ফড়িয়া ১১ টাকা কেজি বলছে। আমার ফোন 01711223344",
        district: "Bogura", upazila: "Shibganj", farmer_id: "FARM-BOG-104",
      });
      setState({ lastVoice: result.data });
      await refreshPools();
    } catch (error) {
      pushAlert("danger", "Underwriting failed", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={cn("grid min-h-0 gap-3 xl:grid-cols-5", className)}>
      <Panel className="xl:col-span-3" icon={<Truck className="size-4 text-amber-300" />} title="Incoming pre-graded 5-ton truckloads"
        actions={<Badge tone="slate"><Building2 className="size-3" /> 7 arats · 3 retail DCs · 66 WFP aggregation centres (62 Cox's Bazar · 4 Kurigram)</Badge>}
        bodyClassName="scroll-thin overflow-x-auto">
        <table className="w-full min-w-[620px] text-left text-xs">
          <thead className="text-[10px] uppercase tracking-wider text-slate-500">
            <tr>
              <th className="py-1.5 pr-2">Load</th><th className="pr-2">Crop / quality</th><th className="pr-2">Fill</th>
              <th className="pr-2">Buyer</th><th className="pr-2">Contract</th><th>Escrow</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-700">
            {loads.map((p) => (
              <tr key={p.pool_id} className="align-top">
                <td className="py-2 pr-2">
                  <div className="font-mono font-semibold text-slate-100">{p.pool_id}</div>
                  <div className="text-[10px] text-slate-500">{p.union}, {p.upazila}</div>
                </td>
                <td className="pr-2"><div className="text-slate-200">{p.crop}</div><div className="text-[10px] text-emerald-300">{gradeMix(p)} · {p.smallholders} farmers</div></td>
                <td className="w-28 pr-2"><div className="mb-1 font-mono text-slate-300">{kg(p.loaded_kg)}</div><ProgressBar value={p.loaded_kg} max={p.capacity_kg} tone={p.status === "DISPATCHED" ? "amber" : "emerald"} /></td>
                <td className="pr-2">{p.dispatch ? <><div className="text-slate-200">{p.dispatch.buyer_name}</div><div className="text-[10px] text-slate-500">{p.dispatch.buyer_type} · ETA {p.dispatch.eta_hours.toFixed(1)} h</div></> : <span className="text-slate-500">forming…</span>}</td>
                <td className="pr-2 font-mono">{p.dispatch ? <>{tk(p.dispatch.contract_price_tk_per_kg)}/kg<div className="text-[10px] text-slate-500">{tk(p.dispatch.contract_value_tk, 0)}</div></> : "-"}</td>
                <td>{p.dispatch ? <Badge tone="amber"><Lock className="size-3" /> {p.dispatch.escrow_id}</Badge> : <Badge tone="slate">open</Badge>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel className="xl:col-span-2" icon={<Landmark className="size-4 text-violet-300" />} title="Parametric Agri-Credit Underwriting Scorecard"
        actions={<Button onClick={underwrite} disabled={busy}>{busy ? <Spinner /> : <Banknote className="size-3.5" />} Underwrite FARM-BOG-104</Button>}
        bodyClassName="space-y-3">
        {!credit ? (
          <div className="py-10 text-center text-xs text-slate-500">Run a farmer request (or underwrite the sample farmer) to score a borrower.</div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <ScoreGauge score={credit.credit_score} />
              <div className="space-y-1 text-xs">
                <Badge tone={credit.loan_eligible ? "emerald" : "red"} className="text-sm">{credit.score_band}</Badge>
                <div className="font-mono text-lg font-bold text-slate-50">{credit.loan_eligible ? tk(credit.loan_amount_tk, 0) : "Not eligible"}</div>
                <div className="text-slate-400">{credit.annual_rate_pct}% · {credit.tenor_months} months · {state?.farmer_id}</div>
                <div className="max-w-[220px] text-[10px] text-slate-500">{credit.lender_model}</div>
              </div>
            </div>
            <div className="space-y-1.5">
              {credit.score_components.map((c) => (
                <div key={c.name}>
                  <div className="flex justify-between text-[11px]"><span className="text-slate-300">{c.name}</span><span className="font-mono text-slate-400">{c.points.toFixed(0)}/{c.max_points}</span></div>
                  <ProgressBar value={c.points} max={c.max_points} tone="violet" className="h-1.5" />
                  <div className="truncate text-[10px] text-slate-500">{c.evidence}</div>
                </div>
              ))}
            </div>
            <div className="grid gap-1.5 rounded-lg bg-black/30 p-2 font-mono text-[10px] text-slate-400">
              <div className="flex items-center gap-1.5"><Fingerprint className="size-3 text-emerald-400" /> grade {cert?.grade ?? "-"} · sha256 {cert ? shortHash(cert.sha256_digest, 12) : "-"}</div>
              <div className="flex items-center gap-1.5"><ShieldCheck className="size-3 text-sky-400" /> collateral: {cold?.reservation?.receipt_id ?? credit.collateral}</div>
              <div className="flex items-center gap-1.5"><Satellite className="size-3 text-amber-400" />
                {credit.flood_applicable ? `Sentinel-1 SAR ${credit.sar_backscatter_db} dB · breach ${credit.flood_breach_probability_pct}% (${credit.flood_alert_level})` : `not a haor upazila · 72 h rain ${credit.rain_next_72h_mm} mm`}
              </div>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
