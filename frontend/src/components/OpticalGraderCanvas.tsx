import { BadgeCheck, Fingerprint, ScanLine, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { BoundingBox, DetectionClass, GradeableCrop, GradeCropResult } from "../api/client";
import { pct, shortHash } from "../lib/format";
import { Badge } from "./ui";

export const SCAN_DURATION_MS = 5_000;

const CLASS_STYLE: Record<DetectionClass, { stroke: string; label: string }> = {
  uniform_A: { stroke: "#3fa97c", label: "uniform_A" },
  minor_bruise: { stroke: "#e58f2b", label: "minor_bruise" },
  fungal_blight: { stroke: "#f2545b", label: "fungal_blight" },
  undersized: { stroke: "#9db0a3", label: "undersized" },
};

const PRODUCE_COLOR: Record<GradeableCrop, [string, string]> = {
  "Cardinal Potato": ["#b5604f", "#7d3a2f"],
  "Diamant Potato": ["#d9b26a", "#a07a3c"],
  "Green Chili": ["#3fa34d", "#1f6b2c"],
  Brinjal: ["#6b3a8c", "#3d1f55"],
  Mango: ["#e8b23a", "#b36d1f"],
  Banana: ["#e6cf4a", "#a08a1d"],
};

function drawTray(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const g = ctx.createLinearGradient(0, 0, w, h);
  g.addColorStop(0, "#1c3a2c");
  g.addColorStop(1, "#122a20");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "rgba(255,255,255,0.035)";
  ctx.lineWidth = 1;
  for (let x = 0; x < w; x += 9) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y < h; y += 9) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
}

