# How to train the KrishiNexus models

A step-by-step runbook for each trainable model: its dataset, its prerequisites, the exact commands, and how it is
evaluated. For *why* each choice was made (base-model survey, split rules, measured numbers, hardware notes), see
[`../TRAINING_PLAN.md`](../TRAINING_PLAN.md) — this file is the "how", that file is the "why".

> **Status:** model 1 has been trained twice with the Kaggle notebook on a T4.
> - The first run (2026-11-08, prompts v3) **failed its targets**.
> - The second run (2026-11-09, tool-grounded prompts v4) **meets every target** on a fresh test split.
>   Negotiation decision accuracy is the narrowest margin, at 0.909 against a 0.90 target.
> - The measured numbers and the diagnosis of both runs are in [`../TRAINING_PLAN.md`](../TRAINING_PLAN.md) §6.
> - Shipped into the app on 2026-11-09:
>   - the adapter, GGUF and Modelfile sit in the git-ignored `backend/models/lora/`, so the backend reports
>     `adapter_present` with the measured scores;
>   - `run_local_inference` grounds each prompt the way the training data does;
>   - live answers need Ollama with the model loaded (`ollama create krishi-bangla -f backend/models/lora/Modelfile`).
> - Model 2, the YOLO potato inspector, was trained once on Kaggle (2026-11-09):
>   - the potato finder meets its target;
>   - the defect segmenter misses its target;
>   - the grade check beats the always-C baseline.
>   Scores are in `../TRAINING_PLAN.md` §8. It isn't wired into the grader yet.

> **Frozen-test rule (applies to every model):** training and validation only ever read the `train` and `val` splits.
> Each `test` split is opened exactly once, by the evaluation step, after the final checkpoint is chosen. Never tune
> hyper-parameters, prompts, or data against a test split or against `../backend/evals/holdout_probe.py`.

---

## Models at a glance

| # | Model | Task | Base | Dataset | Trained? |
|---|---|---|---|---|---|
| 1 | `krishi-bangla-lora-v2` (v1 before it) | Bangla agri market/storage advisor (text) | Qwen2.5-1.5B-Instruct | generated SFT set: v4 3,200 pairs (v1), v5 4,800 freely worded pairs (v2; `prepare_data.py --version 5`) | three times (Kaggle); v2 (2026-11-10) is deployed, meets every target but storage citation (0.806 vs 0.90) |
| 2 | `yolov11n-krishi-bd-v2.1` | potato finder + defect segmenter (two stages) | YOLO11n, YOLO11n-seg | Diamant Potato Dataset (DIU) | twice (Kaggle, 2026-11-09); stage 1 meets target and now outlines, stage 2 misses (0.342 vs 0.50) |
| 3 | `krishi-price-v1` | staple-price forecasts (1–3 months) + wholesale-retail margin flags | LightGBM, GRU, TCN, ensemble | WFP Bangladesh food prices (HDX) | once (Kaggle CPU, 2026-11-09); misses 2 of 3 targets |
| 4 | `krishi-whisper-bn-v1` | Bangla speech-to-text for the voice pipeline (faster-whisper int8) | Whisper Small | Common Voice 13 Bengali (CC0) | once (Kaggle T4, 2026-11-10): WER 0.435 meets, CER 0.229 misses; not installed; notebook `kaggle/krishinexus_whisper_kaggle.ipynb`, results in `../TRAINING_PLAN.md` §8c |

---

## Model 1 — `krishi-bangla-lora-v1` (text LoRA)

Fine-tunes a small instruct model to imitate the deterministic advisory policy offline, in Bangla and its dialects.

### Dataset

