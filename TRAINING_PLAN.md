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

**Kaggle / T4 addendum (2026-11-06).** The runnable version is `training/kaggle/krishinexus_lora_kaggle.ipynb`. It
trains, scores base vs adapter, and exports the GGUF; setup is in `training/kaggle/KAGGLE_DATASET.md`. Re-checking the
library sources for it found four things:
- TRL 1.17.1 does not call `prepare_model_for_kbit_training`. Instead it casts a quantized model's trainable weights
  to bf16 in `SFTTrainer.__init__`. A T4 (sm_75) has no bf16, so the notebook trains in fp16 and recasts the adapter
  weights to fp32 after building the trainer. On Ampere and newer it keeps TRL's bf16.
- transformers 5.22 removed `warmup_ratio`, so the notebook uses `warmup_steps`.
- Current bitsandbytes CUDA 12.8+ wheels drop sm_60, so the notebook refuses a P100 and asks for a T4.
- llama.cpp's converter pins `torch==2.11.0` (CPU) and `transformers==4.57.6`, so it is installed into a side folder
  rather than the training environment.

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

**Shipped into the app (2026-11-09).** The v4 run's outputs were downloaded from Kaggle into the git-ignored
`backend/models/lora/`:

| File | Size | SHA-256 |
|---|---|---|
| `krishi-bangla-q4_K_M.gguf` | 986,048,160 bytes | `372ddc112198849dd8173ae23031617e74c181ddd14fd354fd44244a72a0b2ab` |
| `krishi-bangla-lora-v1/adapter_model.safetensors` | 73,911,112 bytes | `aec4ce8155750dfb4c31e95c8c9aa7dcd15789fc420706d6a14fe2201b061f01` |

What changed in the code:
- **Registry.** `LOCAL_MODELS` gained `krishi-bangla-1.5b` (Ollama tag `krishi-bangla:latest`). The 7B entry no longer
  claims the adapter. `lora_adapter_spec` follows the section 3 retarget checklist (1.5B dims, 18.5 M trainable
  parameters, max length 1024). It reads the measured scores from the adapter's own `eval_report.json`, only when the
  adapter is installed.
- **Grounding.** `ground_prompt` gives each question the tool result the model was trained to read:
  - a named haor gets the flood tool;
  - a store-or-sell question gets the ΔΠ breaker;
  - a crop with an offer gets today's DAM spread;
  - anything else gets the top three retrieved passages.
  The check strips the tool results from all 641 test questions and grounds them again. For the 191 arbitrage and 70
  flood questions it rebuilds the training payload exactly; for every negotiation and storage question it picks the
  right tool. That makes 0 mismatches. The model is decoded greedily, as it was scored.
- **Offline voice.** A simulated blackout now cuts only the internet, so a runtime on the kiosk still answers. Offline
  voice requests ask the fine-tuned model, and all five voice presets complete with grounded prompts.
- **`/docs`.** The "Ollama & LoRA" tester shows the measured score table and asks the model a sample question. Its
  reply is labelled as the fallback until a runtime answers. The Fine-tuning row of the depth matrix is now "Live".

**The deployed GGUF, scored (2026-11-09): it fails the flood-alert target.** Ollama 0.40.15 serves
`krishi-bangla:latest` on the dev PC's RTX 3050 4 GB at a median of 81 tokens/s, using 1.1 GB of VRAM. All 641 test
questions went through it as the app sends them (Modelfile SYSTEM line, greedy decoding) and were scored by the
training notebook's own scorer. Raw report: `training/runs/local-ollama-2026-11-09/eval_report.json`.

| Metric | Target | Training run (4-bit NF4 + adapter) | Deployed Q4_K_M GGUF |
|---|---|---|---|
| negotiation decision accuracy | 0.90 | 0.909 | 0.903 |
| negotiation price fidelity | 0.85 | 0.985 | 0.997 |
| arbitrage verdict exact match | 0.90 | 1.000 | 0.911 |
| arbitrage trace fidelity | 0.80 | 1.000 | 0.963 |
| flood alert accuracy | 0.90 | 1.000 | **0.757** |
| flood probability within ±2 pts | 0.85 | 1.000 | 1.000 |
| storage citation accuracy | 0.90 | 0.925 | 0.950 |
| storage chrF | 60 | 93.28 | 95.49 |

Only 272 of 641 deployed answers (42%) are identical to the training run's. The losses are real decisions, not a
parsing problem:
- 17 flood alerts sit on the wrong side of a band edge, e.g. 29% called GREEN instead of YELLOW and 64% called RED
  instead of ORANGE. Some flood answers are garbled.
- 14 store-or-sell answers say BLOCK where the spot price is above the cost floor (gold: ALLOW_STORAGE).

There are two suspects, and section 5 already warned about the second:
- Q4_K_M quantisation of a 1.5B model.
- The merge itself: the adapter learned against the NF4 base, but was merged into the bf16 base.

`training/kaggle/krishinexus_lora_export_kaggle.ipynb` re-exports the adapter as A-Q8_0 (bf16 merge), B-Q8_0 (merged
into the de-quantised NF4 base) and B-Q4_K_M. It scores each the same way. `/edge/local-models` now serves the
deployed model's scores as `deployed_eval_summary` (from `backend/models/lora/gguf_eval_report.json`), and the `/docs`
tester shows them beside the training run's.

**Re-exports, scored (Kaggle T4, Ollama 0.40.15, private kernel `krishinexus-lora-gguf-export` v2): the merge was the
cause.** Version 1 couldn't install Ollama because Kaggle's image lacks `zstd`; version 2 installs it first.

| Metric (test) | Target | Training run | Shipped Q4_K_M (bf16 merge) | A-Q8_0 (bf16 merge) | **B-Q8_0 (NF4 merge)** | B-Q4_K_M (NF4 merge) |
|---|---|---|---|---|---|---|
| arbitrage verdict | 0.90 | 1.000 | 0.911 | 0.9005 | **1.000** | 0.393 |
| arbitrage trace | 0.80 | 1.000 | 0.963 | 1.000 | **1.000** | 0.351 |
| flood alert | 0.90 | 1.000 | 0.757 | 0.957 | **1.000** | 0.671 |
| flood within ±2 pts | 0.85 | 1.000 | 1.000 | 1.000 | **1.000** | 0.957 |
| negotiation decision | 0.90 | 0.909 | 0.903 | 0.924 | **0.912** | 0.700 |
| negotiation prices | 0.85 | 0.985 | 0.997 | 0.997 | **0.979** | 0.750 |
| storage chrF | 60 | 93.28 | 95.49 | 95.49 | **93.28** | 93.28 |
| storage citation | 0.90 | 0.925 | 0.950 | 0.950 | **0.925** | 0.925 |

What this shows:
- Merging into the de-quantised NF4 weights the adapter trained against (B) reproduces the training run at Q8_0.
- Q4_K_M on top of that merge collapses: two quantisation steps compound.
- Both Q8_0 exports meet every target.

**Shipped: B-Q8_0** (1,646,572,704 bytes, SHA-256 `7c0e7e66bf9c11ade7b9c65dba7f1d112a5976be4fd34a43f72c7ed45d99ab75`).
- The user approved downloading it if it passed.
- The choice rests on construction, not on the best test number: B uses the weights the adapter was trained with.
  The test only confirms it.
- B's smallest margin over a target is 0.012. A-Q8_0 clears the arbitrage verdict by only 0.0005.
- On Kaggle it decodes at about 84 tokens/s against 109 for Q4_K_M, and it needs about 2.2 GB of the RTX 3050's 4 GB.

The training notebook now exports this way by default: an NF4 merge, then a direct `--outtype q8_0` conversion with
no llama.cpp build.

**B-Q8_0 re-scored on the deployment machine (RTX 3050 4 GB, Ollama 0.40.15, 2026-11-09): meets every target.**
- arbitrage 1.000 / 1.000; flood 1.000 / 1.000; negotiation decision 0.915, prices 0.979; storage chrF 93.28,
  citation 0.925.
- 626 of 641 answers (97.7%) are identical to the training run's, against 42% for the old Q4_K_M.
- The only difference from the Kaggle T4 score of the same file is negotiation (0.915 against 0.912, plus one
  unparsed answer): floating-point drift between GPUs under greedy decoding.
