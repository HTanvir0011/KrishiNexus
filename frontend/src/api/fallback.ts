/**
 * Deterministic client-side snapshots shown only when the FastAPI backend is unreachable.
 * Values mirror a real backend run (Bogura / Shibganj, Cardinal potato) so the demo stays coherent;
 * every certificate and session id is prefixed OFFLINE-PREVIEW so it can never pass as a live result.
 */

import type {
  BoundingBox,
  ChamberTelemetry,
  DetectionClass,
  GradeableCrop,
  GradeCropResult,
  LocalModelsReport,
  PoolLot,
  PoolView,
  QuotaResult,
  SamplePreset,
  VoiceInteractBody,
  VoiceInteractResponse,
} from "./client";

function seeded(text: string): () => number {
  let h = 2166136261;
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

const hex = (rand: () => number, length: number) =>
  Array.from({ length }, () => Math.floor(rand() * 16).toString(16)).join("");

const TYPICAL_MM: Record<GradeableCrop, number> = {
  "Cardinal Potato": 62, "Diamant Potato": 64, "Green Chili": 78, Brinjal: 180, Mango: 95, Banana: 170,
};
const ASPECT: Record<GradeableCrop, number> = {
  "Cardinal Potato": 0.8, "Diamant Potato": 0.75, "Green Chili": 0.22, Brinjal: 0.45, Mango: 0.72, Banana: 0.28,
};

export function fallbackGrade(crop: GradeableCrop, preset: SamplePreset): GradeCropResult {
  const rand = seeded(`${crop}|${preset}`);
  const defectRate = preset === "high_grade_harvest" ? 0.1 : preset === "blight_affected_lot" ? 0.45 : 0.25;
  const boxes: BoundingBox[] = Array.from({ length: 10 }, (_, i) => {
    const diameter = TYPICAL_MM[crop] * (0.94 + rand() * 0.12);
    const w = Math.min(300, Math.round(diameter * (1280 / 600)));
    const h = Math.max(8, Math.round(w * ASPECT[crop]));
    const roll = rand();
    const label: DetectionClass = roll > defectRate ? "uniform_A" : roll > defectRate / 3 ? "minor_bruise" : "fungal_blight";
    return {
      object_id: i + 1,
      box: [Math.min(1280 - w, (i % 4) * 320 + 160 - w / 2 + rand() * 40), Math.min(720 - h, Math.floor(i / 4) * 240 + 60 + rand() * 30), w, h],
      class_label: label,
      confidence: Number((label === "uniform_A" ? 0.9 + rand() * 0.09 : 0.85 + rand() * 0.1).toFixed(3)),
      diameter_mm: Number(diameter.toFixed(1)),
      defect_area_pct: label === "uniform_A" ? 0.4 : label === "minor_bruise" ? 4.2 : 14.5,
    };
  });
  const fungal = boxes.filter((b) => b.class_label === "fungal_blight").length;
  const bruise = boxes.filter((b) => b.class_label === "minor_bruise").reduce((s, b) => s + b.defect_area_pct, 0);
  const letter = fungal > 0 ? "B" : "A";
  const rot = Number((0.3 + (35 * fungal) / boxes.length).toFixed(2));
  return {
    crop, district: "Bogura", source: `offline-preview:${preset}`, inference_backend: "client-fallback (backend offline)",
    inspector_model_version: "yolov11n-krishi-bd-v2.1", frame_size: [1280, 720], video_frames_analyzed: 150, bounding_boxes: boxes,
    metrics: {
      sample_count: boxes.length, avg_diameter_mm: TYPICAL_MM[crop], size_uniformity_pct: 94.1,
      mechanical_bruising_pct: Number((bruise / boxes.length).toFixed(2)), rot_blight_risk_pct: rot,
      estimated_moisture_pct: 79.6, undersized_pct: 0,
    },
    assigned_grade: letter === "A" ? "Grade-A (Export / Supermarket Direct)" : "Grade-B (Standard Wholesale)",
    grade_letter: letter, grading_reasons: ["Offline preview: start the backend for a signed certificate"],
    price_premium_pct: letter === "A" ? 27.5 : 8, premium_basis: "BAU benchmark: up to +32% from grading + MAP packaging",
    digital_certificate: {
      cert_id: `OFFLINE-PREVIEW-${hex(rand, 10).toUpperCase()}`, issued_at: new Date().toISOString(),
      grade: letter, inspector_model_version: "yolov11n-krishi-bd-v2.1", inference_backend: "client-fallback (backend offline)",
      sha256_payload_hash: hex(rand, 64), verification_hash: hex(rand, 64),
    },
    latency_ms: 0,
  };
}

function seedLots(code: string, sizes: number[]): PoolLot[] {
  const rand = seeded(code);
  return sizes.map((kg, i) => ({
    farmer_id: `FARM-${code}-${String(i + 1).padStart(3, "0")}`, weight_kg: kg, grade: (i + 1) % 4 ? "A" : "B",
    distance_km: Number((rand() * 4.9).toFixed(2)), source: "seed",
  }));
}

export function fallbackPools(): PoolView[] {
  const seeds: [string, string, string, string, PoolView["crop"], number[]][] = [
    ["POOL-BOGURA-01", "Bogura", "Shibganj", "Mokamtala Union", "Cardinal Potato", [500, 450, 400, 350, 600, 300, 400, 450, 350, 500, 300]],
    ["POOL-RANGPUR-01", "Rangpur", "Mithapukur", "Ranipukur Union", "Cardinal Potato", [400, 450, 350, 500, 300, 400, 350, 400]],
    ["POOL-MUNSHIGANJ-01", "Munshiganj", "Tongibari", "Dighirpar Union", "Diamant Potato", [400, 400, 450, 350, 400, 400, 400]],
  ];
  return seeds.map(([pool_id, district, upazila, union, crop, sizes]) => {
    const lots = seedLots(district.slice(0, 3).toUpperCase(), sizes);
    const loaded = sizes.reduce((a, b) => a + b, 0);
    return {
      pool_id, district, upazila, union, crop, status: "OPEN", capacity_kg: 5000, loaded_kg: loaded, remaining_kg: 5000 - loaded,
      fill_pct: Number(((loaded / 5000) * 100).toFixed(1)), smallholders: lots.length, roster_size: 40, union_radius_km: 5,
      dispatch: null, lots,
    };
  });
}

export function fallbackTelemetry(facilityId: string, chamberId: string): ChamberTelemetry {
  return {
    facility_id: facilityId, facility_name: "Shajahanpur Himagar (offline preview)", chamber_id: chamberId, stored_crop: "Cardinal Potato",
    stored_tons: 1612, temperature_c: 9.3, temperature_f: 48.7, relative_humidity_pct: 93.4, co2_ppm: 1180, power_source: "GRID",
    rot_risk_pct: 1.4, alerts: [], simulated_anomaly_active: false,
  };
}

export function fallbackQuota(district: string): QuotaResult {
  return {
    district,
    total_open_smallholder_quota_mt: 2929,
    facilities: [{
      facility_id: "BCSA-BOG-05", name: "Shajahanpur Himagar", total_capacity_mt: 10200, trader_quota_mt: 4590, owner_quota_mt: 3296.6,
      farmer_quota_mt: 2313.4, farmer_quota_booked_mt: 1556.9, open_smallholder_quota_mt: 756.5, tariff_tk_per_kg: 8.5, power_status: "GRID",
    }],
  };
}

export function fallbackVoice(body: VoiceInteractBody): VoiceInteractResponse {
  const spoken =
    "আপনার ৪০০ কেজি কার্ডিনাল আলু গ্রেড-এ সনদ পেয়েছে। ফড়িয়ার ১১ টাকা দাম উৎপাদন খরচের (কেজি ১৫ টাকা) নিচে, তাই এই বিক্রি আটকে দেওয়া হয়েছে। " +
    "৫ টনের যৌথ ট্রাকে সরাসরি বিক্রি করলে কেজিতে ৫৬.৬৯ টাকা পাবেন। (অফলাইন প্রিভিউ — ব্যাকএন্ড চালু করুন)";
  return {
    status: "COMPLETED",
    transcription: {
      dialect: "Standard Bangla", raw_transcript: body.text ?? body.preset_id ?? "", scrubbed_transcript: body.text ?? "",
      normalized_text: body.text ?? "", pii_entities: ["BD_PHONE"],
      entities: { crop: "Cardinal Potato", crop_local_term: null, quantity_kg: 400, district: "Bogura", upazila: "Shibganj",
                  offered_faria_price_bdt: 11, middleman_role: "Faria", intent: "SELL_OR_STORE" },
    },
    grading: null,
    orchestration: {
      session_id: "OFFLINE-PREVIEW", status: "COMPLETED", graph_path: [], latency_ms: 0, trace_event_count: 0,
      state: {
        session_id: "OFFLINE-PREVIEW", farmer_id: body.farmer_id ?? "FARM-BOG-104", scrubbed_query: body.text ?? "", district: "Bogura",
        upazila: "Shibganj", crop: "Cardinal Potato", quantity_kg: 400, farmer_offer_tk_per_kg: 11, compression_report: {},
        rag_crag_result: null, optical_grade_cert: null,
        syndicate_bypass_plan: {
          farmer_offer_tk_per_kg: 11, dam_grower_tk_per_kg: 36.19, dam_wholesale_tk_per_kg: 55.6, dam_retail_tk_per_kg: 67.65,
          markup_pct: 115.5, severity: "CRITICAL", aratdar_share_of_bepari_marketing_cost_pct: 62.35,
          aratdar_take_tk_per_kg: 6.78, aratdar_grading_spend_tk_per_kg: 0, best_hub_name: "Sylhet Urban Retail Chain DC",
          best_hub_type: "URBAN_RETAIL_CHAIN", best_hub_district: "Sylhet", pooled_transport_tk_per_kg: 5.27, b2b_net_tk_per_kg: 56.69,
          lot_value_b2b_tk: 22676,
          pool: { pool_id: "POOL-BOGURA-01", upazila: "Shibganj", current_kg: 4600, after_join_kg: 5000, capacity_kg: 5000,
                  fill_pct_after_join: 100, neighbor_farmers: 11, will_trigger_dispatch: true },
          anomaly_alert: "Offline preview",
        },
        cold_storage_arbitrage_plan: {
          decision: "SELL_POOLED_B2B", horizon_days: 30, expected_future_price_tk_per_kg: 31.26, lambda_rot: 0.0302, facility: null,
          circuit_breaker: { verdict: "BLOCK_SPOT_SALE", circuit_tripped: true, storage_branch_value_bdt: 8282.38, spot_branch_value_bdt: 4400,
                             delta_pi_bdt: 3882.38, production_cost_floor_bdt: 15,
                             break_even_future_price_bdt: 21.25, micro_credit: null },
          store_vs_b2b_delta_tk: -14393.62, b2b_net_tk_per_kg: 56.69, distress_sale_blocked: true,
          block_reason: "Faria offer Tk 11/kg is below the Tk 15/kg production-cost floor.", reservation: null,
          projected_net_tk_per_kg: 56.69, math_trace: [],
        },
        climate_credit_report: null, final_bangla_voice_response: spoken, requires_farmer_voice_approval: true, node_path: [],
        errors: [], trace_events: [],
      },
    },
    spoken_response_bn: spoken,
    voice: { ssml: "", pronunciation_guide: [], estimated_duration_s: 12 },
    follow_up_question_bn: null,
  };
}

export function fallbackLocalModels(): LocalModelsReport {
  const runtime = (name: string, endpoint: string) => ({ runtime: name, endpoint, reachable: false, models: [] });
  return {
    runtimes: [runtime("ollama", "http://localhost:11434"), runtime("llama.cpp", "http://localhost:8080"), runtime("vllm", "http://localhost:8001")],
    models: [
      { key: "qwen2.5-7b", display_name: "Qwen-2.5-7B-Instruct (Q4_K_M GGUF)", ollama_tag: "qwen2.5:7b-instruct-q4_K_M", quantization: "Q4_K_M GGUF",
        role: "Bangla negotiation answers", lora_adapter: "krishi-bangla-lora-v1", telemetry: { vram_mb: 5366, decode_tokens_per_s: 4.9, fits_on_accelerator: true } },
    ],
    lora_adapter: { name: "krishi-bangla-lora-v1", status: "dataset_ready_not_trained", rank: 16, dataset: { total_examples: 3200, by_category: {} } },
  };
}
