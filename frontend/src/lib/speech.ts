/** Browser speech helpers: Web Speech API recognition (bn-BD) and speech synthesis playback. */

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

/** Without an installed Bangla voice the browser would read Bangla with an English voice; callers say so instead. */
export function hasBanglaVoice(): boolean {
  return "speechSynthesis" in window && window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith("bn"));
}

export function speak(text: string, lang: "bn-BD" | "en-US"): boolean {
  if (!("speechSynthesis" in window) || !text) return false;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = lang === "bn-BD" ? 0.9 : 1;
  const voice = window.speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2)));
  if (voice) utterance.voice = voice;
  window.speechSynthesis.speak(utterance);
  return true;
}
