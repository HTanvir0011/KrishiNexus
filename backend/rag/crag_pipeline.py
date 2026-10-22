"""HyDE Bangla-dialect query rewriting + Corrective RAG (CRAG) over hybrid retrieval and GraphRAG.

Pipeline: PII scrub -> HyDE dialect rewrite -> hybrid BM25+vector retrieval (dense side embeds the
hypothetical document) -> BGE-style rerank -> GraphRAG multi-hop facts -> CRAG grading. When CRAG
confidence is below 0.70 the pipeline rewrites the query for the uncovered intents, re-retrieves,
and augments with live MCP tool results; live-data intents (price, selling channel) are always
augmented when the district is known. Retained passages are decomposed into relevant sentence
strips (knowledge refinement) and recomposed into the verified context.
"""

from __future__ import annotations

import re
import time
from enum import StrEnum

from pydantic import BaseModel, Field

from config import MODEL_ROUTER, RoutingDecision, TaskType
from guardrails.pii_scrubber import PII_SCRUBBER
from mcp_servers import bd_geo
from mcp_servers.agri_weather_sar_mcp import compute_crop_vpd_stress, get_current_weather
from mcp_servers.base import ToolExecutionError
from mcp_servers.coldchain_iot_mcp import DISTRICT_STORAGE_STATS, query_cold_storage_quota
from mcp_servers.dam_market_mcp import find_optimal_selling_hub, get_daily_commodity_spread
from optimization.token_compressor import TOKEN_OPTIMIZER, estimate_tokens
from rag.graph_rag import GraphTraversalResult, get_graph
from rag.hybrid_retriever import RetrievedChunk, get_retriever
from rag.knowledge_seed import KNOWLEDGE_DOCS
from rag.lexicon import concepts_in, detect_crop, detect_dialect, detect_district, normalize_dialect
from schemas.mcp_models import (
    ComputeCropVpdStressInput,
    Crop,
    CropStage,
    FindOptimalSellingHubInput,
    GetCurrentWeatherInput,
    GetDailyCommoditySpreadInput,
    Grade,
    QueryColdStorageQuotaInput,
)

CRAG_THRESHOLD = 0.70
AMBIGUOUS_FLOOR = 0.45
# Crops each seed document applies to; a document with no crops applies to all.
DOC_CROPS: dict[str, tuple[str, ...]] = {
    doc.doc_id: doc.crops or tuple(c.value for c in Crop) for doc in KNOWLEDGE_DOCS
}


class Intent(StrEnum):
    STORAGE_CONDITIONS = "STORAGE_CONDITIONS"
    STORAGE_ACCESS = "STORAGE_ACCESS"
    SELLING_CHANNEL = "SELLING_CHANNEL"
    PRICE = "PRICE"
    DISEASE = "DISEASE"
    PESTICIDE_SAFETY = "PESTICIDE_SAFETY"
    FLOOD = "FLOOD"
    HARVEST = "HARVEST"
    CREDIT = "CREDIT"
    TRANSPORT = "TRANSPORT"
    GENERAL = "GENERAL"


