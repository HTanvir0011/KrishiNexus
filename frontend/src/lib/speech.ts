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
