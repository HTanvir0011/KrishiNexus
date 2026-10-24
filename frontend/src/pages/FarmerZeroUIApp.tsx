import { Ban, Camera, Check, CloudRain, Landmark, Mic, Snowflake, Truck, Volume2, WifiOff } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError, type Crop, type GradeableCrop, type SamplePreset, type VoiceInteractBody } from "../api/client";
import { CertificateCard, OpticalGraderCanvas, SCAN_DURATION_MS } from "../components/OpticalGraderCanvas";
import { Badge, Button, Spinner } from "../components/ui";
import { bnDigits, cn, kg, tk } from "../lib/format";
import { hasBanglaVoice, listenOnce, speak, speechRecognitionSupported } from "../lib/speech";
import { englishSummary } from "../lib/summary";
import { getState, pushAlert, refreshPools, refreshQuota, refreshTelemetry, setState, useAppState } from "../state/store";
import { STORY_PRESETS } from "../story/presets";

interface FarmerPreset {
  id: string;
  title: string;
  subtitle: string;
  crop: Crop;
  district: string;
  upazila: string;
  question: string;
}

/** The five recorded dialect presets the backend ships, as big tap targets. */
const PRESETS: FarmerPreset[] = ([
  { id: "rangpur_potato_distress", title: "রহিম মিয়া · রংপুরের আলু", subtitle: "Rahim Mia, Rangpur potato", crop: "Cardinal Potato", district: "Rangpur", upazila: "Mithapukur" },
  { id: "bogura_chili_syndicate", title: "বগুড়ার কাঁচা মরিচ", subtitle: "Bogura green chili", crop: "Green Chili", district: "Bogura", upazila: "Sariakandi" },
  { id: "sunamganj_haor_flood", title: "আব্দুল · হাওরের বোরো ধান", subtitle: "Abdul, Sunamganj haor rice", crop: "Boro Rice", district: "Sunamganj", upazila: "Tahirpur" },
  { id: "munshiganj_cold_storage", title: "মুন্সিগঞ্জের হিমাগার", subtitle: "Munshiganj cold storage", crop: "Diamant Potato", district: "Munshiganj", upazila: "Tongibari" },
  { id: "jessore_brinjal_pooling", title: "যশোরের বেগুন", subtitle: "Jessore brinjal pooling", crop: "Brinjal", district: "Jessore", upazila: "Jhikargacha" },
] satisfies Omit<FarmerPreset, "question">[]).map((p) => ({ ...p, question: STORY_PRESETS.find((s) => s.id === p.id)?.question ?? "" }));

const SCAN_CROPS: GradeableCrop[] = ["Cardinal Potato", "Green Chili", "Brinjal"];
const SCAN_QUALITIES: { id: SamplePreset; label: string }[] = [
  { id: "high_grade_harvest", label: "High-grade lot" },
  { id: "mixed_wholesale_lot", label: "Mixed lot" },
  { id: "blight_affected_lot", label: "Blight lot" },
];

