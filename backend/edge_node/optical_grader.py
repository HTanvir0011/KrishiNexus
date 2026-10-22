"""Edge optical crop grader and Digital Quality Certificate authority.

Three inference backends, chosen per request and always reported in ``inference_backend``:

* ``ultralytics-yolo``      — a YOLO detector on an uploaded photo when ``KNX_YOLO_WEIGHTS`` points at
                              trained weights and ``ultralytics`` is installed.
* ``classical-cv``          — real image analysis on an uploaded photo with no trained weights: border-
                              referenced background subtraction, Otsu threshold, morphological clean-up,
                              connected components, per-object size and dark-lesion analysis.
* ``simulated-video-sweep`` — a deterministic reconstruction of a 5-second sweep for a named sample preset
                              (or a seeded field sweep), producing the same telemetry shape for demos.

Grades use the thresholds of the active ``vision_grading`` prompt version (shared with Agent 1).
Certificates carry a SHA-256 payload hash plus an HMAC verification hash and can be re-verified.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import importlib.util
import io
import json
import os
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from config import now_bdt, settings
from mcp_servers.base import ToolExecutionError
from prompts.prompt_registry import PROMPT_REGISTRY, grade_rule

INSPECTOR_MODEL_VERSION = "yolov11n-krishi-bd-v2.1"
FRAME_W, FRAME_H = 1280, 720
SWEEP_SECONDS, SWEEP_FPS, KEYFRAMES = 5, 30, 10
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class GradeableCrop(StrEnum):
    CARDINAL_POTATO = "Cardinal Potato"
    DIAMANT_POTATO = "Diamant Potato"
    GREEN_CHILI = "Green Chili"
    BRINJAL = "Brinjal"
    MANGO = "Mango"
    BANANA = "Banana"


class DetectionClass(StrEnum):
    UNIFORM_A = "uniform_A"
    MINOR_BRUISE = "minor_bruise"
    FUNGAL_BLIGHT = "fungal_blight"
    UNDERSIZED = "undersized"


class EdgeGrade(StrEnum):
    A = "Grade-A (Export / Supermarket Direct)"
    B = "Grade-B (Standard Wholesale)"
    C = "Grade-C (Agro-Processing)"


class SamplePreset(StrEnum):
    HIGH_GRADE_HARVEST = "high_grade_harvest"
    MIXED_WHOLESALE_LOT = "mixed_wholesale_lot"
    BLIGHT_AFFECTED_LOT = "blight_affected_lot"
    UNDERSIZED_PROCESSING_LOT = "undersized_processing_lot"
    FIELD_SWEEP = "field_sweep"


@dataclass(frozen=True, slots=True)
class CropProfile:
    typical_mm: float
    a_min_mm: float
    undersized_mm: float
    aspect: float  # minor / major axis
    moisture_band: tuple[float, float]


CROP_PROFILES: dict[GradeableCrop, CropProfile] = {
    GradeableCrop.CARDINAL_POTATO: CropProfile(62, 55, 35, 0.80, (77.0, 82.0)),
    GradeableCrop.DIAMANT_POTATO: CropProfile(64, 55, 35, 0.75, (77.0, 82.0)),
    GradeableCrop.GREEN_CHILI: CropProfile(78, 65, 50, 0.22, (84.0, 90.0)),
    GradeableCrop.BRINJAL: CropProfile(180, 150, 110, 0.45, (90.0, 94.0)),
    GradeableCrop.MANGO: CropProfile(95, 85, 65, 0.72, (80.0, 86.0)),
    GradeableCrop.BANANA: CropProfile(170, 150, 110, 0.28, (72.0, 78.0)),
}


@dataclass(frozen=True, slots=True)
class PresetProfile:
    size_factor: float
    sd_fraction: float
    bruise_p: float
    blight_p: float
    moisture_offset: float  # fraction of the band width, 0.5 = band centre


PRESETS: dict[SamplePreset, PresetProfile] = {
    SamplePreset.HIGH_GRADE_HARVEST: PresetProfile(1.00, 0.055, 0.12, 0.00, 0.45),
    SamplePreset.MIXED_WHOLESALE_LOT: PresetProfile(0.95, 0.140, 0.30, 0.03, 0.60),
    SamplePreset.BLIGHT_AFFECTED_LOT: PresetProfile(0.97, 0.110, 0.25, 0.35, 0.95),
    SamplePreset.UNDERSIZED_PROCESSING_LOT: PresetProfile(0.66, 0.200, 0.30, 0.10, 0.70),
    SamplePreset.FIELD_SWEEP: PresetProfile(0.99, 0.080, 0.15, 0.04, 0.50),
}

_CROP_ALIASES = {"potato": GradeableCrop.CARDINAL_POTATO, "alu": GradeableCrop.CARDINAL_POTATO,
                 "chili": GradeableCrop.GREEN_CHILI, "chilli": GradeableCrop.GREEN_CHILI, "green chilli": GradeableCrop.GREEN_CHILI,
                 "eggplant": GradeableCrop.BRINJAL, "aam": GradeableCrop.MANGO, "kola": GradeableCrop.BANANA}


class BoundingBox(BaseModel):
    object_id: int
    box: tuple[int, int, int, int] = Field(description="[x, y, w, h] in frame pixels.")
    class_label: DetectionClass
    confidence: float = Field(ge=0, le=1)
    diameter_mm: float
    defect_area_pct: float


class GradingMetrics(BaseModel):
    sample_count: int
    avg_diameter_mm: float
    size_uniformity_pct: float
    mechanical_bruising_pct: float
    rot_blight_risk_pct: float
    estimated_moisture_pct: float
    undersized_pct: float


class DigitalCertificate(BaseModel):
    cert_id: str
    issued_at: str
    crop: GradeableCrop
    district: str | None
    farmer_id: str | None
    grade: EdgeGrade
    inspector_model_version: str
    inference_backend: str
    sha256_payload_hash: str
    verification_hash: str = Field(description="HMAC-SHA256 over the payload with the node's signing key.")
    payload: dict[str, Any]


class GradeCropRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    crop: GradeableCrop
    district: str | None = Field(default=None, max_length=60)
    farmer_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9\-]{3,40}$")
    sample_preset: SamplePreset | None = None
    image_base64: str | None = Field(default=None, description="JPEG/PNG photo of the sorting tray (data URI allowed).")
    frame_width_mm: float = Field(default=600.0, gt=50, le=3_000, description="Real width covered by the camera frame.")
    lot_kg: float | None = Field(default=None, gt=0, le=100_000)

    @field_validator("crop", mode="before")
    @classmethod
    def _crop(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _CROP_ALIASES.get(value.strip().lower(), value.strip().title() if value.islower() else value)
        return value

    @model_validator(mode="after")
    def _one_source(self) -> GradeCropRequest:
        if self.sample_preset is not None and self.image_base64 is not None:
            raise ValueError("send either sample_preset or image_base64, not both")
        return self


class GradeCropResult(BaseModel):
    crop: GradeableCrop
    district: str | None
    source: str
    inference_backend: str
    inspector_model_version: str
    frame_size: tuple[int, int]
    video_frames_analyzed: int
    bounding_boxes: list[BoundingBox]
    metrics: GradingMetrics
    assigned_grade: EdgeGrade
    grade_letter: str
    grading_reasons: list[str]
    price_premium_pct: float
    premium_basis: str
    digital_certificate: DigitalCertificate
    latency_ms: float


class VerifyCertificateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cert_id: str | None = Field(default=None, description="Look up a certificate issued by this node.")
    certificate: DigitalCertificate | None = Field(default=None, description="Or submit a full certificate to re-verify.")

    @model_validator(mode="after")
    def _one(self) -> VerifyCertificateRequest:
        if (self.cert_id is None) == (self.certificate is None):
            raise ValueError("send exactly one of cert_id or certificate")
        return self


class CertificateVerification(BaseModel):
    cert_id: str
    known: bool
    payload_hash_valid: bool
    signature_valid: bool
    tampered: bool


# ---------------------------------------------------------------------------
# Shared metric, grade and certificate logic
# ---------------------------------------------------------------------------


def summarize(crop: GradeableCrop, boxes: list[BoundingBox], moisture_pct: float) -> GradingMetrics:
    diameters = np.array([b.diameter_mm for b in boxes], dtype=float)
    n = len(boxes)
    mean = float(diameters.mean()) if n else 0.0
    uniformity = max(0.0, 100.0 * (1 - float(diameters.std()) / mean)) if n and mean > 0 else 0.0
    bruise_area = sum(b.defect_area_pct for b in boxes if b.class_label is DetectionClass.MINOR_BRUISE)
    fungal = sum(b.class_label is DetectionClass.FUNGAL_BLIGHT for b in boxes)
    undersized = sum(b.class_label is DetectionClass.UNDERSIZED for b in boxes)
    return GradingMetrics(
        sample_count=n,
        avg_diameter_mm=round(mean, 1),
        size_uniformity_pct=round(uniformity, 1),
        mechanical_bruising_pct=round(bruise_area / n, 2) if n else 0.0,
        rot_blight_risk_pct=round(0.3 + 35.0 * fungal / n, 2) if n else 0.0,  # latent infection prior + spread risk
        estimated_moisture_pct=round(moisture_pct, 1),
        undersized_pct=round(100.0 * undersized / n, 1) if n else 0.0,
    )


def assign_grade(crop: GradeableCrop, m: GradingMetrics) -> tuple[str, list[str]]:
    params = PROMPT_REGISTRY.params("vision_grading")
    profile = CROP_PROFILES[crop]
    letter = grade_rule(params, {"uniformity": m.size_uniformity_pct, "bruising": m.mechanical_bruising_pct,
                                 "rot": m.rot_blight_risk_pct})
    reasons = [f"uniformity {m.size_uniformity_pct}% / bruising {m.mechanical_bruising_pct}% / rot-blight "
               f"{m.rot_blight_risk_pct}% against {PROMPT_REGISTRY.active('vision_grading').variant_id} thresholds -> {letter}"]
    downgrade = {"A": "B", "B": "C", "C": "C"}
    if letter == "A" and m.avg_diameter_mm < profile.a_min_mm:
        letter = "B"
        reasons.append(f"average size {m.avg_diameter_mm} mm below Grade-A minimum {profile.a_min_mm:g} mm")
    if m.undersized_pct > 25:
        letter = downgrade[letter]
        reasons.append(f"{m.undersized_pct}% undersized (> 25%)")
    low, high = profile.moisture_band
    if not low <= m.estimated_moisture_pct <= high:
        letter = downgrade[letter]
        reasons.append(f"moisture {m.estimated_moisture_pct}% outside {low:g}-{high:g}%")
    return letter, reasons


def price_premium(letter: str, m: GradingMetrics) -> float:
    if letter == "A":
        return round(20.0 + 12.0 * min(1.0, max(0.0, (m.size_uniformity_pct - 90.0) / 8.0)), 1)
    return 8.0 if letter == "B" else -12.0


_ISSUED: dict[str, DigitalCertificate] = {}


def _sign(payload: dict[str, Any]) -> tuple[str, str]:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (hashlib.sha256(canonical.encode()).hexdigest(),
            hmac.new(settings.receipt_signing_key.encode(), canonical.encode(), hashlib.sha256).hexdigest())


def issue_certificate(request: GradeCropRequest, letter: str, m: GradingMetrics, backend: str, boxes: int) -> DigitalCertificate:
    issued = now_bdt().isoformat()
    payload = {
        "crop": request.crop.value, "district": request.district, "farmer_id": request.farmer_id, "lot_kg": request.lot_kg,
        "grade": letter, "metrics": m.model_dump(), "detections": boxes, "issued_at": issued,
        "inspector_model_version": INSPECTOR_MODEL_VERSION, "inference_backend": backend,
    }
    digest, signature = _sign(payload)
    cert = DigitalCertificate(
        cert_id=f"DQC-EDGE-{request.crop.name[:3]}-{issued[:10].replace('-', '')}-{digest[:10].upper()}", issued_at=issued,
        crop=request.crop, district=request.district, farmer_id=request.farmer_id, grade=EdgeGrade[letter],
        inspector_model_version=INSPECTOR_MODEL_VERSION, inference_backend=backend, sha256_payload_hash=digest,
        verification_hash=signature, payload=payload,
    )
    _ISSUED[cert.cert_id] = cert
    return cert


def verify_certificate(cert: DigitalCertificate) -> CertificateVerification:
    digest, signature = _sign(cert.payload)
    payload_ok = hmac.compare_digest(digest, cert.sha256_payload_hash)
    signature_ok = hmac.compare_digest(signature, cert.verification_hash)
    return CertificateVerification(cert_id=cert.cert_id, known=cert.cert_id in _ISSUED, payload_hash_valid=payload_ok,
                                   signature_valid=signature_ok, tampered=not (payload_ok and signature_ok))


# ---------------------------------------------------------------------------
# Backend 1: deterministic 5-second sweep reconstruction for presets
# ---------------------------------------------------------------------------


def simulate_sweep(request: GradeCropRequest, preset: SamplePreset) -> tuple[list[BoundingBox], float]:
    profile, p = CROP_PROFILES[request.crop], PRESETS[preset]
    seed_text = f"{request.crop.value}|{request.district}|{preset.value}|{request.farmer_id}"
    rng = np.random.default_rng(int(hashlib.sha256(seed_text.encode()).hexdigest()[:16], 16))
    n = int(rng.integers(8, 13))
    mean = profile.typical_mm * p.size_factor
    diameters = np.clip(rng.normal(mean, mean * p.sd_fraction, n), 0.4 * mean, None)
    px_per_mm = FRAME_W / request.frame_width_mm
    cols = 4
    boxes: list[BoundingBox] = []
    for i, d in enumerate(diameters):
        if d < profile.undersized_mm:
            label, defect = DetectionClass.UNDERSIZED, float(rng.uniform(0, 1.0))
        elif rng.random() < p.blight_p:
            label, defect = DetectionClass.FUNGAL_BLIGHT, float(rng.uniform(8, 25))
        elif rng.random() < p.bruise_p:
            label, defect = DetectionClass.MINOR_BRUISE, float(rng.uniform(2, 7))
        else:
            label, defect = DetectionClass.UNIFORM_A, float(rng.uniform(0, 0.8))
        w = int(min(300, d * px_per_mm))
        h = int(max(8, w * profile.aspect))
        cx = (i % cols) * (FRAME_W // cols) + FRAME_W // (2 * cols) + int(rng.integers(-30, 31))
        cy = (i // cols) * (FRAME_H // 3) + FRAME_H // 6 + int(rng.integers(-25, 26))
        x, y = int(np.clip(cx - w // 2, 0, FRAME_W - w)), int(np.clip(cy - h // 2, 0, FRAME_H - h))
        confidence = rng.uniform(0.90, 0.99) if label is DetectionClass.UNIFORM_A else rng.uniform(0.85, 0.95)
        boxes.append(BoundingBox(object_id=i + 1, box=(x, y, w, h), class_label=label, confidence=round(float(confidence), 3),
                                 diameter_mm=round(float(d), 1), defect_area_pct=round(defect, 2)))
    low, high = profile.moisture_band
    moisture = low + (high - low) * p.moisture_offset + float(rng.normal(0, 0.15))
    return boxes, moisture


# ---------------------------------------------------------------------------
# Backend 2: classical computer vision on an uploaded photo
# ---------------------------------------------------------------------------

ANALYSIS_MAX_SIDE = 320


def decode_image(image_base64: str) -> Any:
    from PIL import Image, UnidentifiedImageError

    data = image_base64.split(",", 1)[1] if image_base64.startswith("data:") else image_base64
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ToolExecutionError("image_base64 is not valid base64.") from exc
    if len(raw) > MAX_IMAGE_BYTES:
        raise ToolExecutionError(f"Image is {len(raw) / 1e6:.1f} MB; the edge node accepts up to {MAX_IMAGE_BYTES / 1e6:.0f} MB.")
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ToolExecutionError("image_base64 is not a readable JPEG/PNG image.") from exc


def _otsu_threshold(values: np.ndarray) -> float:
    hist, edges = np.histogram(values, bins=256, range=(0.0, 255.0))
    weights = hist.astype(float) / max(1, hist.sum())
    centers = (edges[:-1] + edges[1:]) / 2
    omega = np.cumsum(weights)
    mu = np.cumsum(weights * centers)
    between = (mu[-1] * omega - mu) ** 2 / np.maximum(omega * (1 - omega), 1e-12)
    return float(centers[int(np.argmax(between))])


def _morph(mask: np.ndarray, op: str) -> np.ndarray:
    h, w = mask.shape
    padded = np.pad(mask, 1, constant_values=op == "erode")
    out = np.ones_like(mask) if op == "erode" else np.zeros_like(mask)
    for dy in range(3):
        for dx in range(3):
            window = padded[dy:dy + h, dx:dx + w]
            out = (out & window) if op == "erode" else (out | window)
    return out


def _components(mask: np.ndarray) -> list[np.ndarray]:
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    components: list[np.ndarray] = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if labels[y0, x0]:
            continue
        label = len(components) + 1
        labels[y0, x0] = label
        stack, pixels = [(int(y0), int(x0))], []
        while stack:
            y, x = stack.pop()
            pixels.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = label
                    stack.append((ny, nx))
        components.append(np.array(pixels))
    return components


def classical_cv(request: GradeCropRequest, image: Any) -> list[BoundingBox]:
    """Background-subtraction segmentation and per-object lesion analysis of a sorting-tray photo."""
    original_w, original_h = image.size
    small = image.copy()
    small.thumbnail((ANALYSIS_MAX_SIDE, ANALYSIS_MAX_SIDE))
    rgb = np.asarray(small, dtype=float)
    h, w, _ = rgb.shape
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    background = np.median(border, axis=0)
    distance = np.sqrt(((rgb - background) ** 2).sum(axis=2))
    distance = 255.0 * distance / max(1.0, float(distance.max()))
    mask = distance > max(25.0, _otsu_threshold(distance))
    mask = _morph(_morph(mask, "erode"), "dilate")
    luminance = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    profile = CROP_PROFILES[request.crop]
    mm_per_px = request.frame_width_mm / w
    scale_x, scale_y = original_w / w, original_h / h
    min_area = max(30, int(0.002 * h * w))
    boxes: list[BoundingBox] = []
    for pixels in sorted(_components(mask), key=len, reverse=True):
        if len(pixels) < min_area:
            continue
        ys, xs = pixels[:, 0], pixels[:, 1]
        bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        size_px = max(bw, bh) if profile.aspect < 0.5 else 2.0 * np.sqrt(len(pixels) / np.pi)
        diameter = float(size_px * mm_per_px)
        lum = luminance[ys, xs]
        defect = 100.0 * float((lum < 0.55 * np.median(lum)).mean())
        if diameter < profile.undersized_mm:
            label = DetectionClass.UNDERSIZED
        elif defect >= 8.0:
            label = DetectionClass.FUNGAL_BLIGHT
        elif defect >= 2.0:
            label = DetectionClass.MINOR_BRUISE
        else:
            label = DetectionClass.UNIFORM_A
        contrast = float(distance[ys, xs].mean()) / 255.0
        boxes.append(BoundingBox(
            object_id=len(boxes) + 1,
            box=(int(xs.min() * scale_x), int(ys.min() * scale_y), int(bw * scale_x), int(bh * scale_y)),
            class_label=label, confidence=round(0.85 + 0.14 * min(1.0, 2 * contrast), 3),
            diameter_mm=round(diameter, 1), defect_area_pct=round(defect, 2),
        ))
    return boxes


# ---------------------------------------------------------------------------
# Backend 3: trained YOLO weights (optional)
# ---------------------------------------------------------------------------

_YOLO_MODEL: Any = None


def yolo_detect(request: GradeCropRequest, image: Any) -> list[BoundingBox] | None:
    weights = os.getenv("KNX_YOLO_WEIGHTS")
    if not weights or not os.path.exists(weights) or importlib.util.find_spec("ultralytics") is None:
        return None
    global _YOLO_MODEL
    from ultralytics import YOLO

    if _YOLO_MODEL is None:
        _YOLO_MODEL = YOLO(weights)
    result = _YOLO_MODEL(image, verbose=False)[0]
    mm_per_px = request.frame_width_mm / image.size[0]
    typical_defect = {DetectionClass.MINOR_BRUISE: 4.0, DetectionClass.FUNGAL_BLIGHT: 15.0}
    known = {c.value for c in DetectionClass}
    boxes: list[BoundingBox] = []
    for i, (xywh, conf, cls) in enumerate(zip(result.boxes.xywh.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist())):
        name = str(result.names[int(cls)])
        label = DetectionClass(name) if name in known else DetectionClass.UNIFORM_A
        cx, cy, bw, bh = xywh
        boxes.append(BoundingBox(object_id=i + 1, box=(int(cx - bw / 2), int(cy - bh / 2), int(bw), int(bh)), class_label=label,
                                 confidence=round(float(conf), 3), diameter_mm=round(max(bw, bh) * mm_per_px, 1),
                                 defect_area_pct=typical_defect.get(label, 0.5)))
    return boxes


# ---------------------------------------------------------------------------
# Grader
# ---------------------------------------------------------------------------


class OpticalCropGrader:
    def grade(self, request: GradeCropRequest) -> GradeCropResult:
        started = time.perf_counter()
        profile = CROP_PROFILES[request.crop]
        reasons_extra: list[str] = []
        if request.image_base64:
            image = decode_image(request.image_base64)
            boxes = yolo_detect(request, image)
            backend = f"ultralytics-yolo ({os.getenv('KNX_YOLO_WEIGHTS')})" if boxes is not None else "classical-cv"
            if boxes is None:
                boxes = classical_cv(request, image)
            if not boxes:
                raise ToolExecutionError("No produce detected; photograph the lot spread on a plain tarp under even light.")
            moisture = sum(profile.moisture_band) / 2
            reasons_extra.append("moisture is the crop band prior: an RGB photo cannot measure moisture")
            source, frames, frame_size = "uploaded_image", 1, image.size
        else:
            preset = request.sample_preset or SamplePreset.FIELD_SWEEP
            boxes, moisture = simulate_sweep(request, preset)
            backend, source = "simulated-video-sweep", f"preset:{preset.value}"
            frames, frame_size = SWEEP_SECONDS * SWEEP_FPS, (FRAME_W, FRAME_H)
        metrics = summarize(request.crop, boxes, moisture)
        letter, reasons = assign_grade(request.crop, metrics)
        premium = price_premium(letter, metrics)
        certificate = issue_certificate(request, letter, metrics, backend, len(boxes))
        return GradeCropResult(
            crop=request.crop, district=request.district, source=source, inference_backend=backend,
            inspector_model_version=INSPECTOR_MODEL_VERSION, frame_size=frame_size, video_frames_analyzed=frames,
            bounding_boxes=boxes, metrics=metrics, assigned_grade=EdgeGrade[letter], grade_letter=letter,
            grading_reasons=reasons + reasons_extra, price_premium_pct=premium,
            premium_basis="vs. an ungraded farm-gate lot; BAU trials report up to +32% seasonal income from grading + MAP packaging",
            digital_certificate=certificate, latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    @staticmethod
    def verify(certificate: DigitalCertificate) -> CertificateVerification:
        return verify_certificate(certificate)

    @staticmethod
    def lookup(cert_id: str) -> DigitalCertificate | None:
        return _ISSUED.get(cert_id)


OPTICAL_GRADER = OpticalCropGrader()
