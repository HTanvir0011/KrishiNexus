import { Ban, Camera, Check, Landmark, Mic, Snowflake, Truck, Volume2, WifiOff } from "lucide-react";
import { type ReactNode, useMemo, useRef, useState } from "react";

import { api, ApiError, type Crop, type GradeableCrop, type SamplePreset, type VoiceInteractBody, type VoiceInteractResponse } from "../api/client";
import { CertificateCard, OpticalGraderCanvas, SCAN_DURATION_MS } from "../components/OpticalGraderCanvas";
import { Badge, Button, Spinner } from "../components/ui";
import { bnDigits, cn, kg, tk } from "../lib/format";
import { listenOnce, speak, speechRecognitionSupported } from "../lib/speech";
import { getState, pushAlert, refreshPools, refreshQuota, refreshTelemetry, setState, useAppState } from "../state/store";

interface VoicePresetOption {
  id: string;
  title: string;
  subtitle: string;
  crop: Crop;
  body: VoiceInteractBody;
  transcript: string;
}

const BOGURA_QUERY = "আমার নাম রহিম, ফোন 01711223344। আমার কাছে ৪০০ কেজি কার্ডিনাল আলু আছে, ফড়িয়া ১১ টাকা কেজি বলছে—আজ বিক্রি করব নাকি কোল্ড স্টোরেজে রাখব?";

const PRESETS: VoicePresetOption[] = [
  { id: "bogura_potato", title: "বগুড়া · আলু", subtitle: "Bogura potato distress", crop: "Cardinal Potato", transcript: BOGURA_QUERY,
    body: { text: BOGURA_QUERY, district: "Bogura", upazila: "Shibganj", farmer_id: "FARM-BOG-104" } },
  { id: "rangpur_potato_distress", title: "রংপুরী · আলু", subtitle: "Rangpuri distress sale", crop: "Cardinal Potato",
    transcript: "বাহে, মুই মিঠাপুকুরের রহিম মিয়া… হামার ঘরত দশ মণ লাল পাকরি আলু আছে। ফড়িয়া কয় বারো টাকা কেজি দিবে।",
    body: { preset_id: "rangpur_potato_distress" } },
  { id: "sunamganj_haor_flood", title: "সিলেটি · হাওর", subtitle: "Sunamganj haor flood", crop: "Boro Rice",
    transcript: "হাওরো বোরো ধান পাকি গেছে, পাহাড়ি ঢল আইতাছে হুনছি। চাইর একর জমির ধান কিতা করমু?",
    body: { preset_id: "sunamganj_haor_flood" } },
  { id: "munshiganj_cold_storage", title: "মুন্সিগঞ্জ · হিমাগার", subtitle: "Cold-storage quota", crop: "Diamant Potato",
    transcript: "আমার পঞ্চাশ মণ ডায়মন্ড আলু আছে। হিমাগারে জায়গা পাচ্ছি না… বেপারী চৌদ্দ টাকা কেজি বলছে।",
    body: { preset_id: "munshiganj_cold_storage" } },
  { id: "bogura_chili_syndicate", title: "বগুড়া · মরিচ", subtitle: "Chili syndicate", crop: "Green Chili",
    transcript: "দুই মণ কাঁচা মরিচ তুলিছি। পাইকার পঞ্চাশ টাকা কেজি দিবার চায়, অথচ ঢাকাত মরিচ একশো পঁচিশ টাকা।",
    body: { preset_id: "bogura_chili_syndicate" } },
];

const SCAN_CROPS: GradeableCrop[] = ["Cardinal Potato", "Green Chili", "Brinjal"];
const SCAN_QUALITIES: { id: SamplePreset; label: string }[] = [
  { id: "high_grade_harvest", label: "High-grade lot" },
  { id: "mixed_wholesale_lot", label: "Mixed lot" },
  { id: "blight_affected_lot", label: "Blight lot" },
];