export function FarmerZeroUIApp({ className }: { className?: string }) {
  const offline = useAppState((s) => s.offlineMode);
  const result = useAppState((s) => s.lastVoice);
  const grade = useAppState((s) => s.lastGrade);
  const pools = useAppState((s) => s.pools);
  const [selected, setSelected] = useState<FarmerPreset>(PRESETS[0]);
  const [heard, setHeard] = useState<string | null>(null);
  const [busy, setBusy] = useState<"voice" | "scan" | "join" | null>(null);
  const [listening, setListening] = useState(false);
  const [scanCrop, setScanCrop] = useState<GradeableCrop>("Cardinal Potato");
  const [scanQuality, setScanQuality] = useState<SamplePreset>("high_grade_harvest");
  const [scanStartedAt, setScanStartedAt] = useState<number | null>(null);
  const [scanDone, setScanDone] = useState(false);
  const [joined, setJoined] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const stopListening = useRef<() => void>(() => undefined);
  const scrollRef = useRef<HTMLDivElement>(null);
  const decisionRef = useRef<HTMLElement>(null);

  // Bring a fresh decision into view inside the phone (not the page) once the agents answer.
  useEffect(() => {
    const box = scrollRef.current;
    const decision = decisionRef.current;
    if (box && decision && result && busy === null) box.scrollTo({ top: decision.offsetTop - 12, behavior: "smooth" });
  }, [result, busy]);

  const runVoice = async (preset: FarmerPreset, spoken?: string) => {
    setSelected(preset);
    setHeard(spoken ?? null);
    setBusy("voice");
    setJoined(null);
    setNotice(null);
    const sessionId = `KNX-UI-${Math.random().toString(36).slice(2, 10).toUpperCase()}`;
    setState({ activeSessionId: sessionId });
    const body: VoiceInteractBody = spoken
      ? { text: spoken, district: preset.district, upazila: preset.upazila }
      : { preset_id: preset.id };
    Object.assign(body, { offline_mode: getState().offlineMode, session_id: sessionId });
    if (grade && grade.crop === preset.crop && scanDone) body.grade_sample_preset = scanQuality;
    try {
      const response = await api.voiceInteract(body);
      setState({ lastVoice: response.data, backendLive: response.live });
      const plan = response.data.orchestration?.state;
      if (plan?.syndicate_bypass_plan?.pool) setState({ focusPoolId: plan.syndicate_bypass_plan.pool.pool_id });
      if (plan?.cold_storage_arbitrage_plan?.facility) {
        setState({ focusChamber: { facilityId: plan.cold_storage_arbitrage_plan.facility.facility_id, chamberId: "CH-01", district: plan.district } });
      }
      if (!response.live) pushAlert("warn", "Backend offline", "Showing the cached demo decision; start the backend for live agents.");
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
      (text) => text && void runVoice(selected, text),
      (message) => pushAlert("warn", "Microphone", message),
      () => setListening(false),
    );
  };

  const scan = async () => {
    setBusy("scan");
    setScanDone(false);
    try {
      const response = await api.gradeCrop(scanCrop, scanQuality, selected.district);
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
      pushAlert(joinedResult.accepted ? "success" : "warn", joinedResult.pool.status === "DISPATCHED" ? "5-ton truck dispatch locked" : "Lot added to the truck pool", joinedResult.message);
    } catch (error) {
      pushAlert("danger", "Could not join the pool", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  const listen = (lang: "bn-BD" | "en-US") => {
    if (!result) return;
    if (lang === "bn-BD" && !hasBanglaVoice()) {
      setNotice("এই ডিভাইসে বাংলা কণ্ঠ নেই। This device has no Bangla voice installed.");
      return;
    }
    setNotice(speak(lang === "bn-BD" ? result.spoken_response_bn : englishSummary(result), lang) ? null : "Speech playback is not available in this browser.");
  };

  const offer = state?.farmer_offer_tk_per_kg ?? syn?.farmer_offer_tk_per_kg ?? null;
  const qty = state?.quantity_kg ?? 0;
  const pooledValue = syn?.lot_value_b2b_tk ?? null;
  const storeValue = cold?.circuit_breaker?.storage_branch_value_bdt ?? null;
  const spotValue = cold?.circuit_breaker?.spot_branch_value_bdt ?? (offer !== null ? offer * qty : null);
  const storeFirst = cold?.decision?.startsWith("STORE") ?? false;
  const flood = credit?.flood_applicable && credit.flood_breach_probability_pct !== null ? credit : null;
  const transcript = busy === "voice" ? null : heard ?? result?.transcription.scrubbed_transcript ?? selected.question;

  return (
    <div className={cn("flex justify-center", className)}>
      <div className="flex w-full max-w-[400px] flex-col overflow-hidden rounded-[2.25rem] border-[10px] border-slate-900 bg-white shadow-lift max-sm:max-w-none max-sm:rounded-2xl max-sm:border max-sm:border-slate-200 max-sm:shadow-card">
        <div className="flex items-center justify-between bg-emerald-700 px-4 py-3 text-white">
          <div>
            <div lang="bn" className="text-[17px] font-semibold">কৃষিনেক্সাস কৃষক</div>
            <div className="text-[12px] text-emerald-100">Farmer companion · voice and camera</div>
          </div>
          {offline
            ? <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[12px] font-medium text-amber-800"><WifiOff className="size-3" /> Offline kiosk</span>
            : <span className="inline-flex items-center gap-1 rounded-full bg-white/15 px-2 py-0.5 text-[12px] font-medium text-white">Online</span>}
        </div>

        <div ref={scrollRef} className="scroll-thin relative min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
          <section aria-labelledby="farmer-step-1">
            <StepTitle id="farmer-step-1" n={1} bn="প্রশ্ন বলুন" en="Ask your question" />
            <div className="grid gap-2">
              {PRESETS.map((p) => (
                <button key={p.id} type="button" onClick={() => void runVoice(p)} disabled={busy !== null}
                  className={cn("flex min-h-14 items-center justify-between gap-3 rounded-xl px-3.5 py-2.5 text-left ring-1 ring-inset transition-colors disabled:opacity-60",
                    selected.id === p.id ? "bg-emerald-50 ring-2 ring-emerald-700" : "bg-white ring-slate-300 hover:bg-slate-50")}>
                  <span className="min-w-0">
                    <span lang="bn" className="voice block truncate text-[18px] leading-tight text-slate-900">{p.title}</span>
                    <span className="block truncate text-[12.5px] text-slate-600">{p.subtitle}</span>
                  </span>
                  {busy === "voice" && selected.id === p.id && <Spinner className="shrink-0 text-emerald-700" />}
                </button>
              ))}
            </div>
            <button type="button" onClick={toggleMic} disabled={busy !== null && !listening}
              title={speechRecognitionSupported() ? "Speak in Bangla" : "This browser has no speech recognition; use a preset"}
              className={cn("mt-2 flex w-full min-h-14 items-center gap-3 rounded-xl px-3.5 text-left ring-1 ring-inset transition-colors",
                listening ? "bg-rose-50 ring-rose-600/40" : "bg-slate-50 ring-slate-300 hover:bg-slate-100")}>
              <span className={cn("grid size-10 shrink-0 place-items-center rounded-full text-white shadow-sm", listening ? "bg-rose-600" : "bg-emerald-700")}>
                <Mic className="size-5" aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span lang="bn" className="block text-[15px] font-semibold text-slate-900">{listening ? "শুনছি…" : "নিজের প্রশ্ন বলুন"}</span>
                <span className="block text-[12.5px] text-slate-600">{listening ? "Listening, tap to stop" : "Speak your own question in Bangla"}</span>
              </span>
              <span className="flex h-6 items-end gap-0.5" aria-hidden>
                {Array.from({ length: 7 }, (_, i) => (
                  <span key={i} className={cn("w-1 rounded-full", listening ? "animate-wave bg-rose-600" : "bg-emerald-700/35")}
                    style={{ height: `${30 + ((i * 37) % 70)}%`, animationDelay: `${i * 90}ms` }} />
                ))}
              </span>
            </button>
            <div className="mt-2 rounded-xl bg-slate-50 p-3 ring-1 ring-inset ring-slate-200">
              {transcript === null
                ? <span lang="bn" className="flex items-center gap-2 text-[14px] text-emerald-800"><Spinner /> এজেন্টরা বিশ্লেষণ করছে…</span>
                : <p lang="bn" className="voice m-0 text-[16px] leading-relaxed text-slate-900">{transcript}</p>}
              {result && busy !== "voice" && (
                <div className="mt-2 flex flex-wrap gap-1">
                  <Badge tone="violet">{result.transcription.dialect}</Badge>
                  <Badge tone="sky">{result.transcription.entities.intent}</Badge>
                  {result.transcription.pii_entities.length > 0 && <Badge tone="amber">{result.transcription.pii_entities.length} personal detail hidden</Badge>}
                  {result.transcription.entities.quantity_kg && <Badge tone="slate">{kg(result.transcription.entities.quantity_kg)}</Badge>}
                </div>
              )}
            </div>
          </section>

          <section aria-labelledby="farmer-step-2">
            <StepTitle id="farmer-step-2" n={2} bn="ফসল স্ক্যান" en="Scan the harvest" />
            <div className="mb-2 flex gap-2">
              <select value={scanCrop} onChange={(e) => setScanCrop(e.target.value as GradeableCrop)} aria-label="Crop to scan"
                className="min-h-10 flex-1 rounded-lg border border-slate-300 bg-white px-2 text-[13.5px] text-slate-900">
                {SCAN_CROPS.map((crop) => <option key={crop}>{crop}</option>)}
              </select>
              <select value={scanQuality} onChange={(e) => setScanQuality(e.target.value as SamplePreset)} aria-label="Sample lot"
                className="min-h-10 flex-1 rounded-lg border border-slate-300 bg-white px-2 text-[13.5px] text-slate-900">
                {SCAN_QUALITIES.map((q) => <option key={q.id} value={q.id}>{q.label}</option>)}
              </select>
            </div>
            <OpticalGraderCanvas result={grade} crop={grade?.crop ?? scanCrop} scanStartedAt={scanStartedAt} />
            <Button variant="ghost" className="mt-2 w-full min-h-11" onClick={() => void scan()} disabled={busy !== null}>
              {busy === "scan" ? <Spinner /> : <Camera className="size-4" aria-hidden />} Scan harvest (5 s sweep)
            </Button>
            {grade && scanDone && <div className="mt-2"><CertificateCard result={grade} /></div>}
          </section>

          {result?.status === "NEEDS_CLARIFICATION" && (
            <p lang="bn" className="voice m-0 rounded-xl bg-amber-100/70 p-3 text-[16px] text-amber-900 ring-1 ring-inset ring-amber-600/25">{result.follow_up_question_bn}</p>
          )}

          {state && busy !== "voice" && (
            <section ref={decisionRef} aria-labelledby="farmer-step-3" className="animate-rise space-y-3">
              <StepTitle id="farmer-step-3" n={3} bn="সিদ্ধান্ত" en="Your decision" />

              {flood && (
                <DecisionCard tone={flood.flood_alert_level === "RED" ? "rose" : flood.flood_alert_level === "GREEN" ? "emerald" : "amber"}
                  icon={<CloudRain className="size-5" aria-hidden />} bn="হাওর বন্যার সতর্কতা" en="Haor flood alert (Sentinel-1)"
                  value={`${flood.flood_breach_probability_pct?.toFixed(1)}%`}
                  detail={`Chance the embankment breaks in 72 hours · ${flood.flood_alert_level?.toLowerCase()} · SAR ${flood.sar_backscatter_db} dB`} />
              )}

              {offer !== null && spotValue !== null && (
                <DecisionCard tone="rose" icon={<Ban className="size-5" aria-hidden />} bn="ফড়িয়ার দাম" en="Faria's offer"
                  value={`${tk(offer)}/kg`} struck={cold?.distress_sale_blocked ?? false}
                  detail={cold?.distress_sale_blocked
                    ? `Blocked by the financial circuit breaker: below the ${tk(cold.circuit_breaker?.production_cost_floor_bdt ?? 15, 0)}/kg production cost. Worth only ${tk(spotValue, 0)}.`
                    : `Above the cost floor; worth ${tk(spotValue, 0)} for ${kg(qty)}.`} />
              )}

              {syn && pooledValue !== null && !storeFirst && (
                <RecommendedTruck value={pooledValue} perKg={syn.b2b_net_tk_per_kg} hub={syn.best_hub_name} freight={syn.pooled_transport_tk_per_kg}
                  pool={syn.pool} dispatched={pool?.status === "DISPATCHED"} busy={busy} joined={joined} onJoin={() => void confirm()} />
              )}

              {cold?.circuit_breaker && storeValue !== null && (
                <DecisionCard tone={storeFirst ? "emerald" : "sky"} recommended={storeFirst} icon={<Snowflake className="size-5" aria-hidden />}
                  bn={`${bnDigits(cold.horizon_days)} দিন হিমাগার`} en={`${cold.horizon_days}-day cold storage`}
                  value={tk(storeValue, 0)}
                  detail={`${cold.facility ? `${cold.facility.name} · tariff ${tk(cold.facility.tariff_tk_per_kg)}/kg · ` : ""}expected farm-gate ${tk(cold.expected_future_price_tk_per_kg)}/kg · ΔΠ vs Faria ${tk(cold.circuit_breaker.delta_pi_bdt, 0)}`}
                  footer={credit?.loan_eligible ? <Badge tone="violet"><Landmark className="size-3" aria-hidden /> {tk(credit.loan_amount_tk, 0)} working capital at {credit.annual_rate_pct}% · score {credit.credit_score}</Badge> : undefined} />
              )}

              {syn && pooledValue !== null && storeFirst && (
                <DecisionCard tone="sky" icon={<Truck className="size-5" aria-hidden />} bn="৫ টনের যৌথ ট্রাক" en="5-ton pooled truck"
                  value={tk(pooledValue, 0)} detail={`${tk(syn.b2b_net_tk_per_kg)}/kg to ${syn.best_hub_name}`} />
              )}

              {!cold?.circuit_breaker && credit?.loan_eligible && (
                <p className="m-0 flex items-center gap-2 text-[13px] text-slate-700">
                  <Landmark className="size-4 text-violet-600" aria-hidden /> Credit score {credit.credit_score}: {tk(credit.loan_amount_tk, 0)} at {credit.annual_rate_pct}% pre-approved
                </p>
              )}

              <div className="rounded-xl bg-emerald-50/70 p-3 ring-1 ring-inset ring-emerald-700/10">
                <p lang="bn" className="voice m-0 text-[16px] leading-relaxed text-slate-900">{result?.spoken_response_bn}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button variant="quiet" className="text-emerald-800" onClick={() => listen("bn-BD")}><Volume2 className="size-4" aria-hidden /> <span lang="bn">শুনুন</span></Button>
                  <Button variant="quiet" onClick={() => listen("en-US")}><Volume2 className="size-4" aria-hidden /> English</Button>
                </div>
                {notice && <p className="m-0 mt-1 text-[12.5px] text-slate-600" role="status">{notice}</p>}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function StepTitle({ id, n, bn, en }: { id: string; n: number; bn: string; en: string }) {
  return (
    <h3 id={id} className="m-0 mb-2 flex items-baseline gap-2 text-[14px] font-semibold text-slate-900">
      <span className="num grid size-6 shrink-0 place-items-center self-center rounded-full bg-slate-900 text-[12px] text-white">{bnDigits(n)}</span>
      <span lang="bn">{bn}</span><span className="font-normal text-slate-500">{en}</span>
    </h3>
  );
}

const CARD_TONE = {
  rose: { ring: "bg-rose-50/70 ring-rose-600/20", icon: "text-rose-600", value: "text-rose-600" },
  emerald: { ring: "bg-emerald-50 ring-emerald-700/25", icon: "text-emerald-700", value: "text-emerald-700" },
  sky: { ring: "bg-sky-50/70 ring-sky-600/20", icon: "text-sky-700", value: "text-sky-800" },
  amber: { ring: "bg-amber-100/60 ring-amber-600/25", icon: "text-amber-700", value: "text-amber-800" },
};

function DecisionCard({ tone, icon, bn, en, value, detail, struck = false, recommended = false, footer }: {
  tone: keyof typeof CARD_TONE;
  icon: ReactNode;
  bn: string;
  en: string;
  value: string;
  detail: string;
  struck?: boolean;
  recommended?: boolean;
  footer?: ReactNode;
}) {
  const t = CARD_TONE[tone];
  return (
    <div className={cn("rounded-xl p-3 ring-1 ring-inset", t.ring, recommended && "ring-2")}>
      <div className="flex items-start gap-2.5">
        <span className={cn("mt-0.5", t.icon)}>{icon}</span>
        <div className="min-w-0 flex-1">
          <div lang="bn" className="text-[15px] font-semibold text-slate-900">{bn}</div>
          <div className="text-[12.5px] text-slate-600">{en}{recommended && <Badge tone="emerald" className="ml-1.5">Recommended</Badge>}</div>
        </div>
        <div className={cn("num shrink-0 text-[20px]", t.value, struck && "line-through decoration-2")}>{value}</div>
      </div>
      <p className="m-0 mt-1.5 text-[12.5px] leading-snug text-slate-700">{detail}</p>
      {footer && <div className="mt-2">{footer}</div>}
    </div>
  );
}

function RecommendedTruck({ value, perKg, hub, freight, pool, dispatched, busy, joined, onJoin }: {
  value: number;
  perKg: number;
  hub: string;
  freight: number;
  pool: { pool_id: string; current_kg: number; after_join_kg: number; capacity_kg: number; neighbor_farmers: number } | null;
  dispatched: boolean;
  busy: string | null;
  joined: string | null;
  onJoin: () => void;
}) {
  return (
    <div className="rounded-2xl bg-emerald-700 p-4 text-white shadow-lift">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-[12.5px] font-medium text-emerald-100"><Truck className="size-4" aria-hidden /> Recommended · 5-ton pooled truck</div>
          <div className="num mt-1 text-[34px] leading-none">{tk(value, 0)}</div>
          <div className="mt-1 text-[13px] text-emerald-50">{tk(perKg)}/kg net to {hub}, after {tk(freight)}/kg freight</div>
        </div>
      </div>
      {pool && (
        <div className="mt-3">
          <div className="flex justify-between text-[12px] text-emerald-100">
            <span>{pool.neighbor_farmers} neighbours loading</span>
            <span className="num">{kg(pool.current_kg)} → {kg(pool.after_join_kg)} of {kg(pool.capacity_kg)}</span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-emerald-900/40">
            <div className="h-full rounded-full bg-amber-300" style={{ width: `${Math.min(100, (pool.after_join_kg / pool.capacity_kg) * 100)}%` }} />
          </div>
          <button type="button" onClick={onJoin} disabled={busy !== null || (dispatched && !joined) || Boolean(joined)}
            className="mt-3 flex w-full min-h-12 items-center justify-center gap-2 rounded-xl bg-white px-4 text-[15px] font-semibold text-emerald-800 shadow-sm transition-colors hover:bg-emerald-50 disabled:opacity-70">
            {busy === "join" ? <Spinner /> : <Check className="size-5" aria-hidden />}
            <span lang="bn">{joined ? "যুক্ত হয়েছে" : "হ্যাঁ, ৫-টন ট্রাকে যুক্ত করুন"}</span>
            <span className="text-[13px] font-medium text-emerald-700">{joined ? "Joined" : "(Join 5-ton pool)"}</span>
          </button>
          {joined && <p className="m-0 mt-2 text-[12.5px] text-emerald-50">{joined}</p>}
        </div>
      )}
    </div>
  );
}
