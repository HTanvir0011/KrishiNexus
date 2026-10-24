import { Banknote, Building2, Fingerprint, Landmark, Lock, Satellite, ShieldCheck, Truck } from "lucide-react";
import { useMemo, useState } from "react";

import { api, ApiError, type PoolView } from "../api/client";
import { ScoreDial } from "../components/gauges";
import { Badge, Button, Panel, ProgressBar, Spinner } from "../components/ui";
import { cn, kg, shortHash, tk } from "../lib/format";
import { pushAlert, refreshPools, setState, useAppState } from "../state/store";

/** Agent 4's loan-to-value bands (`backend/agents/climate_credit_agent._ltv_for`); shown here to explain the loan. */
const LTV_BANDS: { min: number; ltv: number }[] = [{ min: 750, ltv: 0.6 }, { min: 700, ltv: 0.5 }, { min: 650, ltv: 0.4 }];
const LOAN_CAP_TK = 50_000;

function gradeMix(pool: PoolView): string {
  const a = pool.lots.filter((l) => l.grade === "A").reduce((s, l) => s + l.weight_kg, 0);
  return `${Math.round((a / Math.max(1, pool.loaded_kg)) * 100)}% Grade-A`;
}

type Verification = { cert_id: string; known: boolean; payload_hash_valid: boolean; signature_valid: boolean; tampered: boolean };