# "cold storage" names a place, so on its own it does not make a question about storage conditions:
# a loan against stored potatoes or the rent of a chamber must not retrieve the temperature protocol.
INTENT_TRIGGERS: dict[Intent, frozenset[str]] = {
    Intent.STORAGE_CONDITIONS: frozenset({"temperature", "humidity", "store", "rot", "spoilage", "cooling", "ventilation",
                                          "chilling", "curing"}),
    Intent.STORAGE_ACCESS: frozenset({"quota", "tariff", "fee", "rent", "hike", "cost", "space", "capacity", "booking", "bcsa"}),
    Intent.SELLING_CHANNEL: frozenset({"sell", "market", "syndicate", "intermediary", "faria", "aratdar", "arat", "paiker", "bepari", "middleman", "haat"}),
    Intent.PRICE: frozenset({"price"}),
    Intent.DISEASE: frozenset({"blight", "disease", "fungicide", "late"}),
    Intent.PESTICIDE_SAFETY: frozenset({"pesticide", "formalin", "calcium", "carbide"}),
    Intent.FLOOD: frozenset({"flood", "embankment", "rain", "storm", "flash"}),
    Intent.HARVEST: frozenset({"harvest"}),
    Intent.CREDIT: frozenset({"credit", "loan", "lend", "collateral"}),
    Intent.TRANSPORT: frozenset({"transport", "truck"}),
}
# Intents whose triggers only count when the question is about cold storage (truck "rent" is transport).
INTENT_CONTEXT: dict[Intent, frozenset[str]] = {
    Intent.STORAGE_ACCESS: frozenset({"cold", "storage", "bcsa"}),
}
# "pre-harvest interval" and "post-harvest loss" are not questions about when to harvest.
_HARVEST_COMPOUND = re.compile(r"\b(?:pre|post)[- ]harvest\b|\bafter harvest\b", re.IGNORECASE)
INTENT_EVIDENCE: dict[Intent, frozenset[str]] = {
    Intent.STORAGE_CONDITIONS: frozenset({"cold", "storage", "temperature", "humidity", "rot", "curing", "ventilate", "stored"}),
    Intent.STORAGE_ACCESS: frozenset({"quota", "tariff", "capacity", "traders", "owners", "smallholders", "bcsa", "space"}),
    Intent.SELLING_CHANNEL: frozenset({"syndicate", "faria", "bepari", "aratdar", "arat", "arats", "wholesale", "retail", "aggregation", "collective", "pooled", "bypass"}),
    Intent.PRICE: frozenset({"price", "prices", "tk", "markup", "cost", "seasonal"}),
    Intent.DISEASE: frozenset({"blight", "fungicide", "mancozeb", "anthracnose", "phomopsis", "blast", "disease"}),
    Intent.PESTICIDE_SAFETY: frozenset({"pesticide", "pesticides", "formalin", "carbide", "banned", "dose", "interval"}),
    Intent.FLOOD: frozenset({"flood", "floods", "embankment", "embankments", "breach", "rainfall", "sentinel", "haor"}),
    Intent.HARVEST: frozenset({"harvest", "maturity", "ripe", "drying", "dry"}),
    Intent.CREDIT: frozenset({"credit", "loan", "warehouse", "receipt", "working", "capital", "lend"}),
    Intent.TRANSPORT: frozenset({"truck", "freight", "corridor", "transport", "bridge", "toll"}),
    Intent.GENERAL: frozenset(),
}
INTENT_QUESTIONS: dict[Intent, str] = {
    Intent.STORAGE_CONDITIONS: "optimal cold-storage temperature (C and F), relative humidity, curing and ventilation to prevent rot",
    Intent.STORAGE_ACCESS: "smallholder access to cold-storage space: capacity, quota held by traders and plant owners, BCSA tariff and all-in cost per kg",
    Intent.SELLING_CHANNEL: "syndicate-free selling channels bypassing Faria, Bepari and Aratdar: wholesale arats, urban retail chains, WFP aggregation centres with pooled truck transport",
    Intent.PRICE: "current grower, wholesale and retail price spread and seasonal price outlook",
    Intent.DISEASE: "disease risk and DAE-recommended control with fungicide dose and pre-harvest interval",
    Intent.PESTICIDE_SAFETY: "DAE-registered versus banned chemicals, safe dose and pre-harvest interval",
    Intent.FLOOD: "flash-flood embankment breach risk and emergency harvest timing",
    Intent.HARVEST: "optimal harvest timing, maturity stage and drying",
    Intent.CREDIT: "collateral-free agri-credit, interest rate, and warehouse-receipt working-capital loans against the stored crop",
    Intent.TRANSPORT: "truck freight corridors, cost per kg and bridge tolls",
    Intent.GENERAL: "agronomic and market guidance",
}
HYDE_PASSAGES: dict[Intent, str] = {
    Intent.STORAGE_CONDITIONS: "{crop} should be cured, then held in cold storage at the recommended temperature and relative humidity band with regular ventilation so CO2 stays low and tubers do not rot, sprout or lose weight.",
    Intent.STORAGE_ACCESS: "Traders and plant owners book most cold-storage quota in {district}, leaving little capacity for {crop} smallholders, and the BCSA tariff per kg sets what storing costs.",
    Intent.SELLING_CHANNEL: "Instead of selling to Faria and Bepari intermediaries, {crop} growers in {district} can pool lots into a 5-ton truck and sell directly to wholesale arats, urban retail chain distribution centres or WFP aggregation centres at transparent prices, bypassing the syndicate markup.",
    Intent.PRICE: "The farm-gate, wholesale and retail price of {crop} in {district} differ by the intermediary markup; prices fall at harvest and rise in the off-season.",
    Intent.DISEASE: "Disease on {crop} is controlled by monitoring humid weather and applying DAE-registered fungicide at label dose while observing the pre-harvest interval.",
    Intent.PESTICIDE_SAFETY: "Only DAE-registered pesticides at label dose are allowed on {crop}; formalin and calcium carbide are banned and the pre-harvest interval must be respected.",
    Intent.FLOOD: "Upstream rainfall and Sentinel-1 radar water detection warn of flash floods and embankment breaches so {crop} in {district} can be harvested early.",
    Intent.HARVEST: "{crop} should be harvested at the right maturity and dried promptly to safe moisture before storage.",
    Intent.CREDIT: "{crop} farmers can borrow through collateral-free agricultural loans at a low interest rate, or pledge a warehouse receipt for working-capital credit and avoid distress sales.",
    Intent.TRANSPORT: "Pooled 5-ton truck freight from {district} to Dhaka costs a few taka per kg including bridge tolls.",
    Intent.GENERAL: "Guidance for {crop} growers in {district}.",
}


