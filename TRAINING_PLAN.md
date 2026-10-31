# TRAINING_PLAN.md — datasets, training and honest evaluation (Phase 9)

Written 2026-10-29. Scope set by the user the same day: **build the plan, the proper splits and the honest
evaluations now; do not run GPU training yet** (zero model downloads). Everything below that carries a number was
measured on this machine today; everything marked *documented, not executed* is a recipe verified by research against
2026-current sources plus an adversarial review, but has not run. Hardware on hand: RTX 3050 Laptop 4 GB VRAM (driver
555.97), 15.7 GB RAM, Python 3.12.10 for training venvs (the backend venv runs 3.14, where the CUDA wheel matrix is thin).

Rubric tie-in (the congress's 110-point AI Depth Score): **Fine-tuning** and **Multimodal** are the two Partial rows in
`/docs`; **Evaluation** is Live but was only as strong as its weakest test set. This phase strengthens Evaluation now
and leaves Fine-tuning/Multimodal ready to flip with one documented run each.

---

## 1. Dataset inventory

| Dataset | Size | Source | State |
|---|---|---|---|
| `krishi-bangla-lora-v1` SFT | 3,200 pairs: negotiation 1,200 · storage_qa 800 · arbitrage 700 · flood 500 | deterministic, generated from the repo's own engines (`edge_node/ollama_local.build_sft_dataset`, seed 20261022) | split v2 shipped (section 2) |
| RAG curated eval set | 19 questions | `evals/regression_suite.RAG_EVAL_SET`, author-written | precision 1.00 — but see section 6 |
| RAG blind holdout probe | 66 questions | **new**, `evals/holdout_probe.py` | measured today: top-1 0.50 |
| Regression suite | 100 seeded cases | `evals/regression_suite` | 100/100 |
| Crop-defect images | none in repo | public candidates found (section 7) | YOLO not trainable until acquired |

The SFT data is synthetic: it distils the deterministic stack (DAM curves, ΔΠ breaker, flood model, knowledge base)
into pairs a small on-device model can learn. That is the honest framing — the adapter learns to *imitate the
deterministic policy offline*, and the test splits measure how well, including on families it never saw.

## 2. SFT split v2 — shipped and verified

The old split ("every 10th example is eval") leaked: templates cycle with the index, so almost every eval example
shared its exact template — and for storage_qa its exact response sentence — with train. Replaced in
`build_sft_dataset` by a family-aware three-way split (`_family_split`): whole families share one split, and three
OOD families are held out of training entirely.

| Rule | Detail |
|---|---|
| OOD: dialect | every Chittagonian negotiation example → test (240) |
| OOD: parameter band | every arbitrage example with holding_months = 7 → test (117) |
| OOD: geography | every flood example for the খালিয়াজুরী (Khaliajuri) haor → test (33); never the Tahirpur demo upazila |
| IID families | negotiation: whole (dialect, crop, district) cells; storage_qa/arbitrage/flood: whole identical-response groups; hashed 10% test / 10% val via `stable_unit` |
| Flood responses | now name the haor, so identical alert texts can no longer collide across upazilas |

Measured counts: **train 2,301 · val 239 · test 660** (test = 270 IID + 240 ood_dialect + 117 ood_months +
33 ood_upazila). Leakage assertions — no response family and no negotiation cell straddles splits (1,096 families,
56 cells) — run inside `training/prepare_data.py` on every export, which writes `training/data/{train,val,test}.jsonl`
in TRL chat format plus `split_report.json`. Adversarial review: not refuted; one caveat to carry into reporting —
19 of the 42 IID flood test responses are verbatim duplicates *of each other* (rounding collisions), so flood IID is
effectively ~23 unique outcomes.

## 3. Base model decision (for when training runs)

**Qwen2.5-1.5B-Instruct**, retargeted from the spec's 7B. It is the only candidate that is simultaneously Apache-2.0
and ungated (no HF account on a kiosk), small enough for this card (NF4 QLoRA peak ≈ 2.2–2.6 GB of 4 GB at seq 512,
including the 151K-vocab logits spike; Windows reserves 300–600 MB of the same VRAM for the desktop), and strong on
Bengali (Qwen2 tokenizer ≈ 0.94 chars/token on Bengali, best of the open tokenizers surveyed). Rejected: Qwen2.5-3B
(research licence, non-commercial; ~3.7–4.2 GB peak — OOM-prone) and Llama-3.2-3B (gated, same size problem);
Gemma-2-2b (gated, no system role, huge tied embedding). Upgrade path if dialect quality disappoints:
`hishab/titulm-gemma-2-2b-v1.1` (Bangla continued-pretrain), licence-gated and seq ≤ 256 on this card.
The 7B spec remains the documented upazila-hub tier; `lora_adapter_spec` keeps rank 16 / alpha 32 / the 7 target
modules. Retarget checklist when training starts: `base_model`, `base_quantized_tag` → `qwen2.5:1.5b-instruct-q4_K_M`,
dims in the `per_layer` maths (hidden 1536, intermediate 8960, kv_dim 256), and the frontend/docs lines naming 7B.

## 4. Training recipe (documented, not executed)

Environment (venv already created at `training/.venv`, Python 3.12.10 — empty until the go-ahead):

```bash
training/.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cu128   # ~2.8 GB
training/.venv/Scripts/pip install "transformers>=5" "trl>=1.16,<2" "peft>=0.17" "accelerate>=1.0" "datasets>=3.0" "bitsandbytes>=0.50.2"
training/.venv/Scripts/python -c "import torch, bitsandbytes; print(torch.cuda.get_device_name(0))"
```

Windows notes that the research and its adversarial pass agreed on: bitsandbytes ships official win_amd64 wheels and
its current CUDA builds pair with **cu128** torch, not cu126; upgrade the NVIDIA driver from 555.97 to a 570+ release
first (five minutes, removes the one "unsupported" risk); no triton and no flash-attn on Windows — keep
`attn_implementation="sdpa"` and never enable `torch_compile`; `dataloader_num_workers=0`; skip unsloth (its Windows
setup costs more than it saves at 1.5B scale). Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` and close
browsers before training.

TRL is 1.x now and the 2024-era tutorials are stale. The load-bearing API facts: `SFTConfig(max_length=512)` (the old
`max_seq_length` is gone); pass the tokenizer as `processing_class`; pass
`quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)`
and `peft_config=LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=[the 7 from lora_adapter_spec])`
directly to `SFTTrainer` (no manual `prepare_model_for_kbit_training`); add
`model_init_kwargs={"dtype": torch.bfloat16}` so the tied embedding loads bf16 not fp32; feed prompt-completion rows
(`{"prompt": [user turn], "completion": [assistant turn]}` from the exported JSONL messages) so completion-only loss
applies by default. Hyper-parameters from the spec: lr 2e-4 cosine, 3 epochs, batch 1 × grad-accum 16,
`optim="paged_adamw_8bit"`, bf16 (Ampere), gradient checkpointing on, eval on the val split per ~50 steps, keep the
best checkpoint. Expected wall-clock: **1.5–3 h** for 3 epochs over 2,301 examples (~430 optimizer steps), plus ~10 min
model download (~3 GB). Training must only ever read `train.jsonl` + `val.jsonl`; `test.jsonl` is opened once, by the
eval script, after the final checkpoint is chosen.

## 5. Deployment to the kiosk (documented, not executed)

Ollama ≥ 0.34.2 **removed LoRA adapter loading** ("LoRA adapters are no longer supported", PR #14969) and create-time
quantization with it — the repo's old `ADAPTER` Modelfile was dead on current Ollama, and
`lora_adapter_spec.gguf_export_command` / `ollama_modelfile` were corrected in code today to the merge route:

1. `merge_and_unload()` the adapter into the bf16 base (RAM peak ≈ 5 GB at 1.5B).
2. `python llama.cpp/convert_hf_to_gguf.py merged/ --outtype f16` (clone llama.cpp, `pip install -r
   requirements/requirements-convert_hf_to_gguf.txt`; the converter streams tensors).
3. `llama-quantize.exe krishi-bangla-f16.gguf krishi-bangla-q4_K_M.gguf Q4_K_M` — binary from the llama.cpp release
   assets (`llama-b<NNNN>-bin-win-cpu-x64.zip`; releases/latest now only lists `nightly-tag.txt`, fetch it first to
   learn the tag).
4. Modelfile: `FROM ./krishi-bangla-q4_K_M.gguf` + the SYSTEM line (same one `training/prepare_data.py` trains with);
   the GGUF carries Qwen's chat template.

Disk needed ≈ 11 GB free at 1.5B. Known quality caveat: the adapter trains against an NF4 base but merges into bf16
and re-quantizes — a small delta, which the eval report (section 6) must measure on the test split, not assume away.

## 6. Adapter evaluation (deterministic, no LLM judge)

A script, not a vibe: every gold value is **recomputed by replaying the example's inputs through the same engines that
generated it** (`market_prices`, `CIRCUIT_BREAKER`, `breach_probability`), generation is greedy (temperature 0, fixed
seed), and each metric is computed twice — base model vs adapter — on identical prompts.

| Metric (test split) | Rule | Target |
|---|---|---|
| negotiation decision accuracy | fair/unfair classification parsed from the Bangla response vs recomputed gold (fair ⇔ offer ≥ 0.95 × grower) | ≥ 0.90 |
| negotiation price fidelity | grower/wholesale/retail integers present (Bangla digits normalised) | ≥ 0.85 |
| arbitrage verdict exact match | one of the five verdict tokens, vs recomputed verdict | ≥ 0.90 |
| arbitrage trace fidelity | storage/spot/ΔΠ values within max(1 Tk, 0.5%) | ≥ 0.80 |
| flood alert accuracy | RED/ORANGE/YELLOW/GREEN vs recomputed `alert_rule` | ≥ 0.90 |
| flood probability error | parsed % within ±2 points (plus MAE) | ≥ 0.85 |
| storage citation accuracy | exactly the gold `[doc-id]` cited | ≥ 0.90 |
| storage chrF | character n-gram F (n 1–6, β 2), pure-Python, citation stripped | ≥ 60 |
| base vs adapter delta | every metric, both models, same decoding | > 0 everywhere |

Report **IID and the three OOD subsets separately** (flood IID with the duplicate-response caveat), plus truncation
rate at max_length. The report lands as JSON at `backend/models/lora/krishi-bangla-lora-v1/eval_report.json`;
`GET /edge/local-models` surfaces it only when the file exists — scores are never hard-coded, and `status` flips to
`adapter_present` only when real weights exist (both per the AGENTS.md integrity rules).

## 7. Retrieval: the blind holdout probe — measured today

66 new farmer questions in `evals/holdout_probe.py`, written by six independent agents that each read only a third of
the knowledge docs, across six surface forms plus negation and cross-doc traps (provenance and the honesty caveat are
in the module docstring). Run: `cd backend && .venv/Scripts/python -m evals.holdout_probe`.

| Slice | n | top-1 gold | top-3 gold |
|---|---|---|---|
| **all probes** | 66 | **0.500** | **0.848** |
| topical | 36 | 0.611 | 0.889 |
| paraphrase | 18 | 0.389 | 0.778 |
| negation | 6 | 0.500 | 0.833 |
| cross_doc | 6 | 0.167 | 0.833 |
| English | 11 | 0.909 | — |
| Standard Bangla | 13 | 0.462 | — |
| Bogura (Varendri) | 9 | 0.444 | — |
| Banglish | 14 | 0.429 | — |
| Rangpuri | 10 | 0.400 | — |
| Sylheti | 9 | 0.333 | — |

Reading: the curated set's 1.00 does not generalise — the whitepaper and MEMORY now carry both numbers side by side.
The gold doc is in the top-3 85% of the time, so the gap is mostly *ranking and intent routing*, concentrated in
dialect and Banglish phrasing (English works because the intent triggers are English words). Improvement protocol, in
integrity order: (1) this 66-probe set is **frozen as test** — never tune the lexicon or intent rules against it;
(2) iterate on separately written dev paraphrases (the misses list names the failing doc pairs: storage-conditions vs
price, blight vs pesticide-safety, post-harvest-loss vs syndicate); (3) after changes, generate a **fresh** blind
batch the same way and report that. Target: top-1 ≥ 0.75 on a fresh batch before the showcase.

## 8. YOLO `yolov11n-krishi-bd-v2.1` (planned, ~1.5 working days, not started)

Primary dataset: **Diamant Potato Dataset** (Mendeley, DOI 10.17632/4vty9rz7zw.1, CC BY 4.0, 4,110 images —
photographed at three Dhaka markets, which fits the krishi-bd story exactly). Optional supplement: Roboflow
"Potato inspection" (techno-soft, CC BY 4.0 pending manual confirmation on the page). Train the **three visual
classes** (uniform_A ← clean instances; minor_bruise ← mechanical damage; fungal_blight ← scab/rot) and derive
`undersized` geometrically from bbox area, as the classical grader already does — no public dataset labels it.
Recipe: masks → YOLO bboxes, 80/10/10 split by image, `yolo detect train model=yolo11n.pt imgsz=640 batch=8` on the
3050 (4–6 GPU-hours), export and wire via the existing `KNX_YOLO_WEIGHTS`; `inference_backend` then honestly reports
`ultralytics-yolo`. Until weights exist the label stays `classical-cv`.

## 9. Timeline to the showcase (26 Dec, ~8 weeks)

Week 1: driver update, pip install, LoRA train + eval report (one evening; needs the user's go-ahead for ~6 GB of
downloads). Week 2: merge → GGUF → Ollama, base-vs-adapter table live in `/docs`. Weeks 2–3: YOLO dataset + training.
Week 4: retrieval dialect/rerank fixes + fresh blind batch. Weeks 5–8: Docker-host run, Whisper STT
(`KNX_WHISPER_MODEL`, faster-whisper small — currently untested), rehearsal, buffer. Nothing here blocks the demo:
every artifact stays honestly labelled until its real run exists.
