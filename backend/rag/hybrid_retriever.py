"""Contextual hybrid retrieval: semantic chunking, BM25 + dense vectors, RRF fusion, BGE-style reranking.

Runs entirely in-process: dense vectors come from a deterministic 384-dim signed
feature-hashing embedder over Bangla/English concept-expanded tokens, stored in an
in-memory numpy matrix laid out exactly like the ``PGVECTOR_SCHEMA`` table. Setting
``KNX_EMBEDDING_MODEL`` (e.g. ``BAAI/bge-m3``) or ``KNX_RERANKER_MODEL`` (e.g.
``BAAI/bge-reranker-large``) swaps in sentence-transformers models when installed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from pydantic import BaseModel

from rag.knowledge_seed import KNOWLEDGE_DOCS, KnowledgeDoc
from rag.lexicon import tokenize

logger = logging.getLogger("krishinexus.rag")

EMBEDDING_DIM = 384
RRF_K = 60
CANDIDATE_POOL = 20

STOPWORDS = frozenset(
    "a an and are as at be by for from in into is it its of on or that the this to with was were will can "
    "কত এবং আমি আমার আমরা কোথায় না হলে ছাড়া করে কি কী যে এই ও থেকে জন্য রাখলে তো কেন কিভাবে".split()
)

PGVECTOR_SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id        TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL,
    title           TEXT NOT NULL,
    source          TEXT NOT NULL,
    crops           TEXT[] NOT NULL DEFAULT '{{}}',
    districts       TEXT[] NOT NULL DEFAULT '{{}}',
    topics          TEXT[] NOT NULL DEFAULT '{{}}',
    context_header  TEXT NOT NULL,
    content         TEXT NOT NULL,
    content_tsv     TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', context_header || ' ' || content)) STORED,
    embedding       VECTOR({EMBEDDING_DIM}) NOT NULL
);
CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw ON rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS rag_chunks_tsv_gin ON rag_chunks USING gin (content_tsv);
""".strip()


def content_terms(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


class HashingEmbedder:
    """Signed feature hashing over unigrams, bigrams and character trigrams (sublinear tf, L2-normalised)."""

    backend = "hashing-384 (local, deterministic)"

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def _features(self, text: str) -> Counter[str]:
        terms = content_terms(text)
        feats: Counter[str] = Counter()
        for term in terms:
            feats[f"u:{term}"] += 1.0
            if term.isascii() and len(term) >= 4:
                for i in range(len(term) - 2):
                    feats[f"c:{term[i:i + 3]}"] += 0.3
        for left, right in zip(terms, terms[1:]):
            feats[f"b:{left}_{right}"] += 0.5
        return feats

    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature, tf in self._features(text).items():
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if digest[4] & 1 else -1.0
                matrix[row, index] += sign * (1.0 + math.log(tf + 1e-9) if tf >= 1 else tf)
            norm = np.linalg.norm(matrix[row])
            if norm > 0:
                matrix[row] /= norm
        return matrix


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.backend = f"sentence-transformers:{model_name}"

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=True), dtype=np.float32)


def build_embedder() -> HashingEmbedder | SentenceTransformerEmbedder:
    model_name = os.getenv("KNX_EMBEDDING_MODEL")
    if model_name and importlib.util.find_spec("sentence_transformers") is not None:
        try:
            return SentenceTransformerEmbedder(model_name)
        except Exception as exc:  # model download / load failure must not take the server down
            logger.warning("Embedding model %s unavailable (%s); using hashing embedder", model_name, exc)
    return HashingEmbedder()


# ---------------------------------------------------------------------------
# Contextual semantic chunking
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContextualChunk:
    chunk_id: str
    doc: KnowledgeDoc
    text: str

    @property
    def header(self) -> str:
        return self.doc.contextual_header()

    @property
    def indexed_text(self) -> str:
        return f"{self.header}\n{self.text}"