export function BuyerBankPortal({ className }: { className?: string }) {
  const pools = useAppState((s) => s.pools);
  const voice = useAppState((s) => s.lastVoice);
  const grade = useAppState((s) => s.lastGrade);
  const [busy, setBusy] = useState<"underwrite" | "verify" | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const state = voice?.orchestration?.state;
  const credit = state?.climate_credit_report;
  const cert = state?.optical_grade_cert;
  const syn = state?.syndicate_bypass_plan;
  const cold = state?.cold_storage_arbitrage_plan;
  const loads = useMemo(() => [...pools].sort((a, b) => Number(b.status === "DISPATCHED") - Number(a.status === "DISPATCHED") || b.fill_pct - a.fill_pct), [pools]);
  const certId = cert?.edge_certificate_id ?? grade?.digital_certificate.cert_id ?? null;

  const ltv = credit ? LTV_BANDS.find((b) => credit.credit_score >= b.min)?.ltv ?? 0 : 0;
  const receipt = cold?.reservation?.receipt_id ? cold : null;
  const collateralValue = receipt && state
    ? state.quantity_kg * (1 - (receipt.lambda_rot ?? 0.012)) * (receipt.expected_future_price_tk_per_kg ?? 0)
    : syn?.lot_value_b2b_tk ?? null;

  const underwrite = async () => {
    setBusy("underwrite");
    setVerification(null);
    try {
      const result = await api.voiceInteract({
        text: "আমার কাছে ৪০০ কেজি কার্ডিনাল আলু আছে, ফড়িয়া ১১ টাকা কেজি বলছে। আমার ফোন 01711223344",
        district: "Bogura", upazila: "Shibganj", farmer_id: "FARM-BOG-104", grade_sample_preset: "high_grade_harvest",
      });
      setState({ lastVoice: result.data });
      await refreshPools();
    } catch (error) {
      pushAlert("danger", "Underwriting failed", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  const verify = async () => {
    if (!certId) return;
    setBusy("verify");
    try {
      setVerification(await api.verifyCertificate(certId));
    } catch (error) {
      pushAlert("danger", "Certificate check failed", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={cn("grid min-w-0 gap-4 xl:grid-cols-5", className)}>
      <Panel className="xl:col-span-3" icon={<Truck className="size-4 text-amber-600" aria-hidden />} title="Pre-graded 5-ton truckloads for buyers"
        actions={<Badge tone="slate" className="whitespace-normal"><Building2 className="size-3 shrink-0" aria-hidden /> 7 arats · 3 retail DCs · 66 WFP centres (62 Cox's Bazar · 4 Kurigram)</Badge>}
        bodyClassName="scroll-thin overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-left text-[13px]">
          <thead className="bg-slate-50 text-[12px] text-slate-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">Load</th><th className="px-2 font-medium">Crop and quality</th><th className="px-2 font-medium">Fill</th>
              <th className="px-2 font-medium">Buyer</th><th className="px-2 font-medium">Contract</th><th className="px-4 font-medium">Escrow</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {loads.map((p) => (
              <tr key={p.pool_id} className="align-top hover:bg-slate-50/70">
                <td className="px-4 py-3">
                  <div className="font-mono text-[12.5px] font-semibold text-slate-900">{p.pool_id}</div>
                  <div className="text-[12px] text-slate-500">{p.union}, {p.upazila}</div>
                </td>
                <td className="px-2 py-3"><div className="text-slate-900">{p.crop}</div><div className="text-[12px] text-emerald-700">{gradeMix(p)} · {p.smallholders} farmers</div></td>
                <td className="w-32 px-2 py-3"><div className="num mb-1 text-[14px] text-slate-900">{kg(p.loaded_kg)}</div><ProgressBar value={p.loaded_kg} max={p.capacity_kg} tone={p.status === "DISPATCHED" ? "amber" : "emerald"} /></td>
                <td className="px-2 py-3">{p.dispatch ? <><div className="text-slate-900">{p.dispatch.buyer_name}</div><div className="text-[12px] text-slate-500">{p.dispatch.buyer_type} · ETA {p.dispatch.eta_hours.toFixed(1)} h</div></> : <span className="text-slate-500">Forming</span>}</td>
                <td className="num px-2 py-3 text-[14px] text-slate-900">{p.dispatch ? <>{tk(p.dispatch.contract_price_tk_per_kg)}/kg<div className="text-[12px] font-normal text-slate-500">{tk(p.dispatch.contract_value_tk, 0)}</div></> : "-"}</td>
                <td className="px-4 py-3">{p.dispatch ? <Badge tone="amber"><Lock className="size-3" aria-hidden /> {p.dispatch.escrow_id}</Badge> : <Badge tone="slate">Open</Badge>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel className="xl:col-span-2" icon={<Landmark className="size-4 text-violet-600" aria-hidden />} title="Agri-credit underwriting"
        actions={<Button onClick={() => void underwrite()} disabled={busy !== null}>{busy === "underwrite" ? <Spinner /> : <Banknote className="size-4" aria-hidden />} Underwrite FARM-BOG-104</Button>}
        bodyClassName="space-y-4">
        {!credit ? (
          <p className="m-0 py-10 text-center text-[13px] text-slate-500">Run a farmer question, or underwrite the sample farmer, to score a borrower.</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-4">
              <ScoreDial score={credit.credit_score} className="w-full max-w-[220px]" />
              <div className="min-w-0 space-y-1">
                <Badge tone={credit.loan_eligible ? "emerald" : "red"} className="text-[13px]">{credit.score_band}</Badge>
                <div className="num text-[28px] leading-tight text-slate-900">{credit.loan_eligible ? tk(credit.loan_amount_tk, 0) : "Not eligible"}</div>
                <div className="text-[13px] text-slate-600">{credit.annual_rate_pct}% a year · {credit.tenor_months} months · {state?.farmer_id}</div>
              </div>
            </div>

            {credit.loan_eligible && collateralValue !== null && (
              <div className="rounded-lg bg-slate-50 p-3 text-[13px] ring-1 ring-inset ring-slate-200">
                <div className="mb-1 text-[12px] font-medium text-slate-500">Loan-to-value</div>
                <div className="num text-slate-900">
                  {Math.round(ltv * 100)}% × {tk(collateralValue, 0)} = {tk(ltv * collateralValue, 0)} → {tk(credit.loan_amount_tk, 0)}
                </div>
                <div className="mt-1 text-[12px] text-slate-500">
                  {ltv * 100}% band for scores ≥ {LTV_BANDS.find((b) => b.ltv === ltv)?.min}, collateral = {credit.collateral}; capped at {tk(LOAN_CAP_TK, 0)} and rounded down to Tk 500.
                </div>
              </div>
            )}

            <div className="space-y-2">
              {credit.score_components.map((c) => (
                <div key={c.name}>
                  <div className="flex justify-between text-[12.5px]"><span className="text-slate-700">{c.name}</span><span className="num text-slate-900">{c.points.toFixed(0)}/{c.max_points}</span></div>
                  <ProgressBar value={c.points} max={c.max_points} tone="violet" className="h-1.5" />
                  <div className="truncate text-[11.5px] text-slate-500">{c.evidence}</div>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Badge tone={credit.seventy_two_hour_clearance ? "emerald" : "red"}>
                <Satellite className="size-3" aria-hidden />
                {credit.flood_applicable
                  ? `SAR ${credit.sar_backscatter_db} dB · breach ${credit.flood_breach_probability_pct}% (${credit.flood_alert_level?.toLowerCase()})`
                  : credit.seventy_two_hour_clearance ? `72 h clearance · ${credit.rain_next_72h_mm} mm rain` : "72 h storm warning"}
              </Badge>
              <Badge tone="sky"><ShieldCheck className="size-3" aria-hidden /> {cold?.reservation?.receipt_id ?? credit.collateral}</Badge>
            </div>

            <div className="rounded-lg bg-white p-3 ring-1 ring-inset ring-slate-200">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-1.5 text-[13px] text-slate-700">
                  <Fingerprint className="size-4 text-emerald-700" aria-hidden />
                  <span className="truncate">Quality certificate {cert ? `${cert.grade} · sha256 ${shortHash(cert.sha256_digest, 10)}` : "not issued"}</span>
                </div>
                <Button onClick={() => void verify()} disabled={!certId || busy !== null}>
                  {busy === "verify" ? <Spinner /> : <ShieldCheck className="size-4" aria-hidden />} Verify HMAC
                </Button>
              </div>
              {verification && (
                <div className={cn("mt-2 rounded-md px-2.5 py-1.5 text-[12.5px]",
                  verification.signature_valid && verification.payload_hash_valid && !verification.tampered ? "bg-emerald-50 text-emerald-800" : "bg-rose-100/70 text-rose-700")}>
                  {verification.cert_id}: {verification.known ? "issued by this edge node" : "unknown to this node"} · payload hash {verification.payload_hash_valid ? "valid" : "invalid"} · signature {verification.signature_valid ? "valid" : "invalid"}{verification.tampered ? " · tampered" : ""}
                </div>
              )}
              {!certId && <p className="m-0 mt-1 text-[12px] text-slate-500">Scan a harvest on the farmer's phone, or underwrite the sample farmer, to issue a certificate.</p>}
            </div>
            <p className="m-0 text-[11.5px] text-slate-500">{credit.lender_model}</p>
          </>
        )}
      </Panel>
    </div>
  );
}