| | |
|---|---|
| **Name** | `krishi-bangla-lora-v1` SFT |
| **Source** | **generated from this repo** — not downloaded. `edge_node/ollama_local.build_sft_dataset`, seed 20261109, tool-grounded prompts v4 (each user turn carries the agent's tool result) |
| **Size** | 3,200 pairs — negotiation 1,200 · storage_qa 800 · arbitrage 700 · flood 500 |
| **Split** | family-aware train/val/test = 2,434 / 125 / 641; three OOD families held out of training entirely (Chittagonian dialect, holding_months = 7, Khaliajuri haor) |
| **Format** | JSONL rows `{"messages": [system, user, assistant], example_id, category, dialect, subset}`; the user turn is the question plus `<tool_result name="...">{json}</tool_result>` |
| **License** | synthetic (distilled from the repo's own deterministic engines) |

### Base model

- **`Qwen/Qwen2.5-1.5B-Instruct`** — https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct (Apache-2.0, ungated). Fits a
  4 GB GPU in 4-bit; strong Bengali tokenizer.
- Upgrade path if dialect quality disappoints: **`hishab/titulm-gemma-2-2b-v1.1`** —
  https://huggingface.co/hishab/titulm-gemma-2-2b-v1.1 (gated, Bangla continued-pretrain).
- Documented hub tier (not for 4 GB): **`Qwen/Qwen2.5-7B-Instruct`** — https://huggingface.co/Qwen/Qwen2.5-7B-Instruct.

### Prerequisites

- Python 3.12, an NVIDIA GPU (free Colab T4 works; local RTX 3050 4 GB works per the plan's Windows notes).
- On local Windows: upgrade the NVIDIA driver to 570+, install the **cu128** torch wheel first, set
  `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, close browsers. No flash-attn / triton on Windows — keep
  `attn_implementation="sdpa"`, never `torch_compile`, `dataloader_num_workers=0`.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128   # local Windows only; Colab has torch
pip install "transformers>=5" "trl>=1.16,<2" "peft>=0.17" "accelerate>=1.0" "datasets>=3.0" "bitsandbytes>=0.50.2"
python -c "import torch, bitsandbytes; print(torch.cuda.get_device_name(0))"
```

### Step 1 — build the dataset

```bash
python training/prepare_data.py
# writes training/data/{train,val,test}.jsonl + split_report.json, with leakage assertions
```

### Step 2 — train

Easiest: run **[`kaggle/krishinexus_lora_kaggle.ipynb`](kaggle/krishinexus_lora_kaggle.ipynb)** on Kaggle's free T4.
It trains the adapter and then scores the base model and the adapter on the frozen test split, beside prompt-blind
baselines. It also exports the GGUF. Upload the data and set up the run per
**[`kaggle/KAGGLE_DATASET.md`](kaggle/KAGGLE_DATASET.md)**.

[`train_qlora.ipynb`](train_qlora.ipynb) is the minimal version for Colab or a local GPU; it only trains and merges.

The recipe (the same in both notebooks), from `lora_adapter_spec`:

- **Base model.** 4-bit NF4 frozen base:
  `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=DTYPE)`.
  - `DTYPE` is bf16 on Ampere or newer and fp16 on a T4 (sm_75 has no bf16).
  - Load the model yourself (`device_map={"": 0}`, `attn_implementation="sdpa"`) and pass the model object to
    `SFTTrainer`.
- **LoRA.** `LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])`.
- **Training settings.** `SFTConfig(max_length=512, num_train_epochs=3, effective batch 16, learning_rate=2e-4,
  lr_scheduler_type="cosine", warmup_steps=~3% of the steps, optim="paged_adamw_8bit", bf16=BF16, fp16=not BF16,
  gradient_checkpointing=True)`. Pass the tokenizer as `processing_class`.
  - Effective batch 16 is 1 × 16 on the 4 GB card and 4 × 4 on a T4.
  - The Kaggle notebook uses `max_length=1024` on 16 GB and checks that nothing is truncated.
  - transformers 5 removed `warmup_ratio`; use `warmup_steps`.
- **fp16 GPUs.** TRL 1.17 casts the adapter weights of a quantized model to bf16. On a GPU without bf16, recast the
  trainable weights to fp32 after building the trainer, as both notebooks do.
- Feed **prompt/completion** rows (`prompt=[system,user]`, `completion=[assistant]`) so completion-only loss applies.
- Eval on the **val** split every ~50 steps; keep the best checkpoint.
- Expect ~430 optimizer steps, **1.5–3 h** on the 4 GB card (faster on a T4), plus ~10 min model download (~3 GB).

### Step 3 — merge and deploy

Ollama ≥ 0.34.2 dropped adapter loading, so deploy the **merged** model as a GGUF. Merge into the base the adapter was
trained against, which is the NF4 weights de-quantised, and convert straight to Q8_0:

```bash
# in the notebook: load the base in 4-bit NF4 as trained, .dequantize(), merge_and_unload() -> krishi-bangla-merged/
git clone https://github.com/ggml-org/llama.cpp
pip install -r llama.cpp/requirements/requirements-convert_hf_to_gguf.txt
python llama.cpp/convert_hf_to_gguf.py krishi-bangla-merged --outtype q8_0 --outfile krishi-bangla-q8_0.gguf
```

Modelfile (same SYSTEM line the data trains with):

```
FROM ./krishi-bangla-q8_0.gguf
PARAMETER temperature 0.2
SYSTEM You are KrishiNexus, a Bangla-speaking agricultural market and storage advisor.
```

```bash
ollama create krishi-bangla -f Modelfile
```

Why this route (measured 2026-11-09, `../TRAINING_PLAN.md` §5):
- The old route merged into the bf16 base and quantised to Q4_K_M. Flood-alert accuracy dropped from 1.000 to 0.757.
- The NF4 merge at Q8_0 reproduced the training run on every metric.
- The NF4 merge at Q4_K_M collapsed.

Score any new GGUF through Ollama before switching the app to it
(`../training/kaggle/krishinexus_lora_export_kaggle.ipynb`).

### Step 4 — evaluate (opens `test.jsonl` once)

Deterministic, no LLM judge: every gold value is recomputed by replaying the example's inputs through the same engines
that generated it (`market_prices`, `CIRCUIT_BREAKER`, `breach_probability`), generation is greedy (temperature 0,
fixed seed), and each metric is computed twice — base vs adapter — on identical prompts. Build `training/eval_lora.py`
per `../TRAINING_PLAN.md` section 6. Metrics and targets:

| Metric (test split) | Rule | Target |
|---|---|---|
| negotiation decision accuracy | fair/unfair parsed from the Bangla response vs recomputed gold (fair ⇔ offer ≥ 0.95 × grower) | ≥ 0.90 |
| negotiation price fidelity | grower/wholesale/retail integers present (Bangla digits normalised) | ≥ 0.85 |
| arbitrage verdict exact match | one of the five verdict tokens, vs recomputed verdict | ≥ 0.90 |
| arbitrage trace fidelity | storage/spot/ΔΠ values within max(1 Tk, 0.5%) | ≥ 0.80 |
| flood alert accuracy | RED/ORANGE/YELLOW/GREEN vs recomputed `alert_rule` | ≥ 0.90 |
| flood probability error | parsed % within ±2 points (plus MAE) | ≥ 0.85 |
| storage citation accuracy | exactly the gold `[doc-id]` cited | ≥ 0.90 |
| storage chrF | character n-gram F (n 1–6, β 2), citation stripped | ≥ 60 |
| base vs adapter delta | every metric, both models, same decoding | > 0 everywhere |

Report IID and the three OOD subsets (ood_dialect, ood_months, ood_upazila) separately, plus the truncation rate at
`max_length`. The report lands as JSON at `../backend/models/lora/krishi-bangla-lora-v1/eval_report.json`;
`GET /edge/local-models` surfaces it only when the file exists, and `status` flips to `adapter_present` only when real
weights exist.

The Kaggle notebook implements these scorers and adds two numbers that keep the targets honest:
- **Balanced accuracy for negotiation decisions.** Only about 6% of test offers are fair.
- **A prompt-blind baseline built from train only.** On the current data it already reaches 0.942 decision accuracy
  and 1.000 citation accuracy, so those two targets alone prove nothing.

Read *Known limitations* in [`kaggle/KAGGLE_DATASET.md`](kaggle/KAGGLE_DATASET.md) before you judge a score.

---

## Model 2 — `yolov11n-krishi-bd-v2.1` (YOLO visual defect detection)

Multimodal track. It replaces the classical-CV grader's visual stage with two trained stages: a potato detector and a
defect segmenter. Design, pre-registered targets and results: `../TRAINING_PLAN.md` section 8.

### Dataset

| | |
|---|---|
| **Name** | **Diamant Potato Dataset for ROI and Surface Defect Instance Segmentation** (Daffodil International University) |
| **Link** | https://data.mendeley.com/datasets/4vty9rz7zw/1 (DOI 10.17632/4vty9rz7zw.1) |
| **Size** | 8.9 GB in two zips: `roi_dataset.zip` (2,386 market photos) and `defect_dataset.zip` (1,724 tuber crops) |
| **License** | CC BY 4.0: credit the authors |
| **Classes** | ROI: `potato`. Defects: `scab`, `rot`, `greening`, `mechanical_damage` (instance polygons) |
| **Split** | the authors' own: ROI 1,670 / 477 / 239, defects 1,281 / 176 / 267 (train / val / test) |

### Base weights

- **Ultralytics YOLO11n** and **YOLO11n-seg**: https://github.com/ultralytics/ultralytics (AGPL-3.0).

### Steps (Kaggle, one T4)

1. Push `kaggle/krishinexus_potato_vision_kaggle.ipynb` as a private notebook with **Internet on** and a **T4 GPU**.
   - The notebook downloads both zips and checks their SHA-256.
   - It checks the counts against the dataset page, then trains, scores and writes `eval_report.json`.
   - Without a GPU it runs a CPU smoke test whose scores are not results.
2. Record `eval_report.json` and `run_manifest.json` in `runs/kaggle-t4-<date>-vision/`, and the numbers in
   `../MEMORY.md`.
3. Install the weights: copy `roi_best.pt`, `defect_best.pt`, `eval_report.json` and the grade check's
   `grade_check.json` into `backend/models/yolo/run2/`, or set `KNX_YOLO_WEIGHTS` to a folder that holds them. Then
   run `.venv/Scripts/python -m pip install ultralytics` in `backend/`.
   - `optical_grader.yolo_detect` runs the two-stage cascade on potato photos: outline each potato, cut it out onto
     black, green-boost it, segment defects, and turn the masks into bruising % and rot %.
   - `inference_backend` then reports `ultralytics-yolo two-stage (...)`. Without the package or the weights, and for
     other crops, it stays `classical-cv`. The Docker image doesn't install `ultralytics`.
4. Grade check: `kaggle/krishinexus_potato_grade_check_kaggle.ipynb` runs on CPU with the training notebook's output
   attached.
   - It scores grade accuracy one crop at a time, using the app's outline masks.
   - It also keeps six untouched validation photos for testing the app.

---

## Model 3 — `krishi-price-v1` (staple prices and market margins)

Forecasts monthly retail prices for coarse rice, wheat flour, masur lentils and palm oil in six divisions. It also
flags unusual Dhaka retail margins over wholesale. Design, pre-registered targets and results:
`../TRAINING_PLAN.md` section 8b.

| | |
|---|---|
| **Data** | WFP *Bangladesh - Food Prices*, https://data.humdata.org/dataset/wfp-food-prices-for-bangladesh (CC BY-IGO); the snapshot is the private Kaggle dataset `taksimulhasandip/krishinexus-bd-food-prices` |
| **Notebook** | `kaggle/krishinexus_price_kaggle.ipynb`, run as the private kernel `krishinexus-price-intelligence`, CPU only, about 1 min |
| **Split by time** | train: targets before 2024-10; validation 2024-10 to 2025-09 (chooses the model); test 2025-10 to 2026-09, scored once |
| **Outputs** | `price_eval_report.json`, `price_forecasts.json`, LightGBM and PyTorch weights |

Steps:
1. Push the notebook with the dataset attached and Internet on (rainfall from the Open-Meteo archive).
2. Copy its outputs to `../backend/models/price/`. `GET /market/price-monitor` and the market seat's "Staple price
   monitor" read them. The forecast is shown beside its measured test score.
3. Record the report in `runs/kaggle-cpu-<date>-price/`.

To refresh with newer HDX data, add a new dataset version and move the validation and test windows forward. Do that
before training, never after seeing scores.

---

## Reproducibility checklist

- [ ] `training/data/*.jsonl` regenerated from `prepare_data.py` (seed 20261022) — split counts 2,301 / 239 / 660.
- [ ] Training logs only `train` + `val`; `test` untouched until the eval step.
- [ ] Adapter eval compares base vs adapter on identical prompts, greedy, fixed seed.
- [ ] YOLO test split held out of training; mAP recorded on it.
- [ ] Measured numbers written to `../MEMORY.md`; no eval number hard-coded in the app.
