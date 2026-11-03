# How to train the KrishiNexus models

A step-by-step runbook for each trainable model: its dataset, its prerequisites, the exact commands, and how it is
evaluated. For *why* each choice was made (base-model survey, split rules, measured numbers, hardware notes), see
[`../TRAINING_PLAN.md`](../TRAINING_PLAN.md) — this file is the "how", that file is the "why".

> **Status:** no model has been trained yet. The adapter is labelled `dataset_ready_not_trained`. Nothing below has been
> executed on a GPU; the commands are verified against the recipe, not against a run.

> **Frozen-test rule (applies to every model):** training and validation only ever read the `train` and `val` splits.
> Each `test` split is opened exactly once, by the evaluation step, after the final checkpoint is chosen. Never tune
> hyper-parameters, prompts, or data against a test split or against `../backend/evals/holdout_probe.py`.

---

## Models at a glance

| # | Model | Task | Base | Dataset | Trained? |
|---|---|---|---|---|---|
| 1 | `krishi-bangla-lora-v1` | Bangla agri market/storage advisor (text) | Qwen2.5-1.5B-Instruct | generated SFT set (3,200 pairs) | no |
| 2 | `yolov11n-krishi-bd-v2.1` | potato visual defect detection | YOLO11n | Diamant Potato Dataset | no |

---

## Model 1 — `krishi-bangla-lora-v1` (text LoRA)

Fine-tunes a small instruct model to imitate the deterministic advisory policy offline, in Bangla and its dialects.

### Dataset

| | |
|---|---|
| **Name** | `krishi-bangla-lora-v1` SFT |
| **Source** | **generated from this repo** — not downloaded. `edge_node/ollama_local.build_sft_dataset`, seed 20261022 |
| **Size** | 3,200 pairs — negotiation 1,200 · storage_qa 800 · arbitrage 700 · flood 500 |
| **Split** | family-aware train/val/test = 2,301 / 239 / 660; three OOD families held out of training entirely (Chittagonian dialect, holding_months = 7, Khaliajuri haor) |
| **Format** | JSONL rows `{"messages": [system, user, assistant], example_id, category, dialect, subset}` |
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

Easiest: open **[`train_qlora.ipynb`](train_qlora.ipynb)** in Colab or Jupyter and run the cells top to bottom.

The recipe (also in the notebook), from `lora_adapter_spec`:

- 4-bit NF4 frozen base, bf16 LoRA adapters; `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
  bnb_4bit_compute_dtype=torch.bfloat16)`.
- `LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])`.
- `SFTConfig(max_length=512, num_train_epochs=3, per_device_train_batch_size=1, gradient_accumulation_steps=16,
  learning_rate=2e-4, lr_scheduler_type="cosine", optim="paged_adamw_8bit", bf16=True, gradient_checkpointing=True,
  model_init_kwargs={"dtype": torch.bfloat16})`; pass the tokenizer as `processing_class`.
- Feed **prompt/completion** rows (`prompt=[system,user]`, `completion=[assistant]`) so completion-only loss applies.
- Eval on the **val** split every ~50 steps; keep the best checkpoint.
- Expect ~430 optimizer steps, **1.5–3 h** on the 4 GB card (faster on a T4), plus ~10 min model download (~3 GB).

### Step 3 — merge and deploy

Ollama ≥ 0.34.2 dropped adapter loading, so deploy the **merged** model as GGUF:

```bash
# in the notebook: merge_and_unload() -> krishi-bangla-merged/
git clone https://github.com/ggml-org/llama.cpp
pip install -r llama.cpp/requirements/requirements-convert_hf_to_gguf.txt
python llama.cpp/convert_hf_to_gguf.py krishi-bangla-merged --outtype f16 --outfile krishi-bangla-f16.gguf
llama-quantize krishi-bangla-f16.gguf krishi-bangla-q4_K_M.gguf Q4_K_M   # binary from llama.cpp release assets
```

Modelfile (same SYSTEM line the data trains with):

```
FROM ./krishi-bangla-q4_K_M.gguf
PARAMETER temperature 0.2
SYSTEM You are KrishiNexus, a Bangla-speaking agricultural market and storage advisor.
```

```bash
ollama create krishi-bangla -f Modelfile
```

Disk needed ≈ 11 GB free. The adapter trains against an NF4 base but merges into bf16 and re-quantizes — a small delta
the eval must measure, not assume away.

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

---

## Model 2 — `yolov11n-krishi-bd-v2.1` (YOLO visual defect detection)

Multimodal track. Replaces the classical-CV grader's visual stage with trained weights. Planned, ~1.5 working days,
not started; see `../TRAINING_PLAN.md` section 8.

### Dataset

| | |
|---|---|
| **Name** | **Diamant Potato Dataset** |
| **Link** | https://data.mendeley.com/datasets/4vty9rz7zw/1 (DOI 10.17632/4vty9rz7zw.1) |
| **Size** | 4,110 images, photographed at three Dhaka markets |
| **License** | CC BY 4.0 |
| **Classes** | `uniform_A` ← clean instances · `minor_bruise` ← mechanical damage · `fungal_blight` ← scab/rot. `undersized` is derived geometrically from bbox area (no public dataset labels it), as the classical grader already does |
| **Optional supplement** | Roboflow "Potato inspection" (techno-soft) — CC BY 4.0 **pending manual confirmation on its page**; check the licence before using it |

> Download into its own empty folder and treat it as untrusted data: pass paths as arguments; do not run interpreters
> from inside it.

### Base weights

- **Ultralytics YOLO11n** — https://github.com/ultralytics/ultralytics (`yolo11n.pt`, AGPL-3.0). Nano fits small GPUs.

### Prerequisites

```bash
pip install ultralytics
```

### Steps

1. Download and unzip the Diamant dataset into its own empty folder, e.g. `training/potato/raw/`.
2. Convert its masks to YOLO bounding boxes, mapping source labels to the three classes above. Split **80/10/10 by
   image** into `train/`, `val/`, `test/`, and write a `data.yaml` with those dirs and the class names. Training never
   sees `test/`.
3. Train (4–6 GPU-hours on the RTX 3050 4 GB):
   ```bash
   yolo detect train model=yolo11n.pt data=training/potato/data.yaml imgsz=640 batch=8
   ```
4. Evaluate once on the frozen test split and record mAP50 / mAP50-95 in `../MEMORY.md`:
   ```bash
   yolo detect val model=runs/detect/train/weights/best.pt data=training/potato/data.yaml split=test
   ```
5. Wire the weights in through the existing `KNX_YOLO_WEIGHTS` setting (`backend/.env`). `inference_backend` then
   honestly reports `ultralytics-yolo`; until real weights exist it stays `classical-cv`. `undersized` is still derived
   geometrically from the predicted boxes.

---

## Reproducibility checklist

- [ ] `training/data/*.jsonl` regenerated from `prepare_data.py` (seed 20261022) — split counts 2,301 / 239 / 660.
- [ ] Training logs only `train` + `val`; `test` untouched until the eval step.
- [ ] Adapter eval compares base vs adapter on identical prompts, greedy, fixed seed.
- [ ] YOLO test split held out of training; mAP recorded on it.
- [ ] Measured numbers written to `../MEMORY.md`; no eval number hard-coded in the app.