function drawProduce(ctx: CanvasRenderingContext2D, crop: GradeableCrop, b: BoundingBox, sx: number, sy: number) {
  const [x, y, w, h] = b.box;
  const cx = (x + w / 2) * sx;
  const cy = (y + h / 2) * sy;
  const rx = (w / 2) * sx * 0.92;
  const ry = (h / 2) * sy * 0.92;
  const [light, dark] = PRODUCE_COLOR[crop];
  const shade = ctx.createRadialGradient(cx - rx * 0.35, cy - ry * 0.4, 1, cx, cy, Math.max(rx, ry));
  shade.addColorStop(0, light);
  shade.addColorStop(1, dark);
  ctx.fillStyle = shade;
  ctx.beginPath();
  if (crop === "Green Chili" || crop === "Banana") {
    ctx.ellipse(cx, cy, rx, ry, crop === "Banana" ? -0.12 : 0.04, 0, Math.PI * 2);
  } else {
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  }
  ctx.fill();
  if (crop === "Brinjal" || crop === "Green Chili") {
    ctx.fillStyle = "#2f7a3a";
    ctx.beginPath();
    ctx.ellipse(cx - rx * 0.92, cy, Math.max(3, rx * 0.14), Math.max(3, ry * 0.55), 0, 0, Math.PI * 2);
    ctx.fill();
  }
  if (b.class_label === "minor_bruise" || b.class_label === "fungal_blight") {
    const blight = b.class_label === "fungal_blight";
    ctx.fillStyle = blight ? "rgba(30,20,12,0.85)" : "rgba(70,40,30,0.55)";
    const spots = blight ? 4 : 2;
    for (let i = 0; i < spots; i++) {
      ctx.beginPath();
      ctx.ellipse(cx + rx * (0.3 * Math.cos(i * 2.1)), cy + ry * (0.3 * Math.sin(i * 2.1)), rx * (blight ? 0.22 : 0.14),
        ry * (blight ? 0.2 : 0.12), i, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function drawBox(ctx: CanvasRenderingContext2D, b: BoundingBox, sx: number, sy: number, alpha: number) {
  const [x, y, w, h] = b.box;
  const style = CLASS_STYLE[b.class_label];
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = style.stroke;
  ctx.lineWidth = 2;
  ctx.strokeRect(x * sx, y * sy, w * sx, h * sy);
  const label = `${style.label} ${(b.confidence * 100).toFixed(0)}%`;
  ctx.font = "600 10px 'JetBrains Mono', monospace";
  const tw = ctx.measureText(label).width + 8;
  const ty = Math.max(0, y * sy - 15);
  ctx.fillStyle = style.stroke;
  ctx.fillRect(x * sx, ty, tw, 14);
  ctx.fillStyle = "#0a1913";
  ctx.fillText(label, x * sx + 4, ty + 10.5);
  ctx.globalAlpha = 1;
}

export function OpticalGraderCanvas({ result, crop, scanStartedAt }: {
  result: GradeCropResult | null;
  crop: GradeableCrop;
  scanStartedAt: number | null;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let raf = 0;

    const render = () => {
      const width = wrap.clientWidth;
      const height = Math.round((width * 9) / 16);
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(width * dpr)) {
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        canvas.style.height = `${height}px`;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawTray(ctx, width, height);
      const [fw, fh] = result?.frame_size ?? [1280, 720];
      const sx = width / fw;
      const sy = height / fh;
      const elapsed = scanStartedAt ? performance.now() - scanStartedAt : SCAN_DURATION_MS;
      const progress = Math.min(1, elapsed / SCAN_DURATION_MS);
      if (result) {
        result.bounding_boxes.forEach((b) => drawProduce(ctx, crop, b, sx, sy));
        const lineX = progress * width;
        result.bounding_boxes.forEach((b) => {
          const centre = (b.box[0] + b.box[2] / 2) * sx;
          if (centre <= lineX) drawBox(ctx, b, sx, sy, Math.min(1, (lineX - centre) / 60 + 0.35));
        });
        if (progress < 1) {
          const grad = ctx.createLinearGradient(lineX - 40, 0, lineX, 0);
          grad.addColorStop(0, "rgba(52,211,153,0)");
          grad.addColorStop(1, "rgba(52,211,153,0.35)");
          ctx.fillStyle = grad;
          ctx.fillRect(lineX - 40, 0, 40, height);
          ctx.fillStyle = "#3fa97c";
          ctx.fillRect(lineX - 1, 0, 2, height);
        }
        setFrame(Math.round(progress * result.video_frames_analyzed));
      }
      if (result && progress < 1) raf = requestAnimationFrame(render);
    };

    render();
    const observer = new ResizeObserver(() => render());
    observer.observe(wrap);
    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [result, crop, scanStartedAt]);

  const scanning = Boolean(result && scanStartedAt && frame < result.video_frames_analyzed);
  return (
    <div ref={wrapRef} className="relative overflow-hidden rounded-xl ring-1 ring-ink-600">
      <canvas ref={canvasRef} className="block w-full" aria-label="Optical crop grading viewport" />
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between bg-gradient-to-b from-black/60 to-transparent px-2.5 py-1.5 font-mono text-[10px] text-emerald-200">
        <span className="flex items-center gap-1">
          <ScanLine className="size-3" /> {result?.inspector_model_version ?? "yolov11n-krishi-bd-v2.1"}
        </span>
        <span>{result ? `frame ${frame}/${result.video_frames_analyzed}` : "ready"}</span>
      </div>
      {!result && (
        <div className="absolute inset-0 grid place-items-center text-center">
          <div className="rounded-lg bg-black/45 px-3 py-2 text-xs text-slate-300">
            <div className="bn text-sm text-slate-100">ফসলের দিকে ক্যামেরা ধরুন</div>
            Point the camera at the sorted harvest and tap Scan
          </div>
        </div>
      )}
      {scanning && <div className="absolute bottom-2 left-2 rounded bg-emerald-500/90 px-2 py-0.5 text-[10px] font-bold text-ink-950">SCANNING 5s SWEEP</div>}
    </div>
  );
}

export function CertificateCard({ result }: { result: GradeCropResult }) {
  const m = result.metrics;
  const cert = result.digital_certificate;
  const gradeTone = result.grade_letter === "A" ? "emerald" : result.grade_letter === "B" ? "amber" : "red";
  return (
    <div className="rounded-xl border border-emerald-500/30 bg-gradient-to-br from-emerald-500/10 via-ink-900 to-ink-900 p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-1.5 label text-[13px] font-semibold text-emerald-300">
            <ShieldCheck className="size-3.5" /> Digital Quality Certificate
          </div>
          <div className="mt-1 text-lg font-bold text-slate-50">{result.assigned_grade}</div>
        </div>
        <Badge tone={gradeTone} className="text-sm">Grade-{result.grade_letter}</Badge>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 font-mono text-xs">
        <div><div className="text-[10px] text-slate-500">Uniformity</div><div className="text-emerald-300">{pct(m.size_uniformity_pct)}</div></div>
        <div><div className="text-[10px] text-slate-500">Bruising</div><div className="text-amber-300">{pct(m.mechanical_bruising_pct, 2)}</div></div>
        <div><div className="text-[10px] text-slate-500">Rot risk</div><div className={m.rot_blight_risk_pct > 2 ? "text-red-300" : "text-emerald-300"}>{pct(m.rot_blight_risk_pct, 2)}</div></div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge tone="emerald"><BadgeCheck className="size-3" /> +{result.price_premium_pct}% vs ungraded</Badge>
        <Badge tone="sky">BAU benchmark: +32% / +$947 per season</Badge>
        <Badge tone="slate">{result.bounding_boxes.length} objects · {result.inference_backend}</Badge>
      </div>
      <div className="mt-2 space-y-0.5 rounded-lg bg-black/30 p-2 font-mono text-[10px] text-slate-400">
        <div className="flex items-center gap-1 text-slate-300"><Fingerprint className="size-3" /> {cert.cert_id}</div>
        <div>sha256 {shortHash(cert.sha256_payload_hash, 14)}</div>
        <div>hmac&nbsp;&nbsp; {shortHash(cert.verification_hash, 14)}</div>
      </div>
    </div>
  );
}
