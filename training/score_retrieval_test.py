"""Score the fresh blind batch once for the frozen dialect retriever (TRAINING_PLAN.md section 7b).

Run with the BACKEND venv, after the model is installed in backend/models/retrieval/:

    cd krishinexus-os/backend
    .venv/Scripts/python ../training/score_retrieval_test.py <folder with fresh_*.jsonl> <report.json>

Scores the fresh batch through the full CRAG pipeline without the model (blend weight 0) and with it (the frozen
weight), re-runs the frozen 66-question probe once with the model, and gives every fresh question its nearest
training question by character 4-gram Jaccard similarity.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

TRAINING = Path(__file__).resolve().parent
sys.path.insert(0, str(TRAINING))
sys.path.insert(0, str(TRAINING.parent / "backend"))

import rag.hybrid_retriever as hr  # noqa: E402
from evals.holdout_probe import HoldoutProbe, run_holdout_probe  # noqa: E402
from prepare_retrieval_data import grams, jaccard, validate  # noqa: E402

FROZEN_WEIGHT = 0.5  # chosen on dev before the batch was written
hr.DIALECT_WEIGHT = FROZEN_WEIGHT


async def main(folder: Path, out: Path) -> None:
    assert hr.get_retriever().dialect is not None, "install the model in backend/models/retrieval/ first"
    rows = [validate(json.loads(line), f"{p.name}:{n}") for p in sorted(folder.glob("fresh_*.jsonl"))
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if line.strip()]
    train = [json.loads(line)["question"] for line in
             (TRAINING / "data" / "retrieval_v1" / "train.jsonl").read_text(encoding="utf-8").splitlines()]
    train_grams = [grams(q) for q in train]
    nearest = [max(jaccard(grams(r["question"]), t) for t in train_grams) for r in rows]
    probes = tuple(HoldoutProbe(**{k: r[k] for k in ("question", "district", "crop", "gold_doc", "dialect", "kind")})
                   for r in rows)

    report: dict[str, object] = {"fresh_questions": len(rows), "frozen_blend_weight": FROZEN_WEIGHT,
                                 "nearest_train_jaccard": {"max": round(max(nearest), 3),
                                                           "mean": round(sum(nearest) / len(nearest), 3),
                                                           "at_least_0.5": sum(j >= 0.5 for j in nearest)}}
    for name, weight in (("fresh_without_model", 0.0), ("fresh_with_model", FROZEN_WEIGHT)):
        hr.DIALECT_WEIGHT = weight
        report[name] = (await run_holdout_probe(probes)).model_dump()
    hr.DIALECT_WEIGHT = FROZEN_WEIGHT
    report["frozen_probe_with_model"] = (await run_holdout_probe()).model_dump()
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for name in ("fresh_without_model", "fresh_with_model", "frozen_probe_with_model"):
        r = report[name]
        print(name, "top1", r["top1_gold"], "top3", r["top3_gold"], {d: v["top1"] for d, v in r["by_dialect"].items()})
    print("nearest train Jaccard", report["nearest_train_jaccard"])


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2])))
