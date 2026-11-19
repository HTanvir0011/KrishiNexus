import { Ban, Camera, Check, CloudRain, ImageUp, Landmark, Mic, ScanLine, ShieldCheck, Snowflake, ThumbsDown, ThumbsUp, Truck, Volume2, WifiOff } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError, type Crop, type GradeableCrop, type SamplePreset, type VoiceInteractBody } from "../api/client";
import { CameraDialog, downscalePhoto } from "../components/CameraCapture";
import { CertificateCard, OpticalGraderCanvas, SCAN_DURATION_MS } from "../components/OpticalGraderCanvas";
import { Badge, Button, Spinner } from "../components/ui";
import { bnDigits, cn, kg, tk } from "../lib/format";
import { hasBanglaVoice, listenOnce, recordOnce, speak, speechRecognitionSupported } from "../lib/speech";
import { englishSummary } from "../lib/summary";
import { getState, pushAlert, refreshPools, refreshQuota, refreshTelemetry, setState, useAppState } from "../state/store";
import { Link } from "../lib/router";
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

const SCAN_CROPS: GradeableCrop[] = ["Cardinal Potato", "Diamant Potato", "Green Chili", "Brinjal"];
const SCAN_QUALITIES: { id: SamplePreset; label: string }[] = [
  { id: "high_grade_harvest", label: "High-grade lot" },
  { id: "mixed_wholesale_lot", label: "Mixed lot" },
  { id: "blight_affected_lot", label: "Blight lot" },
];
/** How wide the photographed scene is: a photo carries no scale, and sizes (undersized, grade-A minimum) need one. */
const PHOTO_WIDTHS = [
  { mm: 0, label: "No ruler: judge by the lot" },   // sizes relative to the lot itself (the grader's default)
  { mm: 150, label: "Close-up, 15 cm" },
  { mm: 300, label: "Handful, 30 cm" },
  { mm: 600, label: "Crate, 60 cm" },
  { mm: 1500, label: "Heap, 1.5 m" },
];
// The farmer's consent before their own voice or photo is used (recorded samples need none); kept on this device.
const CONSENT_KEY = "knx.consent.v1";
function storedConsent(): boolean {
  try {
    return localStorage.getItem(CONSENT_KEY) !== null;
  } catch {
    return false;
  }
}

const SELECT_CLASS = "min-h-10 rounded-lg border border-slate-300 bg-white px-2 text-[13.5px] text-slate-900";