# When the farmer names no place, the dialect is the best location prior.
DIALECT_HOME_DISTRICT: dict[str, str] = {"Rangpuri": "Rangpur", "Bogura (Varendri)": "Bogura", "Sylheti": "Sunamganj"}


class DialectRewrite(BaseModel):
    original_query: str
    detected_dialect: str
    dialect_marker_scores: dict[str, int]
    normalized_bangla: str
    concepts: list[str]
    crop: Crop | None
    district: str | None
    intents: list[Intent]
    formal_query: str
    hypothetical_document: str
    search_queries: list[str]
    routing: RoutingDecision


class ChunkGrade(BaseModel):
    chunk_id: str
    rerank_score: float
    intent_coverage: float
    entity_match: float
    confidence: float
    label: str
    covered_intents: list[Intent]


class McpStrip(BaseModel):
    tool: str
    arguments: dict[str, object]
    summary: str


class KnowledgeStrip(BaseModel):
    source: str
    text: str


class CragReport(BaseModel):
    verdict: str
    confidence: float
    threshold: float
    intent_coverage: dict[Intent, bool]
    grades: list[ChunkGrade]
    corrective_triggered: bool
    actions: list[str]
    rewritten_query: str | None


class RagQueryResult(BaseModel):
    query_redacted: str
    pii_entities_redacted: int
    rewrite: DialectRewrite
    retrieval: list[RetrievedChunk]
    graph: GraphTraversalResult | None
    crag: CragReport
    mcp_augmentation: list[McpStrip]
    verified_context: list[KnowledgeStrip]
    context_tokens: dict[str, int]
    answer_summary: str
    answer_routing: RoutingDecision
    latency_ms: float = Field(ge=0)


# ---------------------------------------------------------------------------
# HyDE dialect rewriter
# ---------------------------------------------------------------------------


