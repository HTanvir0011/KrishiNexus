"""Storage citation of the deployed GGUF (krishi-bangla:latest = v2) with and without a node-side citation check.

The check (pre-registered in TRAINING_PLAN.md §6, "Node-side citation check") sets an answer's citation to the
retrieved passage holding the largest share of the answer's character 4-grams, if that share is at least 0.5; the
words never change. It changed no answer here, so it is not in the app; it is kept in this script to reproduce the run.

Usage: python -I citation_check.py <backend dir> dev|fresh <out.json>
  dev    the v7 validation split's storage rows (180)
  fresh  600 new storage questions: the v7 storage builder at unused indices 1,200-1,799, seed 20261113
Decoding as in the earlier local GGUF scoring: Ollama /api/generate, temperature 0, num_predict 248, seed 0.
"""
import json
import pathlib
import re
import sys
import time
import urllib.request

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
BACKEND, MODE, OUT = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
sys.path.insert(0, BACKEND)
from edge_node.ollama_local import _storage_qa, build_sft_dataset  # noqa: E402
from edge_node.sft_wordings import SENTENCE_TOPICS  # noqa: E402
from rag.hybrid_retriever import SemanticChunker  # noqa: E402
from rag.knowledge_seed import KNOWLEDGE_DOCS  # noqa: E402

HOST, MODEL = "http://127.0.0.1:11434", "krishi-bangla:latest"
QUOTE_MIN_SHARE = 0.5
CITATION_RE = re.compile(r"\s*\[([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\]")   # the training notebook's citation pattern
RETRIEVAL_RE = re.compile(r'<tool_result name="crag_retrieval">(.*?)</tool_result>', re.S)


def citations(text):
    return set(CITATION_RE.findall(text))


def char_grams(text, n=4):
    flat = " ".join(text.lower().split())
    return {flat[k:k + n] for k in range(len(flat) - n + 1)}


def shares(answer, prompt):
    grams = char_grams(CITATION_RE.sub("", answer))
    passages = json.loads(RETRIEVAL_RE.search(prompt).group(1))
    return {p["doc_id"]: len(grams & char_grams(p["text"])) / len(grams) for p in passages} if grams else {}


def cite_quoted_passage(answer, prompt):
    share = shares(answer, prompt)
    if not share:
        return answer
    best = max(share, key=share.__getitem__)
    if share[best] < QUOTE_MIN_SHARE or citations(answer) == {best}:
        return answer
    return f"{CITATION_RE.sub('', answer).strip()} [{best}]"


sentence_of = lambda response: response.split(" [")[0]
seen_by_v2 = {sentence_of(e.response) for e in build_sft_dataset(5) if e.split == "train" and e.category == "storage_qa"}
if MODE == "dev":
    rows = [(e.example_id, e.instruction, e.response) for e in build_sft_dataset(7) if e.split == "val" and e.category == "storage_qa"]
else:
    sentences = [(d.doc_id, d.title, SENTENCE_TOPICS[d.doc_id][k][0], d.crops[0] if d.crops else "ফসল", s)
                 for d in KNOWLEDGE_DOCS for k, s in enumerate(SemanticChunker.sentences(d.text))]
    rng = np.random.default_rng(20261113)
    rows = [(f"FRESH-{n:04d}", e.instruction, e.response)
            for n, e in enumerate((_storage_qa(i, sentences, rng, 7) for i in range(1_200, 1_800)), 1)]
    assert len({sentence_of(r[2]) for r in rows}) == 60 and len(rows) == 600


def generate(prompt):
    req = urllib.request.Request(HOST + "/api/generate", json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0, "num_predict": 248, "seed": 0}}).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["response"]


started, results = time.time(), []
for rid, prompt, gold in rows:
    model = generate(prompt)
    checked = cite_quoted_passage(model, prompt)
    assert CITATION_RE.sub("", checked).strip() == CITATION_RE.sub("", model).strip(), "the check changed words"
    results.append({"id": rid, "seen_by_v2": sentence_of(gold) in seen_by_v2, "gold": gold, "model": model, "checked": checked,
                    "model_ok": citations(model) == citations(gold), "checked_ok": citations(checked) == citations(gold),
                    "best_share": round(max(shares(model, prompt).values(), default=0.0), 3)})


def rate(rs, key):
    return round(sum(r[key] for r in rs) / len(rs), 4) if rs else None


slices = {"all": results, "never_seen_by_v2": [r for r in results if not r["seen_by_v2"]],
          "seen_by_v2": [r for r in results if r["seen_by_v2"]]}
summary = {name: {"rows": len(rs), "sentences": len({sentence_of(r["gold"]) for r in rs}),
                  "citation_without_check": rate(rs, "model_ok"), "citation_with_check": rate(rs, "checked_ok")}
           for name, rs in slices.items()}
summary["check"] = {
    "quote_min_share": QUOTE_MIN_SHARE, "changed": sum(r["checked"] != r["model"] for r in results),
    "fixed": sum(r["checked_ok"] and not r["model_ok"] for r in results),
    "broke": sum(r["model_ok"] and not r["checked_ok"] for r in results),
    "below_share_unchanged": sum(r["best_share"] < QUOTE_MIN_SHARE for r in results),
    "minutes": round((time.time() - started) / 60, 1), "model": MODEL, "mode": MODE,
}
OUT.write_text(json.dumps({"summary": summary, "rows": results}, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(summary, indent=1))