export function FarmerZeroUIApp({ className }: { className?: string }) {
  const offline = useAppState((s) => s.offlineMode);
  const result = useAppState((s) => s.lastVoice);
  const grade = useAppState((s) => s.lastGrade);
  const pools = useAppState((s) => s.pools);
  // A logged-in farmer asks as themself: their id goes with every request and their district's question comes first.
  const user = useAppState((s) => s.user);
  const me = user?.role === "farmer" ? user : null;
  const homePreset = PRESETS.find((p) => p.district === me?.district);
  const [selected, setSelected] = useState<FarmerPreset>(homePreset ?? PRESETS[0]);
  const [heard, setHeard] = useState<string | null>(null);
  const [busy, setBusy] = useState<"voice" | "scan" | "photo" | "join" | null>(null);
  const [photo, setPhoto] = useState<string | null>(null);
  const [photoWidthMm, setPhotoWidthMm] = useState(0);
  const photoInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [listening, setListening] = useState(false);
  const [scanCrop, setScanCrop] = useState<GradeableCrop>("Cardinal Potato");
  const [scanQuality, setScanQuality] = useState<SamplePreset>("high_grade_harvest");
  const [scanStartedAt, setScanStartedAt] = useState<number | null>(null);
  const [scanDone, setScanDone] = useState(false);
  const [joined, setJoined] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const stopListening = useRef<() => void>(() => undefined);
  const [consented, setConsented] = useState(storedConsent);
  const [askConsent, setAskConsent] = useState<(() => void) | null>(null);
  const [typed, setTyped] = useState("");
  /** Run an action that uses the farmer's own voice or photo, asking for consent the first time. */
  const withConsent = (action: () => void) => (consented ? action() : setAskConsent(() => action));
  const agree = () => {
    try {
      localStorage.setItem(CONSENT_KEY, new Date().toISOString());
    } catch {
      // Not persisted: consent lasts for this visit only.
    }
    setConsented(true);
    const action = askConsent;
    setAskConsent(null);
    action?.();   // still inside the tap, so the microphone or file picker may open
  };
  const scrollRef = useRef<HTMLDivElement>(null);
  const decisionRef = useRef<HTMLElement>(null);

  // Bring a fresh decision into view inside the phone (not the page) once the agents answer.
  useEffect(() => {
    const box = scrollRef.current;
    const decision = decisionRef.current;
    if (box && decision && result && busy === null) box.scrollTo({ top: decision.offsetTop - 12, behavior: "smooth" });
  }, [result, busy]);

  const runVoice = async (preset: FarmerPreset, spoken?: string, audio?: string) => {
    setSelected(preset);
    setHeard(spoken ?? null);
    setBusy("voice");
    setJoined(null);
    setNotice(null);
    const sessionId = `KNX-UI-${Math.random().toString(36).slice(2, 10).toUpperCase()}`;
    setState({ activeSessionId: sessionId });
    // A farmer's own words are placed in their home district (with the upazila when a preset covers it).
    const place = me?.district
      ? { district: me.district, upazila: homePreset?.upazila }
      : { district: preset.district, upazila: preset.upazila };
    const body: VoiceInteractBody = audio
      ? { audio_base64: audio, ...place }
      : spoken
        ? { text: spoken, ...place }
        : { preset_id: preset.id };
    Object.assign(body, { offline_mode: getState().offlineMode, session_id: sessionId, farmer_id: me?.user_id });
    if (grade && grade.crop === preset.crop && scanDone) {
      if (grade.source === "uploaded_image") body.edge_certificate_id = grade.digital_certificate.cert_id;   // the photo's own grade
      else body.grade_sample_preset = scanQuality;
    }
    try {
      const response = await api.voiceInteract(body);
      if (audio) setHeard(response.data.transcription.raw_transcript);   // what the kiosk's Whisper heard
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
    withConsent(startListening);
  };

  const startListening = () => {
    const warn = (message: string) => pushAlert("warn", "Microphone", message);
    // Offline, or without Web Speech (which streams audio to a cloud service), the kiosk transcribes with its own Whisper.
    // A node without Whisper (the hosted demo) falls back to the browser's speech service, or to typing.
    const kioskWhisper = getState().health?.speechToText ?? true;
    const webSpeech = speechRecognitionSupported();
    if (!kioskWhisper && !webSpeech) {
      warn("This server has no speech model and this browser has no speech recognition. Type your question instead.");
      return;
    }
    if (offline && !kioskWhisper) pushAlert("info", "Microphone", "This server has no kiosk speech model, so your browser's speech service will listen.");
    setListening(true);
    stopListening.current = (offline || !webSpeech) && kioskWhisper
      ? recordOnce((audio) => void runVoice(selected, undefined, audio), warn, () => setListening(false))
      : listenOnce("bn-BD", (text) => text && void runVoice(selected, text), warn, () => setListening(false));
  };

  const scan = async () => {
    setBusy("scan");
    setScanDone(false);
    try {
      const response = await api.gradeCrop(scanCrop, scanQuality, me?.district || selected.district, me?.user_id);
      setState({ lastGrade: response.data });
      setScanStartedAt(performance.now());
      window.setTimeout(() => setScanDone(true), SCAN_DURATION_MS);
    } catch (error) {
      pushAlert("danger", "Scan failed", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  const gradePhoto = async (file: Blob) => {
    setBusy("photo");
    setScanDone(false);
    try {
      // Upright and at most 1600 px as JPEG; a format this browser cannot draw (HEIC on Chrome) goes as it is.
      const photoFile = await downscalePhoto(file).catch(() => file);
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(photoFile);
      });
      const result = await api.gradePhoto(scanCrop, dataUrl, me?.district || selected.district, photoWidthMm);
      setPhoto((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(photoFile);   // the very image the node graded, so its boxes line up
      });
      setState({ lastGrade: result });
      setScanStartedAt(null);
      setScanDone(true);
    } catch (error) {
      pushAlert("danger", "Photo not graded", error instanceof ApiError ? error.message : String(error));
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

  const listen = async (lang: "bn-BD" | "en-US") => {
    if (!result) return;
    const offline = getState().offlineMode;
    if (lang === "bn-BD" && !(await hasBanglaVoice()) && !offline) setNotice("বাংলা কণ্ঠ আনা হচ্ছে… Fetching the online Bangla voice…");
    const how = await speak(lang === "bn-BD" ? result.spoken_response_bn : englishSummary(result), lang, { online: !offline });
    setNotice(how === "online" ? "অনলাইন বাংলা কণ্ঠে শোনানো হচ্ছে। Playing the online Bangla voice."
      : how === "device" ? null
      : lang === "bn-BD"
        ? (offline ? "অফলাইন মোডে এই ব্রাউজারে বাংলা কণ্ঠ নেই; উত্তরটি উপরে লেখা আছে। Offline, and this browser has no Bangla voice."
          : "বাংলা কণ্ঠ পাওয়া গেল না; উত্তরটি উপরে লেখা আছে। The Bangla voice could not be reached; Microsoft Edge or Chrome on Android can speak it.")
        : "Speech playback is not available in this browser.");
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
            <div className="text-[12px] text-emerald-100">{me ? `${me.name}${me.district ? ` · ${me.district}` : ""}` : "Farmer companion · voice and camera"}</div>
          </div>
          {offline
            ? <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[12px] font-medium text-amber-800"><WifiOff className="size-3" /> Offline kiosk</span>
            : <span className="inline-flex items-center gap-1 rounded-full bg-white/15 px-2 py-0.5 text-[12px] font-medium text-white">Online</span>}
        </div>

        <div ref={scrollRef} className="scroll-thin relative min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
          <section aria-labelledby="farmer-step-1">
            <StepTitle id="farmer-step-1" n={1} bn="প্রশ্ন বলুন" en="Ask your question" />
            {askConsent && <ConsentCard onAgree={agree} onDecline={() => setAskConsent(null)} />}
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
              title={offline || !speechRecognitionSupported() ? "Speak in Bangla; the kiosk transcribes it with its own Whisper model" : "Speak in Bangla"}
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
            <form className="mt-2 flex gap-2" onSubmit={(e) => {
              e.preventDefault();
              const text = typed.trim();
              if (text) withConsent(() => { setTyped(""); void runVoice(selected, text); });
            }}>
              <label className="sr-only" htmlFor="farmer-typed">Type your question</label>
              <input id="farmer-typed" value={typed} onChange={(e) => setTyped(e.target.value)} maxLength={600} lang="bn"
                placeholder="অথবা লিখুন · or type your question"
                className="min-h-11 min-w-0 flex-1 rounded-xl bg-white px-3 text-[15px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-700 focus:outline-none" />
              <Button variant="primary" type="submit" className="min-h-11" disabled={busy !== null || !typed.trim()}>
                <span lang="bn">পাঠান</span>
              </Button>
            </form>
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
            <select value={scanCrop} onChange={(e) => setScanCrop(e.target.value as GradeableCrop)} aria-label="Crop to scan"
              className={cn(SELECT_CLASS, "mb-2 w-full")}>
              {SCAN_CROPS.map((crop) => <option key={crop}>{crop}</option>)}
            </select>
            <OpticalGraderCanvas result={grade} crop={grade?.crop ?? scanCrop} scanStartedAt={scanStartedAt} photo={photo} />
            {/* Each control sits above the button it feeds: lot quality for the sample scan, scene width for a photo */}
            <div className="mt-2 grid grid-cols-2 gap-2">
              <select value={scanQuality} onChange={(e) => setScanQuality(e.target.value as SamplePreset)} aria-label="Sample lot"
                className={SELECT_CLASS}>
                {SCAN_QUALITIES.map((q) => <option key={q.id} value={q.id}>{q.label}</option>)}
              </select>
              <select value={photoWidthMm} onChange={(e) => setPhotoWidthMm(Number(e.target.value))} aria-label="How wide the photo is"
                className={SELECT_CLASS}>
                {PHOTO_WIDTHS.map((w) => <option key={w.mm} value={w.mm}>{w.label}</option>)}
              </select>
              <Button variant="ghost" className="min-h-11" onClick={() => void scan()} disabled={busy !== null}>
                {busy === "scan" ? <Spinner /> : <ScanLine className="size-4" aria-hidden />} Scan sample lot
              </Button>
              <Button variant="ghost" className="min-h-11" onClick={() => withConsent(() => photoInput.current?.click())} disabled={busy !== null}>
                {busy === "photo" ? <Spinner /> : <ImageUp className="size-4" aria-hidden />} Grade a photo
              </Button>
              {/* The live viewfinder where the browser has a camera API; otherwise the phone's own camera app. */}
              <Button variant="primary" className="col-span-2 min-h-12" disabled={busy !== null}
                onClick={() => withConsent(() => (typeof navigator.mediaDevices?.getUserMedia === "function" ? setCameraOpen(true) : cameraInput.current?.click()))}>
                <Camera className="size-4" aria-hidden /> <span lang="bn">ছবি তুলুন</span> · Take a photo
              </Button>
            </div>
            {/* JPEG/PNG only, so iPhones convert HEIC before upload */}
            <input ref={photoInput} type="file" accept="image/jpeg,image/png" className="hidden" aria-label="Photo of the harvest"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) void gradePhoto(file);
              }} />
            {/* On a phone this opens the camera app (capture="environment"); desktops ignore capture and show a file picker. */}
            <input ref={cameraInput} type="file" accept="image/*" capture="environment" className="hidden" aria-label="Photo of the harvest from the camera"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) void gradePhoto(file);
              }} />
            <CameraDialog open={cameraOpen} onClose={() => setCameraOpen(false)}
              onCapture={(shot) => { setCameraOpen(false); void gradePhoto(shot); }}
              onGallery={() => { setCameraOpen(false); photoInput.current?.click(); }}
              onPhoneCamera={() => { setCameraOpen(false); cameraInput.current?.click(); }} />
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
              {me && (
                <Link to="/os/trade" className="flex min-h-11 items-center justify-center gap-2 rounded-xl bg-amber-600 px-3 text-[15px] font-semibold text-white no-underline shadow-sm hover:bg-amber-700">
                  <span lang="bn">সরাসরি ক্রেতাদের কাছে বেচুন</span> · Sell directly to buyers →
                </Link>
              )}
              <AdviceFeedback key={state.session_id} sessionId={state.session_id} />
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

