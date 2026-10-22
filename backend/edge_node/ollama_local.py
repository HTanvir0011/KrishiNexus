"""On-device LLM runtime manager (Ollama / llama.cpp / vLLM) and the krishi-bangla LoRA fine-tune registry.

``LocalEdgeInferenceEngine.run_local_inference`` tries, in order, a live Ollama server
(``/api/generate``), a llama.cpp server (``/completion``) and a vLLM server (``/v1/completions``).
Measured latency, tokens/s and VRAM are reported when a runtime answers. When none is reachable, or
an offline blackout is being simulated, the kiosk answers from its deterministic offline stack
(CRAG over the local knowledge base, or the voice entity extractor) and reports *modelled* telemetry:
Q4_K_M GGUF weight size, fp16 KV-cache size and a memory-bandwidth roofline for decode speed on the
selected kiosk hardware profile. ``telemetry_source`` always says which of the two you are seeing.

The LoRA registry describes ``krishi-bangla-lora-v1`` and builds its 3,200-example supervised
fine-tuning dataset deterministically from this repository's own engines (DAM prices, the knowledge
base, the dPi circuit-breaker and the haor flood model). No adapter weights ship with the repo;
``adapter_present`` turns true when trained weights are placed at ``adapter_path``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import httpx
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from config import MODEL_CATALOG, now_bdt, settings
from mcp_servers.agri_weather_sar_mcp import NETWORK_BLACKOUT
from optimization.token_compressor import estimate_tokens

LLAMACPP_URL = os.getenv("KNX_LLAMACPP_URL", "http://localhost:8080")
VLLM_URL = os.getenv("KNX_VLLM_URL", "http://localhost:8001")
PROBE_TIMEOUT_S = 1.5
GENERATE_TIMEOUT_S = 120.0
ADAPTER_DIR = Path(__file__).resolve().parent.parent / "models" / "lora"


class Runtime(StrEnum):
    OLLAMA = "ollama"
    LLAMA_CPP = "llama.cpp"
    VLLM = "vllm"


@dataclass(frozen=True, slots=True)
class LocalModelSpec:
    key: str
    ollama_tag: str
    display_name: str
    hf_base: str
    params_b: float
    n_layers: int
    kv_heads: int
    head_dim: int
    gguf_size_gb: float
    context_tokens: int
    role: str
    lora_adapter: str | None


LOCAL_MODELS: dict[str, LocalModelSpec] = {m.key: m for m in (
    LocalModelSpec("qwen2.5-7b", "qwen2.5:7b-instruct-q4_K_M", "Qwen-2.5-7B-Instruct (Q4_K_M GGUF)", "Qwen/Qwen2.5-7B-Instruct",
                   7.62, 28, 4, 128, 4.68, 4096, "Bangla negotiation answers and BARI storage Q&A", "krishi-bangla-lora-v1"),
    LocalModelSpec("deepseek-r1-7b", "deepseek-r1:7b-q4_K_M", "DeepSeek-R1-Distill-Qwen-7B (Q4_K_M GGUF)",
                   "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", 7.62, 28, 4, 128, 4.68, 4096,
                   "Offline union-kiosk dPi arbitrage math with reasoning traces", None),
    LocalModelSpec("llama3.2-3b", "llama3.2:3b-instruct-q4_K_M", "Llama-3.2-3B-Instruct (Q4_K_M GGUF)", "meta-llama/Llama-3.2-3B-Instruct",
                   3.21, 28, 8, 128, 2.02, 4096, "Sub-second voice intent and entity extraction", None),
)}
_TAG_TO_KEY = {m.ollama_tag: m.key for m in LOCAL_MODELS.values()}


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    name: str
    description: str
    memory_bandwidth_gbps: float
    decode_efficiency: float
    prefill_multiplier: float
    accelerator_memory_gb: float
    power_w: float


HARDWARE_PROFILES: dict[str, HardwareProfile] = {p.name: p for p in (
    HardwareProfile("union-kiosk-cpu", "Union Digital Centre kiosk: Intel Core i5-1235U, 16 GB DDR4-3200, CPU-only",
                    51.2, 0.45, 6.0, 16.0, 28.0),
    HardwareProfile("union-kiosk-gpu", "Union kiosk with NVIDIA RTX 3050 Laptop GPU (6 GB GDDR6)", 192.0, 0.55, 40.0, 6.0, 75.0),
    HardwareProfile("upazila-hub-gpu", "Upazila aggregation hub: NVIDIA RTX 4060 Ti (16 GB)", 288.0, 0.60, 60.0, 16.0, 165.0),
)}
UPS_BATTERY_WH = 600.0


class RuntimeStatus(BaseModel):
    runtime: Runtime
    endpoint: str
    reachable: bool
    models: list[str]
    detail: str


class ModelTelemetry(BaseModel):
    weights_mb: float
    kv_cache_mb: float
    runtime_overhead_mb: float
    vram_mb: float
    fits_on_accelerator: bool
    decode_tokens_per_s: float
    prefill_tokens_per_s: float


class LocalModelView(BaseModel):
    key: str
    ollama_tag: str
    display_name: str
    hf_base: str
    params_b: float
    quantization: str
    gguf_size_gb: float
    context_tokens: int
    role: str
    lora_adapter: str | None
    installed_in_ollama: bool
    telemetry: ModelTelemetry


class LocalInferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=20_000)
    model_name: str = Field(default="qwen2.5-7b", description="Key or Ollama tag, e.g. 'llama3.2-3b' or 'qwen2.5:7b-instruct-q4_K_M'.")
    simulate_offline_blackout: bool = False
    hardware_profile: str = "union-kiosk-cpu"
    max_tokens: int = Field(default=256, ge=8, le=2_048)


class OfflineResilience(BaseModel):
    internet: Literal["AVAILABLE", "SIMULATED_BLACKOUT"]
    cloud_dependency: str
    power_draw_w: float
    ups_runtime_min: float
    survives_internet_outage: bool


class LocalInferenceResult(BaseModel):
    model: str
    display_name: str
    runtime: str
    generated_by: str
    telemetry_source: Literal["measured", "modelled"]
    output_text: str
    prompt_tokens: int
    output_tokens: int
    latency_ms: float
    tokens_per_s: float
    vram_mb: float
    quantization: str
    lora_adapter: str | None
    api_cost_usd: float
    cloud_equivalent_cost_usd: float
    hardware_profile: str
    offline_resilience: OfflineResilience


def model_spec(name: str) -> LocalModelSpec:
    spec = LOCAL_MODELS.get(name) or LOCAL_MODELS.get(_TAG_TO_KEY.get(name, ""))
    if spec is None:
        raise ValueError(f"unknown local model '{name}'; choose one of {', '.join(LOCAL_MODELS)}")
    return spec


def modelled_telemetry(spec: LocalModelSpec, profile: HardwareProfile) -> ModelTelemetry:
    weights_mb = spec.gguf_size_gb * 1024
    kv_mb = 2 * spec.n_layers * spec.kv_heads * spec.head_dim * spec.context_tokens * 2 / 2**20  # K and V, fp16
    overhead_mb = 350.0
    vram = weights_mb + kv_mb + overhead_mb
    decode = profile.memory_bandwidth_gbps / spec.gguf_size_gb * profile.decode_efficiency
    return ModelTelemetry(
        weights_mb=round(weights_mb, 0), kv_cache_mb=round(kv_mb, 0), runtime_overhead_mb=overhead_mb, vram_mb=round(vram, 0),
        fits_on_accelerator=vram / 1024 <= profile.accelerator_memory_gb, decode_tokens_per_s=round(decode, 1),
        prefill_tokens_per_s=round(decode * profile.prefill_multiplier, 1),
    )


class LocalEdgeInferenceEngine:
    async def probe_runtimes(self) -> list[RuntimeStatus]:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:

            async def probe(runtime: Runtime, url: str, path: str) -> RuntimeStatus:
                try:
                    response = await client.get(f"{url}{path}")
                    response.raise_for_status()
                    payload = response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    return RuntimeStatus(runtime=runtime, endpoint=url, reachable=False, models=[],
                                         detail=f"not reachable ({type(exc).__name__})")
                if runtime is Runtime.OLLAMA:
                    models = [m.get("name", "") for m in payload.get("models", [])]
                elif runtime is Runtime.VLLM:
                    models = [m.get("id", "") for m in payload.get("data", [])]
                else:
                    models = ["(single GGUF loaded by llama-server)"]
                return RuntimeStatus(runtime=runtime, endpoint=url, reachable=True, models=models, detail="ok")

            return list(await asyncio.gather(probe(Runtime.OLLAMA, settings.ollama_host, "/api/tags"),
                                             probe(Runtime.LLAMA_CPP, LLAMACPP_URL, "/health"),
                                             probe(Runtime.VLLM, VLLM_URL, "/v1/models")))

    async def _live(self, spec: LocalModelSpec, prompt: str, max_tokens: int,
                    statuses: list[RuntimeStatus]) -> tuple[str, str, int, int, float, float, float] | None:
        """(runtime, text, prompt_tokens, output_tokens, latency_ms, tokens_per_s, vram_mb) from the first live runtime."""
        by_runtime = {s.runtime: s for s in statuses}
        async with httpx.AsyncClient(timeout=GENERATE_TIMEOUT_S) as client:
            ollama = by_runtime[Runtime.OLLAMA]
            if ollama.reachable and spec.ollama_tag in ollama.models:
                started = time.perf_counter()
                r = await client.post(f"{settings.ollama_host}/api/generate", json={
                    "model": spec.ollama_tag, "prompt": prompt, "stream": False,
                    "options": {"num_predict": max_tokens, "temperature": 0.2}})
                r.raise_for_status()
                body = r.json()
                ps = (await client.get(f"{settings.ollama_host}/api/ps")).json().get("models", [])
                vram = next((m.get("size_vram", 0) for m in ps if m.get("name") == spec.ollama_tag), 0) / 2**20
                eval_s = max(1e-9, body.get("eval_duration", 0) / 1e9)
                return ("ollama", body.get("response", ""), int(body.get("prompt_eval_count", 0)), int(body.get("eval_count", 0)),
                        (time.perf_counter() - started) * 1000, body.get("eval_count", 0) / eval_s, vram)
            if by_runtime[Runtime.LLAMA_CPP].reachable:
                started = time.perf_counter()
                r = await client.post(f"{LLAMACPP_URL}/completion", json={"prompt": prompt, "n_predict": max_tokens, "temperature": 0.2})
                r.raise_for_status()
                body = r.json()
                timings = body.get("timings", {})
                return ("llama.cpp", body.get("content", ""), int(timings.get("prompt_n", 0)), int(timings.get("predicted_n", 0)),
                        (time.perf_counter() - started) * 1000, float(timings.get("predicted_per_second", 0.0)), 0.0)
            vllm = by_runtime[Runtime.VLLM]
            if vllm.reachable and vllm.models:
                started = time.perf_counter()
                r = await client.post(f"{VLLM_URL}/v1/completions", json={"model": vllm.models[0], "prompt": prompt,
                                                                          "max_tokens": max_tokens, "temperature": 0.2})
                r.raise_for_status()
                body = r.json()
                usage = body.get("usage", {})
                elapsed = (time.perf_counter() - started) * 1000
                out = int(usage.get("completion_tokens", 0))
                return ("vllm", body["choices"][0]["text"], int(usage.get("prompt_tokens", 0)), out, elapsed,
                        out / max(1e-9, elapsed / 1000), 0.0)
        return None

    async def _offline_answer(self, spec: LocalModelSpec, prompt: str) -> tuple[str, str]:
        from edge_node.bangla_voice import VOICE_PIPELINE

        entities = VOICE_PIPELINE.transcribe_and_normalize(text=prompt).entities
        if spec.key == "llama3.2-3b":
            return entities.model_dump_json(), "deterministic edge fallback: Bangla voice entity extractor (no local runtime reachable)"
        if spec.key == "deepseek-r1-7b" and entities.quantity_kg and entities.offered_faria_price_bdt is not None:
            return self._arbitrage_trace(entities.crop, entities.quantity_kg, entities.offered_faria_price_bdt, entities.district), (
                "deterministic edge fallback: on-device dPi circuit-breaker (no local runtime reachable)")
        from rag.crag_pipeline import CRAG_PIPELINE

        token = NETWORK_BLACKOUT.set(True)
        try:
            rag = await CRAG_PIPELINE.run(prompt, None, None, top_k=4)
        finally:
            NETWORK_BLACKOUT.reset(token)
        return rag.answer_summary, "deterministic edge fallback: CRAG over the on-device knowledge base (no local runtime reachable)"

    @staticmethod
    def _arbitrage_trace(crop: Any, quantity_kg: float, spot: float, district: str | None) -> str:
        """Kiosk-side dPi with the cached DAM curve: 90-day farm-gate price, mid-band BCSA tariff."""
        from guardrails.financial_circuit import CIRCUIT_BREAKER, ArbitrageCheckInput
        from mcp_servers import bd_geo
        from mcp_servers.dam_market_mcp import market_prices
        from schemas.mcp_models import Crop

        crop = crop if crop in (Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO) else Crop.CARDINAL_POTATO
        place = bd_geo.resolve_district(district or "Munshiganj")
        future = market_prices(crop, place, now_bdt().date() + timedelta(days=90)).grower
        r = CIRCUIT_BREAKER.validate_arbitrage_recommendation(ArbitrageCheckInput(
            crop=crop, quantity_kg=quantity_kg, spot_price_bdt=spot, expected_future_price_bdt=future,
            storage_tariff_bdt=8.75, handling_cost_bdt=0.6, lambda_rot=0.02, district=place.name, holding_months=3))
        return (f"<think>Q={quantity_kg:g} kg, P_spot={spot:g}, E[P_90d]={future:.2f} ({place.name}), C_s=8.75, C_h=0.6, lambda=0.02. "
                f"storage={r.storage_branch_value_bdt:,.0f}; spot={r.spot_branch_value_bdt:,.0f}; dPi={r.delta_pi_bdt:,.0f}.</think> "
                f"{r.verdict.value}: {r.rationale[0]}")

    async def run_local_inference(self, request: LocalInferenceRequest) -> LocalInferenceResult:
        spec = model_spec(request.model_name)
        profile = HARDWARE_PROFILES.get(request.hardware_profile)
        if profile is None:
            raise ValueError(f"unknown hardware_profile; choose one of {', '.join(HARDWARE_PROFILES)}")
        statuses = [] if request.simulate_offline_blackout else await self.probe_runtimes()
        live = None
        if statuses and any(s.reachable for s in statuses):
            try:
                live = await self._live(spec, request.prompt, request.max_tokens, statuses)
            except (httpx.HTTPError, ValueError, KeyError):
                live = None
        telemetry = modelled_telemetry(spec, profile)
        if live is not None:
            runtime, text, prompt_tokens, output_tokens, latency, tps, vram = live
            generated_by, source = f"{runtime} live generation", "measured"
            vram = vram or telemetry.vram_mb
        else:
            text, generated_by = await self._offline_answer(spec, request.prompt)
            runtime, source = "edge-fallback", "modelled"
            prompt_tokens, output_tokens = estimate_tokens(request.prompt), min(request.max_tokens, estimate_tokens(text))
            tps = telemetry.decode_tokens_per_s
            latency = (prompt_tokens / telemetry.prefill_tokens_per_s + output_tokens / tps) * 1000
            vram = telemetry.vram_mb
        sonnet = MODEL_CATALOG["claude-sonnet"]
        cloud_cost = prompt_tokens / 1e6 * sonnet.input_usd_per_mtok + output_tokens / 1e6 * sonnet.output_usd_per_mtok
        return LocalInferenceResult(
            model=spec.ollama_tag, display_name=spec.display_name, runtime=runtime, generated_by=generated_by,
            telemetry_source=source, output_text=text, prompt_tokens=prompt_tokens, output_tokens=output_tokens,
            latency_ms=round(latency, 1), tokens_per_s=round(tps, 1), vram_mb=round(vram, 0), quantization="Q4_K_M GGUF",
            lora_adapter=spec.lora_adapter, api_cost_usd=0.0, cloud_equivalent_cost_usd=round(cloud_cost, 6),
            hardware_profile=profile.description,
            offline_resilience=OfflineResilience(
                internet="SIMULATED_BLACKOUT" if request.simulate_offline_blackout else "AVAILABLE",
                cloud_dependency="none: weights, knowledge base and MCP caches are on the kiosk",
                power_draw_w=profile.power_w, ups_runtime_min=round(UPS_BATTERY_WH / profile.power_w * 60 * 0.85, 0),
                survives_internet_outage=True,
            ),
        )


EDGE_ENGINE = LocalEdgeInferenceEngine()


# ---------------------------------------------------------------------------
# krishi-bangla-lora-v1: adapter spec and deterministic SFT dataset
# ---------------------------------------------------------------------------

DATASET_PLAN: dict[str, int] = {"market_negotiation": 1_200, "storage_qa": 800, "arbitrage_math": 700, "flood_harvest": 500}
EVAL_FRACTION = 0.10
CROP_BN_SHORT = {"Cardinal Potato": "কার্ডিনাল আলু", "Diamant Potato": "ডায়মন্ড আলু", "Green Chili": "কাঁচা মরিচ", "Brinjal": "বেগুন"}
NEGOTIATION_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("Rangpuri", "বাহে, হামার {qty} মণ {crop} আছে, ফড়িয়া {offer} টাকা কেজি দিবার চায়। বেচমু?"),
    ("Bogura (Varendri)", "হামি {qty} মণ {crop} লিয়া বসি আছি, পাইকার {offer} টাকা কয়। ক্যাংকা করমু?"),
    ("Sylheti", "আমার {qty} মণ {crop} আছে, বেপারী {offer} টাকা দিত চায়। কিতা করমু?"),
    ("Chittagonian", "আঁর {qty} মণ {crop} আছে, ফড়িয়া {offer} টাকা কয়। কিল্লাই এত কম?"),
    ("Standard Bangla", "আমার {qty} মণ {crop} আছে, ফড়িয়া কেজি {offer} টাকা দিতে চাইছে। বিক্রি করব?"),
)
STORAGE_QUESTIONS: tuple[str, ...] = (
    "{topic} নিয়ে বারি/বাউর পরামর্শ কী?", "{crop} এর ক্ষেত্রে {topic} কীভাবে করব?", "{topic} সম্পর্কে নিয়মটা বলুন।",
    "হিমাগারে রাখার আগে {topic} কেন জরুরি?", "{topic} ঠিক না হলে কী ক্ষতি হয়?",
)


class SftExample(BaseModel):
    example_id: str
    split: Literal["train", "eval"]
    category: str
    dialect: str
    instruction: str
    response: str
    source: str


class DatasetStats(BaseModel):
    total_examples: int
    train_examples: int
    eval_examples: int
    by_category: dict[str, int]
    by_dialect: dict[str, int]
    avg_instruction_tokens: float
    avg_response_tokens: float
    total_tokens: int
    jsonl_sha256: str
    generator: str


class LoraAdapterSpec(BaseModel):
    name: str
    base_model: str
    base_quantized_tag: str
    method: str
    rank: int
    alpha: int
    dropout: float
    target_modules: list[str]
    learning_rate: float
    epochs: int
    max_seq_len: int
    effective_batch_size: int
    trainable_params_m: float
    status: Literal["dataset_ready_not_trained", "adapter_present"]
    adapter_path: str
    adapter_present: bool
    dataset: DatasetStats
    training_command: str
    gguf_export_command: str
    ollama_modelfile: str


def _negotiation(i: int, rng: np.random.Generator) -> SftExample:
    from mcp_servers import bd_geo
    from mcp_servers.dam_market_mcp import CROP_SURPLUS_DISTRICTS, market_prices
    from schemas.mcp_models import Crop

    crop = (Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO, Crop.GREEN_CHILI, Crop.BRINJAL)[i % 4]
    districts = sorted(CROP_SURPLUS_DISTRICTS[crop]) + ["Dhaka Karwan Bazar", "Sylhet"]
    district = bd_geo.district_by_name(districts[(i // 4) % len(districts)])
    on = date(2026, 1, 1) + timedelta(days=(i * 7) % 365)
    p = market_prices(crop, district, on)
    dialect, template = NEGOTIATION_TEMPLATES[i % len(NEGOTIATION_TEMPLATES)]
    offer = round(p.grower * float(rng.uniform(0.3, 1.0)))
    qty = int(rng.integers(2, 60))
    fair = offer >= 0.95 * p.grower
    response = (f"{on:%d %b} তারিখে {district.name} বাজারে খামার দাম কেজি {p.grower:.0f} টাকা, পাইকারি {p.wholesale:.0f} টাকা, "
                f"খুচরা {p.retail:.0f} টাকা। " + ("এই দাম ন্যায্য, বিক্রি করতে পারেন।" if fair else
                f"{offer} টাকা ন্যায্য খামার দামের চেয়ে {p.grower - offer:.0f} টাকা কম। একা বিক্রি না করে ৫ টনের যৌথ ট্রাকে সরাসরি "
                "আড়ত, সুপারশপ বা WFP কেন্দ্রে বিক্রি করুন।"))
    return SftExample(example_id="", split="train", category="market_negotiation", dialect=dialect,
                      instruction=template.format(qty=qty, crop=CROP_BN_SHORT[crop.value], offer=offer), response=response,
                      source=f"dam-market-mcp market_prices({crop.value}, {district.name}, {on})")


def _storage_qa(i: int, sentences: list[tuple[str, str, str, str]]) -> SftExample:
    doc_id, topic, crop, sentence = sentences[i % len(sentences)]
    question = STORAGE_QUESTIONS[(i // len(sentences)) % len(STORAGE_QUESTIONS)]
    return SftExample(example_id="", split="train", category="storage_qa", dialect="Standard Bangla",
                      instruction=question.format(topic=topic, crop=crop), response=f"{sentence} [{doc_id}]", source=doc_id)


def _arbitrage(i: int, rng: np.random.Generator) -> SftExample:
    from guardrails.financial_circuit import CIRCUIT_BREAKER, ArbitrageCheckInput
    from schemas.mcp_models import Crop

    q = int(rng.integers(4, 100)) * 100
    spot, future = round(float(rng.uniform(5, 40)), 1), round(float(rng.uniform(15, 90)), 1)
    tariff, handling = round(float(rng.choice([8.0, 8.25, 8.5, 8.75, 9.0, 9.25, 9.5])), 2), round(float(rng.uniform(0.4, 0.8)), 2)
    lam, months = round(float(rng.uniform(0.012, 0.09)), 3), int(rng.integers(2, 8))
    r = CIRCUIT_BREAKER.validate_arbitrage_recommendation(ArbitrageCheckInput(
        crop=Crop.CARDINAL_POTATO, quantity_kg=q, spot_price_bdt=spot, expected_future_price_bdt=future,
        storage_tariff_bdt=tariff, handling_cost_bdt=handling, lambda_rot=lam, holding_months=months))
    decision_bn = {"BLOCK_SPOT_SALE": "এখন বিক্রি করবেন না; হিমাগারে রাখুন এবং রসিদের বিপরীতে ঋণ নিন।",
                   "ALLOW_STORAGE": "হিমাগারে রাখলে বেশি লাভ, তবে চাইলে এখন বিক্রিও করতে পারেন।",
                   "ALLOW_SPOT_SALE": "এখন বিক্রি করাই লাভজনক।", "WARN_STORAGE_LOSES_VALUE": "রাখলে লোকসান, এখন বিক্রি করুন।",
                   "WARN_NO_STORAGE_CAPACITY": "হিমাগারে জায়গা নেই; যৌথ ট্রাকে সরাসরি বিক্রি করুন।"}[r.verdict.value]
    return SftExample(
        example_id="", split="train", category="arbitrage_math", dialect="Standard Bangla",
        instruction=f"{q} কেজি আলু আছে। আজ দাম {spot} টাকা, {months} মাস পর {future} টাকা আশা করছি। হিমাগার ভাড়া {tariff} টাকা, "
                    f"হ্যান্ডলিং {handling} টাকা, পচনের হার {lam}। রাখব না বেচব?",
        response=f"<arbitrage_math_trace>storage = {q}*(1-{lam})*{future} - {q}*({tariff}+{handling}) = {r.storage_branch_value_bdt:,.0f}; "
                 f"spot = {q}*{spot} = {r.spot_branch_value_bdt:,.0f}; dPi = {r.delta_pi_bdt:,.0f}</arbitrage_math_trace> "
                 f"{r.verdict.value}: {decision_bn}",
        source="guardrails.financial_circuit.FinancialCircuitBreaker")


def _flood(i: int, rng: np.random.Generator) -> SftExample:
    from mcp_servers import bd_geo
    from mcp_servers.agri_weather_sar_mcp import HAOR_DISTRICTS, HAOR_UPAZILAS, breach_probability, to_bangla_digits
    from prompts.prompt_registry import alert_rule

    name = list(HAOR_UPAZILAS)[i % len(HAOR_UPAZILAS)]
    profile = HAOR_UPAZILAS[name]
    district = HAOR_DISTRICTS[bd_geo.resolve_upazila(name).district]
    rain, sar, month = round(float(rng.uniform(30, 420))), round(float(rng.uniform(-23, -7)), 1), int(rng.choice([3, 4, 5]))
    probability = breach_probability(rain, sar, district, profile, month)[0]
    alert = alert_rule({"red": 0.70, "orange": 0.45, "yellow": 0.20}, {"probability": probability})
    advice = {"RED": "এখনই ৮০% পাকা ধান কেটে উঁচু জায়গায় সরান।", "ORANGE": "২৪ ঘণ্টার মধ্যে ধান কাটার যন্ত্র ও ট্রাক প্রস্তুত করুন।",
              "YELLOW": "শ্রমিক ও যন্ত্র প্রস্তুত রাখুন, পানি পর্যবেক্ষণ করুন।", "GREEN": "স্বাভাবিক সময়সূচিতে ধান কাটুন।"}[alert]
    return SftExample(
        example_id="", split="train", category="flood_harvest", dialect="Sylheti" if i % 2 else "Standard Bangla",
        instruction=f"{profile.name_bn} হাওরে উজানে ৭২ ঘণ্টায় {to_bangla_digits(rain)} মিমি বৃষ্টি, রাডারে পানির সংকেত "
                    f"{to_bangla_digits(sar)} ডিবি। ধান কাটব কখন?",
        response=f"বাঁধ ভাঙার সম্ভাবনা {to_bangla_digits(round(probability * 100))}% ({alert})। {advice}",
        source="agri-weather-sar-mcp breach_probability")


@lru_cache(maxsize=1)
def build_sft_dataset() -> tuple[SftExample, ...]:
    from rag.hybrid_retriever import SemanticChunker
    from rag.knowledge_seed import KNOWLEDGE_DOCS

    rng = np.random.default_rng(20_261_022)
    sentences = [(d.doc_id, topic, d.crops[0] if d.crops else "ফসল", s)
                 for d in KNOWLEDGE_DOCS for s in SemanticChunker.sentences(d.text) for topic in d.topics[:1]]
    examples: list[SftExample] = []
    for category, count in DATASET_PLAN.items():
        for i in range(count):
            if category == "market_negotiation":
                example = _negotiation(i, rng)
            elif category == "storage_qa":
                example = _storage_qa(i, sentences)
            elif category == "arbitrage_math":
                example = _arbitrage(i, rng)
            else:
                example = _flood(i, rng)
            examples.append(example)
    eval_every = round(1 / EVAL_FRACTION)
    return tuple(e.model_copy(update={"example_id": f"KBL-{n:05d}", "split": "eval" if n % eval_every == 0 else "train"})
                 for n, e in enumerate(examples, start=1))


def dataset_stats(examples: tuple[SftExample, ...]) -> DatasetStats:
    jsonl = "\n".join(json.dumps(e.model_dump(), ensure_ascii=False, sort_keys=True) for e in examples)
    instr = [estimate_tokens(e.instruction) for e in examples]
    resp = [estimate_tokens(e.response) for e in examples]
    by_category: dict[str, int] = {}
    by_dialect: dict[str, int] = {}
    for e in examples:
        by_category[e.category] = by_category.get(e.category, 0) + 1
        by_dialect[e.dialect] = by_dialect.get(e.dialect, 0) + 1
    evals = sum(e.split == "eval" for e in examples)
    return DatasetStats(
        total_examples=len(examples), train_examples=len(examples) - evals, eval_examples=evals, by_category=by_category,
        by_dialect=by_dialect, avg_instruction_tokens=round(float(np.mean(instr)), 1), avg_response_tokens=round(float(np.mean(resp)), 1),
        total_tokens=int(sum(instr) + sum(resp)), jsonl_sha256=hashlib.sha256(jsonl.encode()).hexdigest(),
        generator="edge_node.ollama_local.build_sft_dataset (deterministic, seed 20261022)",
    )


def lora_adapter_spec() -> LoraAdapterSpec:
    base = LOCAL_MODELS["qwen2.5-7b"]
    adapter_path = ADAPTER_DIR / "krishi-bangla-lora-v1"
    present = (adapter_path / "adapter_model.safetensors").exists() or (adapter_path.with_suffix(".gguf")).exists()
    rank, hidden, intermediate, layers, kv_dim = 16, 3584, 18944, base.n_layers, base.kv_heads * base.head_dim
    per_layer = rank * ((hidden + hidden) * 2 + (hidden + kv_dim) * 2 + (hidden + intermediate) * 3)  # q,o + k,v + gate,up,down
    stats = dataset_stats(build_sft_dataset())
    return LoraAdapterSpec(
        name="krishi-bangla-lora-v1", base_model=base.hf_base, base_quantized_tag=base.ollama_tag,
        method="QLoRA (4-bit NF4 frozen base, bf16 LoRA adapters)", rank=rank, alpha=32, dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"], learning_rate=2e-4,
        epochs=3, max_seq_len=2048, effective_batch_size=16, trainable_params_m=round(per_layer * layers / 1e6, 1),
        status="adapter_present" if present else "dataset_ready_not_trained", adapter_path=str(adapter_path),
        adapter_present=present, dataset=stats,
        training_command=("python -m edge_node.train_lora is not bundled; train with PEFT/TRL SFTTrainer on the JSONL from "
                          "GET /edge/lora-dataset?format=jsonl using the hyper-parameters above"),
        gguf_export_command="python llama.cpp/convert_lora_to_gguf.py <adapter_dir> --base <Qwen2.5-7B-Instruct dir> "
                            "--outfile krishi-bangla-lora-v1.gguf",
        ollama_modelfile=f"FROM {base.ollama_tag}\nADAPTER ./krishi-bangla-lora-v1.gguf\nPARAMETER temperature 0.2\n"
                         "SYSTEM You are KrishiNexus, a Bangla-speaking agricultural market and storage advisor.",
    )


class LocalModelsReport(BaseModel):
    runtimes: list[RuntimeStatus]
    hardware_profile: str
    models: list[LocalModelView]
    lora_adapter: LoraAdapterSpec
    note: str


async def local_models_report(hardware_profile: str = "union-kiosk-cpu") -> LocalModelsReport:
    profile = HARDWARE_PROFILES.get(hardware_profile)
    if profile is None:
        raise ValueError(f"unknown hardware_profile; choose one of {', '.join(HARDWARE_PROFILES)}")
    runtimes = await EDGE_ENGINE.probe_runtimes()
    installed = {m for r in runtimes if r.runtime is Runtime.OLLAMA for m in r.models}
    return LocalModelsReport(
        runtimes=runtimes,
        hardware_profile=profile.description,
        models=[LocalModelView(key=m.key, ollama_tag=m.ollama_tag, display_name=m.display_name, hf_base=m.hf_base,
                               params_b=m.params_b, quantization="Q4_K_M GGUF", gguf_size_gb=m.gguf_size_gb,
                               context_tokens=m.context_tokens, role=m.role, lora_adapter=m.lora_adapter,
                               installed_in_ollama=m.ollama_tag in installed, telemetry=modelled_telemetry(m, profile))
                for m in LOCAL_MODELS.values()],
        lora_adapter=lora_adapter_spec(),
        note="Telemetry here is modelled from GGUF size, fp16 KV cache and memory bandwidth; /edge/local-inference reports "
             "measured numbers whenever a local runtime answers. Pull models with: ollama pull <ollama_tag>.",
    )