- Median 56 tokens/s, 1,745 MB of VRAM, 28.5 min for the split.
- This report is installed as `backend/models/lora/gguf_eval_report.json` (served as `deployed_eval_summary`) and
  recorded in `training/runs/local-ollama-2026-11-09-q8/`.

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

**Target caveat (measured 2026-11-06).** A prompt-blind baseline built from train alone already scores 0.942
negotiation decision accuracy and 1.000 storage citation accuracy on the full test split, so those two targets are met
without a model. The reasons:
- only 22 of 380 test offers are fair;
- every storage test question also occurs in train, with an answer from the same document.

The Kaggle notebook therefore also reports balanced accuracy and the baseline column.

**Prompts v3 (2026-11-07).** Two inputs the answers depend on used to be missing from the questions:
- the negotiation market and date;
- the flood month, which changes 11 of the 75 test alerts.

Both now appear in the questions. Replaying every question through the engines reproduces its answer: 1,200/1,200
negotiation and 500/500 flood rows. Answers, split membership, subsets and dialects are byte-identical to v2, and the
baselines are unchanged. *Known limitations* in `training/kaggle/KAGGLE_DATASET.md` lists what remains.

**First measured run (Kaggle T4, 2026-11-08): fails its targets.**

Run setup:
- Private Kaggle kernel `taksimulhasandip/krishinexus-bangla-lora-training`, version 1, on data `2ad09dcf…9825`.
- 3 epochs (432 steps) in 35.6 min, fp16.
- The Q4_K_M GGUF exported without errors.
- Raw outputs are in `training/runs/kaggle-t4-2026-11-08/`: `eval_report.json`, `run_manifest.json`, `training_log.json`.

Results on the full 660-row test split with greedy decoding:

| Metric | Target | Adapter | Base | Prompt-blind baseline |
|---|---|---|---|---|
| negotiation decision accuracy | 0.90 | 0.942 | 0.116 | 0.942 |
| negotiation balanced accuracy | — | 0.500 | 0.083 | 0.500 |
| negotiation price fidelity | 0.85 | 0.005 | 0.000 | 0.000 |
| arbitrage verdict exact match | 0.90 | 0.211 | 0.000 | 0.560 |
| arbitrage trace fidelity | 0.80 | 0.000 | 0.000 | 0.000 |
| flood alert accuracy | 0.90 | 0.560 | 0.000 | 0.680 |
| flood probability within ±2 pts | 0.85 | 0.200 | 0.000 | 0.000 |
| flood probability MAE, pts | — | 23.54 (n 63) | — | — |
| storage citation accuracy | 0.90 | 0.051 | 0.000 | 1.000 |
| storage chrF | 60 | 14.64 | 0.29 | 19.47 |

The adapter beats the base model on every metric. That comparison is weak, though: 87% of the base model's
negotiation answers can't be parsed at all.

The only target it meets is negotiation decision accuracy, which the prompt-blind baseline also meets. It scores below
that baseline on three metrics:
- arbitrage verdict accuracy;
- flood alert accuracy;
- storage (both citation accuracy and chrF).

By subset, flood alert accuracy drops from 0.619 on IID rows to 0.485 on the unseen haor. The other subsets track
the overall numbers. The full IID and OOD breakdown is in the report.

Diagnosis, from `predictions_test.jsonl`:
- **Label collapse.** The adapter learned each task's answer template but not the decision inside it:
  - Negotiation: `unfair` for all 380 rows.
  - Arbitrage: `BLOCK_SPOT_SALE` for all 166 rows; the gold labels are 93 ALLOW_STORAGE, 38 ALLOW_SPOT_SALE and 35 BLOCK_SPOT_SALE.
  - Flood: `RED` or no alert on all 75 rows.
- **Numbers are guessed, not computed:**
  - The farm-gate price has a median relative error of 21%.
  - In the arbitrage trace, the spot value (one multiplication) is within tolerance for 85 of 166 rows, the storage value for 4, and ΔΠ for none.
- **Checkpoint choice.** Validation loss was lowest at step 50 (0.494) and then rose to 0.789, while training loss fell to 0.045.
  - Because `load_best_model_at_end` is on, the model evaluated is the step-50 checkpoint, about 0.35 of an epoch.
  - Loss on these templated answers is mostly loss on number tokens, so validation loss is a poor way to pick a checkpoint here.
- **Storage.** The adapter gave only 10 distinct answers to the 39 questions, and it often cited the wrong document.

Conclusion:
- A 1.5B adapter trained on 2,301 rows can't do the arithmetic, the seasonal-curve price lookup or the logistic flood
  formula in its weights.
- In the production pipeline, the MCP tools and agents compute these numbers. The language model only has to extract
  the inputs and phrase the answer.
- This test split is now spent for this task formulation. Any reformulated dataset must be scored on a freshly
  generated test batch (§7 rule), not on this split.

**Prompts v4 (2026-11-09): tool-grounded.** The user chose to change the task, not just rerun it.

What changed:
- Each user turn is the farmer's question plus the tool result the agent would get, as
  `<tool_result name="...">{json}</tool_result>`:
  - negotiation: `get_daily_commodity_spread` gives the three prices, rounded to whole taka;
  - arbitrage: `financial_circuit_breaker` gives the floor, the storage value, the spot value and ΔΠ;
  - flood: `calculate_haor_flash_flood_risk` gives the breach percent;
  - storage: `crag_retrieval` gives three passages, the gold one plus two from other documents.
- The model still has to decide:
  - fair if the offer is at least 95% of farm-gate;
  - the verdict, from today's price against the floor and the sign of ΔΠ;
  - the alert band;
  - which passage answers the question.
- Labels are balanced by re-sampling inputs until the engine gives a drawn target label:
  - negotiation is 575 fair to 625 unfair;
  - arbitrage is 236 / 224 / 240 across BLOCK / ALLOW_STORAGE / ALLOW_SPOT_SALE;
  - flood is 114–129 per alert.
- The new seed (20261109) and split salt (`split-v4`) make the test batch fresh: no v4 test question is a v3 test
  question.

Results:
- Splits: train 2,434, val 125, test 641. The test split holds 240 IID rows plus the OOD subsets: 240 dialect,
  128 months and 33 upazila.
- `jsonl_sha256` is `794becfc…87a1`.

Verified:
- A rule reader recovers all 3,200 labels from the user turn alone.
- Replaying the inputs through the engines reproduces every tool result.
- The scorer self-tests pass, and the notebook's CPU checks pass.

The prompt-blind baseline now meets only one target, storage citation (1.000). The other baselines are:
- negotiation decision accuracy 0.547;
- arbitrage verdict 0.288;
- flood alert 0.229;
- storage chrF 21.52.

Storage citation stays trivially met because the topic in the question names the document.

What the scores now mean:
- The numeric metrics measure faithful reading of the tool result, not knowledge.
- To make the app use the adapter, `run_local_inference` must put the same tool results into the prompt; today it
  sends only the raw prompt.

**Second measured run (prompts v4, Kaggle T4, 2026-11-09): meets every target.**

Run setup:
- Private kernel `taksimulhasandip/krishinexus-bangla-lora-training`, version 2, on data `794becfc…87a1`.
- 3 epochs (459 steps) in 41.4 min, fp16. The Q4_K_M GGUF exported without errors.
- Raw outputs are in `training/runs/kaggle-t4-2026-11-09/`.

Results on the fresh 641-row test split with greedy decoding:

| Metric | Target | Adapter | Base | Prompt-blind baseline |
|---|---|---|---|---|
| negotiation decision accuracy | 0.90 | 0.909 | 0.000 | 0.547 |
| negotiation balanced accuracy | — | 0.909 | 0.000 | 0.500 |
| negotiation price fidelity | 0.85 | 0.985 | 0.003 | 0.000 |
| arbitrage verdict exact match | 0.90 | 1.000 | 0.000 | 0.288 |
| arbitrage trace fidelity | 0.80 | 1.000 | 0.000 | 0.000 |
| flood alert accuracy | 0.90 | 1.000 | 0.000 | 0.229 |
| flood probability within ±2 pts | 0.85 | 1.000 | 0.571 | 0.000 |
| flood probability MAE, pts | — | 0.00 (n 70) | 0.00 (n 40) | — |
| storage citation accuracy | 0.90 | 0.925 | 0.000 | 1.000 |
| storage chrF | 60 | 93.28 | 18.53 | 21.52 |

