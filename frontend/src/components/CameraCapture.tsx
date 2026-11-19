import { Camera, ImageUp, Smartphone, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button, Spinner } from "./ui";

/** Longest side of a photo sent for grading: enough for the grader, a fraction of a phone camera's upload. */
export const MAX_PHOTO_PX = 1600;

/** Draw an image or a video frame into a canvas at most `max` px on its long side, and encode it as JPEG. */
function toJpeg(image: CanvasImageSource, width: number, height: number, max = MAX_PHOTO_PX): Promise<Blob> {
  const scale = Math.min(1, max / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  const context = canvas.getContext("2d");
  if (!context) return Promise.reject(new Error("This browser cannot draw the photo."));
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("The photo could not be encoded."))), "image/jpeg", 0.88));
}

/** A chosen or captured photo, upright (EXIF orientation applied) and at most 1600 px, as JPEG. */
export async function downscalePhoto(file: Blob): Promise<Blob> {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    return await toJpeg(bitmap, bitmap.width, bitmap.height);
  } finally {
    bitmap.close();
  }
}

/** True on touch phones and tablets, where a file input with capture="environment" opens the camera app. */
export const isPhone = () => typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches;

type CameraState = "starting" | "ready" | "denied" | "missing" | "busy" | "failed";

const PROBLEM: Record<Exclude<CameraState, "starting" | "ready">, { bn: string; en: string }> = {
  denied: {
    bn: "ক্যামেরার অনুমতি বন্ধ। ব্রাউজারের সাইট সেটিংসে ক্যামেরা চালু করুন, অথবা একটি ছবি বেছে নিন।",
    en: "Camera permission is blocked. Allow the camera for this site in the browser's settings, or choose a photo instead.",
  },
  missing: { bn: "এই যন্ত্রে কোনো ক্যামেরা পাওয়া যায়নি।", en: "No camera was found on this device." },
  busy: { bn: "ক্যামেরা অন্য কোনো অ্যাপ ব্যবহার করছে।", en: "Another app is using the camera." },
  failed: { bn: "ক্যামেরা চালু করা গেল না।", en: "The camera could not start." },
};

/**
 * A live viewfinder (rear camera) with a framing guide and a shutter. The shot is drawn into a canvas at most 1600 px,
 * as JPEG. The stream stops when the dialog closes. Gallery and the phone's own camera app are the fallbacks.
 */
export function CameraDialog({ open, onClose, onCapture, onGallery, onPhoneCamera }: {
  open: boolean;
  onClose: () => void;
  onCapture: (photo: Blob) => void;
  onGallery: () => void;
  onPhoneCamera: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [state, setState] = useState<CameraState>("starting");
  const [aspect, setAspect] = useState(4 / 3);
  const [shooting, setShooting] = useState(false);

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let stream: MediaStream | null = null;
    let cancelled = false;
    setState("starting");
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
      .then(async (s) => {
        if (cancelled) return s.getTracks().forEach((t) => t.stop());
        stream = s;
        const v = video.current;
        if (!v) return;
        v.srcObject = s;
        await v.play().catch(() => undefined);
        setState("ready");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const name = error instanceof DOMException ? error.name : "";
        setState(name === "NotAllowedError" || name === "SecurityError" ? "denied"
          : name === "NotFoundError" || name === "OverconstrainedError" ? "missing"
          : name === "NotReadableError" ? "busy" : "failed");
      });
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
      if (video.current) video.current.srcObject = null;
    };
  }, [open]);

  const shoot = async () => {
    const v = video.current;
    if (!v || !v.videoWidth) return;
    setShooting(true);
    try {
      onCapture(await toJpeg(v, v.videoWidth, v.videoHeight));
    } finally {
      setShooting(false);
    }
  };

  const problem = state === "starting" || state === "ready" ? null : PROBLEM[state];
  return (
    <dialog ref={dialog} onClose={onClose} aria-labelledby="camera-title"
      className="m-auto w-[min(640px,calc(100vw-2rem))] max-w-none overflow-hidden rounded-2xl bg-white p-0 text-slate-900 shadow-lift backdrop:bg-slate-950/70 max-sm:h-dvh max-sm:max-h-none max-sm:w-full max-sm:rounded-none">
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-2">
          <h2 id="camera-title" className="m-0 text-[15px] font-semibold"><span lang="bn">ছবি তুলুন</span> · Take a photo</h2>
          <button type="button" onClick={onClose} aria-label="Close the camera"
            className="grid size-11 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"><X className="size-5" aria-hidden /></button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col justify-center bg-slate-950">
          {problem ? (
            <div role="alert" className="grid gap-3 p-6 text-center text-white">
              <p lang="bn" className="m-0 text-[16px]">{problem.bn}</p>
              <p className="m-0 text-[14px] text-slate-300">{problem.en}</p>
            </div>
          ) : (
            <>
              <div className="relative mx-auto max-h-[62dvh] w-full overflow-hidden" style={{ aspectRatio: aspect }}>
                <video ref={video} muted playsInline aria-label="Camera preview" className="size-full object-cover"
                  onLoadedMetadata={(e) => e.currentTarget.videoWidth && setAspect(e.currentTarget.videoWidth / e.currentTarget.videoHeight)} />
                {/* Framing guide: the crop goes inside; the rest of the frame is dimmed. */}
                <div aria-hidden className="pointer-events-none absolute inset-[10%] rounded-2xl border-2 border-dashed border-white/90 shadow-[0_0_0_100vmax_rgb(2_6_23/0.35)]" />
                {state === "starting" && <span className="absolute inset-0 grid place-items-center text-white"><Spinner className="size-6" /></span>}
              </div>
              <p className="m-0 px-4 py-3 text-center text-[13.5px] text-slate-200">
                <span lang="bn" className="block text-[15px] text-white">ফসল ফ্রেমের ভেতরে রাখুন, দিনের আলোয়</span>
                Fit the crop inside the frame, in daylight
              </p>
            </>
          )}
        </div>

        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <Button variant="ghost" className="min-h-11 justify-self-start" onClick={onGallery}>
            <ImageUp className="size-4" aria-hidden /> <span lang="bn">গ্যালারি</span><span className="max-sm:hidden"> · Gallery</span>
          </Button>
          <button type="button" onClick={() => void shoot()} disabled={state !== "ready" || shooting} aria-label="Take the photo"
            className="grid size-16 place-items-center rounded-full bg-emerald-700 text-white shadow-lift ring-4 ring-emerald-700/20 transition-transform enabled:active:scale-95 disabled:bg-slate-300 disabled:shadow-none">
            {shooting ? <Spinner className="size-5" /> : <Camera className="size-7" aria-hidden />}
          </button>
          {problem && isPhone() ? (
            <Button variant="ghost" className="min-h-11 justify-self-end" onClick={onPhoneCamera}>
              <Smartphone className="size-4" aria-hidden /> <span lang="bn">ফোনের ক্যামেরা</span>
            </Button>
          ) : <span />}
        </div>
      </div>
    </dialog>
  );
}