def detect_intents(text: str, concepts: list[str]) -> list[Intent]:
    """Intents from lexicon concepts plus the question's own English words."""
    signals = set(concepts) | _words(_HARVEST_COMPOUND.sub(" ", text))
    found = [
        intent for intent, triggers in INTENT_TRIGGERS.items()
        if triggers & signals and (intent not in INTENT_CONTEXT or INTENT_CONTEXT[intent] & signals)
    ]
    return found or [Intent.GENERAL]


class HyDEDialectRewriter:
    """Informal Rangpuri / Bogura / Sylheti / Standard Bangla / Banglish -> formal agronomic query + HyDE doc."""

    def rewrite(self, query: str, district: str | None = None, crop: Crop | None = None) -> DialectRewrite:
        dialect, scores = detect_dialect(query)
        normalized = normalize_dialect(query)
        concepts = list(dict.fromkeys(concepts_in(query) + concepts_in(normalized)))
        crop = crop or detect_crop(normalized)
        district = district or detect_district(normalized) or DIALECT_HOME_DISTRICT.get(dialect)
        intents = detect_intents(normalized, concepts)

        crop_label = crop.value if crop else "the crop"
        place = district or "Bangladesh"
        formal = f"{crop_label} in {place}: " + "; ".join(INTENT_QUESTIONS[i] for i in intents)
        hyde = " ".join(HYDE_PASSAGES[i].format(crop=crop_label, district=place) for i in intents)
        keywords = " ".join(dict.fromkeys(concepts + ([crop.value] if crop else []) + ([district] if district else [])))
        complexity = 0.2 + (0.15 if dialect not in ("Standard Bangla", "English") else 0.0) + 0.05 * len(intents)
        return DialectRewrite(
            original_query=query,
            detected_dialect=dialect,
            dialect_marker_scores=scores,
            normalized_bangla=normalized,
            concepts=concepts,
            crop=crop,
            district=district,
            intents=intents,
            formal_query=formal,
            hypothetical_document=hyde,
            search_queries=[formal, keywords],
            routing=MODEL_ROUTER.route_query(TaskType.DIALECT_REWRITE, complexity),
        )


# ---------------------------------------------------------------------------
# Corrective RAG evaluator
# ---------------------------------------------------------------------------


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


class CorrectiveRAGEvaluator:
    def grade(self, chunk: RetrievedChunk, intents: list[Intent], crop: Crop | None, district: str | None) -> ChunkGrade:
        words = _words(chunk.text + " " + " ".join(chunk.topics))
        covered = [i for i in intents if INTENT_EVIDENCE[i] & words]
        coverage = len(covered) / len(intents) if intents and intents != [Intent.GENERAL] else 1.0
        crop_score = 1.0 if crop and crop.value in chunk.crops else 0.6 if not chunk.crops or crop is None else 0.2
        district_score = 1.0 if district and district in chunk.districts else 0.6 if not chunk.districts or district is None else 0.3
        entity = 0.7 * crop_score + 0.3 * district_score
        confidence = 0.5 * chunk.rerank_score + 0.3 * coverage + 0.2 * entity
        label = "CORRECT" if confidence >= CRAG_THRESHOLD else "AMBIGUOUS" if confidence >= AMBIGUOUS_FLOOR else "INCORRECT"
        return ChunkGrade(chunk_id=chunk.chunk_id, rerank_score=chunk.rerank_score, intent_coverage=round(coverage, 3),
                          entity_match=round(entity, 3), confidence=round(confidence, 4), label=label, covered_intents=covered)

    def overall(self, grades: list[ChunkGrade], intents: list[Intent]) -> tuple[str, float, dict[Intent, bool]]:
        usable = [g for g in grades if g.label != "INCORRECT"]
        coverage = {i: any(i in g.covered_intents for g in usable) for i in intents}
        if intents == [Intent.GENERAL]:
            coverage = {Intent.GENERAL: bool(usable)}
        best = max((g.confidence for g in grades), default=0.0)
        confidence = 0.6 * best + 0.4 * (sum(coverage.values()) / max(1, len(coverage)))
        verdict = "CORRECT" if confidence >= CRAG_THRESHOLD else "AMBIGUOUS" if confidence >= AMBIGUOUS_FLOOR else "INCORRECT"
        return verdict, round(confidence, 4), coverage


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?।])\s+", text) if s.strip()]