The held-out subsets hold up:
- negotiation decision accuracy is 0.920 on IID rows and 0.904 on the unseen Chittagonian dialect;
- arbitrage on the unseen 7-month holding period and flood on the unseen haor both score 1.000.

Validation loss fell at every evaluation, from 0.0087 at step 50 to 0.00021 at step 450, so the checkpoint evaluated
is the last one.

Diagnosis, from `predictions_test.jsonl`:
- **Negotiation is the only real decision left, and it is barely over target.** 31 of 340 answers are wrong: 17 call
  an unfair offer fair, 14 the reverse.
  - Errors cluster near the 95% line: 13 of the 34 offers at 85–95% of farm-gate are wrong, against 4 of 152 below 85%.
  - Some wrong answers misstate the gap. For example, an offer of 19 Tk against a 17 Tk farm-gate price is called
    "2 Tk below".
  - The model is comparing two numbers in its weights; that comparison is not reliable.
- **Storage:** all 3 citation misses have the same gold answer. The generator files the chili chilling-injury
  sentence under the topic "pre-cooling", and in one case the adapter picked a passage that is actually about
  pre-cooling. This is label noise in the generator, not only a model error.
- **Arbitrage and flood now score 1.000 because they are copy-and-threshold tasks.** These scores show the adapter
  reads the tool result and applies the rule, including on unseen months and an unseen haor. They don't show any
  forecasting skill: the engines still compute every number.
- The base model's zero scores are mostly formatting: none of its negotiation answers can be parsed.

What this run does not show:
- The app does not use this adapter. Its weights stay on Kaggle, and `run_local_inference` doesn't build the
  tool-grounded prompt yet.
- The evaluation ran on the 4-bit NF4 model as trained. The exported Q4_K_M GGUF, which Ollama would serve, was not
  scored.
- Test questions come from the same templates as training. Real farmer phrasing is untested.
- The dialect hold-out covers only Chittagonian negotiation questions.

**Prompts v5 (2026-11-10): freely worded questions.** The user approved a retrain on 2026-11-10 ("Yes, start v5").

Why: in the app, the deployed v4 model handles questions in its training templates but not others. Three questions
asked through `/edge/local-inference` on 2026-11-09:
- the Rangpuri price question (a training template) was answered correctly;
- "4000 কেজি আলু আছে। আজ দাম 12 টাকা, রাখব না বেচব?" got a made-up trace (`storage = 4000*(15-12)`). The trace needs
  the tariff, handling cost, rot rate and expected price, and the question states none of them;
- "তাহিরপুর হাওরে পানি বাড়ছে, বাঁধ ভাঙবে নাকি? ধান কাটব কখন?" echoed the prompt and called a 5% breach YELLOW, which is GREEN.

These three are dev examples now, not test questions.

The app's routing (`ground_prompt`) also missed freely worded questions:
- "৫০ মণ আলু আছে, এখন বাজারে ১২ টাকা কেজি। হিমাগারে রাখব না বেচে দিব?" went to the price tool, not the store-or-sell breaker;
- English and Banglish offers ("14 taka per kg") weren't read at all.

What changes (`edge_node/sft_wordings.py`, `build_sft_dataset(5)`, `training/prepare_data.py --version 5`):
- **Wordings.** Each question is drawn from a bank per task: v4's template plus new ones in colloquial Bangla, Rangpuri,
  Bogura, Sylheti, Banglish and English. Arbitrage questions may state any subset of the numbers; flood questions may
  give no readings. Answers keep the v4 formats, so the §6 scorers apply unchanged.
- **Arbitrage tool result.** It now carries the breaker's seven inputs, so the trace can be written when the farmer
  states only the quantity and today's price. The app's router fills unstated inputs with its kiosk defaults, as before.
- **Held-out wordings.** A separate agent wrote 8 wordings per task (`edge_node/sft_heldout_wordings.json`). It was given
  only the task and slot descriptions and told not to open the repository, so it never saw the training bank. They appear only in test: half of the in-distribution test rows use one,
  as the new subset `ood_wording`. The other half keep training wordings (`iid`). The v4 OOD subsets stay:
  Chittagonian, 7-month holding, খালিয়াজুরী.
- **Fresh test batch.** Seed 20261110 and salt `split-v5`. The data is 1.5 times v4's: 4,800 rows. Test is 10% of
  families and validation 6%. Negotiation families are (crop, district, quarter) market cells, because the wording is
  now picked after the split.
- **Router.** `_tool_result` reads more phrasings: the spot price, months, expected price, rent, handling, and rot as a
  fraction or a percent; store words; readings in mm and dB; English month names. `bangla_voice._offer` also reads
  "taka" and "tk", and the lexicon knows "diamond".
  - v4 stays the app's prompt format (`PROMPT_VERSION = 4`) until a v5 model ships.
  - `build_sft_dataset(4)` still reproduces v4's data byte for byte (sha256 `794becfc…87a1`).
  - All 641 v4 test questions still route as before.
- **Model.** `krishi-bangla-lora-v2`, with the §4 recipe unchanged: Qwen2.5-1.5B-Instruct, QLoRA r16, 3 epochs.
  Export is Q8_0 via the NF4 merge (§5). The Kaggle notebook also scores that GGUF through Ollama on the same test split.

Pre-registered targets for `krishi-bangla-lora-v2`, set before any v5 result or held-out wording was seen:

| # | Measure | Target |
|---|---|---|
| 1 | The eight §6 metrics on the full v5 test split | each meets its §6 target |
| 2 | The same eight metrics on the `ood_wording` subset (held-out wordings) | each meets its §6 target |
| 3 | The same eight metrics on the `iid` subset (training wordings, new families) | each meets its §6 target |
| 4 | The exported Q8_0 GGUF through Ollama, on the full v5 test split | each meets its §6 target |
| 5 | Router: share of `ood_wording` test questions that `ground_prompt(…, version=5)` sends to the same tool with every stated number read correctly | ≥ 0.80 |

Rules:
- The model ships to the app only if targets 1–4 are met, and only after the user approves the ~1.6 GB download.
- Target 5 is about the app, not the model. It is measured once, on the held-out wordings, before training. If it
  misses, the router may only be improved on newly written dev wordings and re-measured on a fresh blind batch (§7 rule).
- The v4 model is also scored on the v5 test split through the local Ollama, before training, as a baseline. Arbitrage
  rows there are outside its format (inputs in the tool result), so that task is reported separately.

**v5 data, built and checked (2026-11-10).**

Splits (`training/data/split_report.json`, jsonl sha256 `e35ace55…96fe9`):
- train 3,638, validation 274, test 888;
- test subsets: `iid` 221, `ood_wording` 239, `ood_dialect` 200, `ood_months` 178, `ood_upazila` 50;
- leakage check passed: 1,649 response families and 88 negotiation cells, none in two splits.

Checks (`check_v5.py` in the scratchpad):
- Each question is matched back to the template it came from, so every slot value is known exactly.
- On all 4,800 rows: every tool result replays exactly through the engines; every label follows from the prompt;
  every number the question states equals the tool input it maps to.
- `ground_prompt(…, version=5)` rebuilds the tool result from the question alone for all 3,638 train and 274
  validation rows, and for every test row in `iid` and the three v4 OOD subsets.
- The scorer self-tests pass on the v5 splits, and the notebook's CPU checks pass.

The prompt-blind baseline meets none of the eight targets on the v5 test split:
- overall: negotiation 0.533, arbitrage verdict 0.303, flood alert 0.252, storage citation 0.467;
- on held-out wordings, storage citation is 0.000, because the train-answer lookup needs the exact question.

**Target 5, measured once: met.** The router reads 212 of the 239 held-out-wording questions correctly (0.887 against
≥ 0.80). It is frozen against these wordings now.

| Task | Routed correctly |
|---|---|
| negotiation | 66/66 |
| storage | 92/92 |
| arbitrage | 33/48: 12 misread the rot rate, 3 misread other numbers |
| flood | 21/33: the haor was always found, but in 12 questions the stated readings (rain, radar or month) weren't all read |

**Training started:** private kernel `krishinexus-bangla-lora-training` version 3, on the private dataset
`taksimulhasandip/krishinexus-bangla-agri-sft-v5`, at 02:37 on 2026-11-10.

**Baseline, measured 2026-11-10: the deployed v4 model on the v5 test split.** This is the Q8_0 GGUF served by the local
Ollama (RTX 3050) over all 888 rows, greedy decoding. It took 33.6 min at 56.6 tok/s.