class SemanticChunker:
    """Split a document where adjacent-sentence similarity drops or the token budget is reached."""

    def __init__(self, embedder: HashingEmbedder | SentenceTransformerEmbedder, max_tokens: int = 160,
                 breakpoint_percentile: float = 20.0) -> None:
        self.embedder = embedder
        self.max_tokens = max_tokens
        self.breakpoint_percentile = breakpoint_percentile

    @staticmethod
    def sentences(text: str) -> list[str]:
        return [s.strip() for s in re.split(r"(?<=[.!?।])\s+", text) if s.strip()]

    def chunk(self, doc: KnowledgeDoc) -> list[ContextualChunk]:
        sentences = self.sentences(doc.text)
        if len(sentences) <= 1:
            return [ContextualChunk(f"{doc.doc_id}#0", doc, doc.text)]
        vectors = self.embedder.embed(sentences)
        similarities = np.sum(vectors[:-1] * vectors[1:], axis=1)
        threshold = float(np.percentile(similarities, self.breakpoint_percentile))
        groups: list[list[str]] = [[sentences[0]]]
        for i, sentence in enumerate(sentences[1:]):
            group_tokens = sum(len(s.split()) for s in groups[-1])
            if similarities[i] < threshold and group_tokens >= self.max_tokens // 2 or group_tokens + len(sentence.split()) > self.max_tokens:
                groups.append([sentence])
            else:
                groups[-1].append(sentence)
        return [ContextualChunk(f"{doc.doc_id}#{n}", doc, " ".join(g)) for n, g in enumerate(groups)]


# ---------------------------------------------------------------------------
# Lexical and dense indexes
# ---------------------------------------------------------------------------


class BM25Index:
    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tfs = [Counter(doc) for doc in documents]
        self.lengths = np.array([len(doc) for doc in documents], dtype=float)
        self.avg_len = float(self.lengths.mean()) if len(documents) else 0.0
        df: Counter[str] = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(documents)
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def scores(self, query_terms: list[str]) -> np.ndarray:
        out = np.zeros(len(self.tfs))
        for i, tf in enumerate(self.tfs):
            norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_len)
            out[i] = sum(
                self.idf[t] * tf[t] * (self.k1 + 1) / (tf[t] + norm) for t in set(query_terms) if t in tf
            )
        return out


class VectorIndex:
    def __init__(self, matrix: np.ndarray) -> None:
        self.matrix = matrix

    def scores(self, query_vector: np.ndarray) -> np.ndarray:
        return self.matrix @ query_vector


# ---------------------------------------------------------------------------
# Cross-encoder style reranker
# ---------------------------------------------------------------------------


class BGEReranker:
    """Pairwise (query, passage) relevance in [0, 1].

    With ``KNX_RERANKER_MODEL`` set and sentence-transformers installed this runs the
    ``bge-reranker-large`` cross-encoder; otherwise a calibrated logistic over the same
    signals a cross-encoder learns: term coverage, term proximity, entity agreement,
    lexical and dense similarity.
    """

    def __init__(self) -> None:
        self._cross_encoder: Any = None
        self.backend = "bge-reranker-large logic (local logistic cross-features)"
        model_name = os.getenv("KNX_RERANKER_MODEL")
        if model_name and importlib.util.find_spec("sentence_transformers") is not None:
            try:
                from sentence_transformers import CrossEncoder

                self._cross_encoder = CrossEncoder(model_name)
                self.backend = f"cross-encoder:{model_name}"
            except Exception as exc:
                logger.warning("Reranker %s unavailable (%s); using local reranker", model_name, exc)

    @staticmethod
    def _proximity(query_terms: set[str], passage_terms: list[str]) -> float:
        positions = [i for i, t in enumerate(passage_terms) if t in query_terms]
        if len(positions) < 2:
            return 0.0
        window = min(positions[j + 2] - positions[j] for j in range(len(positions) - 2)) if len(positions) > 2 else positions[1] - positions[0]
        return 1.0 / (1.0 + window / 4.0)

    def score(self, query: str, chunk: ContextualChunk, bm25_norm: float, dense: float,
              crop: str | None, district: str | None) -> float:
        if self._cross_encoder is not None:
            return float(1 / (1 + math.exp(-self._cross_encoder.predict([(query, chunk.indexed_text)])[0])))
        query_terms = set(content_terms(query))
        passage_terms = content_terms(chunk.indexed_text)
        coverage = len(query_terms & set(passage_terms)) / max(1, len(query_terms))
        crop_match = 1.0 if crop and crop in chunk.doc.crops else 0.5 if not chunk.doc.crops else 0.0
        district_match = 1.0 if district and district in chunk.doc.districts else 0.5 if not chunk.doc.districts else 0.0
        logit = (
            -3.0 + 3.2 * coverage + 1.5 * dense + 1.2 * bm25_norm + 0.8 * crop_match + 0.5 * district_match
            + 0.6 * self._proximity(query_terms, passage_terms)
        )
        return 1.0 / (1.0 + math.exp(-logit))


