"""Export a krishi-bangla SFT dataset to chat-format JSONL, re-verifying the split on every run.

Run with the BACKEND venv (it imports the backend's deterministic generators):

    cd krishinexus-os
    backend/.venv/Scripts/python training/prepare_data.py [--version 5]

--version 4 rebuilds the data the deployed model was trained on; 5 (the default) is prompts v5, freely worded
questions (TRAINING_PLAN.md section 6). Writes training/data/{train,val,test}.jsonl plus split_report.json. Each line
is TRL-ready: {"messages": [{"role": "system"|"user"|"assistant", ...}], "example_id", "category", "dialect", "subset"}
where subset marks the held-out generalisation families inside test:
iid | ood_dialect | ood_months | ood_upazila, plus ood_wording in v5.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from edge_node.ollama_local import (  # noqa: E402
    NEGOTIATION_HOLDOUT_DIALECT,
    SftExample,
    build_sft_dataset,
    dataset_stats,
    subset_of,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
# Must match the Ollama Modelfile SYSTEM line in lora_adapter_spec, so training and deployment agree.
SYSTEM_PROMPT = "You are KrishiNexus, a Bangla-speaking agricultural market and storage advisor."


def assert_no_leakage(examples: tuple[SftExample, ...], version: int) -> tuple[int, int]:
    """Re-verify, on every export, that no family straddles splits. Fails loudly rather than train on a leak."""
    response_families: dict[tuple[str, str], set[str]] = {}
    negotiation_cells: dict[tuple[str, ...], set[str]] = {}
    for e in examples:
        if " | wording heldout-" in e.source:
            assert e.split == "test" and subset_of(e) == "ood_wording", f"{e.example_id}: held-out wording outside test"
        if e.category == "market_negotiation":
            if e.dialect == NEGOTIATION_HOLDOUT_DIALECT:
                assert e.split == "test", f"{e.example_id}: OOD dialect outside test"
                continue
            crop, district, day = e.source.split("market_prices(")[1].split(")")[0].split(", ")
            # v4 cells are (dialect, crop, district); v5 picks the wording after the split, so its cells are market cells.
            cell = (e.dialect, crop, district) if version < 5 else (crop, district, str((int(day[5:7]) - 1) // 3))
            negotiation_cells.setdefault(cell, set()).add(e.split)
        else:
            response_families.setdefault((e.category, e.response), set()).add(e.split)
    straddling = [k for k, splits in (response_families | negotiation_cells).items() if len(splits) > 1]
    assert not straddling, f"families straddle splits: {straddling[:3]}"
    return len(response_families), len(negotiation_cells)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", type=int, choices=(4, 5), default=5, help="SFT prompt version to export")
    version = parser.parse_args().version
    examples = build_sft_dataset(version)
    families, cells = assert_no_leakage(examples, version)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    counts: Counter[tuple[str, str]] = Counter()
    handles = {split: (DATA_DIR / f"{split}.jsonl").open("w", encoding="utf-8", newline="\n") for split in ("train", "val", "test")}
    try:
        for e in examples:
            counts[(e.split, e.category)] += 1
            handles[e.split].write(json.dumps({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": e.instruction},
                    {"role": "assistant", "content": e.response},
                ],
                "example_id": e.example_id, "category": e.category, "dialect": e.dialect,
                "subset": subset_of(e) if e.split == "test" else "iid",
            }, ensure_ascii=False) + "\n")
    finally:
        for handle in handles.values():
            handle.close()

    stats = dataset_stats(examples, version)
    report = {
        "prompt_version": version,
        "splits": {split: sum(n for (s, _), n in counts.items() if s == split) for split in ("train", "val", "test")},
        "by_split_and_category": {f"{s}/{c}": n for (s, c), n in sorted(counts.items())},
        "test_subsets": dict(Counter(subset_of(e) for e in examples if e.split == "test")),
        "holdouts": stats.holdouts,
        "leakage_check": f"passed: {families} response families and {cells} negotiation cells, none straddling splits",
        "jsonl_sha256": stats.jsonl_sha256,
        "generator": stats.generator,
        "system_prompt": SYSTEM_PROMPT,
    }
    (DATA_DIR / "split_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["splits"]), json.dumps(report["test_subsets"]), "->", DATA_DIR)


if __name__ == "__main__":
    main()