/** What the farmer agrees to, in plain Bangla and English; every claim here matches what the backend does (see /docs#data). */
function ConsentCard({ onAgree, onDecline }: { onAgree: () => void; onDecline: () => void }) {
  return (
    <div role="dialog" aria-labelledby="consent-title" className="mb-3 rounded-xl bg-sky-50 p-3.5 ring-1 ring-inset ring-sky-600/25">
      <div id="consent-title" className="flex items-center gap-2 text-[15px] font-semibold text-slate-900">
        <ShieldCheck className="size-4 text-sky-700" aria-hidden /> <span lang="bn">আপনার অনুমতি</span> · Your consent
      </div>
      <p lang="bn" className="voice m-0 mt-2 text-[15px] leading-relaxed text-slate-800">
        আপনার কথা ও ছবি শুধু এই পরামর্শের জন্য ব্যবহার হবে। নাম, ফোন ও এনআইডি নম্বর লুকানো থাকে এবং ২৪ ঘণ্টার মধ্যে মুছে যায়;
        কণ্ঠস্বর বা ছবি জমা রাখা হয় না। সিদ্ধান্ত আপনার।
      </p>
      <p className="m-0 mt-2 text-[12.5px] leading-relaxed text-slate-600">
        Your words and photo are used only for this advice. Names, phone and NID numbers are hidden and erased within
        24 hours; voice and photos are not saved. Online, your browser's speech service hears the question; offline, the
        kiosk transcribes it itself. The decision stays yours.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button variant="primary" className="min-h-11" onClick={onAgree}><span lang="bn">রাজি</span> · I agree</Button>
        <Button variant="ghost" className="min-h-11" onClick={onDecline}><span lang="bn">এখন না</span> · Not now</Button>
      </div>
    </div>
  );
}