# ---------------------------------------------------------------------------
# Hybrid retriever
# ---------------------------------------------------------------------------


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    source: str
    crops: list[str]
    districts: list[str]
    topics: list[str]
    context_header: str
    text: str
    bm25_score: float
    bm25_rank: int | None
    vector_score: float
    vector_rank: int | None
    hybrid_rrf_score: float
    hybrid_rank: int
    rerank_score: float
    final_rank: int


class HybridRetriever:
    def __init__(self, docs: tuple[KnowledgeDoc, ...] = KNOWLEDGE_DOCS) -> None:
        self.embedder = build_embedder()
        self.chunker = SemanticChunker(self.embedder)
        self.chunks: list[ContextualChunk] = [c for doc in docs for c in self.chunker.chunk(doc)]
        self.reranker = BGEReranker()
        self._build_indexes()

    def _build_indexes(self) -> None:
        self.bm25 = BM25Index([content_terms(c.indexed_text) for c in self.chunks])
        self.vectors = VectorIndex(self.embedder.embed([c.indexed_text for c in self.chunks]))

    def upsert_documents(self, docs: list[KnowledgeDoc]) -> int:
        """Replace (by doc_id) or add documents and rebuild both indexes; returns the new chunk count."""
        replaced = {d.doc_id for d in docs}
        self.chunks = [c for c in self.chunks if c.doc.doc_id not in replaced]
        self.chunks += [c for doc in docs for c in self.chunker.chunk(doc)]
        self._build_indexes()
        return len(self.chunks)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "documents": len({c.doc.doc_id for c in self.chunks}),
            "chunks": len(self.chunks),
            "embedding_backend": self.embedder.backend,
            "embedding_dim": int(self.vectors.matrix.shape[1]),
            "reranker_backend": self.reranker.backend,
            "fusion": f"reciprocal rank fusion (k={RRF_K}) + metadata boost",
        }

    def search(self, query: str, top_k: int = 5, crop: str | None = None, district: str | None = None,
               dense_query: str | None = None) -> list[RetrievedChunk]:
        """BM25 on ``query``; dense search on ``dense_query`` (e.g. a HyDE document) or ``query``."""
        bm25 = self.bm25.scores(content_terms(query))
        dense = self.vectors.scores(self.embedder.embed([dense_query or query])[0])
        bm25_order = [int(i) for i in np.argsort(-bm25, kind="stable")]
        dense_order = [int(i) for i in np.argsort(-dense, kind="stable")]
        bm25_rank = {i: r + 1 for r, i in enumerate(bm25_order) if bm25[i] > 0}
        dense_rank = {i: r + 1 for r, i in enumerate(dense_order)}

        candidates = set(bm25_order[:CANDIDATE_POOL]) | set(dense_order[:CANDIDATE_POOL])
        fused: dict[int, float] = {}
        for i in candidates:
            score = 1.0 / (RRF_K + dense_rank[i])
            if i in bm25_rank:
                score += 1.0 / (RRF_K + bm25_rank[i])
            doc = self.chunks[i].doc
            score += 0.004 if crop and crop in doc.crops else 0.0
            score += 0.003 if district and district in doc.districts else 0.0
            fused[i] = score
        hybrid_order = sorted(fused, key=lambda i: -fused[i])
        bm25_max = float(bm25.max()) or 1.0

        reranked = sorted(
            ((i, self.reranker.score(query, self.chunks[i], bm25[i] / bm25_max, float(dense[i]), crop, district))
             for i in hybrid_order),
            key=lambda pair: (-pair[1], -fused[pair[0]]),
        )
        results: list[RetrievedChunk] = []
        for final_rank, (i, rerank) in enumerate(reranked[:top_k], start=1):
            chunk = self.chunks[i]
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc.doc_id,
                    title=chunk.doc.title,
                    source=chunk.doc.source,
                    crops=list(chunk.doc.crops),
                    districts=list(chunk.doc.districts),
                    topics=list(chunk.doc.topics),
                    context_header=chunk.header,
                    text=chunk.text,
                    bm25_score=round(float(bm25[i]), 4),
                    bm25_rank=bm25_rank.get(i),
                    vector_score=round(float(dense[i]), 4),
                    vector_rank=dense_rank[i],
                    hybrid_rrf_score=round(fused[i], 5),
                    hybrid_rank=hybrid_order.index(i) + 1,
                    rerank_score=round(rerank, 4),
                    final_rank=final_rank,
                )
            )
        return results


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    return HybridRetriever()
