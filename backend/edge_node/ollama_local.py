"""On-device LLM runtime manager (Ollama / llama.cpp / vLLM) and the krishi-bangla LoRA fine-tune registry.

``LocalEdgeInferenceEngine.run_local_inference`` tries, in order, a live Ollama server
(``/api/generate``), a llama.cpp server (``/completion``) and a vLLM server (``/v1/completions``).
A simulated blackout cuts the internet, not the kiosk's own runtime, so local runtimes are probed either way.
Measured latency, tokens/s and VRAM are reported when a runtime answers. When none is reachable, the kiosk
answers from its deterministic offline stack (CRAG over the local knowledge base, or the voice entity
extractor) and reports *modelled* telemetry: GGUF weight size, fp16 KV-cache size and a
memory-bandwidth roofline for decode speed on the selected kiosk hardware profile. ``telemetry_source``
always says which of the two you are seeing.

The LoRA registry describes ``krishi-bangla-lora-v2`` (trained on prompts v5; v1 on prompts v4) and builds its
4,800-example supervised fine-tuning dataset deterministically from this repository's own engines (DAM prices, the knowledge
base, the dPi circuit-breaker and the haor flood model). The fine-tuned model reads tool-grounded
prompts, so ``ground_prompt`` adds the agent's tool result to each question before it is sent. No
adapter weights ship with the repo; ``adapter_present`` turns true when trained weights are placed at
``adapter_path``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
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
from edge_node.sft_wordings import (ARBITRAGE_WORDINGS, CROP_NAMES, FLOOD_WORDINGS, MONTH_NAMES, NEGOTIATION_GROUPS,
                                    NEGOTIATION_WORDINGS, STORAGE_WORDINGS, TOPIC_BN, Wording, heldout_wordings)
from mcp_servers.agri_weather_sar_mcp import NETWORK_BLACKOUT
from mcp_servers.base import stable_unit
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
    quantization: str = "Q4_K_M GGUF"


LOCAL_MODELS: dict[str, LocalModelSpec] = {m.key: m for m in (
    # The fine-tuned model: krishi-bangla-lora-v2 merged into the de-quantised NF4 base it trained against, as Q8_0
    # (TRAINING_PLAN.md section 5: the bf16 merge at Q4_K_M lost flood and arbitrage decisions); `ollama create krishi-bangla`.
    LocalModelSpec("krishi-bangla-1.5b", "krishi-bangla:latest", "KrishiNexus Bangla advisor: Qwen2.5-1.5B + LoRA (Q8_0 GGUF)",
                   "Qwen/Qwen2.5-1.5B-Instruct", 1.54, 28, 2, 128, 1.65, 4096,
                   "Fine-tuned: fair price, store or sell, flood alert and storage answers from the agent's tool results",
                   "krishi-bangla-lora-v2", "Q8_0 GGUF"),
    LocalModelSpec("qwen2.5-7b", "qwen2.5:7b-instruct-q4_K_M", "Qwen-2.5-7B-Instruct (Q4_K_M GGUF)", "Qwen/Qwen2.5-7B-Instruct",
                   7.62, 28, 4, 128, 4.68, 4096, "Bangla negotiation answers and BARI storage Q&A", None),
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
    grounded_prompt: str | None = Field(default=None, description="What the fine-tuned model read: the question plus the tool result.")
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
                    # The fine-tuned model was scored with greedy decoding, so it answers the same way here.
                    "options": {"num_predict": max_tokens, "temperature": 0.0 if spec.lora_adapter else 0.2}})
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
        statuses = await self.probe_runtimes()
        grounded = await ground_prompt(request.prompt) if spec.lora_adapter else None
        live = None
        if any(s.reachable for s in statuses):
            try:
                live = await self._live(spec, grounded or request.prompt, request.max_tokens, statuses)
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
            latency_ms=round(latency, 1), tokens_per_s=round(tps, 1), vram_mb=round(vram, 0), quantization=spec.quantization,
            lora_adapter=spec.lora_adapter, grounded_prompt=grounded, api_cost_usd=0.0, cloud_equivalent_cost_usd=round(cloud_cost, 6),
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
# krishi-bangla LoRA: adapter spec and the deterministic SFT datasets (prompts v4 and v5)
# ---------------------------------------------------------------------------

DATASET_PLAN: dict[str, int] = {"market_negotiation": 1_200, "storage_qa": 800, "arbitrage_math": 700, "flood_harvest": 500}
# Family-aware split v2. The old split (every 10th example was "eval") leaked: templates cycle with the index, so
# nearly every eval example shared its exact template — and for storage_qa its exact response sentence — with train.
# Now whole families move together, and three OOD families are held out of training entirely to measure generalisation.
TEST_FRACTION, VAL_FRACTION = 0.10, 0.10
NEGOTIATION_HOLDOUT_DIALECT = "Chittagonian"
ARBITRAGE_HOLDOUT_MONTHS = 7
_MONTHS_RE = re.compile(r"(\d+) মাস পর")
CROP_BN_SHORT = {"Cardinal Potato": "কার্ডিনাল আলু", "Diamant Potato": "ডায়মন্ড আলু", "Green Chili": "কাঁচা মরিচ", "Brinjal": "বেগুন"}
NEGOTIATION_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("Rangpuri", "বাহে, হামার {qty} মণ {crop} আছে, ফড়িয়া {offer} টাকা কেজি দিবার চায়। বেচমু?"),
    ("Bogura (Varendri)", "হামি {qty} মণ {crop} লিয়া বসি আছি, পাইকার {offer} টাকা কয়। ক্যাংকা করমু?"),
    ("Sylheti", "আমার {qty} মণ {crop} আছে, বেপারী {offer} টাকা দিত চায়। কিতা করমু?"),
    ("Chittagonian", "আঁর {qty} মণ {crop} আছে, ফড়িয়া {offer} টাকা কয়। কিল্লাই এত কম?"),
    ("Standard Bangla", "আমার {qty} মণ {crop} আছে, ফড়িয়া কেজি {offer} টাকা দিতে চাইছে। বিক্রি করব?"),
)
MONTH_BN = {3: "মার্চ", 4: "এপ্রিল", 5: "মে"}
STORAGE_QUESTIONS: tuple[str, ...] = (
    "{topic} নিয়ে বারি/বাউর পরামর্শ কী?", "{crop} এর ক্ষেত্রে {topic} কীভাবে করব?", "{topic} সম্পর্কে নিয়মটা বলুন।",
    "হিমাগারে রাখার আগে {topic} কেন জরুরি?", "{topic} ঠিক না হলে কী ক্ষতি হয়?",
)
# Prompts v4 are tool-grounded: the first LoRA run (TRAINING_PLAN.md section 6) showed a 1.5B adapter cannot compute
# prices, dPi or breach probabilities in its weights, so each prompt carries what the agent's tool call returned and
# the model decides and explains from it. A new seed and split salt make the v4 test batch fresh.
SFT_SEED, SPLIT_SALT = 20_261_109, "split-v4"
STORAGE_PASSAGES = 3
# Prompts v5 word every question freely (edge_node/sft_wordings.py), so the model learns to read the tool result
# whatever the wording, and the arbitrage tool result carries the breaker's inputs, which farmers rarely state.
# A new seed and salt make the v5 test batch fresh; held-out wordings fill half its in-distribution rows.
SFT_V5_SEED, SPLIT_V5_SALT = 20_261_110, "split-v5"
DATASET_PLAN_V5 = {category: n * 3 // 2 for category, n in DATASET_PLAN.items()}
V5_TEST_FRACTION, V5_VAL_FRACTION, V5_HELDOUT_SHARE = 0.10, 0.06, 0.5
# The prompt format the deployed krishi-bangla model was trained on; ground_prompt builds this one. 5 since
# krishi-bangla-lora-v2 shipped (2026-11-10); set 4 to serve the v1 model (Ollama tag krishi-bangla:v4).
PROMPT_VERSION = 5
_TO_BANGLA = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _num(value: float, bangla: bool = False) -> str:
    text = str(int(value)) if float(value).is_integer() else str(value)
    return text.translate(_TO_BANGLA) if bangla else text


def _v5_split(category: str, ood: bool, *family: Any) -> Literal["train", "val", "test"]:
    """Whole families move together, as in v4; an out-of-distribution family goes to test in full."""
    if ood:
        return "test"
    unit = stable_unit(SPLIT_V5_SALT, category, *family)
    return "test" if unit < V5_TEST_FRACTION else "val" if unit < V5_TEST_FRACTION + V5_VAL_FRACTION else "train"


def _v5_wording(category: str, i: int, split: str, ood_subset: str | None,
                bank: tuple[Wording, ...]) -> tuple[Wording, bool, str]:
    """(wording, Bangla digits?, provenance). Held-out wordings fill half the in-distribution test rows (ood_wording)."""
    heldout = split == "test" and ood_subset is None and stable_unit(SPLIT_V5_SALT, "heldout", category, i) < V5_HELDOUT_SHARE
    pool = heldout_wordings()[category] if heldout else bank
    k = int(stable_unit(SPLIT_V5_SALT, "wording", category, i) * len(pool))
    subset = ood_subset or ("ood_wording" if heldout else "iid")
    bangla = pool[k][0] == "bn" and stable_unit(SPLIT_V5_SALT, "digits", category, i) < 0.5
    return pool[k], bangla, f" | wording {'heldout' if heldout else 'train'}-{k} | subset {subset}"


def _grounded(question: str, tool: str, result: Any) -> str:
    return f'{question}\n<tool_result name="{tool}">{json.dumps(result, ensure_ascii=False)}</tool_result>'


def _draw(target: str, sample: Any, label: Any, tries: int = 2_000) -> Any:
    """Re-sample until the engine's label is the target, so every task's labels are balanced by construction."""
    for _ in range(tries):
        drawn = sample()
        if label(drawn) == target:
            return drawn
    raise RuntimeError(f"no sample labelled {target} in {tries} draws")


class SftExample(BaseModel):
    example_id: str
    split: Literal["train", "val", "test"]
    category: str
    dialect: str
    instruction: str
    response: str
    source: str


class DatasetStats(BaseModel):
    total_examples: int
    train_examples: int
    val_examples: int
    test_examples: int
    holdouts: dict[str, str]
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
    eval_summary: list[dict[str, Any]] | None = Field(
        default=None, description="Measured on the held-out test split by the training run: read from the adapter's "
                                  "eval_report.json when it is installed, never typed in.")
    deployed_eval_summary: list[dict[str, Any]] | None = Field(
        default=None, description="The same split scored on the deployed GGUF through Ollama (gguf_eval_report.json): "
                                  "the model the app actually runs.")
    dataset: DatasetStats
    training_command: str
    gguf_export_command: str
    ollama_modelfile: str


def _negotiation(i: int, rng: np.random.Generator, version: int = 4) -> SftExample:
    from mcp_servers import bd_geo
    from mcp_servers.dam_market_mcp import CROP_SURPLUS_DISTRICTS, market_prices
    from schemas.mcp_models import Crop

    crop = (Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO, Crop.GREEN_CHILI, Crop.BRINJAL)[i % 4]
    districts = sorted(CROP_SURPLUS_DISTRICTS[crop]) + ["Dhaka Karwan Bazar", "Sylhet"]
    district = bd_geo.district_by_name(districts[(i // 4) % len(districts)])
    on = date(2026, 1, 1) + timedelta(days=(i * 7) % 365)
    p = market_prices(crop, district, on)
    grower, wholesale, retail = round(p.grower), round(p.wholesale), round(p.retail)
    dialect, template = NEGOTIATION_TEMPLATES[i % len(NEGOTIATION_TEMPLATES)]
    # Half the offers are fair (>= 95% of the grower price); v3 had 6% fair, so "always unfair" scored 0.94.
    offer = round(grower * float(rng.uniform(0.95, 1.10) if rng.random() < 0.5 else rng.uniform(0.3, 0.95)))
    qty = int(rng.integers(2, 60))
    fair = offer >= 0.95 * grower
    response = (f"{on:%d %b} তারিখে {district.name} বাজারে খামার দাম কেজি {grower} টাকা, পাইকারি {wholesale} টাকা, "
                f"খুচরা {retail} টাকা। " + ("এই দাম ন্যায্য, বিক্রি করতে পারেন।" if fair else
                f"{offer} টাকা ন্যায্য খামার দামের চেয়ে {grower - offer} টাকা কম। একা বিক্রি না করে ৫ টনের যৌথ ট্রাকে সরাসরি "
                "আড়ত, সুপারশপ বা WFP কেন্দ্রে বিক্রি করুন।"))
    spread = {"crop": crop.value, "district": district.name, "market_date": on.isoformat(), "grower_price_tk_per_kg": grower,
              "wholesale_price_tk_per_kg": wholesale, "retail_price_tk_per_kg": retail}
    source = f"dam-market-mcp market_prices({crop.value}, {district.name}, {on})"
    split: Literal["train", "val", "test"] = "train"   # v4 splits after building (_family_split)
    question = template.format(qty=qty, crop=CROP_BN_SHORT[crop.value], offer=offer)
    if version >= 5:
        group = NEGOTIATION_GROUPS[i % len(NEGOTIATION_GROUPS)]
        ood = group == NEGOTIATION_HOLDOUT_DIALECT
        # Families are (crop, district, quarter) market cells, whatever the wording.
        split = _v5_split("market_negotiation", ood, crop.value, district.name, (on.month - 1) // 3)
        (lang, dialect, template), bangla, provenance = _v5_wording(
            "market_negotiation", i, split, "ood_dialect" if ood else None, NEGOTIATION_WORDINGS[group])
        question = template.format(qty=_num(qty, bangla), crop=CROP_NAMES[lang][crop.value], offer=_num(offer, bangla))
        source += provenance
    return SftExample(example_id="", split=split, category="market_negotiation", dialect=dialect,
                      instruction=_grounded(question, "get_daily_commodity_spread", spread), response=response, source=source)


def _storage_qa(i: int, sentences: list[tuple[str, str, str, str, str]], rng: np.random.Generator,
                version: int = 4) -> SftExample:
    doc_id, title, topic, crop, sentence = sentences[i % len(sentences)]
    question = STORAGE_QUESTIONS[(i // len(sentences)) % len(STORAGE_QUESTIONS)].format(topic=topic, crop=crop)
    # Retrieved passages: the gold sentence plus distractors from other documents (each document has its own topic).
    others = [s for s in sentences if s[0] != doc_id]
    passages = [sentences[i % len(sentences)]] + [others[k] for k in rng.choice(len(others), STORAGE_PASSAGES - 1, replace=False)]
    retrieved = [{"doc_id": passages[k][0], "title": passages[k][1], "text": passages[k][4]} for k in rng.permutation(len(passages))]
    response, dialect, source = f"{sentence} [{doc_id}]", "Standard Bangla", doc_id
    split: Literal["train", "val", "test"] = "train"
    if version >= 5:
        split = _v5_split("storage_qa", False, response)
        (lang, dialect, template), _, provenance = _v5_wording("storage_qa", i, split, None, STORAGE_WORDINGS)
        crop_en = crop if crop in CROP_NAMES["bn"] else "ফসল" if lang == "bn" else "crop"
        question = template.format(topic=topic, topic_bn=TOPIC_BN[topic], crop=crop_en, crop_bn=CROP_NAMES["bn"].get(crop, "ফসল"))
        source += provenance
    return SftExample(example_id="", split=split, category="storage_qa", dialect=dialect,
                      instruction=_grounded(question, "crag_retrieval", retrieved), response=response, source=source)


def _arbitrage(i: int, rng: np.random.Generator, version: int = 4) -> SftExample:
    from guardrails.financial_circuit import CIRCUIT_BREAKER, ArbitrageCheckInput
    from schemas.mcp_models import Crop

    def sample() -> tuple[ArbitrageCheckInput, Any]:
        # v5 quantities are whole maunds and 50 kg sacks too (multiples of 200 kg), as farmers may state them that way.
        quantity = int(rng.integers(4, 100)) * 100 if version < 5 else int(rng.integers(2, 50)) * 200
        params = ArbitrageCheckInput(
            crop=Crop.CARDINAL_POTATO, quantity_kg=quantity, spot_price_bdt=round(float(rng.uniform(5, 40)), 1),
            expected_future_price_bdt=round(float(rng.uniform(15, 90)), 1),
            storage_tariff_bdt=round(float(rng.choice([8.0, 8.25, 8.5, 8.75, 9.0, 9.25, 9.5])), 2),
            handling_cost_bdt=round(float(rng.uniform(0.4, 0.8)), 2), lambda_rot=round(float(rng.uniform(0.012, 0.09)), 3),
            holding_months=int(rng.integers(2, 8)))
        return params, CIRCUIT_BREAKER.validate_arbitrage_recommendation(params)

    # The three verdicts the default inputs reach (all-facility quota, proposed sale), balanced.
    target = ("BLOCK_SPOT_SALE", "ALLOW_STORAGE", "ALLOW_SPOT_SALE")[int(rng.integers(3))]
    params, r = _draw(target, sample, lambda drawn: drawn[1].verdict.value)
    q, spot, future, tariff = int(params.quantity_kg), params.spot_price_bdt, params.expected_future_price_bdt, params.storage_tariff_bdt
    handling, lam, months = params.handling_cost_bdt, params.lambda_rot, params.holding_months
    storage, spot_value, delta_pi = round(r.storage_branch_value_bdt), round(r.spot_branch_value_bdt), round(r.delta_pi_bdt)
    decision_bn = {"BLOCK_SPOT_SALE": "এখন বিক্রি করবেন না; হিমাগারে রাখুন এবং রসিদের বিপরীতে ঋণ নিন।",
                   "ALLOW_STORAGE": "হিমাগারে রাখলে বেশি লাভ, তবে চাইলে এখন বিক্রিও করতে পারেন।",
                   "ALLOW_SPOT_SALE": "এখন বিক্রি করাই লাভজনক।", "WARN_STORAGE_LOSES_VALUE": "রাখলে লোকসান, এখন বিক্রি করুন।",
                   "WARN_NO_STORAGE_CAPACITY": "হিমাগারে জায়গা নেই; যৌথ ট্রাকে সরাসরি বিক্রি করুন।"}[r.verdict.value]
    response = (f"<arbitrage_math_trace>storage = {q}*(1-{lam})*{future} - {q}*({tariff}+{handling}) = {storage}; "
                f"spot = {q}*{spot} = {spot_value}; dPi = {delta_pi}</arbitrage_math_trace> {r.verdict.value}: {decision_bn}")
    payload: dict[str, Any] = {"production_cost_floor_bdt": r.production_cost_floor_bdt, "storage_branch_value_bdt": storage,
                               "spot_branch_value_bdt": spot_value, "delta_pi_bdt": delta_pi}
    question = (f"{q} কেজি আলু আছে। আজ দাম {spot} টাকা, {months} মাস পর {future} টাকা আশা করছি। হিমাগার ভাড়া {tariff} টাকা, "
                f"হ্যান্ডলিং {handling} টাকা, পচনের হার {lam}। রাখব না বেচব?")
    dialect, source = "Standard Bangla", "guardrails.financial_circuit.FinancialCircuitBreaker"
    split: Literal["train", "val", "test"] = "train"
    if version >= 5:
        payload = {"inputs": _breaker_inputs(q, spot, future, tariff, handling, lam, months), **payload}
        ood = months == ARBITRAGE_HOLDOUT_MONTHS
        split = _v5_split("arbitrage_math", ood, response)   # identical math traces never straddle splits
        (lang, dialect, template), bangla, provenance = _v5_wording(
            "arbitrage_math", i, split, "ood_months" if ood else None, ARBITRAGE_WORDINGS)
        question = template.format(**{k: _num(v, bangla) for k, v in {
            "qty_kg": q, "qty_mon": q // 40, "qty_bosta": q // 50, "spot": spot, "months": months, "future": future,
            "tariff": tariff, "handling": handling, "rot": lam, "rot_pct": round(lam * 100, 1)}.items()})
        source += provenance
    return SftExample(example_id="", split=split, category="arbitrage_math", dialect=dialect,
                      instruction=_grounded(question, "financial_circuit_breaker", payload), response=response, source=source)


def _breaker_inputs(quantity: float, spot: float, future: float, tariff: float, handling: float, lam: float,
                    months: int) -> dict[str, Any]:
    """The circuit-breaker inputs as prompts v5 show them: the trace copies them, whether or not the farmer said them."""
    return {"quantity_kg": int(quantity) if float(quantity).is_integer() else quantity, "spot_price_bdt": float(spot),
            "expected_future_price_bdt": float(future), "storage_tariff_bdt": float(tariff),
            "handling_cost_bdt": float(handling), "lambda_rot": float(lam), "holding_months": int(months)}


def _flood(i: int, rng: np.random.Generator, version: int = 4) -> SftExample:
    from mcp_servers import bd_geo
    from mcp_servers.agri_weather_sar_mcp import HAOR_DISTRICTS, HAOR_UPAZILAS, breach_probability, to_bangla_digits
    from prompts.prompt_registry import alert_rule

    name = list(HAOR_UPAZILAS)[i % len(HAOR_UPAZILAS)]
    profile = HAOR_UPAZILAS[name]
    district = HAOR_DISTRICTS[bd_geo.resolve_upazila(name).district]
    def sample() -> tuple[int, float, int, int, str]:
        rain, sar, month = round(float(rng.uniform(30, 420))), round(float(rng.uniform(-23, -7)), 1), int(rng.choice([3, 4, 5]))
        pct = round(breach_probability(rain, sar, district, profile, month)[0] * 100)
        # The alert is ruled on the whole-number percentage the prompt shows, so the label follows from the prompt.
        return rain, sar, month, pct, alert_rule({"red": 0.70, "orange": 0.45, "yellow": 0.20}, {"probability": pct / 100})

    rain, sar, month, pct, alert = _draw(("RED", "ORANGE", "YELLOW", "GREEN")[int(rng.integers(4))], sample, lambda drawn: drawn[4])
    advice = {"RED": "এখনই ৮০% পাকা ধান কেটে উঁচু জায়গায় সরান।", "ORANGE": "২৪ ঘণ্টার মধ্যে ধান কাটার যন্ত্র ও ট্রাক প্রস্তুত করুন।",
              "YELLOW": "শ্রমিক ও যন্ত্র প্রস্তুত রাখুন, পানি পর্যবেক্ষণ করুন।", "GREEN": "স্বাভাবিক সময়সূচিতে ধান কাটুন।"}[alert]
    # v4: the haor name stays first, as it is the OOD holdout key.
    question = (f"{profile.name_bn} হাওরে {MONTH_BN[month]} মাসে উজানে ৭২ ঘণ্টায় {to_bangla_digits(rain)} মিমি বৃষ্টি, রাডারে পানির "
                f"সংকেত {to_bangla_digits(sar)} ডিবি। ধান কাটব কখন?")
    response = f"{profile.name_bn} হাওরে বাঁধ ভাঙার সম্ভাবনা {to_bangla_digits(pct)}% ({alert})। {advice}"
    dialect, source = "Sylheti" if i % 2 else "Standard Bangla", "agri-weather-sar-mcp breach_probability"
    split: Literal["train", "val", "test"] = "train"
    if version >= 5:
        ood = profile.name_bn == flood_holdout_name_bn()
        split = _v5_split("flood_harvest", ood, response)   # identical alerts never straddle splits
        (lang, dialect, template), bangla, provenance = _v5_wording(
            "flood_harvest", i, split, "ood_upazila" if ood else None, FLOOD_WORDINGS)
        # Without stated readings the question still gets the breach percent the tool computes for this haor.
        question = template.format(haor=profile.name_bn, haor_en=name, rain=_num(rain, bangla), sar=_num(sar, bangla),
                                   month=MONTH_NAMES[lang][month])
        source += provenance
    return SftExample(example_id="", split=split, category="flood_harvest", dialect=dialect,
                      instruction=_grounded(question, "calculate_haor_flash_flood_risk",
                                            {"upazila": name, "embankment_breach_probability_pct": pct}),
                      response=response, source=source)


@lru_cache(maxsize=1)
def flood_holdout_name_bn() -> str:
    """Held-out haor for the OOD test: deterministic, never the Tahirpur demo upazila."""
    from mcp_servers.agri_weather_sar_mcp import HAOR_UPAZILAS

    names = [profile.name_bn for name, profile in HAOR_UPAZILAS.items() if name != "Tahirpur"]
    return max(names, key=lambda name: stable_unit("flood-holdout", name))


_TO_ASCII = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_NUMBER = r"(-?\d+(?:\.\d+)?)"
_GAP = r"\D{0,12}?"   # a few words between a cue and its number: "আজ দাম কেজি ১২"
# The numbers an SFT arbitrage question may state (the v4 template and the v5 wordings in sft_wordings.py); a farmer
# who leaves one out gets the kiosk defaults. A rot rate written with % is a percentage.
_ARBITRAGE_NUMBERS = {
    "quantity_kg": rf"{_NUMBER} কেজি",
    "spot_price_bdt": rf"(?:আজ(?:কের)? (?:দাম|দর)|এখন বাজারে|aj(?:ker)? (?:dam|dor)|today'?s price is|price today is){_GAP}{_NUMBER}",
    "holding_months": rf"{_NUMBER} ?(?:মাস|months?|mash)",
    "expected_future_price_bdt": rf"(?:মাস পরে?|রাখলে|rakhle|expect){_GAP}{_NUMBER}",
    "storage_tariff_bdt": rf"(?:ভাড়া|rent){_GAP}{_NUMBER}",
    "handling_cost_bdt": rf"(?:হ্যান্ডলিং|লোড-আনলোড|handling){_GAP}{_NUMBER}",
    "lambda_rot": rf"(?:পচনের হার|পচন ধরলে|rot loss){_GAP}{_NUMBER}( ?%)?",
}
_STORE_WORDS = re.compile(r"হিমাগার|কোল্ড স্টোর|স্টোরে|রাখব|রাখলে|cold storage|\bstore\b|himagar|rakhbo|rakhle", re.IGNORECASE)
_MONTHS_EN = {"March": 3, "April": 4, "May": 5}


def _stated_numbers(text: str) -> dict[str, float]:
    stated = {}
    for key, rx in _ARBITRAGE_NUMBERS.items():
        if m := re.search(rx, text, re.IGNORECASE):
            stated[key] = float(m.group(1)) / (100 if key == "lambda_rot" and m.group(2) else 1)
    if "lambda_rot" in stated:
        stated["lambda_rot"] = round(stated["lambda_rot"], 4)
    return stated


async def _tool_result(prompt: str, version: int = PROMPT_VERSION) -> tuple[str, Any] | None:
    """(tool, result) for a flood, store-or-sell or price question, built as the SFT builders above build them."""
    from edge_node.bangla_voice import VOICE_PIPELINE
    from guardrails.financial_circuit import CIRCUIT_BREAKER, ArbitrageCheckInput
    from mcp_servers import bd_geo
    from mcp_servers.agri_weather_sar_mcp import (HAOR_DISTRICTS, HAOR_UPAZILAS, breach_probability,
                                                  calculate_haor_flash_flood_risk, simulated_sar_db)
    from mcp_servers.dam_market_mcp import market_prices
    from schemas.mcp_models import CalculateHaorFlashFloodRiskInput, Crop

    text = prompt.translate(_TO_ASCII)
    entities = VOICE_PIPELINE.transcribe_and_normalize(text=prompt).entities
    today = now_bdt().date()
    haor = next((name for name, p in HAOR_UPAZILAS.items() if p.name_bn in prompt or name.lower() in text.lower()), None)
    if haor is None and entities.intent == "FLOOD_EMERGENCY_HARVEST":   # flood talk without a haor named: the farmer's place
        haor = next((name for name in (entities.upazila, f"{entities.district} Sadar") if name in HAOR_UPAZILAS), None)
    if haor:
        rain, sar = re.search(rf"{_NUMBER} ?(?:মিমি|mm)", text), re.search(rf"{_NUMBER} ?(?:ডিবি|db)", text, re.IGNORECASE)
        if rain and sar:   # the question states the readings, as some SFT flood questions do
            month = next((m for m, bn in MONTH_BN.items() if f"{bn} মাস" in prompt), None) or next(
                (m for en, m in _MONTHS_EN.items() if re.search(rf"\b{en}\b", prompt)), today.month)
            district = HAOR_DISTRICTS[bd_geo.resolve_upazila(haor).district]
            probability = breach_probability(float(rain.group(1)), float(sar.group(1)), district, HAOR_UPAZILAS[haor], month)[0]
            pct = round(probability * 100)
        else:
            risk = await calculate_haor_flash_flood_risk(CalculateHaorFlashFloodRiskInput(
                upazila=haor, sar_water_backscatter_db=simulated_sar_db(haor, now_bdt())))
            pct = round(risk.embankment_breach_probability_pct)
        return "calculate_haor_flash_flood_risk", {"upazila": haor, "embankment_breach_probability_pct": pct}

    stated = _stated_numbers(text)
    quantity = stated.get("quantity_kg", entities.quantity_kg)
    spot = stated.get("spot_price_bdt", entities.offered_faria_price_bdt)
    store_or_sell = "holding_months" in stated or entities.intent == "SELL_OR_STORE" or _STORE_WORDS.search(text)
    if quantity and spot is not None and store_or_sell:
        months = int(stated.get("holding_months", 3))
        crop = entities.crop if entities.crop in (Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO) else Crop.CARDINAL_POTATO
        future = stated.get("expected_future_price_bdt") or round(market_prices(
            crop, bd_geo.resolve_district(entities.district or "Munshiganj"), today + timedelta(days=30 * months)).grower, 1)
        tariff, handling = stated.get("storage_tariff_bdt", 8.75), stated.get("handling_cost_bdt", 0.6)
        lam = stated.get("lambda_rot", 0.02)
        # No district, as in the SFT data: the all-facility quota check, which gives the three verdicts the model learned.
        r = CIRCUIT_BREAKER.validate_arbitrage_recommendation(ArbitrageCheckInput(
            crop=crop, quantity_kg=quantity, spot_price_bdt=spot, expected_future_price_bdt=future,
            storage_tariff_bdt=tariff, handling_cost_bdt=handling, lambda_rot=lam, holding_months=months))
        values = {"production_cost_floor_bdt": r.production_cost_floor_bdt, "storage_branch_value_bdt": round(r.storage_branch_value_bdt),
                  "spot_branch_value_bdt": round(r.spot_branch_value_bdt), "delta_pi_bdt": round(r.delta_pi_bdt)}
        if version >= 5:
            values = {"inputs": _breaker_inputs(quantity, spot, future, tariff, handling, lam, months), **values}
        return "financial_circuit_breaker", values

    if entities.crop is not None and entities.offered_faria_price_bdt is not None:
        district = bd_geo.resolve_district(entities.district or "Munshiganj")
        p = market_prices(entities.crop, district, today)
        return "get_daily_commodity_spread", {
            "crop": entities.crop.value, "district": district.name, "market_date": today.isoformat(),
            "grower_price_tk_per_kg": round(p.grower), "wholesale_price_tk_per_kg": round(p.wholesale),
            "retail_price_tk_per_kg": round(p.retail)}
    return None


async def ground_prompt(prompt: str, version: int = PROMPT_VERSION) -> str:
    """The prompt as the deployed krishi-bangla model was trained to read it: the farmer's words plus the agent's tool
    result, in the prompt format `version` (PROMPT_VERSION, unless a check grounds another version's questions).

    A named haor gets the flood tool, a store-or-sell question the dPi circuit-breaker, a crop with an offer today's DAM
    spread, and anything else (or a tool that cannot answer) the top three retrieved knowledge passages.
    """
    from mcp_servers.base import ToolExecutionError
    from rag.hybrid_retriever import get_retriever

    if "<tool_result" in prompt:
        return prompt
    try:
        found = await _tool_result(prompt, version)
    except (ToolExecutionError, ValueError, KeyError):
        found = None
    if found is not None:
        return _grounded(prompt, *found)
    passages = get_retriever().search(prompt, top_k=STORAGE_PASSAGES)
    return _grounded(prompt, "crag_retrieval", [{"doc_id": c.doc_id, "title": c.title, "text": c.text} for c in passages])


def _family_split(category: str, dialect: str, instruction: str, response: str, source: str) -> Literal["train", "val", "test"]:
    """Assign a split so whole families move together; the three OOD families go to test in full."""
    if category == "market_negotiation":
        if dialect == NEGOTIATION_HOLDOUT_DIALECT:
            return "test"
        crop, district = source.split("market_prices(")[1].split(", ")[:2]
        unit = stable_unit(SPLIT_SALT, category, dialect, crop, district)  # whole (dialect, crop, district) cells
    elif category == "arbitrage_math":
        months = _MONTHS_RE.search(instruction)
        if months and int(months.group(1)) == ARBITRAGE_HOLDOUT_MONTHS:
            return "test"
        unit = stable_unit(SPLIT_SALT, category, response)  # identical math traces never straddle splits
    elif category == "flood_harvest":
        if instruction.startswith(flood_holdout_name_bn()):
            return "test"
        unit = stable_unit(SPLIT_SALT, category, response)  # identical alerts never straddle splits
    else:  # storage_qa: the response sentence is the family; one sentence never straddles splits
        unit = stable_unit(SPLIT_SALT, category, response)
    if unit < TEST_FRACTION:
        return "test"
    if unit < TEST_FRACTION + VAL_FRACTION:
        return "val"
    return "train"


@lru_cache(maxsize=2)
def build_sft_dataset(version: int = PROMPT_VERSION) -> tuple[SftExample, ...]:
    """Prompts v4 (the deployed model's data, byte-identical to its Kaggle dataset) or v5 (freely worded questions)."""
    from rag.hybrid_retriever import SemanticChunker
    from rag.knowledge_seed import KNOWLEDGE_DOCS

    rng = np.random.default_rng(SFT_SEED if version < 5 else SFT_V5_SEED)
    sentences = [(d.doc_id, d.title, topic, d.crops[0] if d.crops else "ফসল", s)
                 for d in KNOWLEDGE_DOCS for s in SemanticChunker.sentences(d.text) for topic in d.topics[:1]]
    examples: list[SftExample] = []
    for category, count in (DATASET_PLAN if version < 5 else DATASET_PLAN_V5).items():
        for i in range(count):
            if category == "market_negotiation":
                example = _negotiation(i, rng, version)
            elif category == "storage_qa":
                example = _storage_qa(i, sentences, rng, version)
            elif category == "arbitrage_math":
                example = _arbitrage(i, rng, version)
            else:
                example = _flood(i, rng, version)
            examples.append(example)
    if version >= 5:   # the builders already split v5 (its wordings depend on the split)
        return tuple(e.model_copy(update={"example_id": f"KB5-{n:05d}"}) for n, e in enumerate(examples, start=1))
    return tuple(e.model_copy(update={
        "example_id": f"KBL-{n:05d}",
        "split": _family_split(e.category, e.dialect, e.instruction, e.response, e.source),
    }) for n, e in enumerate(examples, start=1))


def subset_of(example: SftExample) -> str:
    """Which test family an example belongs to: 'iid', or the held-out family it measures."""
    if " | subset " in example.source:   # prompts v5 record it when they build the example
        return example.source.rsplit(" | subset ", 1)[1]
    if example.category == "market_negotiation" and example.dialect == NEGOTIATION_HOLDOUT_DIALECT:
        return "ood_dialect"
    if example.category == "arbitrage_math":
        months = _MONTHS_RE.search(example.instruction)
        if months and int(months.group(1)) == ARBITRAGE_HOLDOUT_MONTHS:
            return "ood_months"
    if example.category == "flood_harvest" and example.instruction.startswith(flood_holdout_name_bn()):
        return "ood_upazila"
    return "iid"


def dataset_stats(examples: tuple[SftExample, ...], version: int = PROMPT_VERSION) -> DatasetStats:
    jsonl = "\n".join(json.dumps(e.model_dump(), ensure_ascii=False, sort_keys=True) for e in examples)
    instr = [estimate_tokens(e.instruction) for e in examples]
    resp = [estimate_tokens(e.response) for e in examples]
    by_category: dict[str, int] = {}
    by_dialect: dict[str, int] = {}
    for e in examples:
        by_category[e.category] = by_category.get(e.category, 0) + 1
        by_dialect[e.dialect] = by_dialect.get(e.dialect, 0) + 1
    by_split = {"train": 0, "val": 0, "test": 0}
    for e in examples:
        by_split[e.split] += 1
    return DatasetStats(
        total_examples=len(examples), train_examples=by_split["train"], val_examples=by_split["val"],
        test_examples=by_split["test"],
        holdouts={
            "market_negotiation": f"OOD: the {NEGOTIATION_HOLDOUT_DIALECT} dialect template is fully held out in test; "
                                  "IID families are whole " + ("(dialect, crop, district)" if version < 5 else
                                                               "(crop, district, quarter)") + " cells",
            "arbitrage_math": f"OOD: holding_months == {ARBITRAGE_HOLDOUT_MONTHS} is fully held out in test",
            "flood_harvest": f"OOD: the {flood_holdout_name_bn()} haor is fully held out in test",
            "storage_qa": "split by response sentence; one sentence never straddles splits",
            **({} if version < 5 else {"wording": "OOD: wordings written separately (sft_heldout_wordings.json) fill "
                                                  f"{V5_HELDOUT_SHARE:.0%} of the in-distribution test rows and no other split"}),
        },
        by_category=by_category,
        by_dialect=by_dialect, avg_instruction_tokens=round(float(np.mean(instr)), 1), avg_response_tokens=round(float(np.mean(resp)), 1),
        total_tokens=int(sum(instr) + sum(resp)), jsonl_sha256=hashlib.sha256(jsonl.encode()).hexdigest(),
        generator=(f"edge_node.ollama_local.build_sft_dataset (deterministic, seed {SFT_SEED}, family-aware split salted "
                   f"{SPLIT_SALT}, tool-grounded prompts v4)" if version < 5 else
                   f"edge_node.ollama_local.build_sft_dataset(5) (deterministic, seed {SFT_V5_SEED}, family-aware split salted "
                   f"{SPLIT_V5_SALT}, tool-grounded prompts v5: freely worded questions)"),
    )


def lora_adapter_spec() -> LoraAdapterSpec:
    base = LOCAL_MODELS["krishi-bangla-1.5b"]
    assert base.lora_adapter is not None
    adapter_path = ADAPTER_DIR / base.lora_adapter
    present = (adapter_path / "adapter_model.safetensors").exists() or (adapter_path.with_suffix(".gguf")).exists()
    report, deployed = adapter_path / "eval_report.json", ADAPTER_DIR / "gguf_eval_report.json"
    rank, hidden, intermediate, layers, kv_dim = 16, 1536, 8960, base.n_layers, base.kv_heads * base.head_dim
    per_layer = rank * ((hidden + hidden) * 2 + (hidden + kv_dim) * 2 + (hidden + intermediate) * 3)  # q,o + k,v + gate,up,down
    stats = dataset_stats(build_sft_dataset(PROMPT_VERSION), PROMPT_VERSION)
    return LoraAdapterSpec(
        name=base.lora_adapter, base_model=base.hf_base, base_quantized_tag="qwen2.5:1.5b-instruct-q4_K_M",
        method="QLoRA (4-bit NF4 frozen base, fp16 LoRA adapters on a T4)", rank=rank, alpha=32, dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"], learning_rate=2e-4,
        epochs=3, max_seq_len=1024, effective_batch_size=16, trainable_params_m=round(per_layer * layers / 1e6, 1),
        status="adapter_present" if present else "dataset_ready_not_trained", adapter_path=str(adapter_path),
        adapter_present=present, dataset=stats,
        eval_summary=json.loads(report.read_text(encoding="utf-8")).get("summary") if present and report.exists() else None,
        deployed_eval_summary=json.loads(deployed.read_text(encoding="utf-8")).get("summary") if deployed.exists() else None,
        training_command=("export splits with training/prepare_data.py, then run training/kaggle/krishinexus_lora_kaggle.ipynb "
                          "on a Kaggle T4 (TRAINING_PLAN.md sections 4-6)"),
        # Ollama >= 0.34.2 removed LoRA adapter loading ("LoRA adapters are no longer supported"), so the adapter is
        # merged into the base and shipped as one quantized GGUF instead of an ADAPTER file.
        gguf_export_command="load the base in 4-bit NF4 as trained, dequantize(), merge with peft merge_and_unload, then "
                            "python llama.cpp/convert_hf_to_gguf.py <merged_dir> --outtype q8_0 --outfile "
                            "krishi-bangla-q8_0.gguf (section 4 of training/kaggle/krishinexus_lora_kaggle.ipynb; TRAINING_PLAN.md section 5)",
        ollama_modelfile="FROM ./krishi-bangla-q8_0.gguf\nPARAMETER temperature 0.2\n"
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
                               params_b=m.params_b, quantization=m.quantization, gguf_size_gb=m.gguf_size_gb,
                               context_tokens=m.context_tokens, role=m.role, lora_adapter=m.lora_adapter,
                               installed_in_ollama=m.ollama_tag in installed, telemetry=modelled_telemetry(m, profile))
                for m in LOCAL_MODELS.values()],
        lora_adapter=lora_adapter_spec(),
        note="Telemetry here is modelled from GGUF size, fp16 KV cache and memory bandwidth; /edge/local-inference reports "
             "measured numbers whenever a local runtime answers. Pull models with: ollama pull <ollama_tag>; load the "
             "fine-tuned one with: ollama create krishi-bangla -f backend/models/lora/Modelfile.",
    )