| Metric | Target | All | `iid` | `ood_wording` |
|---|---|---|---|---|
| negotiation decision accuracy | 0.90 | 0.741 | 0.757 | 0.576 |
| negotiation price fidelity | 0.85 | 0.908 | 0.829 | 0.818 |
| flood alert accuracy | 0.90 | 0.414 | 0.429 | 0.303 |
| flood probability within ±2 pts | 0.85 | 0.622 | 0.786 | 0.424 |
| storage citation accuracy | 0.90 | 0.778 | 0.818 | 0.739 |
| storage chrF | 60 | 81.55 | 83.56 | 79.64 |
| arbitrage verdict exact match* | 0.90 | 0.410 | 0.429 | 0.500 |
| arbitrage trace fidelity* | 0.80 | 0.376 | 0.314 | 0.479 |

\* Arbitrage rows carry the v5 tool result, which adds the breaker's inputs. They are outside this model's format, so
those two rows don't measure wording alone.

What it shows:
- The same model scored 1.000 flood alert accuracy and 0.912–0.915 negotiation accuracy on v4's own test split.
- Wording alone takes flood alerts down to 0.414.
- Even v4's own Chittagonian template (`ood_dialect`) drops in negotiation, from 0.904 in the v4 training run's
  evaluation to 0.790 here. v5 writes half its numbers in Bangla digits, where v4's negotiation questions used ASCII,
  so the digit script alone may account for part of it.
- `iid` here means v5's training wordings, which this model mostly never saw.
- Predictions: `scratchpad/v5baseline/`.

**Measured run (prompts v5, Kaggle T4, finished 2026-11-10 04:38): every target met except storage citation.**

Run setup:
- Kernel `krishinexus-bangla-lora-training` version 3, adapter `krishi-bangla-lora-v2`.
- 684 steps in 72.5 min, fp16; no training example was truncated.
- Validation loss fell at every evaluation, from 0.018 at step 50 to 0.00046, so the last checkpoint was evaluated.
- The Q8_0 GGUF (1,646,572,704 bytes) exported and was scored through Ollama 0.40.15 on the T4: 25.3 min at a median
  81.9 tok/s. 844 of its 888 answers are identical to the 4-bit model's.
- Reports are in `training/runs/kaggle-t4-2026-11-10-lora-v5/`; predictions are in `scratchpad/downloads/lora-v5/`.

Targets 1–4: each cell is the score, with the target in the first column. Targets 1–3 use the 4-bit model as trained;
target 4 is the GGUF through Ollama.

| Metric | Target | 1: all | 2: `ood_wording` | 3: `iid` | 4: GGUF, all | Base, all |
|---|---|---|---|---|---|---|
| negotiation decision accuracy | 0.90 | 0.991 | 0.985 | 0.971 | 0.988 | 0.021 |
| negotiation price fidelity | 0.85 | 1.000 | 1.000 | 1.000 | 1.000 | 0.039 |
| arbitrage verdict exact match | 0.90 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| arbitrage trace fidelity | 0.80 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| flood alert accuracy | 0.90 | 0.982 | 1.000 | 1.000 | 0.964 | 0.000 |
| flood probability within ±2 pts | 0.85 | 0.982 | 1.000 | 1.000 | 0.964 | 0.405 |
| **storage citation accuracy** | 0.90 | **0.789** | **0.717** | **0.864** | **0.806** | 0.000 |
| storage chrF | 60 | 83.56 | 78.42 | 88.90 | 84.97 | 20.63 |

Target 5 (routing) was met earlier: 0.887.

Against the deployed v4 model, both scored as GGUFs through Ollama on the same 888 rows:
- every metric is higher;
- negotiation decisions 0.741 → 0.988 (held-out wordings 0.576 → 0.985);
- flood alerts 0.414 → 0.964 (held-out wordings 0.303 → 1.000; the unseen haor 0.480 → 0.920);
- arbitrage verdicts and traces 0.410 / 0.376 → 1.000;
- storage citation only 0.778 → 0.806.

Diagnosis of storage citation, from the GGUF's 35 misses out of 180:
- Every miss cites exactly one document, and it is always one of the three passages shown. None is invented.
- 18 misses have gold `BARI-CHILI-01`, whose topic is "pre-cooling" but whose sentences are mostly about storage
  temperature and chilling injury. The model often cites `BARI-BRINJAL-01` instead, which covers the same ground.
  This is the label noise already noted for v4: the question asks about a document's main topic, while the gold
  answer is one sentence of it.
- Questions written only in Bangla script miss more often: 21 of 72 (29%), against 14 of 108 (13%) for questions
  containing English words. In those questions the topic is not the English keyword in the passage titles.
- A next data version could ask about each sentence's own topic. That has to be built on dev data and measured on a
  fresh test batch, because this split is now spent.

Ship rule: by the rule set before training, v5 does **not** ship automatically, because storage citation misses
targets 1–4. Whether to ship it anyway is the user's decision. It is better on every metric than the model the app
runs now.

**Shipped on 2026-11-10, by the user's decision ("Yes, ship v5"), with the storage citation miss on record.**
- Downloaded from kernel version 3: `krishi-bangla-q8_0.gguf` (1,646,572,704 bytes, sha256 `069293ff…8e3b`, GGUF magic
  checked), the `krishi-bangla-lora-v2/` adapter with its `eval_report.json`, and the Modelfile. The adapter's
  `training_args.bin`, a pickle, was not downloaded.
- `ollama create krishi-bangla -f Modelfile`: the model layer is `sha256-069293ff…`, the file's own hash. v1 stays as
  `krishi-bangla:v4` (layer `7c0e7e66…`) and as `backend/models/lora/krishi-bangla-v4-q8_0.gguf`, with
  `gguf_eval_report_v4.json` and `Modelfile.v4`.
- `PROMPT_VERSION = 5`. `lora_adapter_spec` reads the adapter name from the registry (`krishi-bangla-lora-v2`).
  `gguf_eval_report.json` is v5's.
- Checked through the app, offline blackout, on the RTX 3050 at about 57 tok/s. All five dev questions get complete,
  correct answers:
  - the Rangpuri price question;
  - "4000 কেজি আলু আছে। আজ দাম 12 টাকা, রাখব না বেচব?": the full trace with the kiosk's default inputs, ΔΠ −36,008,
    ALLOW_SPOT_SALE (v4 had made up a trace);
  - the Tahirpur flood question: "৪% (GREEN)" with the normal-schedule advice (v4 said 5% YELLOW and echoed the prompt);
  - "৫০ মণ আলু… হিমাগারে রাখব না বেচে দিব?";
  - the English price question.
- The `/docs` tester shows `krishi-bangla-lora-v2 · 4,800 SFT examples · split 3,638/274/888`, with both score
  columns from the installed reports. Storage citation is marked amber in both.
