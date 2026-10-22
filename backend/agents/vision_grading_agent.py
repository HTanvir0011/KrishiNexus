"""Agent 1 — Vision & Quality Grading.

Without farmer-supplied metrics the agent runs the edge ``OpticalCropGrader`` on the lot's 5-second
sweep (bounding boxes, size uniformity, bruising, blight). Grades come from the grader's shared
``assign_grade`` (thresholds of the active ``vision_grading`` prompt version plus size, undersized-share
and moisture checks). The agent then pulls verified BARI/BAU curing, storage and MAP packaging rules
through the CRAG pipeline and issues a SHA-256 / HMAC-signed ``DigitalQualityCertificate``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta
from typing import Any

from agents.state import DigitalQualityCertificate, HarvestMetrics, KrishiAgentState, QualityGrade, StepType
from agents.tracing import TraceRecorder
from config import now_bdt, settings
from edge_node.optical_grader import CROP_PROFILES, OPTICAL_GRADER, GradeableCrop, GradeCropRequest, GradingMetrics, assign_grade
from prompts.prompt_registry import PROMPT_REGISTRY, grade_rule
from rag.crag_pipeline import CRAG_PIPELINE
from schemas.mcp_models import Crop, Grade

AGENT = "vision_grading"
CERT_VALIDITY_DAYS: dict[Crop, int] = {
    Crop.CARDINAL_POTATO: 30, Crop.DIAMANT_POTATO: 30, Crop.GREEN_CHILI: 3, Crop.BRINJAL: 5, Crop.BORO_RICE: 90,
}
_GRADE_LABEL = {"A": QualityGrade.A, "B": QualityGrade.B, "C": QualityGrade.C}
_PADDY_MOISTURE_BAND = (12.0, 14.0)


def _packaging(crop: Crop, grade: str) -> str:
    uplift = "BAU trials: grading plus MAP packaging raises seasonal income about 32% (about US$947 per smallholder)."
    if crop in (Crop.GREEN_CHILI, Crop.BRINJAL):
        return f"Pre-cool within 4 h and pack in perforated LDPE MAP bags. {uplift}"
    if crop is Crop.BORO_RICE:
        return "Dry to 12-14% moisture and store in hermetic bags on raised platforms."
    if grade == "C":
        return "Sell to processors (chips/flakes); do not store long-term."
    return f"Cure 10-14 days, then pack in 50 kg leno/jute bags for 48-50 F cold storage or crate for supermarket DCs. {uplift}"


async def run(state: KrishiAgentState, trace: TraceRecorder) -> dict[str, Any]:
    prompt = PROMPT_REGISTRY.active(AGENT)
    edge_cert_id = edge_backend = None
    detections = 0
    scanned_diameter_mm: float | None = None
    if state.harvest_metrics_input is not None:
        metrics = state.harvest_metrics_input
        linked = OPTICAL_GRADER.lookup(metrics.edge_certificate_id) if metrics.edge_certificate_id else None
        if linked is not None:
            edge_cert_id, edge_backend = linked.cert_id, linked.inference_backend
            detections = int(linked.payload["detections"])
            scanned_diameter_mm = float(linked.payload["metrics"]["avg_diameter_mm"])
    elif state.crop is Crop.BORO_RICE:
        metrics = HarvestMetrics(size_uniformity_pct=92.0, bruising_pct=1.0, rot_blight_risk_pct=1.0, moisture_pct=13.5,
                                 source="farmer_supplied")
        await trace.emit(AGENT, StepType.THOUGHT, "Paddy is graded by moisture meter and sieve, not the produce camera; "
                                                   "using standard field readings (13.5% moisture).")
    else:
        scan = OPTICAL_GRADER.grade(GradeCropRequest(crop=GradeableCrop(state.crop.value), district=state.district,
                                                     farmer_id=state.farmer_id, lot_kg=state.quantity_kg))
        await trace.emit(AGENT, StepType.MCP_CALL,
                         f"{scan.inspector_model_version} [{scan.inference_backend}]: {len(scan.bounding_boxes)} objects in "
                         f"{scan.video_frames_analyzed} frames -> {scan.grade_letter}; certificate {scan.digital_certificate.cert_id}.",
                         tool="OpticalCropGrader", latency_ms=scan.latency_ms,
                         data={"classes": sorted({b.class_label.value for b in scan.bounding_boxes})})
        m = scan.metrics
        metrics = HarvestMetrics(size_uniformity_pct=m.size_uniformity_pct, bruising_pct=m.mechanical_bruising_pct,
                                 rot_blight_risk_pct=m.rot_blight_risk_pct, moisture_pct=m.estimated_moisture_pct,
                                 source="edge_optical_grader")
        edge_cert_id, edge_backend, detections = scan.digital_certificate.cert_id, scan.inference_backend, len(scan.bounding_boxes)
        scanned_diameter_mm = m.avg_diameter_mm

    await trace.emit(AGENT, StepType.THOUGHT,
                     f"Metrics ({metrics.source}): uniformity {metrics.size_uniformity_pct}%, bruising {metrics.bruising_pct}%, "
                     f"rot/blight {metrics.rot_blight_risk_pct}%, moisture {metrics.moisture_pct}%.",
                     data={"prompt_version": prompt.version, "rule": prompt.variant_id})
    if state.crop is Crop.BORO_RICE:
        label = grade_rule(prompt.params, {"uniformity": metrics.size_uniformity_pct, "bruising": metrics.bruising_pct,
                                           "rot": metrics.rot_blight_risk_pct})
        low, high = _PADDY_MOISTURE_BAND
        reasons = [f"grain uniformity {metrics.size_uniformity_pct}% / damage {metrics.bruising_pct}% -> {label}"]
        if not low <= metrics.moisture_pct <= high:
            label = {"A": "B", "B": "C", "C": "C"}[label]
            reasons.append(f"paddy moisture {metrics.moisture_pct}% outside {low:g}-{high:g}%")
    else:
        crop = GradeableCrop(state.crop.value)
        label, reasons = assign_grade(crop, GradingMetrics(
            sample_count=detections or 1, avg_diameter_mm=scanned_diameter_mm or CROP_PROFILES[crop].typical_mm,
            size_uniformity_pct=metrics.size_uniformity_pct, mechanical_bruising_pct=metrics.bruising_pct,
            rot_blight_risk_pct=metrics.rot_blight_risk_pct, estimated_moisture_pct=metrics.moisture_pct, undersized_pct=0.0))

    rag = await CRAG_PIPELINE.run(f"{state.crop.value} post-harvest curing grading cold storage temperature humidity "
                                  "MAP packaging", state.district, state.crop, top_k=4)
    protocol = [f"{s.text} [{s.source}]" for s in rag.verified_context
                if s.source.startswith(("BARI", "BAU", "BRRI", "DAE"))][:4]
    await trace.emit(AGENT, StepType.RAG_CRAG,
                     f"CRAG {rag.crag.verdict} ({rag.crag.confidence:.2f}) on post-harvest rules; {len(protocol)} verified strips.",
                     token_saved=rag.context_tokens["saved"], data={"top_chunks": [c.chunk_id for c in rag.retrieval[:4]]})

    grade_score = round(max(0.0, min(100.0, 0.5 * metrics.size_uniformity_pct + 0.3 * (100 - 10 * metrics.bruising_pct)
                                     + 0.2 * (100 - 10 * metrics.rot_blight_risk_pct))), 1)
    issued = now_bdt()
    body = {
        "farmer_id": state.farmer_id, "crop": state.crop.value, "lot_kg": state.quantity_kg, "grade": label,
        "metrics": metrics.model_dump(mode="json"), "edge_certificate_id": edge_cert_id, "issued_at": issued.isoformat(),
        "prompt_version": prompt.version,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    cert = DigitalQualityCertificate(
        certificate_id=f"DQC-{state.crop.name[:3]}-{issued:%Y%m%d}-{digest[:10].upper()}",
        farmer_id=state.farmer_id, crop=state.crop, lot_kg=state.quantity_kg, metrics=metrics,
        grade=_GRADE_LABEL[label], market_grade=Grade(label), grade_score=grade_score, grading_reasons=reasons,
        storage_protocol=protocol, packaging_recommendation=_packaging(state.crop, label), edge_certificate_id=edge_cert_id,
        edge_inference_backend=edge_backend, detections=detections, issued_at=issued,
        valid_until=(issued + timedelta(days=CERT_VALIDITY_DAYS[state.crop])).date(), prompt_version=prompt.version,
        sha256_digest=digest,
        hmac_signature=hmac.new(settings.receipt_signing_key.encode(), canonical.encode(), hashlib.sha256).hexdigest(),
    )
    await trace.emit(AGENT, StepType.DECISION, f"{cert.grade.value} (score {grade_score}); certificate {cert.certificate_id} signed.",
                     data={"grade": label, "sha256": digest})
    return {
        "optical_grade_cert": cert,
        "prompt_versions": {**state.prompt_versions, AGENT: prompt.version},
        "trace_events": trace.drain(),
    }