class CragPipeline:
    def __init__(self) -> None:
        self.rewriter = HyDEDialectRewriter()
        self.evaluator = CorrectiveRAGEvaluator()

    async def _mcp_augment(self, intents: list[Intent], crop: Crop | None, district: str | None,
                           uncovered: set[Intent]) -> list[McpStrip]:
        strips: list[McpStrip] = []
        if district is None:
            return strips
        try:
            place = bd_geo.resolve_district(district)
        except ToolExecutionError:
            return strips
        crop = crop or Crop.CARDINAL_POTATO
        wanted = set(intents)
        if wanted & {Intent.PRICE, Intent.SELLING_CHANNEL}:
            spread = await get_daily_commodity_spread(GetDailyCommoditySpreadInput(crop=crop, district=place.name))
            strips.append(McpStrip(tool="get_daily_commodity_spread", arguments={"crop": crop.value, "district": place.name},
                                   summary=f"DAM today in {place.name}: grower Tk {spread.grower_price_tk_per_kg}/kg, wholesale "
                                           f"Tk {spread.wholesale_price_tk_per_kg}/kg, retail Tk {spread.retail_price_tk_per_kg}/kg "
                                           f"({spread.total_markup_spread_pct:.0f}% markup)."))
        if Intent.SELLING_CHANNEL in wanted:
            hubs = await find_optimal_selling_hub(FindOptimalSellingHubInput(crop=crop, weight_kg=1000, origin_district=place.name, grade=Grade.A))
            if hubs.best_option:
                b = hubs.best_option
                strips.append(McpStrip(tool="find_optimal_selling_hub",
                                       arguments={"crop": crop.value, "weight_kg": 1000, "origin_district": place.name, "grade": "A"},
                                       summary=f"Best direct buyer for 1,000 kg Grade A: {b.hub_name} ({b.hub_type.value}), net Tk "
                                               f"{b.net_payout_tk_per_kg}/kg vs farm-gate Tk {hubs.farmgate_baseline_tk_per_kg}/kg "
                                               f"(+{b.uplift_vs_farmgate_pct:.0f}%)."))
        if (wanted & {Intent.STORAGE_CONDITIONS, Intent.STORAGE_ACCESS} and crop in (Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO)
                and place.name in DISTRICT_STORAGE_STATS):
            quota = await query_cold_storage_quota(QueryColdStorageQuotaInput(district=place.name, radius_km=60, tons_needed=5))
            cheapest = min(quota.facilities, key=lambda f: f.all_in_cost_tk_per_kg, default=None)
            if cheapest:
                strips.append(McpStrip(tool="query_cold_storage_quota", arguments={"district": place.name, "radius_km": 60, "tons_needed": 5},
                                       summary=f"{quota.facilities_found} BCSA cold storages within 60 km have "
                                               f"{quota.total_open_smallholder_quota_mt:,.0f} t open smallholder quota; cheapest all-in "
                                               f"Tk {cheapest.all_in_cost_tk_per_kg}/kg at {cheapest.name}."))
        if uncovered & {Intent.HARVEST} or wanted & {Intent.FLOOD, Intent.DISEASE}:
            weather = await get_current_weather(GetCurrentWeatherInput(latitude=place.lat, longitude=place.lon))
            strips.append(McpStrip(tool="get_current_weather", arguments={"latitude": place.lat, "longitude": place.lon},
                                   summary=f"Weather near {place.name}: {weather.temperature_c} C, RH {weather.relative_humidity_pct}%, "
                                           f"{weather.weather_description} ({weather.data_source.value})."))
            if Intent.DISEASE in wanted:
                vpd = await compute_crop_vpd_stress(ComputeCropVpdStressInput(
                    crop=crop, crop_stage=CropStage.VEGETATIVE, temp_c=weather.temperature_c, rh_pct=weather.relative_humidity_pct))
                strips.append(McpStrip(tool="compute_crop_vpd_stress", arguments={"crop": crop.value, "temp_c": weather.temperature_c},
                                       summary=f"VPD {vpd.vpd_kpa} kPa; {vpd.pathogen} risk {vpd.fungal_risk_pct:.0f}% ({vpd.fungal_risk_level.value})."))
        return strips

    @staticmethod
    def _refine(chunks: list[RetrievedChunk], grades: list[ChunkGrade], intents: list[Intent]) -> list[KnowledgeStrip]:
        keep = {g.chunk_id for g in grades if g.label != "INCORRECT"}
        vocab = set().union(*(INTENT_EVIDENCE[i] for i in intents)) if intents != [Intent.GENERAL] else set()
        strips: list[KnowledgeStrip] = []
        for chunk in chunks:
            if chunk.chunk_id not in keep:
                continue
            for sentence in _sentences(chunk.text):
                if not vocab or vocab & _words(sentence):
                    strips.append(KnowledgeStrip(source=chunk.doc_id, text=sentence))
        deduped = TOKEN_OPTIMIZER.deduplicate_semantic_chunks([s.text for s in strips], 0.88)
        kept_texts = set(deduped.kept)
        return [s for s in strips if s.text in kept_texts]

    @staticmethod
    def _answer(intents: list[Intent], strips: list[KnowledgeStrip], graph: GraphTraversalResult | None,
                mcp: list[McpStrip], crop: Crop | None) -> str:
        parts: list[str] = []
        by_tool = {m.tool: m.summary for m in mcp}
        if Intent.STORAGE_CONDITIONS in intents:
            storage = next((s for s in strips if re.search(r"\d+\s*-\s*\d+\s*F\b", s.text)), None) or next(
                (s for s in strips if "relative humidity" in s.text), None
            )
            if storage:
                parts.append(f"Storage: {storage.text} [{storage.source}]")
        if "query_cold_storage_quota" in by_tool:
            parts.append(f"Capacity: {by_tool['query_cold_storage_quota']}")
        if Intent.SELLING_CHANNEL in intents:
            if graph and graph.paths:
                parts.append(f"Syndicate-free route: {graph.paths[0].narrative} [GraphRAG]")
            if "find_optimal_selling_hub" in by_tool:
                parts.append(f"Direct sale: {by_tool['find_optimal_selling_hub']}")
        if "get_daily_commodity_spread" in by_tool:
            parts.append(f"Market: {by_tool['get_daily_commodity_spread']}")
        for intent in intents:
            if intent in (Intent.STORAGE_CONDITIONS, Intent.SELLING_CHANNEL, Intent.PRICE, Intent.GENERAL):
                continue
            evidence = [
                (len(INTENT_EVIDENCE[intent] & _words(s.text)), crop is None or crop.value in DOC_CROPS.get(s.source, (crop.value,)), -n, s)
                for n, s in enumerate(strips)
            ]
            best = max(evidence, key=lambda e: (e[1], e[0], e[2]) if e[0] > 0 else (False, 0, e[2]), default=None)
            strip = best[3] if best and best[0] > 0 else None
            if strip:
                parts.append(f"{intent.value.replace('_', ' ').title()}: {strip.text} [{strip.source}]")
        if not parts and strips:
            parts.append(f"{strips[0].text} [{strips[0].source}]")
        return " ".join(parts) if parts else "No verified guidance found; escalate to a DAE extension officer."

    async def run(self, query: str, district: str | None = None, crop: Crop | None = None, top_k: int = 5) -> RagQueryResult:
        started = time.perf_counter()
        scrub = PII_SCRUBBER.scrub(query)
        rewrite = self.rewriter.rewrite(scrub.anonymized_text, district, crop)
        crop, district = rewrite.crop, rewrite.district
        retriever = get_retriever()
        lexical_query = f"{rewrite.formal_query} {rewrite.normalized_bangla}"
        chunks = retriever.search(lexical_query, top_k, crop.value if crop else None, district,
                                  dense_query=rewrite.hypothetical_document)
        grades = [self.evaluator.grade(c, rewrite.intents, crop, district) for c in chunks]
        verdict, confidence, coverage = self.evaluator.overall(grades, rewrite.intents)

        actions: list[str] = []
        rewritten: str | None = None
        corrective = confidence < CRAG_THRESHOLD
        if corrective:
            uncovered = [i for i, ok in coverage.items() if not ok] or rewrite.intents
            rewritten = f"{crop.value if crop else ''} {district or ''} " + " ".join(INTENT_QUESTIONS[i] for i in uncovered)
            extra = retriever.search(rewritten, top_k, crop.value if crop else None, district)
            seen = {c.chunk_id for c in chunks}
            chunks += [c for c in extra if c.chunk_id not in seen]
            grades = [self.evaluator.grade(c, rewrite.intents, crop, district) for c in chunks]
            verdict, confidence, coverage = self.evaluator.overall(grades, rewrite.intents)
            actions.append(f"Rewrote query for uncovered intents {[i.value for i in uncovered]} and re-retrieved.")

        graph: GraphTraversalResult | None = None
        if district:
            try:
                graph = get_graph().traverse(district, crop, max_paths=3)
            except ToolExecutionError as exc:
                actions.append(f"GraphRAG skipped: {exc}")

        uncovered_now = {i for i, ok in coverage.items() if not ok}
        mcp = await self._mcp_augment(rewrite.intents, crop, district, uncovered_now if corrective else set())
        if mcp:
            actions.append(f"Augmented with live MCP data from {', '.join(m.tool for m in mcp)}.")
            if corrective:
                covered_by_mcp = {Intent.PRICE, Intent.SELLING_CHANNEL} & uncovered_now
                if covered_by_mcp:
                    coverage.update({i: True for i in covered_by_mcp})
                    best = max((g.confidence for g in grades), default=0.0)
                    confidence = round(0.6 * best + 0.4 * sum(coverage.values()) / max(1, len(coverage)), 4)
                    verdict = "CORRECT" if confidence >= CRAG_THRESHOLD else "AMBIGUOUS" if confidence >= AMBIGUOUS_FLOOR else "INCORRECT"

        strips = self._refine(chunks, grades, rewrite.intents)
        if graph:
            strips += [KnowledgeStrip(source="GraphRAG", text=p.narrative) for p in graph.paths]
        strips += [KnowledgeStrip(source=f"MCP:{m.tool}", text=m.summary) for m in mcp]
        retrieved_tokens = sum(estimate_tokens(c.context_header + " " + c.text) for c in chunks)
        verified_tokens = sum(estimate_tokens(s.text) for s in strips)
        complexity = min(1.0, 0.3 + 0.1 * len(rewrite.intents) + (0.2 if verdict != "CORRECT" else 0.0))
        return RagQueryResult(
            query_redacted=scrub.anonymized_text,
            pii_entities_redacted=len(scrub.entities),
            rewrite=rewrite,
            retrieval=chunks,
            graph=graph,
            crag=CragReport(verdict=verdict, confidence=confidence, threshold=CRAG_THRESHOLD, intent_coverage=coverage,
                            grades=grades, corrective_triggered=corrective, actions=actions, rewritten_query=rewritten),
            mcp_augmentation=mcp,
            verified_context=strips,
            context_tokens={"retrieved": retrieved_tokens, "verified": verified_tokens,
                            "saved": max(0, retrieved_tokens - verified_tokens)},
            answer_summary=self._answer(rewrite.intents, strips, graph, mcp, crop),
            answer_routing=MODEL_ROUTER.route_query(TaskType.RAG_ANSWER, complexity),
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )


CRAG_PIPELINE = CragPipeline()