- **Re-scored on this PC** (RTX 3050, Ollama 0.40.15, the installed file `069293ff…`, all 888 test rows, greedy):
  - negotiation 0.988, price fidelity 1.000, arbitrage verdict and trace 1.000;
  - flood alert and ±2 pts 0.955 (Kaggle's T4: 0.964); storage citation 0.800 (0.806), chrF 84.66;
  - on held-out wordings: flood 1.000, negotiation 0.985, storage citation 0.739;
  - 874 of 888 answers are identical to the Kaggle GGUF's, and 845 to the 4-bit model's;
  - median 55.7 tok/s, 1,745 MB VRAM, 35.2 min.
  - Installed as `gguf_eval_report.json`, so the `/docs` "Deployed" column is this machine's measurement. Recorded
    in `training/runs/local-ollama-2026-11-10-v5/`.

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

## 8. YOLO `yolov11n-krishi-bd-v2.1` (two-stage potato inspector; training on Kaggle from 2026-11-09)

**Dataset, as checked on Mendeley on 2026-11-09:** Diamant Potato Dataset, DOI 10.17632/4vty9rz7zw.1.
- Published 10 Aug 2026 by Daffodil International University under CC BY 4.0.
- Photographed at the Ashulia, Banasree and Khilgaon markets in Dhaka.
- It is instance segmentation in two zips (8.9 GB in all), each with a published SHA-256.

| Set | Images | Classes | Published split (train / val / test) |
|---|---|---|---|
| `roi_dataset` | 2,386 photos, 3000×3000 JPG, 3,589 potatoes (2,581 / 645 / 363; the page's "2,581" is the train count); includes 144 distractor images (ginger, eggs, brown surfaces) | 1: potato | 1,670 / 477 / 239 |
| `defect_dataset` | 1,724 background-removed tuber crops, lossless PNG, 6,576 defects | 4: scab, rot, greening, mechanical damage | 1,281 / 176 / 267 |

Defect classes are skewed: scab is 67% of instances and greening 1.9%. The defect crops are "green-boosted" (HSV
saturation ×1.5 and value ×1.3 in the green band), and the same transform must be applied at inference.

**Design.** The dataset is built for a cascade, so the model is two stages:
1. a YOLO11n detector finds each potato in a photo;
2. a YOLO11n-seg model segments the defects on each potato crop.

The defect masks feed the app's existing grade rule (`prompt_registry` "bari-standard") per potato:
- "bruising %" = scab + greening + mechanical damage, as surface blemishes;
- "rot %" = rot.

This replaces the earlier plan, which assumed one detector over three classes; the published classes don't fit it.
`undersized` stays geometric, from the box size.

**Pre-registered targets (set 2026-11-09, before any vision result exists):**

| Metric | Split | Target |
|---|---|---|
| Stage 1 box mAP50 | ROI test (239) | ≥ 0.90 |
| Stage 2 mask mAP50 | defect test (267) | ≥ 0.50 |
| Per-potato grade accuracy (A/B/C from predicted masks vs from label masks) | defect test (267) | ≥ 0.70, and above the majority-grade baseline from the train split |

Also reported: per-class mask AP50, image-level presence precision/recall per class, and the mean absolute error of
"bruising %" and "rot %".

The CPU smoke run (2026-11-09) passed every data check: both SHA-256s, the images per split, and all 12 defect
instance counts. It also showed the label grades are skewed: on the train split they are C 829, A 362 and B 90, so
always answering "C" scores 0.674 on test. The 0.70 target therefore asks little beyond the baseline. The report adds
**grade balanced accuracy** (mean per-grade recall, where always "C" scores 0.33) as the stricter view. The
pre-registered targets are unchanged.

**Recipe:** `training/kaggle/krishinexus_potato_vision_kaggle.ipynb` runs on a Kaggle T4.
- It downloads both zips and checks their SHA-256.
- It checks the image and instance counts against the dataset page, and resizes images to at most 1024 px.
- It trains with seed 20261109: stage 1 for up to 80 epochs and stage 2 for up to 150, both at 640 px.
- It scores each stage once on the published test split.

The test splits are the dataset authors' own, fixed before this project touched them. Without a GPU, the notebook runs
a 1-epoch CPU smoke test instead, and its report labels the scores as not results.

**Wiring (planned for after a run meets its targets; done for run 2 with the user's approval, see the end of this
section):** `optical_grader.yolo_detect` must become the two-stage cascade, with the green-boost applied to each crop.
`inference_backend` keeps reporting `classical-cv` until real weights are installed.

**First T4 run (Kaggle, 2026-11-09): stage 1 and grading meet their targets; stage 2 misses.**
- Private kernel `krishinexus-potato-vision-training`, version 3, with Ultralytics 8.4.208 on a Tesla T4.
- Stage 1 ran all 80 epochs in 20.1 min. Stage 2 stopped early at 127 of 150 epochs, in 34.1 min.
- Raw outputs are in `training/runs/kaggle-t4-2026-11-09-vision/`.
- The weights (`roi_best.pt` SHA-256 `b9d429d9…a428`, `defect_best.pt` `1b8ddded…cfd7`) are in the git-ignored
  `backend/models/yolo/`.

| Metric | Target | Best val | Test (opened once) | |
|---|---|---|---|---|
| Stage 1 box mAP50 | ≥ 0.90 | 0.995 | **0.994** (P 0.984, R 0.989, mAP50-95 0.978) | met |
| Stage 2 mask mAP50 | ≥ 0.50 | 0.396 | **0.335** (box 0.367) | **missed** |
| Per-potato grade accuracy | ≥ 0.70 and > always-C (0.674) | — | **0.768** | met |
| Grade balanced accuracy (always-C = 0.333) | reported | — | 0.644 | — |

Stage 2 by class, test mask AP50: scab 0.435, rot 0.429, mechanical damage 0.286, greening 0.189.

Image-level presence (does this potato show the defect?):

| Defect | Precision | Recall | F1 |
|---|---|---|---|
| scab | 0.93 | 0.96 | 0.95 |
| rot | 0.65 | 0.69 | 0.67 |
| mechanical damage | 0.56 | 0.57 | 0.57 |
| greening (25 potatoes) | 0.60 | 0.24 | 0.34 |

Reading the numbers:
- Stage 1 is solved.
- Stage 2 is weak on validation too, so the shortfall isn't a quirk of the test split. The nano model at 640 px loses
  the small lesions; the crops are stored at up to 1024 px.
- The grade beats the always-C baseline by 9 points, mostly on scab presence. Area estimates are poor:
  - "bruising %" (scab + greening + mechanical damage) is off by 19.2 points on average;
  - "rot %" is off by 1.0.
- Grade confusion (label → predicted):
  - A → A 41, B 4, C 19;
  - B → B 10, A 3, C 10;
  - C → C 154, A 20, B 6.

Next, selected on **validation** only, because the test split has now been opened once:
- a stage 2 run at 1024 px, and/or YOLO11s-seg;
- stage 1 retrained as YOLO11n-seg, so inference can cut each potato out of its background the way the defect crops
  were made.

Not wired into the grader yet, so `inference_backend` still reports `classical-cv`.

**Run 2 design (fixed 2026-11-09, before it trains; the user approved the run):**
- Stage 1 becomes YOLO11n-seg at 640 px, so the app can cut each potato out of its background.
- Stage 2 trains two candidates side by side on Kaggle's T4 ×2: YOLO11n-seg at 1024 px and YOLO11s-seg at 640 px.
- The candidate with the higher **validation** mask mAP50 is kept. The test split is opened once more, for that
  winner only.
- The targets are unchanged: stage 1 box mAP50 ≥ 0.90, stage 2 mask mAP50 ≥ 0.50, and grade accuracy ≥ 0.70 and
  above always-C.

**Run 2 (Kaggle T4 ×2, 2026-11-09): stage 1 now outlines potatoes; stage 2 misses its target again.**
- Kernel v5; 107 min of training on two GPUs side by side.
- Raw outputs are in `training/runs/kaggle-t4x2-2026-11-09-vision2/`; the weights are in git-ignored
  `backend/models/yolo/run2/` (`roi_best.pt` `4c3374a4…04ed`, `defect_best.pt` `84a079d7…198d`).

| | Target | Run 1 | Run 2 |
|---|---|---|---|
| Stage 1 box mAP50 (test) | ≥ 0.90 | 0.994 (detector) | **0.9945**; outlines: mask mAP50 0.9946, mask mAP50-95 0.984 |
| Stage 2 validation mask mAP50 | — | 0.396 (n, 640 px) | n at 1024 px **0.3956** (chosen), s at 640 px 0.3937 |
| Stage 2 test mask mAP50 | ≥ 0.50 | 0.335 | **0.342: missed** (scab 0.490, rot 0.449, mechanical damage 0.253, greening 0.176) |
| Grade accuracy (test) | ≥ 0.70, > always-C | 0.768 | the grading cell ran out of GPU memory predicting at 1024 px with full-size masks; measured afterwards on CPU: **0.764, met** (grade check below) |

Reading the numbers:
- Higher resolution and a larger model both landed at the run-1 validation score (about 0.40). The ceiling is
  probably the data, not model capacity: small lesions, a rare greening class with 79 train instances, and lesion
  boundaries that are hard to draw consistently.
- Stage 1 is solved and now gives the potato outline the app needs to cut crops out of the background.
- Grading for the run-2 model needed prediction one image at a time without full-size masks; the grade check below
  does that.

**Run 2 grade check (Kaggle CPU, 2026-11-09): grade accuracy 0.764, meets its target.**
- This is run 2's pre-registered grading check, run once after its out-of-memory crash, with nothing retuned. The
  model (SHA-256 checked), the image size (1024 px) and the threshold (0.25) are run 2's.
- Private CPU kernel `krishinexus-potato-grade-check`, version 1; notebook
  `training/kaggle/krishinexus_potato_grade_check_kaggle.ipynb`.
- Predicted masks are rasterised from their `masks.xy` outlines at each crop's size, as the app does, so the score
  describes the deployed mask path. CPU time is 0.39 s per crop.
- The report is `training/runs/kaggle-cpu-2026-11-09-gradecheck/grade_check.json`, also installed beside the weights.

| Measure (267 test crops) | Run 1 | Run 2 |
|---|---|---|
| Grade accuracy (target ≥ 0.70 and > always-C 0.674) | 0.768 | **0.764: met** |
| Grade balanced accuracy (always-C = 0.333) | 0.644 | 0.663 |
| Bruising-% MAE / rot-% MAE (points) | 19.2 / 1.0 | 17.6 / 1.05 |
| Presence F1: scab / rot / mechanical damage / greening | 0.95 / 0.67 / 0.57 / 0.34 | 0.94 / 0.64 / 0.51 / 0.41 |

- Grade confusion (label → predicted):
  - A → A 51, C 12, B 1;
  - B → A 10, B 9, C 4;
  - C → C 144, A 31, B 5.
- Stage 2 grades about as well as run 1's model; the higher resolution did not move the grade. (Run 1 was scored with
  full-size masks rather than outlines, a small difference.)
- The commonest error is calling a C potato A (31 of 180), which flatters a lot.

**Wiring (2026-11-09; the user approved connecting run 2 although stage 2 misses its target):**
- `optical_grader.yolo_detect` is now the two-stage cascade for Cardinal and Diamant potato photos. Other crops keep
  classical CV.
- Stage 1 outlines each potato at 640 px. Each potato is cut out onto black and green-boosted, as the defect crops
  were made. Stage 2 then segments it at 1024 px with conf 0.25.
- Masks are rasterised from their `masks.xy` outlines at the crop's own size. A 12 MP phone photo never builds a
  full-size mask stack, which is what crashed run 2's grading cell.
- Per potato, bruising % is the scab + greening + mechanical-damage area and rot % is the rot area. The labels are:
  - undersized below 35 mm;
  - otherwise fungal_blight when rot covers more than the active grade-A rot limit (2% under `bari-standard`), as in
    the measured per-potato rule;
  - otherwise minor_bruise for any blemish, and uniform_A for none.
  - The lot metrics and the BARI grade rule are unchanged.
- A box's confidence is that of the detection that decided its label (for example the rot mask's), not stage 1's
  "this is a potato".
