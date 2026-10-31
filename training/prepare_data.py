"""Export the krishi-bangla-lora-v1 SFT dataset to chat-format JSONL, re-verifying the split on every run.

Run with the BACKEND venv (it imports the backend's deterministic generators):

    cd krishinexus-os
    backend/.venv/Scripts/python training/prepare_data.py

Writes training/data/{train,val,test}.jsonl plus split_report.json. Each line is TRL-ready:
{"messages": [{"role": "system"|"user"|"assistant", ...}], "example_id", "category", "dialect", "subset"}
where subset marks the held-out generalisation families inside test: iid | ood_dialect | ood_months | ood_upazila.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from edge_node.ollama_local import (  # noqa: E402
    ARBITRAGE_HOLDOUT_MONTHS,
    NEGOTIATION_HOLDOUT_DIALECT,
    SftExample,
    build_sft_dataset,
    dataset_stats,
    flood_holdout_name_bn,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
# Must match the Ollama Modelfile SYSTEM line in lora_adapter_spec, so training and deployment agree.
SYSTEM_PROMPT = "You are KrishiNexus, a Bangla-speaking agricultural market and storage advisor."
_MONTHS_RE = re.compile(r"(\d+) মাস পর")


def subset_of(example: SftExample) -> str:
    """Which test family an example belongs to; 'iid' for everything that is not an OOD holdout."""
    if example.category == "market_negotiation" and example.dialect == NEGOTIATION_HOLDOUT_DIALECT:
        return "ood_dialect"
    if example.category == "arbitrage_math":
        months = _MONTHS_RE.search(example.instruction)
        if months and int(months.group(1)) == ARBITRAGE_HOLDOUT_MONTHS:
            return "ood_months"
    if example.category == "flood_harvest" and example.instruction.startswith(flood_holdout_name_bn()):
        return "ood_upazila"
    return "iid"


def assert_no_leakage(examples: tuple[SftExample, ...]) -> tuple[int, int]:
    """Re-verify, on every export, that no family straddles splits. Fails loudly rather than train on a leak."""
    response_families: dict[tuple[str, str], set[str]] = {}
    negotiation_cells: dict[tuple[str, str, str], set[str]] = {}
    for e in examples:
        if e.category == "market_negotiation":
            if e.dialect == NEGOTIATION_HOLDOUT_DIALECT:
                assert e.split == "test", f"{e.example_id}: OOD dialect outside test"
                continue
            crop, district = e.source.split("market_prices(")[1].split(", ")[:2]
            negotiation_cells.setdefault((e.dialect, crop, district), set()).add(e.split)
        else:
            response_families.setdefault((e.category, e.response), set()).add(e.split)
    straddling = [k for k, splits in (response_families | negotiation_cells).items() if len(splits) > 1]
    assert not straddling, f"families straddle splits: {straddling[:3]}"
    return len(response_families), len(negotiation_cells)


def main() -> None:
    examples = build_sft_dataset()
    families, cells = assert_no_leakage(examples)
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

    stats = dataset_stats(examples)
    report = {
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
    print(json.dumps(report["splits"]), "->", DATA_DIR)


if __name__ == "__main__":
    main()
