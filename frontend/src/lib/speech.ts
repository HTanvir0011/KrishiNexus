/** Browser speech helpers: Web Speech API recognition (bn-BD) and speech playback (device voice, else the node's online Bangla voice). */

import { fetchBanglaSpeech } from "../api/client";

interface RecognitionResultEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}

interface Recognition {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const speechRecognitionSupported = () => recognitionCtor() !== null;

export function listenOnce(lang: string, onText: (text: string) => void, onError: (message: string) => void, onEnd: () => void): () => void {
  const Ctor = recognitionCtor();
  if (!Ctor) {
    onError("This browser has no Web Speech recognition; use a dialect preset instead.");
    onEnd();
    return () => undefined;
  }
  const recognition = new Ctor();
  recognition.lang = lang;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onresult = (event) => onText(event.results[0]?.[0]?.transcript ?? "");
  recognition.onerror = (event) => onError(`Speech recognition error: ${event.error}`);
  recognition.onend = onEnd;
  recognition.start();
  return () => recognition.stop();
}

/** Records the microphone until stopped (or maxMs), then hands the clip over as a data URL for the kiosk's own Whisper. */
export function recordOnce(onAudio: (dataUrl: string) => void, onError: (message: string) => void, onEnd: () => void, maxMs = 15_000): () => void {
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    onError("This browser cannot record audio; use a dialect preset instead.");
    onEnd();
    return () => undefined;
  }
  let recorder: MediaRecorder | null = null;
  let wanted = true;
  let timer = 0;
  const stop = () => {
    wanted = false;
    window.clearTimeout(timer);
    if (recorder?.state === "recording") recorder.stop();
  };
  navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    if (!wanted) {   // stopped before the microphone opened
      stream.getTracks().forEach((track) => track.stop());
      onEnd();
      return;
    }
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(stream);
    recorder = rec;
    rec.ondataavailable = (event) => chunks.push(event.data);
    rec.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      const reader = new FileReader();
      reader.onload = () => { onEnd(); onAudio(String(reader.result)); };
      reader.onerror = () => { onEnd(); onError("Could not read the recording."); };
      reader.readAsDataURL(new Blob(chunks, { type: rec.mimeType || "audio/webm" }));
    };
    rec.start();
    timer = window.setTimeout(stop, maxMs);
  }).catch((error: unknown) => {
    onError(`Microphone: ${error instanceof Error ? error.message : String(error)}`);
    onEnd();
  });
  return stop;
}

/** The voice list arrives late (Chrome fills it only after the first call), so wait for it, at most 1.5 s. */
function voicesReady(): Promise<SpeechSynthesisVoice[]> {
  if (!("speechSynthesis" in window)) return Promise.resolve([]);
  const synth = window.speechSynthesis;
  const now = synth.getVoices();
  if (now.length) return Promise.resolve(now);
  return new Promise((resolve) => {
    const done = () => {
      synth.removeEventListener("voiceschanged", done);
      window.clearTimeout(timer);
      resolve(synth.getVoices());
    };
    const timer = window.setTimeout(done, 1500);
    synth.addEventListener("voiceschanged", done);
  });
}

/** The best voice for a language: Bangladesh Bangla first, then any Bangla, and natural (neural) voices before others. */
function pickVoice(voices: SpeechSynthesisVoice[], lang: "bn-BD" | "en-US"): SpeechSynthesisVoice | undefined {
  const norm = (v: SpeechSynthesisVoice) => v.lang.toLowerCase().replace("_", "-");
  const natural = (list: SpeechSynthesisVoice[]) => list.find((v) => /natural|neural|online/i.test(v.name)) ?? list[0];
  if (lang === "bn-BD") {
    const bangla = voices.filter((v) => norm(v).startsWith("bn") || /bangla|bengali|বাংলা/i.test(v.name));
    return natural(bangla.filter((v) => norm(v) === "bn-bd")) ?? natural(bangla);
  }
  return natural(voices.filter((v) => norm(v) === "en-us")) ?? natural(voices.filter((v) => norm(v).startsWith("en")));
}

/**
 * Without a Bangla voice the browser would read Bangla with an English one, so callers say so instead. Microsoft Edge
 * (Nabanita, Pradeep) and Chrome on Android have Bangla voices; desktop Chrome and plain Windows do not.
 */
export async function hasBanglaVoice(): Promise<boolean> {
  return pickVoice(await voicesReady(), "bn-BD") !== undefined;
}

let playing: HTMLAudioElement | null = null;

/** How an answer was spoken: the device's own voice, the node's online Bangla voice, or not at all. */
export type Spoken = "device" | "online" | "none";

/**
 * Speaks with the device's voice when it has one for the language. Bangla on a device without a Bangla voice falls back
 * to the node's online voice (an MP3), unless `online` is false (Offline edge mode).
 */
export async function speak(text: string, lang: "bn-BD" | "en-US", { online = true }: { online?: boolean } = {}): Promise<Spoken> {
  if (!text) return "none";
  playing?.pause();
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  const voice = "speechSynthesis" in window ? pickVoice(await voicesReady(), lang) : undefined;
  if (voice || (lang === "en-US" && "speechSynthesis" in window)) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = voice?.lang ?? lang;
    utterance.rate = lang === "bn-BD" ? 0.9 : 1;
    if (voice) utterance.voice = voice;
    window.speechSynthesis.speak(utterance);
    return "device";
  }
  if (lang !== "bn-BD" || !online) return "none";
  try {
    const url = URL.createObjectURL(await fetchBanglaSpeech(text));
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    playing = audio;
    await audio.play();
    return "online";
  } catch {
    return "none";
  }
}