- `inference_backend` reports `ultralytics-yolo two-stage (run2: roi_best.pt + defect_best.pt)`. Each photo grade's
  reasons quote, from the installed reports, the defect stage's test mask mAP50 against its target and the grade
  check's accuracy against its target and the always-C baseline. The farmer app lists these reasons under a photo's
  certificate.
- A photo carries no scale, and the diameters feed the undersized label and the grade-A size check. So the farmer app
  asks how wide the photo is (close-up 15 cm, handful 30 cm, crate 60 cm, heap 1.5 m) and sends it as
  `frame_width_mm`. The reasons state the width used.
  - At the old fixed 60 cm, a close-up of one potato read 258 mm across. At "close-up, 15 cm" it reads 64.5 mm.
  - It remains the user's estimate, not a measurement.
- Heap photos were a gap: stage 1 was trained on photos of one or two potatoes and runs at 640 px. In a synthetic
  8 × 8 mosaic of the six photos (64 potatoes in 3000 px) it found only 17.
- **Tiled potato finding (2026-11-09, the user said "Yes, try it"):** `find_potatoes` runs stage 1 on the whole photo
  and on overlapping square tiles, each at 640 px.
  - The tiles span the long side in a 4 × 4 grid with an overlap of 15% of the long side, so a tile shows potatoes
    2.8× larger. The whole-photo pass finds few potatoes under about a tenth of the long side, and any such potato fits
    whole in some tile.
  - A tile detection cut by an inner tile edge is dropped. Detections overlapping by more than half the smaller box
    keep the surest. Stage 2 then works on each potato as before.
  - First, a scale sweep on the six photos (one potato, 49–86% of the long side) found the potato at every input size
    from 128 to 1280 px. At 1920 px and above it found a fragment instead. So a potato needs roughly 60 px or more
    in the model's input, and a native-resolution pass would break close-ups (and takes 5 s).
  - The grid was chosen on two synthetic heaps built from validation photos. One is the mosaic. The other is a seeded
    scatter of 40 potatoes, cut out by their label outlines, rotated and sized 2–9% of a 4000 × 3000 frame, with no
    overlaps. Neither is a test set. Stage 1 alone, with box IoU ≥ 0.5 against the label outlines, on the in-memory
    images:

    | Grid (+ whole photo) | Mosaic (64) | Scatter (40) | Six close-ups | Added time per photo |
    |---|---|---|---|---|
    | none (before) | 17 | 1 | 1 each | — |
    | 2 × 2 | 63 | 14 | 1 each | 0.5 s |
    | 3 × 3 | 64 | 31 | 1 each | 0.9 s |
    | 4 × 4 (chosen) | 64 | 34 | 1 each | 1.4 s |

  - No grid produced a false detection. 4 × 4 was chosen because 3 × 3 starts to miss at the size a phone held at
    standing height gives (an estimate, not a measurement: a 55 mm potato in a frame about 1.7 m wide is 3–4%).
  - From the saved JPEGs, decoded as the API decodes them: mosaic 64/64 and scatter 36/40, no false detection. Three
    of the four scatter misses are under 3% of the frame width and one is 4.7%; the smallest potato found is 2.3%.
  - Grading small potatoes is weaker than finding them. Graded at a width that keeps every mosaic copy above the
    undersized cut, the rotten potato (0164) was still fungal_blight in all 11 copies (rot 15.5% against 16.0% at full
    size). But potato 1229, 59% blemished at full size, read uniform_A in 8 of its 10 copies: fine scab disappears at
    a few hundred pixels.
  - Cost on a laptop CPU through the API: a warm close-up grade takes 2.05 s (it was 0.72 s). The mosaic at 1.5 m takes
    9.2 s (64 potatoes) and the scatter 7.5 s (36). `/health` stays under 70 ms meanwhile. The app waits up to 120 s.