/** "Was this advice useful?": one tap, an optional comment, sent once per decision (backend feedback.py). */
function AdviceFeedback({ sessionId }: { sessionId: string }) {
  const lang = useAppState((s) => s.lang);
  const [useful, setUseful] = useState<boolean | null>(null);
  const [comment, setComment] = useState("");
  const [state, setFeedbackState] = useState<"idle" | "sending" | "sent">("idle");

  const send = async () => {
    if (useful === null) return;
    setFeedbackState("sending");
    try {
      await api.sendFeedback({ useful, comment: comment.trim() || undefined, session_id: sessionId, lang, context: "farmer_decision" });
      setFeedbackState("sent");
    } catch (error) {
      setFeedbackState("idle");
      pushAlert("danger", "Feedback not sent", error instanceof ApiError ? error.message : String(error));
    }
  };

  if (state === "sent") {
    return <p className="m-0 rounded-xl bg-slate-50 p-3 text-[13.5px] text-slate-700 ring-1 ring-inset ring-slate-200" role="status"><span lang="bn">ধন্যবাদ!</span> Thank you, your answer helps us improve.</p>;
  }
  return (
    <div className="rounded-xl bg-slate-50 p-3 ring-1 ring-inset ring-slate-200">
      <div className="text-[14px] font-semibold text-slate-900"><span lang="bn">পরামর্শটি কি কাজে লাগল?</span> <span className="font-normal text-slate-600">Was this advice useful?</span></div>
      <div className="mt-2 grid grid-cols-2 gap-2" role="group" aria-label="Was this advice useful?">
        {([true, false] as const).map((value) => (
          <button key={String(value)} type="button" aria-pressed={useful === value} onClick={() => setUseful(value)}
            className={cn("flex min-h-11 items-center justify-center gap-2 rounded-lg text-[14px] font-medium ring-1 ring-inset transition-colors",
              useful === value ? (value ? "bg-emerald-700 text-white ring-emerald-700" : "bg-rose-600 text-white ring-rose-600") : "bg-white text-slate-800 ring-slate-300 hover:bg-slate-100")}>
            {value ? <ThumbsUp className="size-4" aria-hidden /> : <ThumbsDown className="size-4" aria-hidden />}
            <span lang="bn">{value ? "হ্যাঁ" : "না"}</span> · {value ? "Yes" : "No"}
          </button>
        ))}
      </div>
      {useful !== null && (
        <>
          <label className="mt-2 grid gap-1 text-[12.5px] text-slate-600">
            <span><span lang="bn">কিছু বলতে চাইলে লিখুন</span> · Anything to add? (optional, personal details are removed)</span>
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} rows={2}
              className="rounded-lg bg-white px-3 py-2 text-[14px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-700 focus:outline-none" />
          </label>
          <Button variant="primary" className="mt-2 min-h-11 w-full" onClick={() => void send()} disabled={state === "sending"}>
            {state === "sending" ? <Spinner /> : null} <span lang="bn">পাঠান</span> · Send
          </Button>
        </>
      )}
    </div>
  );
}