function englishSummary(r: VoiceInteractResponse): string {
  const s = r.orchestration?.state;
  if (!s) return r.follow_up_question_bn ?? "";
  const syn = s.syndicate_bypass_plan;
  const cold = s.cold_storage_arbitrage_plan;
  const credit = s.climate_credit_report;
  return [
    s.optical_grade_cert && `Your ${s.quantity_kg} kilograms of ${s.crop} are certified ${s.optical_grade_cert.grade}.`,
    cold?.distress_sale_blocked && `The middleman offer of ${s.farmer_offer_tk_per_kg} taka per kilo is below the 15 taka production cost, so that sale is blocked.`,
    syn && `A pooled five-ton truck to ${syn.best_hub_name} pays ${syn.b2b_net_tk_per_kg.toFixed(2)} taka per kilo.`,
    credit?.loan_eligible && `Your agri-credit score is ${credit.credit_score}; up to ${credit.loan_amount_tk} taka working capital is pre-approved.`,
  ].filter(Boolean).join(" ");
}

export function FarmerZeroUIApp({ className }: { className?: string }) {
  const offline = useAppState((s) => s.offlineMode);
  const result = useAppState((s) => s.lastVoice);
  const grade = useAppState((s) => s.lastGrade);
  const pools = useAppState((s) => s.pools);
  const [selected, setSelected] = useState<VoicePresetOption>(PRESETS[0]);
  const [busy, setBusy] = useState<"voice" | "scan" | "join" | null>(null);
  const [listening, setListening] = useState(false);
  const [scanCrop, setScanCrop] = useState<GradeableCrop>("Cardinal Potato");
  const [scanQuality, setScanQuality] = useState<SamplePreset>("high_grade_harvest");
  const [scanStartedAt, setScanStartedAt] = useState<number | null>(null);
  const [scanDone, setScanDone] = useState(false);
  const [joined, setJoined] = useState<string | null>(null);
  const stopListening = useRef<() => void>(() => undefined);

  const runVoice = async (option: VoicePresetOption, overrideText?: string) => {
    setSelected(option);
    setBusy("voice");
    setJoined(null);
    const sessionId = `KNX-UI-${Math.random().toString(36).slice(2, 10).toUpperCase()}`;
    setState({ activeSessionId: sessionId });
    const body: VoiceInteractBody = { ...option.body, offline_mode: getState().offlineMode, session_id: sessionId };
    if (overrideText) Object.assign(body, { preset_id: undefined, text: overrideText, district: option.body.district ?? "Bogura", upazila: option.body.upazila ?? "Shibganj" });
    if (grade && grade.crop === option.crop && scanDone) body.grade_sample_preset = scanQuality;
    try {
      const response = await api.voiceInteract(body);
      setState({ lastVoice: response.data, backendLive: response.live });
      const plan = response.data.orchestration?.state;
      if (plan?.syndicate_bypass_plan?.pool) setState({ focusPoolId: plan.syndicate_bypass_plan.pool.pool_id });
      if (plan?.cold_storage_arbitrage_plan?.facility) {
        setState({ focusChamber: { facilityId: plan.cold_storage_arbitrage_plan.facility.facility_id, chamberId: "CH-01", district: plan.district } });
      }
      if (!response.live) pushAlert("warn", "Backend offline", "Showing the cached demo decision; start uvicorn on :8000 for live agents.");
      await Promise.all([refreshPools(), refreshTelemetry(), refreshQuota()]);
    } catch (error) {
      pushAlert("danger", "Voice request rejected", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  const toggleMic = () => {
    if (listening) {
      stopListening.current();
      return;
    }
    setListening(true);
    stopListening.current = listenOnce(
      "bn-BD",
      (text) => text && void runVoice({ ...selected, id: "microphone", transcript: text }, text),
      (message) => pushAlert("warn", "Microphone", message),
      () => setListening(false),
    );
  };

  const scan = async () => {
    setBusy("scan");
    setScanDone(false);
    try {
      const response = await api.gradeCrop(scanCrop, scanQuality, selected.body.district ?? "Bogura", selected.body.farmer_id);
      setState({ lastGrade: response.data });
      setScanStartedAt(performance.now());
      window.setTimeout(() => setScanDone(true), SCAN_DURATION_MS);
    } catch (error) {
      pushAlert("danger", "Scan failed", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  const state = result?.orchestration?.state;
  const syn = state?.syndicate_bypass_plan;
  const cold = state?.cold_storage_arbitrage_plan;
  const credit = state?.climate_credit_report;
  const pool = useMemo(() => pools.find((p) => p.pool_id === syn?.pool?.pool_id), [pools, syn]);

  const confirm = async () => {
    if (!state || !syn?.pool) return;
    setBusy("join");
    try {
      const joinedResult = await api.joinPool({
        cluster_id: syn.pool.pool_id, farmer_id: state.farmer_id, crop: state.crop, weight_kg: state.quantity_kg,
        grade: `Grade-${state.optical_grade_cert?.market_grade ?? "B"}`,
      });
      setJoined(joinedResult.message);
      setState((s) => ({
        pools: s.pools.map((p) => (p.pool_id === joinedResult.pool.pool_id ? joinedResult.pool : p)),
        focusPoolId: joinedResult.pool.pool_id,
        reservationPulse: s.reservationPulse + 1,
      }));
      pushAlert(joinedResult.accepted ? "success" : "warn", joinedResult.pool.status === "DISPATCHED" ? "5-ton truck DISPATCH LOCKED" : "Lot added to truck pool", joinedResult.message);
    } catch (error) {
      pushAlert("danger", "Could not join pool", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  const offer = state?.farmer_offer_tk_per_kg ?? syn?.farmer_offer_tk_per_kg ?? null;
  const recommended = cold?.decision;
  const storagePerKg = cold?.circuit_breaker && state ? cold.circuit_breaker.storage_branch_value_bdt / state.quantity_kg : null;

  return (
    <div className={cn("flex justify-center", className)}>
      <div className="flex w-full max-w-[420px] flex-col overflow-hidden rounded-[2rem] border-[6px] border-ink-700 bg-ink-900 shadow-2xl shadow-emerald-950/40">
        <div className="flex items-center justify-between bg-gradient-to-r from-emerald-700 to-emerald-600 px-4 py-2.5">
          <div>
            <div className="bn text-base font-bold text-white">কৃষিনেক্সাস কৃষক</div>
            <div className="text-[10px] text-emerald-100">Zero-UI voice + vision · rural edge node</div>
          </div>
          {offline ? <Badge tone="amber"><WifiOff className="size-3" /> Offline kiosk</Badge> : <Badge tone="emerald">Online</Badge>}
        </div>

        <div className="scroll-thin flex-1 space-y-3 overflow-y-auto p-3">
          <section>
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">1 · আপনার কথা বলুন / Speak</div>
            <div className="grid grid-cols-2 gap-1.5">
              {PRESETS.map((p) => (
                <button key={p.id} type="button" onClick={() => runVoice(p)} disabled={busy !== null}
                  className={cn("rounded-xl px-2.5 py-2 text-left ring-1 transition-colors disabled:opacity-60",
                    selected.id === p.id ? "bg-emerald-500/20 ring-emerald-400/60" : "bg-ink-800 ring-ink-600 hover:bg-ink-700")}>
                  <div className="bn text-sm font-semibold text-slate-100">{p.title}</div>
                  <div className="text-[10px] text-slate-400">{p.subtitle}</div>
                </button>
              ))}
              <button type="button" onClick={toggleMic} disabled={busy !== null && !listening}
                title={speechRecognitionSupported() ? "Speak in Bangla" : "Web Speech recognition is not available in this browser"}
                className={cn("flex items-center gap-2 rounded-xl px-2.5 py-2 ring-1",
                  listening ? "bg-red-500/20 ring-red-400/60" : "bg-ink-800 ring-ink-600 hover:bg-ink-700")}>
                <Mic className={cn("size-5", listening ? "text-red-300" : "text-emerald-300")} />
                <div className="flex h-6 items-end gap-0.5">
                  {Array.from({ length: 9 }, (_, i) => (
                    <span key={i} className={cn("w-1 rounded-full bg-emerald-400", listening ? "animate-wave" : "opacity-40")}
                      style={{ height: `${30 + ((i * 37) % 70)}%`, animationDelay: `${i * 90}ms` }} />
                  ))}
                </div>
              </button>
            </div>
            <div className="bn mt-2 rounded-lg bg-black/30 p-2 text-[13px] leading-relaxed text-slate-200">
              {busy === "voice" ? <span className="flex items-center gap-2 text-emerald-300"><Spinner /> এজেন্টরা বিশ্লেষণ করছে…</span> : selected.transcript}
            </div>
            {result && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                <Badge tone="violet">{result.transcription.dialect}</Badge>
                <Badge tone="sky">{result.transcription.entities.intent}</Badge>
                {result.transcription.pii_entities.length > 0 && <Badge tone="amber">{result.transcription.pii_entities.length} PII redacted</Badge>}
                {result.transcription.entities.quantity_kg && <Badge tone="slate">{kg(result.transcription.entities.quantity_kg)}</Badge>}
              </div>
            )}
          </section>

          <section>
            <div className="mb-1.5 flex items-center justify-between">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">2 · ফসল স্ক্যান / Scan</div>
              <div className="flex gap-1">
                <select value={scanCrop} onChange={(e) => setScanCrop(e.target.value as GradeableCrop)} aria-label="Crop to scan"
                  className="rounded-md bg-ink-800 px-1 py-0.5 text-[11px] ring-1 ring-ink-600">
                  {SCAN_CROPS.map((c) => <option key={c}>{c}</option>)}
                </select>
                <select value={scanQuality} onChange={(e) => setScanQuality(e.target.value as SamplePreset)} aria-label="Sample lot"
                  className="rounded-md bg-ink-800 px-1 py-0.5 text-[11px] ring-1 ring-ink-600">
                  {SCAN_QUALITIES.map((q) => <option key={q.id} value={q.id}>{q.label}</option>)}
                </select>
              </div>
            </div>
            <OpticalGraderCanvas result={grade} crop={grade?.crop ?? scanCrop} scanStartedAt={scanStartedAt} />
            <Button variant="primary" className="mt-2 w-full py-2.5 text-sm" onClick={scan} disabled={busy !== null}>
              {busy === "scan" ? <Spinner /> : <Camera className="size-4" />} Scan Harvest (5s YOLOv11)
            </Button>
            {grade && scanDone && <div className="mt-2"><CertificateCard result={grade} /></div>}
          </section>

          {result?.status === "NEEDS_CLARIFICATION" && (
            <div className="bn rounded-xl border border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-100">{result.follow_up_question_bn}</div>
          )}

          {state && (
            <section className="space-y-2">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">3 · সিদ্ধান্ত / Decision</div>
              {offer !== null && (
                <OptionCard tone="red" icon={<Ban className="size-5" />} title="A · ফড়িয়ার স্পট দাম" subtitle="Village Faria spot sale"
                  price={tk(offer)} blocked={cold?.distress_sale_blocked ?? false}
                  detail={cold?.distress_sale_blocked ? `BLOCKED BY FINANCIAL CIRCUIT-BREAKER · below Tk ${cold.circuit_breaker?.production_cost_floor_bdt ?? 15}/kg production cost` : "Above cost floor"} />
              )}
              {syn && (
                <OptionCard tone="emerald" icon={<Truck className="size-5" />} title="B · ৫ টনের যৌথ ট্রাক" subtitle={`Direct to ${syn.best_hub_name}`}
                  price={`${tk(syn.b2b_net_tk_per_kg)}/kg`} recommended={recommended === "SELL_POOLED_B2B"}
                  detail={`${offer ? `+${Math.round(((syn.b2b_net_tk_per_kg - offer) / offer) * 100)}% vs Faria · ` : ""}${syn.markup_pct.toFixed(0)}% syndicate markup bypassed${syn.pool ? ` · pool ${kg(syn.pool.current_kg)} → ${kg(syn.pool.after_join_kg)}` : ""}`} />
              )}
              {cold?.circuit_breaker && (
                <OptionCard tone="sky" icon={<Snowflake className="size-5" />} title={`C · ${bnDigits(cold.horizon_days)} দিন হিমাগার`} subtitle="Cold-storage arbitrage (ΔΠ verified)"
                  price={storagePerKg !== null ? `${tk(storagePerKg)}/kg` : "-"} recommended={recommended?.startsWith("STORE")}
                  detail={`ΔΠ vs Faria ${tk(cold.circuit_breaker.delta_pi_bdt, 0)} · vs truck ${tk(cold.store_vs_b2b_delta_tk, 0)} · λrot ${cold.lambda_rot ?? "-"}${cold.facility ? ` · tariff ${tk(cold.facility.tariff_tk_per_kg)}` : ""}`} />
              )}
              {credit && (
                <div className="flex items-center gap-2 rounded-xl bg-ink-800 p-2.5 ring-1 ring-ink-600">
                  <Landmark className="size-5 text-violet-300" />
                  <div className="text-xs">
                    <div className="font-semibold text-slate-100">Credit score {credit.credit_score}/850 · {credit.score_band}</div>
                    <div className="text-slate-400">{credit.loan_eligible ? `${tk(credit.loan_amount_tk, 0)} working capital at ${credit.annual_rate_pct}% pre-approved` : "Not yet eligible for instant credit"}</div>
                  </div>
                </div>
              )}
              <div className="bn rounded-xl bg-emerald-950/40 p-3 text-[13px] leading-relaxed text-emerald-50 ring-1 ring-emerald-500/30">{result?.spoken_response_bn}</div>
              <div className="grid grid-cols-2 gap-1.5">
                <Button onClick={() => speak(result?.spoken_response_bn ?? "", "bn-BD") || pushAlert("warn", "Audio", "Speech synthesis unavailable")}>
                  <Volume2 className="size-4" /> শুনুন (বাংলা)
                </Button>
                <Button onClick={() => result && (speak(englishSummary(result), "en-US") || pushAlert("warn", "Audio", "Speech synthesis unavailable"))}>
                  <Volume2 className="size-4" /> Listen (English)
                </Button>
              </div>
              {syn?.pool && (
                <Button variant="primary" className="w-full py-3 text-sm" onClick={confirm} disabled={busy !== null || pool?.status === "DISPATCHED" && !joined}>
                  {busy === "join" ? <Spinner /> : <Check className="size-4" />}
                  <span className="bn">হ্যাঁ, ট্রাকে যুক্ত করুন / স্টোরেজ বুক করুন</span>
                </Button>
              )}
              {syn?.pool && <div className="text-center text-[10px] text-slate-500">Confirm &amp; Join 5-Ton Truck Pool {syn.pool.pool_id}</div>}
              {joined && <div className="rounded-lg bg-emerald-500/10 p-2 text-[11px] text-emerald-200 ring-1 ring-emerald-500/30">{joined}</div>}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function OptionCard({ tone, icon, title, subtitle, price, detail, blocked = false, recommended = false }: {
  tone: "red" | "emerald" | "sky";
  icon: ReactNode;
  title: string;
  subtitle: string;
  price: string;
  detail: string;
  blocked?: boolean;
  recommended?: boolean;
}) {
  const ring = { red: "ring-red-500/50 bg-red-500/10", emerald: "ring-emerald-500/50 bg-emerald-500/10", sky: "ring-sky-500/50 bg-sky-500/10" }[tone];
  const text = { red: "text-red-300", emerald: "text-emerald-300", sky: "text-sky-300" }[tone];
  return (
    <div className={cn("relative rounded-xl p-2.5 ring-1", ring, recommended && "ring-2")}>
      {recommended && <span className="absolute -top-2 right-2 rounded-full bg-emerald-400 px-2 py-0.5 text-[9px] font-bold text-ink-950">RECOMMENDED</span>}
      <div className="flex items-center gap-2">
        <span className={text}>{icon}</span>
        <div className="min-w-0 flex-1">
          <div className="bn text-sm font-semibold text-slate-100">{title}</div>
          <div className="truncate text-[10px] text-slate-400">{subtitle}</div>
        </div>
        <div className={cn("font-mono text-lg font-bold", text, blocked && "line-through decoration-2")}>{price}</div>
      </div>
      <div className={cn("mt-1 text-[11px]", blocked ? "font-semibold text-red-300" : "text-slate-300")}>{detail}</div>
    </div>
  );
}