- **Defect detail against potato size (rule set 2026-11-09 before the sweep ran; the user said "Yes, measure it"):**
  - Question: below what width in pixels does stage 2 stop seeing what it sees on the same potato at full size?
  - Data: all 477 photos of the Diamant ROI validation split; the defect test split stays closed. Each labelled
    potato is cut out by its hand-drawn outline, as `_cascade` cuts a stage-1 outline. Stage 2 grades it at full size,
    then again after the photo is shrunk (Lanczos, then saved as JPEG quality 90) until the potato is 48, 64, 96, 128,
    192, 256, 384, 512 or 768 px wide. Width means the diameter of a circle of the same area, as `diameter_mm` uses.
  - Measure: the share of potatoes whose per-potato grade (the BARI rule on blemish % and rot %) equals their
    full-size grade. Also reported: label agreement, grades turned milder or harsher, and blemish area kept.
  - Rule: the warning threshold is the smallest tested width at which, and at every larger tested width, at least
    90% of potatoes keep their full-size grade. If no tested width qualifies, no threshold is set and this says so.
  - It runs once, on Kaggle CPU (`krishinexus-potato-size-sweep`). Nothing is tuned against the result.
  - **Result (run once on 2026-11-09, 34 min on Kaggle CPU):** 645 potatoes in the 477 photos, none skipped (54
    photos hold two or more). At full size they are 657–1984 px wide (5th–95th percentile, median 1408) and grade
    A 234, B 50, C 361. A width is tested only on potatoes wider than it, so 51 potatoes sit out at 768 px.

    | Width | Potatoes | Grade kept | Label kept | Grade milder | Grade harsher | Blemish area kept (median) | Rot kept |
    |---|---|---|---|---|---|---|---|
    | 48 px | 645 | 0.406 | 0.521 | 0.532 | 0.062 | 0.009 | 34/70 |
    | 64 px | 645 | 0.467 | 0.539 | 0.471 | 0.062 | 0.010 | 39/70 |
    | 96 px | 645 | 0.614 | 0.550 | 0.329 | 0.057 | 0.085 | 46/70 |
    | 128 px | 645 | 0.690 | 0.659 | 0.243 | 0.067 | 0.878 | 53/70 |
    | 192 px | 644 | 0.798 | 0.814 | 0.115 | 0.087 | 0.998 | 53/70 |
    | 256 px | 643 | 0.823 | 0.871 | 0.076 | 0.101 | 1.003 | 56/70 |
    | 384 px | 638 | 0.865 | 0.906 | 0.052 | 0.083 | 1.005 | 58/70 |
    | 512 px | 628 | 0.892 | 0.931 | 0.040 | 0.069 | 1.004 | 62/70 |
    | 768 px | 594 | 0.923 | 0.941 | 0.034 | 0.044 | 1.001 | 56/67 |

    Blemish area kept is over potatoes at least 1% blemished at full size. Rot kept counts potatoes over the 2% rot
    limit at full size that stay over it.
  - By the rule, the threshold is **768 px**: 512 px keeps 0.892 of grades, just under 0.90.
  - Small potatoes lose their defects. Grades turn milder for 12% of potatoes at 192 px, 24% at 128 px and 53% at
    48 px. The median blemish area kept drops from 0.88 at 128 px to 0.09 at 96 px.
  - From 256 px up, grades move both ways, a little more often harsher (3–10% each). So part of the change is the
    re-encoding itself: even at 768 px, 7.7% of grades move.
  - Rot is the most fragile defect: 8 of 70 rotten potatoes lose it at 512 px and 11 of 67 at 768 px.
  - For orientation only (arithmetic, not measured): in a 4000 px wide photo a 60 mm potato is about 1,600 px wide in
    a 15 cm close-up, 800 px in a 30 cm handful, 400 px in a 60 cm crate and 160 px in a 1.5 m heap. So close-ups pass
    and crates and heaps are warned.
  - **Wiring:** `size_warning` reads `min_potato_px` and the per-width numbers from the installed report
    (`backend/models/yolo/run2/size_sweep.json`, a copy of
    `training/runs/kaggle-cpu-2026-11-09-sizesweep/size_sweep.json`). It turns each potato's `diameter_mm` back into
    pixels. If any potato is narrower than the threshold, the grade result gets a `warnings` entry that cites the
    measured share of grades kept at the tested width nearest below the smallest potato. The farmer app shows it as an
    amber note under the certificate's grade.
  - Since 2026-11-10 (the user said "Yes, sign it") the warnings are also signed into the certificate payload.
    `/edge/verify-certificate` returns them for a certificate that verifies, and none for one that doesn't. The
    buyer portal shows them under its verification line. A certificate stripped of its warning reads tampered
    (checked through the API).
  - Since 2026-11-10 (the user said "Yes, link it") a photo grade also grades the loan. The farmer app's voice
    request and the buyer portal's underwrite send a same-crop photo grade's certificate as `edge_certificate_id`.
    The server reads the lot's numbers from its own signed record of that certificate, not from the client. So the
    portal verifies the photo's certificate and shows its size warning. Checked through the API and in the browser.
  - Checked through the API on a laptop CPU:
    - two full-size close-ups (1288 px and wider) get no warning;
    - 0762 shrunk to 1000 px (potato 431 px) gets "87% of 638 potatoes kept their full-size grade" at 384 px;
    - the mosaic (smallest 162 px) gets 69% at 128 px;
    - the scatter (smallest 83 px) gets 47% at 64 px.
    - In the browser, the scatter at "Heap, 1.5 m" shows the note on its Grade-C certificate.
  - Limits: hand-drawn outlines stand in for stage 1's, the photos are shrunk validation photos rather than real
    heaps, the warning quotes the worst potato's width, and the measure is the per-potato grade, not the lot grade.
- Photos are turned upright from their EXIF tag first, as the training images were.
- In the farmer app, step 2 gained **Grade a photo** (JPEG/PNG upload). The preset sweep is now labelled **Scan sample
  lot**.
- Smoke test on six original validation photos (3000 × 3000 px, one potato each; the grade check saved them):
  - every potato was found, and the outline matches the hand-drawn one;
  - grades A, A, C, C, C, C, in 0.5–0.8 s each on a laptop CPU;
  - the C grades come from large scab areas (59–95% of the surface, on netted skins) and one decaying end marked as
    rot (15%).
  - These photos are validation images, so this checks the wiring, not accuracy.

## 8b. Price intelligence `krishi-price-v1` (staple forecasts + spread anomalies; designed 2026-11-09)

The user asked for an AI-driven commodity price monitor (DAM/TCB/WFP-HDX prices, LightGBM and GRU/TCN forecasts,
wholesale-retail spread anomaly detection).

**Data:** WFP *Bangladesh - Food Prices* on HDX.
- 34,489 rows from 1998-07 to 2026-09, 124 markets, CC BY-IGO.
- Snapshot of 2026-11-04, sha256 `2f009010…0ce`.
- Long retail series exist for four staples: coarse rice, wheat flour, masur lentils and palm oil.
- WFP reported division averages until mid-2020 and about 100 district markets after. Each (staple, division) series
  is therefore WFP's division average up to its last month, then the median of that division's district markets.
  The jump at the join is reported.
- This gives 4 staples × 6 divisions (Barisal, Chittagong, Dhaka, Khulna, Rajshahi, Sylhet), monthly.
- Potatoes, onions, chili and similar series exist only from 2024: too short to train on.

**Features:**
- past log-returns of the price;
- the target month, and the share of it that falls in Ramadan (tabular Islamic calendar);
- the taka-dollar rate, implied by WFP's own `price / usdprice`;
- monthly rainfall anomaly per division from the Open-Meteo archive.

No long fuel-price series exists in the data, so fuel is left out.

**Models**, each forecasting 1, 2 and 3 months ahead:
- naive (last price);
- seasonal naive (same month last year);
- LightGBM (direct, one model per horizon);
- a GRU and a TCN over the last 24 months;
- the mean of the three learned models.

**Split by time:**
- train: targets before 2024-10;
- validation: 2024-10 to 2025-09, used to choose the model;
- test: 2025-10 to 2026-09, scored once after the choice.

All models' test scores are reported, and the validation choice is marked as the pre-registered one.

**Pre-registered targets** (set before any training), for the validation-chosen model on test:
- mean sMAPE over 1–3 months below the naive forecast's;
- 3-month sMAPE below the seasonal-naive forecast's;
- 3-month direction accuracy ≥ 0.55 on moves larger than 1%.

**Spread anomalies:** WFP has wholesale and retail pairs only for Dhaka (coarse rice, medium rice and wheat flour,
2008–2021).
- The retail margin over wholesale is flagged two ways:
  - when its trailing robust z-score reaches 3.5;
  - by an IsolationForest on margin and price changes.
- No hoarding labels exist. The flags are compared with three publicly reported disruption windows:
  - the 2008 food-price crisis;
  - the 2017 rice spike after the haor flash floods;
  - the 2020 COVID-19 lockdown.
- This is a case study, not a metric.

**First run (Kaggle CPU, 2026-11-09): misses two of the three targets.**
- Private notebook `krishinexus-price-intelligence` v1 on the private dataset `krishinexus-bd-food-prices` (the HDX
  snapshot), 49 s.
- Rainfall was on. LightGBM stopped at 42 / 22 / 75 trees. The GRU and TCN early-stopped at epochs 33 and 32: their
  best validation loss came within the first few epochs.
- A local debug run that read only validation found no bugs. The test year was scored once, in this run.
- Raw outputs are in `training/runs/kaggle-cpu-2026-11-09-price/`; the models are in git-ignored
  `backend/models/price/`.

Mean sMAPE over 1–3 months:

| Split | naive | seasonal naive | LightGBM | GRU | TCN | ensemble |
|---|---|---|---|---|---|---|
| validation (2024-10 to 2025-09) | 2.736 | 10.217 | 2.731 | 2.742 | 2.739 | **2.721** (chosen) |
| test (2025-10 to 2026-09) | **2.643** | 8.296 | 3.004 | 2.729 | 2.673 | 2.747 |

| Pre-registered target (test) | Chosen ensemble | Reference | |
|---|---|---|---|
| mean sMAPE below naive | 2.747 | naive 2.643 | **missed** |
| 3-month sMAPE below seasonal naive | 3.619 | 8.170 | met |
| 3-month direction accuracy ≥ 0.55 | 0.49 | — | **missed** |

What the result means:
- The direction signal seen on validation did not hold on test. LightGBM called 64% of 3-month moves on validation
  but 53% on test, and the 1-month moves 45%.
- No learned model beat "no change" on the test year. Monthly staple retail prices move little, and 24 series of about
  20 years give the models little to learn from.
