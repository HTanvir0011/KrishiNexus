"""Token optimisation engine.

* ``compress_prompt_llmlingua`` — LLMLingua-2-style keep/drop token classification. Bulky JSON
  (DAM price tables, 168-hour weather arrays) is first compacted losslessly (row tables, run-length
  encoded numeric series, nulls dropped); prose is then pruned of low-information filler while every
  number, Tk price, crop, district, unit and value-chain term is protected.
* ``deduplicate_semantic_chunks`` — greedy cosine-similarity dedup of RAG passages.
* ``build_cached_messages`` — Anthropic ``cache_control``, Gemini ``cachedContent`` and DeepSeek
  automatic prefix-cache payloads built around one stable, hashed prefix.
* ``RollingSummaryMemory`` — folds farmer turns beyond the last N into a compact, PII-scrubbed state.

Token counts use a cl100k-calibrated heuristic (Latin ~4 chars/token, Bangla ~2 chars/token,
digits ~3 per token) so the engine runs without a tokenizer download.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from config import MODEL_CATALOG
from guardrails.pii_scrubber import PII_SCRUBBER
from mcp_servers import bd_geo
from rag.hybrid_retriever import HashingEmbedder
from rag.lexicon import BANGLA_TO_ASCII_DIGITS, concepts_in, detect_crop, detect_district
from schemas.mcp_models import Crop

_PIECE_RE = re.compile(r"[ঀ-৿]+|[A-Za-z]+|[0-9০-৯]+|[^\s\w]", re.UNICODE)
_NUMBER_RE = re.compile(r"[0-9০-৯]+(?:\.[0-9০-৯]+)?")

FILLER_WORDS = frozenset(
    "a an the of to is are was were be been being at in on for from by with and or that this these those it its "
    "as which who whom whose there here very really quite just also then than so such into onto upon about "
    "please kindly note following report reported market's currently approximately around per cent "
    "এবং ও যে এই সেই তো হয় হয়েছে করা করে থেকে জন্য দিয়ে আর কিন্তু".split()
)
DOMAIN_TERMS = frozenset(
    "grower farmgate farm-gate wholesale retail faria bepari aratdar paiker retailer commission arat haat "
    "cold storage tariff fee rh humidity temperature price prices tk bdt kg mt ton tons quota rot lambda "
    "rain rainfall precipitation gust wind flood breach sar backscatter spot future harvest grade "
    "potato chili brinjal boro rice cardinal diamant".split()
)
_PROTECTED_NAMES = frozenset(
    {w.lower() for d in bd_geo.DISTRICTS for w in re.findall(r"[A-Za-z']+", d.name)}
    | {u.name.lower() for u in bd_geo.UPAZILAS}
    | {w.lower() for c in Crop for w in c.value.split()}
)


def estimate_tokens(text: str) -> int:
    total = 0
    for piece in _PIECE_RE.findall(text):
        if piece[0].isascii() and piece.isalpha():
            total += math.ceil(len(piece) / 4)
        elif "ঀ" <= piece[0] <= "৿" and not piece[0].isdigit():
            total += math.ceil(len(piece) / 2)
        elif piece[0].isdigit():
            total += math.ceil(len(piece) / 3)
        else:
            total += 1
    return total


_ISO_TIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?")


def _numbers(text: str) -> set[str]:
    """Distinct numeric values (timestamps excluded: they are range-encoded, not dropped)."""
    values: set[str] = set()
    for raw in _NUMBER_RE.findall(_ISO_TIME_RE.sub(" ", text)):
        ascii_value = raw.translate(BANGLA_TO_ASCII_DIGITS)
        try:
            values.add(f"{float(ascii_value):g}")
        except ValueError:
            values.add(ascii_value)
    return values


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class ModelSaving(BaseModel):
    model_key: str
    model_id: str
    saved_usd_per_1k_calls: float


class CompressionResult(BaseModel):
    method: str
    structural_pass: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float = Field(description="compressed / original tokens")
    reduction_factor: float = Field(description="original / compressed tokens")
    target_ratio: float
    target_met: bool
    all_numbers_preserved: bool
    protected_terms: list[str]
    dropped_sample: list[str]
    compressed_text: str
    savings: list[ModelSaving]


class DuplicatePair(BaseModel):
    removed_index: int
    duplicate_of_index: int
    similarity: float


class DedupResult(BaseModel):
    similarity_threshold: float
    input_chunks: int
    kept_chunks: int
    kept: list[str]
    removed: list[DuplicatePair]
    tokens_before: int
    tokens_after: int


class CachedMessages(BaseModel):
    prefix_sha256: str
    static_prefix_tokens: int
    dynamic_tokens: int
    cache_eligible: dict[str, bool]
    estimated_input_cost_usd: dict[str, dict[str, float]] = Field(
        description="Per provider: first (uncached) call vs. repeat call with a warm prefix cache."
    )
    anthropic: dict[str, Any]
    gemini: dict[str, Any]
    deepseek: dict[str, Any]


# ---------------------------------------------------------------------------
# Lossless structural compaction of JSON payloads
# ---------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _rle(values: list[Any]) -> str:
    runs: list[list[Any]] = []
    for value in values:
        token = _fmt(value)
        if runs and runs[-1][0] == token:
            runs[-1][1] += 1
        else:
            runs.append([token, 1])
    return ",".join(token if count == 1 else f"{token}x{count}" for token, count in runs)


def _time_range(values: list[Any]) -> str | None:
    """Encode an evenly spaced ISO timestamp column as 'start+step*n'."""
    if len(values) < 3 or not all(isinstance(v, str) for v in values):
        return None
    try:
        stamps = [datetime.fromisoformat(v) for v in values]
    except ValueError:
        return None
    step = stamps[1] - stamps[0]
    if step.total_seconds() <= 0 or any(b - a != step for a, b in zip(stamps, stamps[1:])):
        return None
    minutes = int(step.total_seconds() // 60)
    unit = f"{minutes // 60}h" if minutes % 60 == 0 else f"{minutes}m"
    return f"{values[0]}+{unit}*{len(values)}"


def _column(values: list[Any]) -> str:
    present = [v for v in values if v is not None]
    if not present:
        return "null"
    return _time_range(values) or _rle(values)


def _compact(node: Any) -> str:
    if isinstance(node, dict):
        parts = [f"{k}={_compact(v)}" for k, v in node.items() if v is not None and v != [] and v != {}]
        return "{" + ";".join(parts) + "}"
    if isinstance(node, list):
        if node and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in node):
            return f"[{_rle(node)}]"
        if node and all(isinstance(v, dict) for v in node):
            columns = list(dict.fromkeys(k for row in node for k in row))
            encoded = {c: _column([row.get(c) for row in node]) for c in columns}
            return f"table(n={len(node)})" + "{" + ";".join(f"{c}=[{v}]" for c, v in encoded.items() if v != "null") + "}"
        return "[" + ",".join(_compact(v) for v in node) + "]"
    return _fmt(node)


# ---------------------------------------------------------------------------
# Rolling summary memory
# ---------------------------------------------------------------------------

_QUANTITY_RE = re.compile(r"([0-9০-৯][0-9০-৯.,]*)\s*(kg|কেজি|মণ|mon|maund|ton|tons|টন)", re.IGNORECASE)
_PRICE_RE = re.compile(r"(?:tk\.?\s*|৳\s*)([0-9০-৯][0-9০-৯.]*)|([0-9০-৯][0-9০-৯.]*)\s*(?:টাকা|taka)", re.IGNORECASE)
_UNIT_KG = {"kg": 1.0, "কেজি": 1.0, "মণ": 40.0, "mon": 40.0, "maund": 40.0, "ton": 1000.0, "tons": 1000.0, "টন": 1000.0}


class MemoryTurn(BaseModel):
    role: str
    text: str


class MemoryState(BaseModel):
    crop: str | None = None
    district: str | None = None
    quantity_kg: float | None = None
    prices_mentioned_tk: list[float] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)
    turns_summarized: int = 0


class RollingSummaryMemory:
    """Keep the last ``max_turns`` turns verbatim; fold older turns into a structured state line."""

    def __init__(self, max_turns: int = 4) -> None:
        self.max_turns = max_turns
        self.turns: list[MemoryTurn] = []
        self.state = MemoryState()
        self._raw_tokens = 0

    def add_turn(self, role: str, text: str) -> None:
        clean = PII_SCRUBBER.scrub(text).anonymized_text
        self._raw_tokens += estimate_tokens(clean)
        self.turns.append(MemoryTurn(role=role, text=clean))
        while len(self.turns) > self.max_turns:
            self._fold(self.turns.pop(0))

    def _fold(self, turn: MemoryTurn) -> None:
        s = self.state
        crop = detect_crop(turn.text)
        s.crop = crop.value if crop else s.crop
        s.district = detect_district(turn.text) or s.district
        for amount, unit in _QUANTITY_RE.findall(turn.text):
            s.quantity_kg = float(amount.translate(BANGLA_TO_ASCII_DIGITS).replace(",", "")) * _UNIT_KG[unit.lower()]
        for tk, taka in _PRICE_RE.findall(turn.text):
            value = float((tk or taka).translate(BANGLA_TO_ASCII_DIGITS))
            if value not in s.prices_mentioned_tk:
                s.prices_mentioned_tk.append(value)
        for concept in concepts_in(turn.text):
            if concept in {"sell", "store", "price", "credit", "flood", "harvest", "pesticide", "transport", "rot"}:
                if concept not in s.intents:
                    s.intents.append(concept)
        s.turns_summarized += 1

    def summary_line(self) -> str:
        s = self.state
        return (
            f"FARMER STATE | crop={s.crop or '?'}; district={s.district or '?'}; "
            f"quantity_kg={s.quantity_kg if s.quantity_kg is not None else '?'}; "
            f"prices_tk={s.prices_mentioned_tk}; intents={s.intents}; summarized_turns={s.turns_summarized}"
        )

    def context(self) -> list[dict[str, str]]:
        messages = [{"role": t.role, "content": t.text} for t in self.turns]
        if self.state.turns_summarized:
            messages.insert(0, {"role": "system", "content": self.summary_line()})
        return messages

    def token_stats(self) -> dict[str, int]:
        compact = sum(estimate_tokens(m["content"]) for m in self.context())
        return {"raw_history_tokens": self._raw_tokens, "compacted_tokens": compact,
                "tokens_saved": max(0, self._raw_tokens - compact)}


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------


class TokenOptimizer:
    def __init__(self) -> None:
        self._embedder = HashingEmbedder()

    @staticmethod
    def _is_protected(word: str) -> bool:
        bare = word.strip(".,;:()[]{}\"'!?।").lower()
        return (
            any(ch.isdigit() for ch in word)
            or bare in _PROTECTED_NAMES
            or bare in DOMAIN_TERMS
            or bare in {"°c", "°f", "%", "৳"}
            or (bare.isupper() and len(bare) >= 2)
            or (word.strip(".,;:()") .isupper() and len(word.strip(".,;:()")) >= 2)
        )

    def compress_prompt_llmlingua(self, raw_context: str, target_ratio: float = 0.25) -> CompressionResult:
        original_tokens = estimate_tokens(raw_context)
        structural = "none"
        text = raw_context
        try:
            parsed = json.loads(raw_context)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            text = _compact(parsed)
            structural = "json-compaction (row tables, run-length numeric series, nulls dropped)"

        words = text.split()
        counts = Counter(w.lower() for w in words)
        total = sum(counts.values()) or 1
        budget = max(1, math.ceil(original_tokens * target_ratio))
        keep = [True] * len(words)
        protected_terms: list[str] = []
        scored: list[tuple[float, int]] = []
        for i, word in enumerate(words):
            if self._is_protected(word):
                protected_terms.append(word.strip(".,;:"))
                continue
            bare = word.strip(".,;:()").lower()
            information = -math.log(counts[word.lower()] / total) + 0.15 * len(bare)
            scored.append((-10.0 if bare in FILLER_WORDS or not bare else information, i))

        dropped: list[str] = []
        for _, i in sorted(scored):
            if estimate_tokens(" ".join(w for w, k in zip(words, keep) if k)) <= budget:
                break
            keep[i] = False
            dropped.append(words[i])
        compressed = " ".join(w for w, k in zip(words, keep) if k)
        compressed_tokens = estimate_tokens(compressed)
        saved = original_tokens - compressed_tokens
        return CompressionResult(
            method="LLMLingua-2-style token classification (local information-score keep/drop)",
            structural_pass=structural,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=round(compressed_tokens / max(1, original_tokens), 3),
            reduction_factor=round(original_tokens / max(1, compressed_tokens), 2),
            target_ratio=target_ratio,
            target_met=compressed_tokens <= budget,
            all_numbers_preserved=_numbers(raw_context) <= _numbers(compressed),
            protected_terms=list(dict.fromkeys(protected_terms))[:40],
            dropped_sample=dropped[:25],
            compressed_text=compressed,
            savings=[
                ModelSaving(model_key=spec.key, model_id=spec.model_id,
                            saved_usd_per_1k_calls=round(saved / 1e6 * spec.input_usd_per_mtok * 1000, 6))
                for spec in MODEL_CATALOG.values() if spec.input_usd_per_mtok > 0
            ],
        )

    def deduplicate_semantic_chunks(self, chunks: list[str], similarity_threshold: float = 0.88) -> DedupResult:
        if not chunks:
            return DedupResult(similarity_threshold=similarity_threshold, input_chunks=0, kept_chunks=0, kept=[],
                               removed=[], tokens_before=0, tokens_after=0)
        vectors = self._embedder.embed(chunks)
        kept_idx: list[int] = []
        removed: list[DuplicatePair] = []
        for i in range(len(chunks)):
            if kept_idx:
                sims = vectors[kept_idx] @ vectors[i]
                best = int(np.argmax(sims))
                if float(sims[best]) >= similarity_threshold:
                    removed.append(DuplicatePair(removed_index=i, duplicate_of_index=kept_idx[best],
                                                 similarity=round(float(sims[best]), 4)))
                    continue
            kept_idx.append(i)
        kept = [chunks[i] for i in kept_idx]
        return DedupResult(
            similarity_threshold=similarity_threshold,
            input_chunks=len(chunks),
            kept_chunks=len(kept),
            kept=kept,
            removed=removed,
            tokens_before=sum(estimate_tokens(c) for c in chunks),
            tokens_after=sum(estimate_tokens(c) for c in kept),
        )

    def build_cached_messages(self, system_prompt: str, static_rag_schema: str, dynamic_user_query: str) -> CachedMessages:
        prefix = f"{system_prompt}\n\n{static_rag_schema}"
        prefix_hash = hashlib.sha256(prefix.encode("utf-8")).hexdigest()
        static_tokens = estimate_tokens(prefix)
        dynamic_tokens = estimate_tokens(dynamic_user_query)
        sonnet, gemini, deepseek = MODEL_CATALOG["claude-sonnet"], MODEL_CATALOG["gemini-flash"], MODEL_CATALOG["deepseek-r1"]

        def cost(spec_key: str, cached: bool) -> float:
            spec = MODEL_CATALOG[spec_key]
            prefix_price = spec.input_usd_per_mtok * (spec.cached_input_multiplier if cached else 1.0)
            return round((static_tokens * prefix_price + dynamic_tokens * spec.input_usd_per_mtok) / 1e6, 8)

        return CachedMessages(
            prefix_sha256=prefix_hash,
            static_prefix_tokens=static_tokens,
            dynamic_tokens=dynamic_tokens,
            cache_eligible={
                "anthropic": static_tokens >= 512,  # Claude Sonnet 5.5 minimum cacheable prefix
                "gemini": static_tokens >= 1024,  # Gemini 2.5 Flash explicit-cache minimum
                "deepseek": static_tokens >= 64,  # DeepSeek caches in 64-token prefix units
            },
            estimated_input_cost_usd={
                key: {"first_call": cost(key, False), "repeat_call_cached": cost(key, True)}
                for key in ("claude-sonnet", "gemini-flash", "deepseek-r1")
            },
            anthropic={
                "model": sonnet.model_id,
                "max_tokens": 16000,
                "system": [
                    {"type": "text", "text": system_prompt},
                    {"type": "text", "text": static_rag_schema, "cache_control": {"type": "ephemeral"}},
                ],
                "messages": [{"role": "user", "content": dynamic_user_query}],
            },
            gemini={
                "create_cache": {
                    "endpoint": "POST https://generativelanguage.googleapis.com/v1beta/cachedContents",
                    "body": {
                        "model": f"models/{gemini.model_id}",
                        "displayName": f"knx-{prefix_hash[:12]}",
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"role": "user", "parts": [{"text": static_rag_schema}]}],
                        "ttl": "3600s",
                    },
                },
                "generate_content": {
                    "endpoint": f"POST https://generativelanguage.googleapis.com/v1beta/models/{gemini.model_id}:generateContent",
                    "body": {
                        "cachedContent": "<name returned by create_cache, e.g. cachedContents/abc123>",
                        "contents": [{"role": "user", "parts": [{"text": dynamic_user_query}]}],
                    },
                },
            },
            deepseek={
                "endpoint": "POST https://api.deepseek.com/chat/completions",
                "body": {
                    "model": deepseek.model_id,
                    "messages": [
                        {"role": "system", "content": prefix},
                        {"role": "user", "content": dynamic_user_query},
                    ],
                },
                "note": "Automatic prefix caching: keep the system prefix byte-identical; usage.prompt_cache_hit_tokens reports hits.",
            },
        )


TOKEN_OPTIMIZER = TokenOptimizer()
