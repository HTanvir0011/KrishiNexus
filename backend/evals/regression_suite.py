"""Evaluation engine: measured RAGAS-style metrics and a deterministic 100-scenario regression suite.

Every number this module reports is computed when it runs; nothing is hard-coded. Targets from the
project brief are returned alongside the measured values so the gap is visible.

RAGAS-style metrics (computed over ``RAG_EVAL_SET`` with the network blacked out for determinism):

* ``context_precision``  RAGAS rank-weighted precision@k of gold documents in the top-5 retrieval.
* ``context_recall``     share of gold documents that appear in the top-5 retrieval.
* ``faithfulness``       share of answer claims whose content words are >= 70% present in the
                         verified context the answer was built from (token-overlap support, no LLM).
* ``answer_relevancy``   share of the question's intents the answer addresses with intent evidence
                         (deterministic stand-in for RAGAS' LLM-generated-question similarity).
* ``mcp_json_schema_validity``  share of live MCP tool calls whose JSON payload re-validates against
                         the tool's published output contract.
* ``pii_redaction_recall`` / precision  over a labelled Bangladeshi PII corpus.

The regression suite generates seeded scenarios in five categories and checks each tool or guardrail
against an independently recomputed expectation (the "mathematical proof" in each case).
A deterministic rubric judge scores the rationale text of decision cases; an LLM judge is not run.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from config import now_bdt
from guardrails.pii_scrubber import PII_SCRUBBER
from mcp_servers.agri_weather_sar_mcp import NETWORK_BLACKOUT
from mcp_servers.registry import GATEWAY, SERVERS
from rag.crag_pipeline import CRAG_PIPELINE, INTENT_EVIDENCE, Intent
from schemas.mcp_models import Crop

TARGETS: dict[str, float] = {
    "faithfulness": 0.94,
    "answer_relevancy": 0.92,
    "context_precision": 0.95,
    "context_recall": 0.91,
    "mcp_json_schema_validity": 0.994,
    "pii_redaction_recall": 1.0,
}

# ---------------------------------------------------------------------------
# Labelled evaluation data
# ---------------------------------------------------------------------------


class RagEvalItem(BaseModel):
    question: str
    district: str | None
    crop: Crop | None
    gold_docs: tuple[str, ...]


RAG_EVAL_SET: tuple[RagEvalItem, ...] = (
    RagEvalItem(question="মুন্সিগঞ্জে কার্ডিনাল আলু কোল্ড স্টোরেজে কত তাপমাত্রায় রাখলে পচবে না?", district="Munshiganj",
                crop=Crop.CARDINAL_POTATO, gold_docs=("BARI-POT-STORE-01",)),
    RagEvalItem(question="potato late blight fungicide spray schedule and pre-harvest interval", district="Bogura",
                crop=Crop.CARDINAL_POTATO, gold_docs=("DAE-BLIGHT-01",)),
    RagEvalItem(question="সিন্ডিকেট ছাড়া কাঁচা মরিচ কোথায় বেচব? ফড়িয়া দাম কম দেয়", district="Bogura",
                crop=Crop.GREEN_CHILI, gold_docs=("CPD-SYND-01", "WFP-AGG-01")),
    RagEvalItem(question="haor flash flood embankment breach: when should I harvest Boro?", district="Sunamganj",
                crop=Crop.BORO_RICE, gold_docs=("FFWC-HAOR-01", "BRRI-BORO-01")),
    RagEvalItem(question="can I get a working capital loan against potatoes in cold storage warehouse receipt", district="Munshiganj",
                crop=Crop.CARDINAL_POTATO, gold_docs=("BB-WHR-01",)),
    RagEvalItem(question="ফরমালিন বা কার্বাইড দিয়ে কি ফল পাকানো যায়? কীটনাশক কতদিন আগে দেব", district=None, crop=None,
                gold_docs=("DAE-SAFE-01",)),
    RagEvalItem(question="green chili storage temperature and humidity to avoid rot", district="Jessore",
                crop=Crop.GREEN_CHILI, gold_docs=("BARI-CHILI-01",)),
    RagEvalItem(question="brinjal cold storage temperature chilling injury", district="Jessore", crop=Crop.BRINJAL,
                gold_docs=("BARI-BRINJAL-01",)),
    RagEvalItem(question="হিমাগারে কৃষকের জায়গা নেই, ব্যবসায়ীরা কোটা নিয়ে নিয়েছে, ভাড়া কত?", district="Munshiganj",
                crop=Crop.CARDINAL_POTATO, gold_docs=("BCSA-QUOTA-01",)),
    RagEvalItem(question="potato production cost versus harvest price and seasonal price rise", district="Rangpur",
                crop=Crop.CARDINAL_POTATO, gold_docs=("DAM-POT-PRICE-01",)),
    RagEvalItem(question="truck freight cost from Bogura to Dhaka and bridge toll", district="Bogura", crop=None,
                gold_docs=("DAM-TRANS-01",)),
    RagEvalItem(question="modified atmosphere packaging MAP for vegetables farmer income", district="Jessore",
                crop=Crop.BRINJAL, gold_docs=("BAU-MAP-01",)),
    RagEvalItem(question="how much post-harvest loss do traders suffer in the banana value chain", district=None, crop=None,
                gold_docs=("BAU-PHL-02",)),
    RagEvalItem(question="Diamant potato variety grading for export and storage", district="Thakurgaon",
                crop=Crop.DIAMANT_POTATO, gold_docs=("BARI-POT-VAR-01",)),
    RagEvalItem(question="cold chamber CO2 ventilation and stacking during load-shedding", district="Munshiganj",
                crop=Crop.CARDINAL_POTATO, gold_docs=("BARI-POT-STORE-02",)),
    RagEvalItem(question="বাহে, মুই কাইল আলু কোনঠে বেচমু? ফড়িয়া দাম কম দেয়", district=None, crop=None,
                gold_docs=("CPD-SYND-01",)),
    RagEvalItem(question="collateral-free agri loan interest rate for a smallholder without land title", district=None,
                crop=None, gold_docs=("AGRI-FIN-01",)),
    RagEvalItem(question="how much pineapple and mango is lost after harvest", district=None, crop=None,
                gold_docs=("BAU-PHL-02",)),
    RagEvalItem(question="cold storage rent hike: old and new BCSA tariff and total cost in Thakurgaon", district="Thakurgaon",
                crop=Crop.CARDINAL_POTATO, gold_docs=("BCSA-QUOTA-01",)),
)

# (text, [(entity_type, original value)]) — every value listed must be redacted with that type.
PII_CORPUS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("আমার NID 1992269485738, ফোন 01712345678।", (("BD_NID", "1992269485738"), ("BD_PHONE", "01712345678"))),
    ("বিকাশ 01898765432 নম্বরে টাকা পাঠান", (("MFS_WALLET", "01898765432"),)),
    ("Nagad: ০১৮১২৩৪৫৬৭৮ e den", (("MFS_WALLET", "০১৮১২৩৪৫৬৭৮"),)),
    ("Call +880 1712-345678 after 5pm", (("BD_PHONE", "+880 1712-345678"),)),
    ("smart card NID ১৯৮৫২৬৯৪৮৫৭৩৮১২৩৪ জমা দিলাম", (("BD_NID", "১৯৮৫২৬৯৪৮৫৭৩৮১২৩৪"),)),
    ("old NID 2694857381 is on the form", (("BD_NID", "2694857381"),)),
    ("Rocket 017123456789 e payment", (("MFS_WALLET", "017123456789"),)),
    ("a/c no 1234-5678-901234 Sonali Bank", (("BANK_ACCOUNT", "1234-5678-901234"),)),
    ("my number is 8801911223344", (("BD_PHONE", "8801911223344"),)),
    ("মোবাইল ০১৫৫১২৩৪৫৬৭, বিকাশ ০১৯৮৭৬৫৪৩২১", (("BD_PHONE", "০১৫৫১২৩৪৫৬৭"), ("MFS_WALLET", "০১৯৮৭৬৫৪৩২১"))),
)
PII_NEGATIVES: tuple[str, ...] = (
    "Potato Tk 15/kg, 5000 kg, 48-50F, 92-95% RH on 2026-10-22",
    "Munshiganj capacity 540,760 MT vs 1,000,738 MT output",
    "৪০০ কেজি আলু ১১ টাকা কেজি, ৯০ দিন পরে ৪৮ টাকা",
    "Truck TRK-BOG-521B64D4 escrow ESC-0D2F762CFE13 Tk 318,200",
)

# Representative argument sets for every MCP tool (validity is checked on each live response).
MCP_EVAL_CALLS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("get_daily_commodity_spread", {"crop": "Green Chili", "district": "Bogura"}),
    ("get_daily_commodity_spread", {"crop": "Boro Rice", "district": "Sunamganj"}),
    ("detect_syndicate_markup_anomaly", {"crop": "Green Chili", "upazila": "Bogura", "retail_hub": "Dhaka Karwan Bazar"}),
    ("detect_syndicate_markup_anomaly", {"crop": "Cardinal Potato", "upazila": "Tongibari", "retail_hub": "Dhaka Mirpur"}),
    ("find_optimal_selling_hub", {"crop": "Cardinal Potato", "weight_kg": 5000, "origin_district": "Munshiganj", "grade": "A"}),
    ("find_optimal_selling_hub", {"crop": "Brinjal", "weight_kg": 800, "origin_district": "Jessore", "grade": "B"}),
    ("get_historical_seasonal_curve", {"crop": "Cardinal Potato", "month_range": [2, 3, 8, 9]}),
    ("get_historical_seasonal_curve", {"crop": "Green Chili", "month_range": [12, 1, 6, 7]}),
    ("get_current_weather", {"latitude": 25.0658, "longitude": 91.395}),
    ("get_weather_by_datetime_range", {"latitude": 24.8466, "longitude": 89.3776,
                                       "start_date": "2026-04-10", "end_date": "2026-04-16"}),
    ("calculate_haor_flash_flood_risk", {"upazila": "Tahirpur", "sar_water_backscatter_db": -19.5}),
    ("calculate_haor_flash_flood_risk", {"upazila": "Itna", "sar_water_backscatter_db": -11.0}),
    ("compute_crop_vpd_stress", {"crop": "Cardinal Potato", "crop_stage": "vegetative", "temp_c": 16, "rh_pct": 94}),
    ("compute_crop_vpd_stress", {"crop": "Boro Rice", "crop_stage": "post_harvest_storage", "temp_c": 30, "rh_pct": 85}),
    ("trigger_early_harvest_window", {"cluster_id": "EVAL-SUN-01", "upazila": "Derai", "urgency_level": "HIGH"}),
    ("query_cold_storage_quota", {"district": "Munshiganj", "radius_km": 60, "tons_needed": 250}),
    ("query_cold_storage_quota", {"district": "Rangpur", "radius_km": 120, "tons_needed": 900}),
    ("get_chamber_telemetry", {"facility_id": "BCSA-MUN-01", "chamber_id": "CH-03"}),
    ("get_chamber_telemetry", {"facility_id": "BCSA-THA-02", "chamber_id": "CH-04"}),
    ("calculate_dynamic_shelf_life", {"crop": "Green Chili", "grade": "A", "transit_temp_c": 30, "rh_pct": 60}),
    ("calculate_dynamic_shelf_life", {"crop": "Cardinal Potato", "grade": "C", "transit_temp_c": 3, "rh_pct": 99}),
    ("reserve_collective_storage_slot", {"cluster_id": "EVAL-POOL-01", "facility_id": "BCSA-RAN-02", "tons": 0.5, "farmer_count": 1}),
)

# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class QuestionScore(BaseModel):
    question: str
    gold_docs: list[str]
    retrieved_docs: list[str]
    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float
    crag_verdict: str


class MetricValue(BaseModel):
    name: str
    value: float
    target: float
    meets_target: bool
    method: str
    sample_size: int


class RagasReport(BaseModel):
    generated_at: str
    duration_ms: float
    metrics: list[MetricValue]
    pii_redaction_precision: float
    per_question: list[QuestionScore]
    mcp_failures: list[str]
    pii_misses: list[str]
    notes: list[str]


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_STOP = frozenset("a an and are as at be by for from in into is it its of on or that the this to with was were can than".split())


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1}


def _claims(answer: str) -> list[str]:
    stripped = re.sub(r"\[[^\]]+\]", " ", answer)
    stripped = re.sub(r"\b(Storage|Capacity|Syndicate-free route|Direct sale|Market|[A-Z][a-z]+(?: [A-Z][a-z]+)*):\s", " ", stripped)
    return [c.strip() for c in re.split(r"(?<=[.;])\s+", stripped) if len(_content_words(c)) >= 3]


def _faithfulness(answer: str, context: str) -> float:
    claims = _claims(answer)
    if not claims:
        return 0.0
    support = _content_words(context)
    supported = sum(len(_content_words(c) & support) / len(_content_words(c)) >= 0.7 for c in claims)
    return supported / len(claims)


def _context_precision(retrieved: list[str], gold: set[str]) -> float:
    hits, score = 0, 0.0
    for k, doc in enumerate(retrieved, start=1):
        if doc in gold:
            hits += 1
            score += hits / k
    return score / max(1, min(len(gold), len(retrieved))) if hits else 0.0


def _answer_relevancy(answer: str, intents: list[Intent]) -> float:
    if not intents or intents == [Intent.GENERAL]:
        return 1.0 if answer.strip() else 0.0
    words = _content_words(answer)
    return sum(bool(INTENT_EVIDENCE[i] & words) for i in intents) / len(intents)


def _metric(name: str, value: float, method: str, n: int) -> MetricValue:
    target = TARGETS[name]
    return MetricValue(name=name, value=round(value, 4), target=target, meets_target=value >= target, method=method, sample_size=n)


async def _mcp_validity() -> tuple[int, list[str]]:
    valid, failures = 0, []
    for name, args in MCP_EVAL_CALLS:
        entry = GATEWAY.lookup(name)
        try:
            result = await GATEWAY.call_tool(name, args)
            if result.get("isError") or "structuredContent" not in result or entry is None:
                failures.append(f"{name}: isError ({result.get('content', [{}])[0].get('text', '')[:80]})")
                continue
            entry[1].output_model.model_validate(json.loads(json.dumps(result["structuredContent"])))
            json.loads(result["content"][0]["text"])
            valid += 1
        except Exception as exc:  # any protocol or contract violation counts as invalid
            failures.append(f"{name}: {type(exc).__name__}: {str(exc)[:120]}")
    return valid, failures


def _pii_scores() -> tuple[float, float, int, list[str]]:
    expected_total, hits, false_positives, misses = 0, 0, 0, []
    for text, expected in PII_CORPUS:
        found = [(e.entity_type, text[e.start:e.end]) for e in PII_SCRUBBER.scrub(text).entities]
        for item in expected:
            expected_total += 1
            if item in found:
                hits += 1
            else:
                misses.append(f"{item[0]} '{item[1]}' in '{text}'")
        false_positives += sum(1 for f in found if f not in expected)
    false_positives += sum(len(PII_SCRUBBER.scrub(t).entities) for t in PII_NEGATIVES)
    recall = hits / expected_total
    precision = hits / max(1, hits + false_positives)
    return recall, precision, expected_total, misses


class EvaluationEngine:
    def __init__(self) -> None:
        self._cached: tuple[float, RagasReport] | None = None

    async def get_ragas_metrics(self, max_age_s: float = 600.0) -> RagasReport:
        if self._cached and time.monotonic() - self._cached[0] < max_age_s:
            return self._cached[1]
        started = time.perf_counter()
        blackout = NETWORK_BLACKOUT.set(True)
        try:
            per_question: list[QuestionScore] = []
            for item in RAG_EVAL_SET:
                result = await CRAG_PIPELINE.run(item.question, item.district, item.crop, top_k=5)
                retrieved = list(dict.fromkeys(c.doc_id for c in result.retrieval[:5]))
                gold = set(item.gold_docs)
                context = " ".join(s.text for s in result.verified_context)
                per_question.append(QuestionScore(
                    question=item.question, gold_docs=list(item.gold_docs), retrieved_docs=retrieved,
                    context_precision=round(_context_precision(retrieved, gold), 4),
                    context_recall=round(len(gold & set(retrieved)) / len(gold), 4),
                    faithfulness=round(_faithfulness(result.answer_summary, context), 4),
                    answer_relevancy=round(_answer_relevancy(result.answer_summary, result.rewrite.intents), 4),
                    crag_verdict=result.crag.verdict,
                ))
            valid, mcp_failures = await _mcp_validity()
        finally:
            NETWORK_BLACKOUT.reset(blackout)
        recall, precision, pii_n, misses = _pii_scores()
        n = len(per_question)

        def mean(attr: str) -> float:
            return float(np.mean([getattr(q, attr) for q in per_question]))

        report = RagasReport(
            generated_at=now_bdt().isoformat(),
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            metrics=[
                _metric("faithfulness", mean("faithfulness"), "answer claims with >=70% content-word support in the verified context", n),
                _metric("answer_relevancy", mean("answer_relevancy"), "share of detected question intents the answer addresses", n),
                _metric("context_precision", mean("context_precision"), "RAGAS rank-weighted precision of gold docs in top-5", n),
                _metric("context_recall", mean("context_recall"), "share of gold docs retrieved in top-5", n),
                _metric("mcp_json_schema_validity", valid / len(MCP_EVAL_CALLS), "live tools/call payloads re-validated against output contracts",
                        len(MCP_EVAL_CALLS)),
                _metric("pii_redaction_recall", recall, "labelled BD NID / phone / MFS wallet / bank entities redacted with the right type", pii_n),
            ],
            pii_redaction_precision=round(precision, 4),
            per_question=per_question,
            mcp_failures=mcp_failures,
            pii_misses=misses,
            notes=[
                "Computed live on this deployment's seed knowledge base with the network blacked out (climatology weather).",
                "Faithfulness and relevancy use deterministic token/intent checks, not an LLM judge; treat them as lower-fidelity than RAGAS proper.",
                "Answers are extractive (assembled from verified context sentences and tool outputs), so faithfulness is high by construction.",
                f"Evaluation set: {n} labelled questions (Bangla, Banglish, dialect, English), {len(MCP_EVAL_CALLS)} MCP calls, {pii_n} PII entities.",
            ],
        )
        self._cached = (time.monotonic(), report)
        return report

    async def run_regression_suite(self, sample_size: int = 20, categories: list[str] | None = None) -> RegressionReport:
        """Run ``sample_size`` seeded scenarios per category (5 x 20 = the 100-case benchmark)."""
        started_at = now_bdt().isoformat()
        started = time.perf_counter()
        selected = [c for c in CATEGORY_RUNNERS if categories is None or c in categories]
        cases: list[RegressionCase] = []
        summaries: list[CategorySummary] = []
        for index, key in enumerate(selected):
            title, runner = CATEGORY_RUNNERS[key]
            rng = np.random.default_rng(SUITE_SEED + index)
            category_cases: list[RegressionCase] = []
            for i in range(sample_size):
                case_started = time.perf_counter()
                try:
                    case = await runner(i, rng)
                except Exception as exc:  # a crash is a failed case, never a crashed suite
                    case = RegressionCase(case_id="", category=key, title="runner error", inputs={}, expected={},
                                          actual={"error": f"{type(exc).__name__}: {exc}"}, passed=False, proof="exception raised")
                case = case.model_copy(update={"case_id": f"{key.upper()[:4]}-{i + 1:03d}", "category": key,
                                               "latency_ms": round((time.perf_counter() - case_started) * 1000, 2)})
                category_cases.append(case)
            passed = sum(c.passed for c in category_cases)
            summaries.append(CategorySummary(
                category=key, title=title, total=len(category_cases), passed=passed,
                pass_rate_pct=round(100 * passed / max(1, len(category_cases)), 1),
                avg_latency_ms=round(float(np.mean([c.latency_ms for c in category_cases])), 2) if category_cases else 0.0,
            ))
            cases += category_cases
        passed_total = sum(c.passed for c in cases)
        return RegressionReport(
            suite="KrishiNexus deterministic regression suite", seed=SUITE_SEED, sample_size_per_category=sample_size,
            total_cases=len(cases), passed=passed_total, failed=len(cases) - passed_total,
            pass_rate_pct=round(100 * passed_total / max(1, len(cases)), 1), started_at=started_at,
            duration_ms=round((time.perf_counter() - started) * 1000, 1), categories=summaries, cases=cases,
        )


# ---------------------------------------------------------------------------
# Regression suite
# ---------------------------------------------------------------------------

SUITE_SEED = 20_261_226


class JudgeScore(BaseModel):
    judge: str = "deterministic rubric judge (no LLM call)"
    criteria: dict[str, bool]
    score: float = Field(ge=0, le=1)


class RegressionCase(BaseModel):
    case_id: str
    category: str
    title: str
    inputs: dict[str, Any]
    expected: dict[str, Any]
    actual: dict[str, Any]
    passed: bool
    latency_ms: float = 0.0
    proof: str
    judge: JudgeScore | None = None


class CategorySummary(BaseModel):
    category: str
    title: str
    total: int
    passed: int
    pass_rate_pct: float
    avg_latency_ms: float


class RegressionReport(BaseModel):
    suite: str
    seed: int
    sample_size_per_category: int
    total_cases: int
    passed: int
    failed: int
    pass_rate_pct: float
    started_at: str
    duration_ms: float
    categories: list[CategorySummary]
    cases: list[RegressionCase]


class RegressionRequest(BaseModel):
    sample_size: int = Field(default=20, ge=1, le=20, description="Cases per category (20 -> 100-case benchmark).")
    categories: list[str] | None = Field(default=None, description="Subset of category keys; omit for all five.")


def _judge(text: str, criteria: dict[str, str]) -> JudgeScore:
    lowered = text.lower()
    results = {name: needle.lower() in lowered for name, needle in criteria.items()}
    return JudgeScore(criteria=results, score=round(sum(results.values()) / len(results), 3))


def _pick(rng: np.random.Generator, items: list[Any] | tuple[Any, ...]) -> Any:
    return items[int(rng.integers(0, len(items)))]


# --- Category 1: distress spot-sale circuit-breaker --------------------------------------------

DISTRESS_SPOT_RANGE_TK = (5.0, 14.0)  # harvest distress farm-gate price vs the Tk 15-20/kg production cost


async def _case_circuit_breaker(i: int, rng: np.random.Generator) -> RegressionCase:
    from guardrails.financial_circuit import CIRCUIT_BREAKER, ArbitrageCheckInput
    from mcp_servers.coldchain_iot_mcp import FACILITIES, open_farmer_quota_mt, power_state
    from schemas.mcp_models import PowerSource

    control = i % 4 == 3  # every fourth case is a control priced above the floor
    crop = Crop.CARDINAL_POTATO if i % 2 == 0 else Crop.DIAMANT_POTATO
    q = int(rng.integers(4, 60)) * 100
    spot = round(float(rng.uniform(15.5, 40.0) if control else rng.uniform(*DISTRESS_SPOT_RANGE_TK)), 2)
    future = round(float(rng.uniform(35.0, 85.0)), 2)
    tariff = float(_pick(rng, [8.0, 8.25, 8.5, 8.75, 9.0, 9.25, 9.5]))
    handling, lam = round(float(rng.uniform(0.4, 0.8)), 2), round(float(rng.uniform(0.012, 0.09)), 4)
    c_ts = round(q * float(rng.uniform(0.3, 1.5)), 2)
    result = CIRCUIT_BREAKER.validate_arbitrage_recommendation(ArbitrageCheckInput(
        crop=crop, quantity_kg=q, spot_price_bdt=spot, expected_future_price_bdt=future, storage_tariff_bdt=tariff,
        handling_cost_bdt=handling, lambda_rot=lam, transport_to_storage_bdt=c_ts))

    storage = q * (1 - lam) * future - q * (tariff + handling) - c_ts
    dpi = storage - q * spot
    at = now_bdt()
    open_t = sum(open_farmer_quota_mt(f) for f in FACILITIES.values() if power_state(f, None, at).source is not PowerSource.OUTAGE)
    expected_block = spot < 15.0 and dpi > 0 and open_t * 1000 >= q
    passed = abs(dpi - result.delta_pi_bdt) < 0.01 and result.circuit_tripped == expected_block
    rationale = " ".join(result.rationale)
    criteria = {"cites_delta_pi": "dPi", "states_break_even": "breaks even"}
    if spot < 15.0 and dpi > 0:
        criteria["cites_cost_floor"] = "floor"
    if expected_block:
        criteria["offers_receipt_credit"] = "working capital"
    return RegressionCase(
        case_id="", category="", title=f"{'Control' if control else 'Distress'} {crop.value} at Tk {spot}/kg (Q={q} kg)",
        inputs={"crop": crop.value, "quantity_kg": q, "spot": spot, "expected_future": future, "tariff": tariff,
                "handling": handling, "lambda_rot": lam, "transport_to_storage": c_ts},
        expected={"delta_pi_bdt": round(dpi, 2), "circuit_tripped": expected_block},
        actual={"delta_pi_bdt": result.delta_pi_bdt, "circuit_tripped": result.circuit_tripped, "verdict": result.verdict.value},
        passed=passed,
        proof=f"dPi = {q}(1-{lam})*{future} - {q}({tariff}+{handling}) - {c_ts} - {q}*{spot} = {dpi:,.2f}; "
              f"block = spot<15 ({spot < 15}) and dPi>0 ({dpi > 0}) and quota {open_t:,.0f} t >= {q / 1000:g} t",
        judge=_judge(rationale, criteria),
    )


# --- Category 2: syndicate markup and pooled-truck economics ------------------------------------

_TOLLS = {"Bangabandhu (Jamuna) Bridge": 1800.0, "Padma Multipurpose Bridge": 2800.0, "Lalon Shah (Paksey) Bridge": 480.0}


async def _case_syndicate(i: int, rng: np.random.Generator) -> RegressionCase:
    from mcp_servers.dam_market_mcp import detect_syndicate_markup_anomaly, find_optimal_selling_hub
    from schemas.mcp_models import DetectSyndicateMarkupAnomalyInput, FindOptimalSellingHubInput, Grade

    crops = [Crop.GREEN_CHILI, Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO, Crop.BRINJAL, Crop.BORO_RICE]
    if i % 2 == 0:
        crop = crops[(i // 2) % len(crops)]
        upazila = _pick(rng, ["Shibganj", "Sariakandi", "Mithapukur", "Tongibari", "Jhikargacha", "Badarganj", "Itna", "Bogura"])
        hub = _pick(rng, ["Dhaka Karwan Bazar", "Dhaka Mirpur", "Sylhet"])
        r = await detect_syndicate_markup_anomaly(DetectSyndicateMarkupAnomalyInput(crop=crop, upazila=upazila, retail_hub=hub))
        markup = (r.retail_price_tk_per_kg - r.grower_price_tk_per_kg) / r.grower_price_tk_per_kg * 100
        tier_sum = sum(t.gross_margin_tk_per_kg for t in r.tier_breakdown)
        margin = r.retail_price_tk_per_kg - r.grower_price_tk_per_kg
        primary = r.wholesale_price_tk_per_kg > r.grower_price_tk_per_kg
        cost_lines = sum(line.tk_per_kg for line in r.bepari_marketing_cost_breakdown)
        expected_take = round(0.6235 * r.bepari_marketing_cost_tk_per_kg, 2)
        passed = (abs(markup - r.markup_pct) < 0.05 and r.is_anomaly == (markup > 40.0) and abs(tier_sum - margin) < 0.06
                  and r.aratdar_share_of_bepari_marketing_cost_pct == (62.35 if primary else 0.0)
                  and abs(r.aratdar_take_tk_per_kg - expected_take) < 0.02
                  and abs(cost_lines - r.bepari_marketing_cost_tk_per_kg) < 0.06
                  and r.aratdar_grading_spend_tk_per_kg == 0.0)
        return RegressionCase(
            case_id="", category="", title=f"Markup anomaly: {crop.value} {upazila} -> {hub}",
            inputs={"crop": crop.value, "upazila": upazila, "retail_hub": hub},
            expected={"markup_pct": round(markup, 2), "is_anomaly": markup > 40.0, "tier_margin_sum": round(margin, 2),
                      "aratdar_share_of_bepari_cost_pct": 62.35 if primary else 0.0, "aratdar_take_tk": expected_take,
                      "bepari_cost_lines_sum_tk": r.bepari_marketing_cost_tk_per_kg, "aratdar_grading_tk": 0.0},
            actual={"markup_pct": r.markup_pct, "is_anomaly": r.is_anomaly, "tier_margin_sum": round(tier_sum, 2),
                    "aratdar_share_of_bepari_cost_pct": r.aratdar_share_of_bepari_marketing_cost_pct,
                    "aratdar_take_tk": r.aratdar_take_tk_per_kg, "bepari_cost_lines_sum_tk": round(cost_lines, 2),
                    "aratdar_grading_tk": r.aratdar_grading_spend_tk_per_kg, "severity": r.severity.value},
            passed=passed,
            proof=f"({r.retail_price_tk_per_kg} - {r.grower_price_tk_per_kg}) / {r.grower_price_tk_per_kg} = {markup:.2f}% "
                  f"{'>' if markup > 40 else '<='} 40%; 5 tiers sum to Tk {tier_sum:.2f} of Tk {margin:.2f}",
            judge=_judge(r.narrative, {"quotes_markup": "% markup", "names_aratdar": "Aratdar", "pooled_truck": "5-ton"}),
        )
    crop = _pick(rng, [Crop.CARDINAL_POTATO, Crop.GREEN_CHILI, Crop.BRINJAL])
    origin = _pick(rng, ["Bogura", "Rangpur", "Munshiganj", "Jessore", "Thakurgaon"])
    weight = float(int(rng.integers(5, 51)) * 100)
    r = await find_optimal_selling_hub(FindOptimalSellingHubInput(crop=crop, weight_kg=weight, origin_district=origin, grade=Grade.A))
    best = r.best_option
    if best is None:
        return RegressionCase(case_id="", category="", title=f"Pooled truck {crop.value} from {origin}", inputs={}, expected={"best": "any"},
                              actual={"best": None}, passed=False, proof="no hub returned")
    trip = best.road_distance_km * 68.0 + 1500.0 + sum(_TOLLS[b] for b in best.bridge_crossings)
    per_kg = trip / 5000 + 0.10
    loss = min(40.0, best.transit_loss_pct)
    hub_net = best.hub_price_tk_per_kg * (1 - loss / 100) - best.fees_tk_per_kg - best.transport_cost_tk_per_kg
    passed = abs(trip - best.truck_trip_cost_tk) <= 4.0 and abs(per_kg - best.transport_cost_tk_per_kg) <= 0.011 and (
        best.capacity_limited or abs(hub_net - best.net_payout_tk_per_kg) <= 0.03)
    return RegressionCase(
        case_id="", category="", title=f"Pooled 5-ton truck: {weight:g} kg {crop.value} from {origin} -> {best.hub_name}",
        inputs={"crop": crop.value, "weight_kg": weight, "origin_district": origin, "grade": "A"},
        expected={"trip_cost_tk": round(trip, 2), "freight_tk_per_kg": round(per_kg, 3), "net_tk_per_kg": round(hub_net, 2)},
        actual={"trip_cost_tk": best.truck_trip_cost_tk, "freight_tk_per_kg": best.transport_cost_tk_per_kg,
                "net_tk_per_kg": best.net_payout_tk_per_kg, "bridges": best.bridge_crossings},
        passed=passed,
        proof=f"trip = {best.road_distance_km} km x Tk 68 + Tk 1,500 + tolls {best.bridge_crossings} = Tk {trip:,.1f}; "
              f"per kg = trip/5000 + 0.10 = Tk {per_kg:.3f}",
    )


# --- Category 3: cold-chamber telemetry, lambda_rot and rerouting -------------------------------


async def _case_cold_chamber(i: int, rng: np.random.Generator) -> RegressionCase:
    from mcp_servers.anomaly_state import ANOMALIES
    from mcp_servers.coldchain_iot_mcp import FACILITIES, calculate_dynamic_shelf_life, get_chamber_telemetry, query_cold_storage_quota
    from schemas.mcp_models import CalculateDynamicShelfLifeInput, GetChamberTelemetryInput, Grade, QueryColdStorageQuotaInput

    facility = list(FACILITIES.values())[i % len(FACILITIES)]
    chamber = f"CH-{int(rng.integers(1, facility.chambers + 1)):02d}"
    elapsed = int(rng.integers(60, 601))
    anomaly = ANOMALIES.inject("cold_chamber_power_cut", f"{facility.facility_id}/ALL", {
        "facility_id": facility.facility_id, "chamber_id": None, "generator_failed": True, "elapsed_minutes": elapsed}, 10)
    try:
        t = await get_chamber_telemetry(GetChamberTelemetryInput(facility_id=facility.facility_id, chamber_id=chamber))
        base = await calculate_dynamic_shelf_life(CalculateDynamicShelfLifeInput(crop=Crop.CARDINAL_POTATO, grade=Grade.A,
                                                                                   transit_temp_c=9.5, rh_pct=93.0))
        drift = await calculate_dynamic_shelf_life(CalculateDynamicShelfLifeInput(
            crop=Crop.CARDINAL_POTATO, grade=Grade.A, transit_temp_c=t.temperature_c, rh_pct=min(100.0, t.relative_humidity_pct)))
        quota = await query_cold_storage_quota(QueryColdStorageQuotaInput(district=facility.district, radius_km=60, tons_needed=1))
    finally:
        ANOMALIES.clear(anomaly.anomaly_id)
    out_of_band = t.temperature_f > 50.0 or t.relative_humidity_pct > 95.0
    allocated = [leg.facility_id for leg in quota.recommended_allocation]
    rerouted = facility.facility_id not in allocated and bool(allocated)
    passed = t.power_source.value == "OUTAGE" and out_of_band and drift.lambda_rot > base.lambda_rot and rerouted
    return RegressionCase(
        case_id="", category="", title=f"Power cut {facility.facility_id}/{chamber}, {elapsed} min outage",
        inputs={"facility_id": facility.facility_id, "chamber_id": chamber, "outage_minutes": elapsed},
        expected={"power": "OUTAGE", "out_of_48_50F_or_92_95RH": True, "lambda_rot_increases": True, "rerouted": True},
        actual={"power": t.power_source.value, "temperature_f": t.temperature_f, "rh_pct": t.relative_humidity_pct,
                "lambda_rot": [base.lambda_rot, drift.lambda_rot], "allocated_to": allocated},
        passed=passed,
        proof=f"{t.temperature_f:.1f} F / {t.relative_humidity_pct:.1f}% RH after {elapsed} min -> lambda_rot "
              f"{base.lambda_rot} -> {drift.lambda_rot}; smallholder allocation rerouted to {allocated[:2]}",
    )


# --- Category 4: Sentinel-1 SAR flood shield and parametric credit ------------------------------

_BENCHMARK = {"Sunamganj": 65.0, "Kishoreganj": 44.0, "Netrokona": 21.0}


async def _case_flood(i: int, rng: np.random.Generator) -> RegressionCase:
    from agents.climate_credit_agent import run as climate_run
    from agents.state import KrishiAgentState
    from agents.tracing import TraceBroadcaster, TraceRecorder
    from mcp_servers import bd_geo
    from mcp_servers.agri_weather_sar_mcp import HAOR_DISTRICTS, HAOR_UPAZILAS, calculate_haor_flash_flood_risk
    from mcp_servers.anomaly_state import ANOMALIES
    from schemas.mcp_models import CalculateHaorFlashFloodRiskInput

    name = list(HAOR_UPAZILAS)[i % len(HAOR_UPAZILAS)]
    district = bd_geo.resolve_upazila(name).district
    rain, sar = round(float(rng.uniform(60, 420)), 1), round(float(rng.uniform(-23.0, -8.0)), 2)
    anomaly = ANOMALIES.inject("haor_flash_flood", f"{district}/{name}", {
        "upazila": name, "district": district, "upstream_rainfall_72h_mm": rain, "sar_water_backscatter_db": sar, "scenario_month": 4}, 10)
    blackout = NETWORK_BLACKOUT.set(True)
    try:
        r = await calculate_haor_flash_flood_risk(CalculateHaorFlashFloodRiskInput(upazila=name, sar_water_backscatter_db=sar))
        credit = None
        if i % 5 == 4:
            state = KrishiAgentState(session_id=f"EVAL-{i}", farmer_id=f"EVAL-FLD-{i:03d}", raw_query_bangla="eval", district=district,
                                     upazila=name, crop=Crop.BORO_RICE, quantity_kg=2000, sar_backscatter_override_db=sar)
            update = await climate_run(state, TraceRecorder(state.session_id, TraceBroadcaster()))
            credit = update["climate_credit_report"]
    finally:
        NETWORK_BLACKOUT.reset(blackout)
        ANOMALIES.clear(anomaly.anomaly_id)

    profile, haor = HAOR_UPAZILAS[name], HAOR_DISTRICTS[district]
    water = 1 / (1 + math.exp((sar + 16.5) / 1.6))
    z = -5.0 + 3.2 * r.upstream_rainfall_72h_mm / haor.trigger_rainfall_72h_mm + 2.6 * water + 2.0 * profile.embankment_vulnerability + 1.2
    p = 100 / (1 + math.exp(-z))
    alert = "RED" if p >= 70 else "ORANGE" if p >= 45 else "YELLOW" if p >= 20 else "GREEN"
    passed = (r.upstream_rainfall_72h_mm >= rain and abs(p - r.embankment_breach_probability_pct) < 0.02
              and r.alert_level.value == alert and r.historical_boro_loss_benchmark_pct == _BENCHMARK[district]
              and abs(r.expected_boro_loss_pct - _BENCHMARK[district] * p / 100) < 0.02)
    actual: dict[str, Any] = {"breach_pct": r.embankment_breach_probability_pct, "alert": r.alert_level.value,
                              "benchmark_pct": r.historical_boro_loss_benchmark_pct, "expected_loss_pct": r.expected_boro_loss_pct}
    expected: dict[str, Any] = {"breach_pct": round(p, 2), "alert": alert, "benchmark_pct": _BENCHMARK[district],
                                "expected_loss_pct": round(_BENCHMARK[district] * p / 100, 2)}
    proof = (f"z = -5 + 3.2*{r.upstream_rainfall_72h_mm}/{haor.trigger_rainfall_72h_mm:g} + 2.6*{water:.3f} + "
             f"2*{profile.embankment_vulnerability} + 1.2*1.0 -> p = {p:.2f}% ({alert})")
    if credit is not None:
        climate_points = next(c.points for c in credit.score_components if c.name.startswith("Climate"))
        expected_points = round((1 - (credit.flood_breach_probability_pct or 0) / 100) * 120, 1)
        harvest_expected = credit.flood_alert_level is not None and credit.flood_alert_level.value in ("ORANGE", "RED")
        credit_ok = (300 <= credit.credit_score <= 850 and abs(climate_points - expected_points) < 0.11
                     and (credit.early_harvest_dispatch_id is not None) == harvest_expected
                     and credit.loan_eligible == (credit.loan_amount_tk > 0) and (not credit.loan_eligible or credit.credit_score >= 650))
        passed = passed and credit_ok
        actual |= {"credit_score": credit.credit_score, "climate_points": climate_points, "harvest_dispatch": credit.early_harvest_dispatch_id}
        expected |= {"climate_points": expected_points, "harvest_dispatch_iff_orange_or_red": harvest_expected}
        proof += f"; credit climate points = (1 - p) x 120 = {expected_points}"
    return RegressionCase(case_id="", category="", title=f"SAR flood {name} ({district}): {rain} mm, {sar} dB",
                          inputs={"upazila": name, "upstream_rain_72h_mm": rain, "sar_db": sar, "scenario_month": 4},
                          expected=expected, actual=actual, passed=passed, proof=proof)


# --- Category 5: PII redaction and DAE chemical guardrails --------------------------------------

_BN = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _digits(rng: np.random.Generator, n: int) -> str:
    return "".join(str(int(d)) for d in rng.integers(0, 10, n))


async def _case_guardrails(i: int, rng: np.random.Generator) -> RegressionCase:
    from guardrails.financial_circuit import CIRCUIT_BREAKER, DosageCheckInput

    if i % 2 == 0:
        kind = int(rng.integers(0, 3))
        nid = (str(int(rng.integers(1, 10))) + _digits(rng, 9) if kind == 0 else
               str(int(rng.integers(1, 8))) + _digits(rng, 12) if kind == 1 else
               str(int(rng.integers(1960, 2006))) + _digits(rng, 13))
        phone = "01" + str(int(rng.integers(3, 10))) + _digits(rng, 8)
        phone_text = phone if i % 4 == 0 else f"+880 {phone[1:5]}-{phone[5:]}"
        wallet = "01" + str(int(rng.integers(3, 10))) + _digits(rng, 8) + ("" if i % 3 else _digits(rng, 1))
        keyword = _pick(rng, ["বিকাশ", "নগদ", "bKash", "Nagad", "রকেট"])
        if i % 3 == 0:
            nid, wallet = nid.translate(_BN), wallet.translate(_BN)
        text = f"আমার এনআইডি {nid}, মোবাইল {phone_text}, {keyword} {wallet} - ফড়িয়া ১১ টাকা দিচ্ছে"
        scrub = PII_SCRUBBER.scrub(text)
        found = {(e.entity_type, text[e.start:e.end]) for e in scrub.entities}
        expected = {("BD_NID", nid), ("BD_PHONE", phone_text), ("MFS_WALLET", wallet)}
        leaked = [v for _, v in expected if v in scrub.anonymized_text]
        passed = expected <= found and not leaked
        return RegressionCase(
            case_id="", category="", title=f"PII: {len(nid)}-digit NID + phone + {keyword} wallet",
            inputs={"text": text}, expected={"redacted": sorted(t for t, _ in expected), "leaks": 0},
            actual={"redacted": sorted(t for t, _ in found), "leaks": len(leaked), "anonymized": scrub.anonymized_text},
            passed=passed, proof=f"{len(expected & found)}/{len(expected)} entities redacted with correct type; raw values absent from output",
        )
    scenarios = [
        ("Formalin", Crop.BRINJAL, 1.0, "ml/L", 5, "BLOCK_BANNED_SUBSTANCE"),
        ("calcium carbide", Crop.GREEN_CHILI, 1.0, "g/L", 5, "BLOCK_BANNED_SUBSTANCE"),
        ("ফরমালিন", Crop.CARDINAL_POTATO, 2.0, "ml/L", 20, "BLOCK_BANNED_SUBSTANCE"),
        ("lead chromate", Crop.CARDINAL_POTATO, 1.0, "g/L", 20, "BLOCK_BANNED_SUBSTANCE"),
        ("Dithane M-45", Crop.CARDINAL_POTATO, round(float(rng.uniform(2.3, 4.0)), 2), "g/L", 20, "BLOCK_OVERDOSE"),
        ("Ridomil Gold", Crop.DIAMANT_POTATO, 2.0, "g/L", int(rng.integers(0, 7)), "BLOCK_PHI_VIOLATION"),
        ("Glyphosate 41SL", Crop.BRINJAL, 1.0, "ml/L", 30, "BLOCK_NOT_REGISTERED"),
        ("Trooper 75WP", Crop.BORO_RICE, 0.8, "g/L", 30, "APPROVED"),
        ("Bavistin", Crop.BORO_RICE, 1.0, "g/L", 30, "BLOCK_NOT_REGISTERED_FOR_CROP"),
        ("Proclaim", Crop.BRINJAL, 1.0, "g/L", int(rng.integers(3, 15)), "APPROVED"),
    ]
    chemical, crop, dose, unit, days, expected_verdict = scenarios[(i // 2) % len(scenarios)]
    r = CIRCUIT_BREAKER.validate_agronomic_dosage(DosageCheckInput(chemical=chemical, crop=crop, dose=dose, dose_unit=unit,
                                                                   days_until_harvest=days))
    return RegressionCase(
        case_id="", category="", title=f"Chemical: {chemical} on {crop.value} ({dose:g} {unit}, harvest in {days} d)",
        inputs={"chemical": chemical, "crop": crop.value, "dose": dose, "unit": unit, "days_until_harvest": days},
        expected={"verdict": expected_verdict}, actual={"verdict": r.verdict.value, "resolved": r.resolved_name},
        passed=r.verdict.value == expected_verdict, proof=r.rationale[0],
    )


CATEGORY_RUNNERS: dict[str, tuple[str, Callable[[int, np.random.Generator], Awaitable[RegressionCase]]]] = {
    "distress_circuit_breaker": ("Distress spot-sale circuit-breaker", _case_circuit_breaker),
    "syndicate_markup": ("Syndicate markup anomaly & pooled-truck economics", _case_syndicate),
    "cold_chamber_rot": ("Cold-chamber telemetry, lambda_rot & rerouting", _case_cold_chamber),
    "sar_flood_shield": ("72-hour Sentinel-1 SAR flood shield & parametric credit", _case_flood),
    "pii_chemical_guardrails": ("Presidio-style PII & DAE chemical guardrails", _case_guardrails),
}

EVALUATION_ENGINE = EvaluationEngine()
