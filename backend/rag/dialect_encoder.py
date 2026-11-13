"""Trained dialect retriever ``krishi-dialect-e5-small-v1`` (TRAINING_PLAN.md section 7b).

A fine-tuned multilingual-e5-small, exported to ONNX with int8 weights, that reads the farmer's own words (Standard
Bangla, Rangpuri, Sylheti, Bogura, Banglish or English) and scores each knowledge document. It runs with onnxruntime and
``tokenizers``, which faster-whisper already installs. Without the model folder or those packages the app runs exactly
as before. The weights stay out of git (``backend/models/`` is ignored); training/kaggle/KAGGLE_DATASET.md says where
to download them.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

logger = logging.getLogger("krishinexus.rag")

MODEL_DIR = Path(os.getenv("KNX_DIALECT_RETRIEVER", Path(__file__).resolve().parent.parent / "models" / "retrieval"
                           / "krishi-dialect-e5-small-v1"))
TEMPERATURE = 0.05  # the training temperature, so the softmax below is the model's own distribution over documents


class DialectEncoder:
    def __init__(self, folder: Path) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.config = json.loads((folder / "krishi_retriever.json").read_text(encoding="utf-8"))
        self._session = ort.InferenceSession(str(folder / "model_int8.onnx"), providers=["CPUExecutionProvider"])
        self._tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._tokenizer.enable_padding(pad_id=self._tokenizer.token_to_id("<pad>"), pad_token="<pad>")
        self.backend = f"{folder.name} (onnx int8)"

    def embed(self, texts: list[str], query: bool) -> np.ndarray:
        prefix = self.config["query_prefix" if query else "passage_prefix"]
        self._tokenizer.enable_truncation(self.config["query_max_len" if query else "passage_max_len"])
        encoded = self._tokenizer.encode_batch([prefix + t for t in texts])
        ids = np.array([e.ids for e in encoded], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        hidden = self._session.run(None, {"input_ids": ids, "attention_mask": mask})[0]
        pooled = (hidden * mask[..., None]).sum(1) / np.maximum(mask.sum(1, keepdims=True), 1e-9)
        return pooled / np.linalg.norm(pooled, axis=1, keepdims=True)

    def doc_probabilities(self, question: str, passages: np.ndarray) -> np.ndarray:
        """Softmax over the documents whose passage embeddings are the rows of ``passages``."""
        logits = passages @ self.embed([question], query=True)[0] / TEMPERATURE
        weights = np.exp(logits - logits.max())
        return weights / weights.sum()


@lru_cache(maxsize=1)
def get_dialect_encoder() -> DialectEncoder | None:
    if not (MODEL_DIR / "model_int8.onnx").exists():
        return None
    if importlib.util.find_spec("onnxruntime") is None or importlib.util.find_spec("tokenizers") is None:
        logger.warning("Dialect retriever found at %s but onnxruntime or tokenizers is missing; not used", MODEL_DIR)
        return None
    try:
        return DialectEncoder(MODEL_DIR)
    except Exception as exc:  # a broken model file must not take the server down
        logger.warning("Dialect retriever at %s failed to load (%s); not used", MODEL_DIR, exc)
        return None
