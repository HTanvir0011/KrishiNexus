"""Merge the writer agents' question files into the dialect-retriever dataset (TRAINING_PLAN.md section 7b).

Run with the BACKEND venv:

    cd krishinexus-os
    backend/.venv/Scripts/python training/prepare_retrieval_data.py <folder with train_*.jsonl and dev_*.jsonl>

Writes training/data/retrieval_v1/{train,dev,passages}.jsonl and stats.json. Every row is validated, exact duplicates
are dropped, dev rows that near-duplicate a train row are dropped, and any row that near-duplicates a question of the
frozen 66-probe holdout is dropped, so re-running that probe after training stays honest.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from evals.holdout_probe import HOLDOUT_PROBES  # noqa: E402
from rag.knowledge_seed import KNOWLEDGE_DOCS  # noqa: E402
from schemas.mcp_models import Crop  # noqa: E402

OUT = Path(__file__).resolve().parent / "data" / "retrieval_v1"
DOC_IDS = {d.doc_id for d in KNOWLEDGE_DOCS}
DIALECTS = {"Standard Bangla", "Rangpuri", "Sylheti", "Bogura (Varendri)", "Banglish", "English"}
KINDS = {"topical", "paraphrase", "negation", "cross_doc"}
KEYS = {"question", "gold_doc", "dialect", "kind", "crop", "district"}
NEAR_DUP = 0.5  # character 4-gram Jaccard


def grams(text: str) -> set[str]:
    t = re.sub(r"\s+", " ", text.lower()).strip()
    return {t[i:i + 4] for i in range(max(1, len(t) - 3))}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def validate(row: dict, where: str) -> dict:
    assert set(row) == KEYS, f"{where}: keys {sorted(row)}"
    assert isinstance(row["question"], str) and row["question"].strip(), f"{where}: empty question"
    assert row["gold_doc"] in DOC_IDS, f"{where}: gold_doc {row['gold_doc']}"
    assert row["dialect"] in DIALECTS, f"{where}: dialect {row['dialect']}"
    assert row["kind"] in KINDS, f"{where}: kind {row['kind']}"
    assert row["crop"] is None or row["crop"] in {c.value for c in Crop}, f"{where}: crop {row['crop']}"
    assert row["district"] is None or isinstance(row["district"], str), f"{where}: district"
    return {**row, "question": re.sub(r"\s+", " ", row["question"]).strip()}


def load(folder: Path, prefix: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(folder.glob(f"{prefix}_*.jsonl")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                rows.append({**validate(json.loads(line), f"{path.name}:{n}"), "writer": path.stem})
    return rows


def main(folder: Path) -> None:
    holdout = [grams(p.question) for p in HOLDOUT_PROBES]
    dropped: Counter[str] = Counter()

    def keep(rows: list[dict], split: str, against: list[set[str]] | None = None) -> list[dict]:
        out, seen = [], set()
        for row in rows:
            g = grams(row["question"])
            if row["question"] in seen:
                dropped[f"{split}: exact duplicate"] += 1
            elif max((jaccard(g, h) for h in holdout), default=0.0) >= NEAR_DUP:
                dropped[f"{split}: near a frozen holdout probe"] += 1
            elif against and max(jaccard(g, t) for t in against) >= NEAR_DUP:
                dropped[f"{split}: near a train row"] += 1
            else:
                seen.add(row["question"])
                out.append(row)
        return out

    train = keep(load(folder, "train"), "train")
    dev = keep(load(folder, "dev"), "dev", [grams(r["question"]) for r in train])
    passages = [{"doc_id": d.doc_id, "text": f"{d.contextual_header()}\n{d.text}"} for d in KNOWLEDGE_DOCS]

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", train), ("dev", dev), ("passages", passages)):
        (OUT / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    stats = {
        split: {"rows": len(rows), "by_doc": dict(Counter(r["gold_doc"] for r in rows)),
                "by_dialect": dict(Counter(r["dialect"] for r in rows)), "by_kind": dict(Counter(r["kind"] for r in rows)),
                "by_writer": dict(Counter(r["writer"] for r in rows))}
        for split, rows in (("train", train), ("dev", dev))
    }
    stats["dropped"] = dict(dropped)
    stats["near_duplicate_rule"] = f"character 4-gram Jaccard >= {NEAR_DUP}"
    missing = DOC_IDS - set(stats["train"]["by_doc"])
    assert not missing, f"docs with no train rows: {sorted(missing)}"
    (OUT / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