- Only the seasonal-naive target was met, and that baseline is weak because prices trend.

Spread anomalies: 34 flags across the three Dhaka series.
- Margins: medians of 8.7–15.8%, ranging from 2.2% to 35.7%.
- 8.8% of flags fall in the reported windows, against 8.0% of months: enrichment 1.1, i.e. none.
- The flags cluster in 2012 (coarse rice, margin 18–22%) and February–May 2015. Those periods are outside the
  pre-registered windows, so they are reported as found, not counted as hits.

Consequence for the app: the forecasts are shown only beside the "no change" baseline and these test scores. The
monitoring part of the system stands without any forecasting claim: latest prices, their change, and margin flags.

## 8c. Bangla speech-to-text `krishi-whisper-bn-v1` (designed 2026-11-09; the user approved training)

The voice pipeline (`edge_node/bangla_voice.py`) transcribes speech on the device with faster-whisper when
`KNX_WHISPER_MODEL` names a CTranslate2 model. No model was installed, so the Multimodal row in `/docs` stays
"Partial" on audio.

**Data:** *Common Voice 13, Bengali (normalized)* on Kaggle, `umongsain/common-voice-13-bengali-normalized`.
- It is Mozilla Common Voice 13's Bengali subset (CC0), keeping only clips with more upvotes than downvotes.
- Transcripts are normalized with bnUnicodeNormalizer and stripped of punctuation.
- Common Voice's official splits: train 20,729, dev 9,230, test 9,230 clips, about 9 words each.
- Common Voice keeps speakers out of more than one split. This copy dropped the speaker IDs, so that can't be
  re-checked here. Only 3 test sentences also occur in train.

**Model:** fine-tune `openai/whisper-small` (244 M parameters) with language `bengali` and task `transcribe`.
- Full fine-tune, fp16, gradient checkpointing, batch 16, learning rate 1e-5, 3,000 steps (about 2.3 epochs).
- The checkpoint is chosen by WER on a fixed 500-clip dev sample.
- The best checkpoint is converted to CTranslate2 int8, the format the app's faster-whisper loads.

**Scoring:**
- A fixed, seeded sample of 2,000 test clips, scored once after the checkpoint is chosen, for both the zero-shot base
  model and the fine-tuned one.
- Hypotheses and references both go through the same normalizer: NFC, punctuation to spaces, whitespace collapsed.
- WER and CER are corpus-level edit distance over words and characters.
- The converted int8 model is scored with faster-whisper on CPU, as the app runs it, on 300 of those clips beside the
  fine-tuned checkpoint.

**Pre-registered targets** (set before any training):

| Metric | Target |
|---|---|
| Fine-tuned WER, 2,000 test clips | ≤ 0.45, and below the zero-shot base model's |
| Fine-tuned CER, 2,000 test clips | ≤ 0.15, and below the zero-shot base model's |
| Deployed int8 CTranslate2 WER, 300 clips | within 0.02 of the fine-tuned checkpoint on the same clips |

Caveat: Common Voice is read speech of standard written Bangla. A good score here says little about farmers' dialect
speech, which no open labelled set covers.

**Measured run (Kaggle T4, finished 2026-11-10 03:54): meets 2 of the 3 targets.**

Run setup:
- Private kernel `krishinexus-bangla-whisper-training` version 4.
- 3,000 steps took 533 min of training, against the 4–5 GPU hours estimated. The whole run took about 10 h, inside
  Kaggle's 12-hour limit.
- Validation WER on the 500 dev clips fell at every check, from 0.555 at step 500 to 0.418 at step 3,000, so the last
  checkpoint was chosen.
- Outputs are in `training/runs/kaggle-t4-2026-11-10-whisper/`. The predictions file and the run log stayed in the
  scratchpad. The model files were not downloaded.

| Measure | Target | Fine-tuned | Zero-shot base | Result |
|---|---|---|---|---|
| WER, 2,000 test clips, greedy | ≤ 0.45 and below base | 0.435 | 1.164 | **meets** |
| CER, 2,000 test clips, greedy | ≤ 0.15 and below base | 0.229 | 1.108 | **misses** |
| int8 CT2 WER minus checkpoint WER, same 300 clips | ≤ 0.02 | −0.094 | – | **meets** |

The zero-shot base model scores above 1.0, which means it makes more edit errors than there are words.

The parity check compares the deployed setup with the checkpoint on the same 300 clips:

| On the same 300 clips | WER | CER |
|---|---|---|
| Fine-tuned checkpoint, greedy, GPU | 0.429 | 0.226 |
| int8 CTranslate2, beam 5, CPU (as the app runs it) | 0.335 | 0.110 |

Reading the parity check:
- The int8 model's lead comes from beam search, not from quantization. The comparison mixes the two, so it shows that
  int8 loses nothing, not that int8 helps.
- On those 300 clips the deployed setup is under both the WER and CER limits. That isn't the pre-registered CER
  measure, which is greedy decoding on 2,000 clips and stays a miss.
- It took 10.3 s per clip on Kaggle's CPU.
- None of the 2,000 greedy transcripts is empty or runs over 1.5 times the reference length.

**Correction (2026-11-10): the 2,000-clip scores were measured with a length cap that cut long transcripts.**
- The notebook generated with `max_new_tokens=128`, and validation used `generation_max_length=128`. Whisper spends
  about two tokens per Bangla character, so 128 tokens is about 70 characters.
- The longest of the 2,000 greedy transcripts is 70 characters, while 146 references are longer than 100.
- 304 transcripts are under three quarters of their reference's length.
- So WER 0.435 and CER 0.229 understate the model. The earlier reading here, that the CER miss came from errors spread
  through the text, was wrong; much of it is truncation.
- The parity check, in faster-whisper with no such cap, gives the app's real numbers: WER 0.335, CER 0.110 on 300 of
  those clips.
- The recorded result stays as pre-registered: WER met, CER missed. A corrected re-score of the same 2,000 clips with
  a long enough cap would not touch the model or the checkpoint choice; it has not been run.

**Installed in the app (2026-11-10, by the user's decision).**
- `faster-whisper` 1.2.1 is installed in the backend venv. Every dependency had a Python 3.14 wheel: ctranslate2 4.8.5,
  av 19.0.2, onnxruntime 1.31.1.
- The int8 model (`model.bin` 244.6 MB plus tokenizer and configs) is in
  `backend/models/whisper/krishi-whisper-bn-v1-ct2-int8/`. `bangla_voice` uses that folder unless `KNX_WHISPER_MODEL`
  names another.
- faster-whisper 1.2.1 decodes audio with an argument PyAV 19 no longer accepts (`metadata_errors`), the same break
  the Kaggle notebook hit. `_decode_16k_mono` decodes with PyAV to 16 kHz mono itself. Undecodable audio is a 422,
  not a 500.
- The farmer app records with the browser's MediaRecorder and sends the clip as `audio_base64`. This happens in
  offline mode, or when the browser has no Web Speech recognition, which streams audio to a cloud service. Otherwise it
  keeps using Web Speech.
- Checked:
  - Six Common Voice test clips through `POST /edge/voice-interact`, scored with the notebook's scorer: WER 0.200 and
    CER 0.095 over 70 words. The capped Kaggle transcripts score 0.343 and 0.279 on the same clips. Six clips is a
    smoke check, not a result. Each request took 7–12 s on this PC's CPU, including the rest of the voice pipeline.
  - A WebM/Opus clip, the format Chrome's MediaRecorder writes, transcribed exactly.
  - In the browser, in offline mode, a recorded clip stood in for the microphone (a test-only `getUserMedia` stub). The
    farmer app showed Whisper's transcript, an exact match, tagged Standard Bangla. No real microphone was used.

## 9. Timeline to the showcase (26 Dec, ~8 weeks)

Week 1: driver update, pip install, LoRA train + eval report (one evening; needs the user's go-ahead for ~6 GB of
downloads). Week 2: merge → GGUF → Ollama, base-vs-adapter table live in `/docs`. Weeks 2–3: YOLO dataset + training.
Week 4: retrieval dialect/rerank fixes + fresh blind batch. Weeks 5–8: Docker-host run, Whisper STT
(`KNX_WHISPER_MODEL`, faster-whisper small — currently untested), rehearsal, buffer. Nothing here blocks the demo:
every artifact stays honestly labelled until its real run exists.
