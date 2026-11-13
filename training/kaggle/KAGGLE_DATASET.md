# KrishiNexus on Kaggle: run guide and dataset description

This file has two parts:

- **Part 1** tells you how to put the SFT data on Kaggle and run
  [`krishinexus_lora_kaggle.ipynb`](krishinexus_lora_kaggle.ipynb) end to end.
- **Part 2** is the dataset description. Paste it into the dataset's *About Dataset* box on Kaggle.

Every figure here was measured on 2026-11-09 from the exported files (`split_report.json` and the files themselves).
Kaggle's menus and quotas change from time to time, so the click paths are a guide rather than a contract. The notebook
checks the GPU, the Internet connection and the data itself, and stops with a clear message if something is off.

---

## Part 1 · Run it on Kaggle

### 1. Build the dataset files (on your machine)

```bash
backend/.venv/Scripts/python training/prepare_data.py
```

This writes `training/data/` with four files: `train.jsonl` (2,434 rows), `val.jsonl` (125), `test.jsonl` (641) and
`split_report.json`. The export is deterministic (seed 20261109) and re-runs the leakage assertions every time.

### 2. Create the Kaggle dataset

Use these values:

| Field | Value | Kaggle's rule |
|---|---|---|
| Title | `KrishiNexus Bangla Agri-Advisor SFT` | 6–50 characters |
| Subtitle | `3,200 synthetic Bangla and dialect farm-advice chats with OOD test splits` | 20–80 characters |
| Slug | `krishinexus-bangla-agri-sft` | 3–50 characters |
| License | your choice; `CC-BY-4.0` keeps attribution | exactly one is required |

The repository itself has no LICENSE file, so choose the license deliberately.

**Website.** Go to Datasets → New Dataset and upload the four files from `training/data/`. Set the title and the
license, then create the dataset. On the dataset page, edit *About Dataset* and paste Part 2. A cover image
(`dataset-cover-image.png`, at least 560×280 px) is optional.

**CLI.** Install the CLI and set up its credentials as the [kaggle-cli README](https://github.com/Kaggle/kaggle-cli)
describes. Then save the following as `training/data/dataset-metadata.json`. The exporter only rewrites its own four
files, so this one survives a re-export.

```json
{
  "title": "KrishiNexus Bangla Agri-Advisor SFT",
  "subtitle": "3,200 synthetic Bangla and dialect farm-advice chats with OOD test splits",
  "id": "YOUR-KAGGLE-USERNAME/krishinexus-bangla-agri-sft",
  "licenses": [{"name": "CC-BY-4.0"}],
  "keywords": ["agriculture", "nlp", "text generation", "bangladesh"],
  "resources": [
    {"path": "train.jsonl", "description": "Training split: 2,434 single-turn chats"},
    {"path": "val.jsonl", "description": "Validation split for checkpoint selection: 125 chats"},
    {"path": "test.jsonl", "description": "Frozen test split, including three out-of-distribution families: 641 chats"},
    {"path": "split_report.json", "description": "Split counts, holdout rules, leakage check, SHA-256 and the system prompt"}
  ]
}
```

Then upload:

```bash
kaggle datasets create -p training/data -t
```

- `-t` keeps the `.jsonl` files as they are; by default Kaggle converts tabular files to CSV.
- The dataset is private unless you add `-u`.
- A later re-export is published with `kaggle datasets version -p training/data -t -m "message"`.
- Paste Part 2 into *About Dataset* afterwards.
- Keywords that don't match an existing Kaggle tag are skipped.

### 3. Open the notebook

1. In Kaggle, go to Code → New Notebook → File → Import Notebook.
2. Pick `training/kaggle/krishinexus_lora_kaggle.ipynb`.
3. In the right-hand panel, set:
   - **Accelerator:** GPU T4 ×2. The notebook uses one T4; on an L4 or newer GPU it switches to bf16 by itself.
   - **Internet:** on. `pip` and the model download need it. If the toggle is greyed out, verify your phone number in
     your Kaggle account settings.
   - **Add Input:** Datasets → your new dataset. If you skip this, the notebook rebuilds the data from GitHub instead.

### 4. Run

1. **Smoke run (recommended first, roughly 20–30 min, estimated).** In the config cell set `MAX_STEPS = 20` and
   `EVAL_LIMIT = 32`, then Run All. Every cell, including the GGUF export, then runs once.
2. **Full run.** Put the defaults back, then use **Save Version → Save & Run All**. It runs in the background, so you can
   close the tab. The first full run (prompts v3, 2026-11-08) took 58 minutes on a T4: 36 minutes of training, then
   the evaluation and the GGUF export. Check your remaining weekly GPU quota before you start.

### 5. Collect the results

Download these from the version's Output tab:

| Output | What it is |
|---|---|
| `krishi-bangla-lora-v1/` | the LoRA adapter, its tokenizer and `eval_report.json` |
| `krishi-bangla-q8_0.gguf` and `Modelfile` | the merged model for Ollama: the adapter merged into the de-quantised NF4 base, at Q8_0 |
| `predictions_test.jsonl` | every test question with the reference, base and adapter answers |
| `training_log.json` and `loss_curve.png` | training and validation loss |
| `run_manifest.json` | GPU, library versions, data hash and settings |

### 6. Bring the results home

1. Copy `krishi-bangla-lora-v1/` to `backend/models/lora/krishi-bangla-lora-v1/`. `GET /edge/local-models` then reports
   `adapter_present`, and the folder already holds `eval_report.json`.
2. In the folder with the GGUF, run:

   ```bash
   ollama create krishi-bangla -f Modelfile
   ```

3. Copy the measured numbers from `eval_report.json` into `MEMORY.md`, and never type them into the app (AGENTS.md §2).
4. Done on 2026-11-09: `lora_adapter_spec` and `LOCAL_MODELS` now describe the 1.5B model (`krishi-bangla-1.5b`), and
   the app grounds its prompts the same way the training data does (`ollama_local.ground_prompt`).
5. Dialect retriever (`krishi-dialect-e5-small-v1`, TRAINING_PLAN.md §7b): from the output of the private kernel
   `krishinexus-dialect-retriever-training` (version 2), copy the folder `krishi-dialect-e5-small-v1/`
   (`model_int8.onnx`, `tokenizer.json`, `krishi_retriever.json`, about 135 MB) to
   `backend/models/retrieval/krishi-dialect-e5-small-v1/`, and check each file's SHA-256 against the kernel's
   `run_manifest.json`. It needs `onnxruntime` and `tokenizers`, which `faster-whisper` installs; without them or the
   folder, retrieval runs as before. `GET /rag/stats` reports `dialect_retriever` when it is loaded.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `No GPU` assertion | Set the accelerator to GPU T4 ×2, then run all again. |
| `More than one GPU is visible` | Restart the session, so the first cell's `CUDA_VISIBLE_DEVICES` applies before torch is imported. |
| `sm_60 ... too old` | P100-class GPUs aren't in current bitsandbytes 4-bit wheels. Pick T4 ×2. |
| `pip` prints dependency-resolver warnings | Usually harmless. They come from preinstalled Kaggle packages pinned to older transformers. |
| The data cell says it is rebuilding from GitHub | The dataset isn't attached, or Kaggle converted the JSONL files. Re-upload with `-t`, or let it rebuild (Internet on). |
| CUDA out of memory | Set `BATCH, GRAD_ACCUM = 2, 8` (the effective batch stays 16). |
| Loss becomes `nan` in fp16 | Set `LEARNING_RATE = 1e-4` and run again. |
| The GGUF step fails | Training and evaluation outputs are already saved. Set `EXPORT_GGUF = False` and convert locally per `TRAINING_PLAN.md` §5. |

---

## Part 2 · Dataset description (paste below this line into Kaggle → About Dataset)

# KrishiNexus Bangla Agri-Advisor SFT

KrishiNexus OS is an edge-to-cloud multi-agent system for Bangladeshi smallholder farmers. It was built for the
International AI Builders Congress 2026 (AgriSphere AI → FarmMarket track). This dataset is what its on-device adapter,
`krishi-bangla-lora-v1`, learns from.

It holds **3,200 single-turn chats**. In each one, a farmer asks a question in Bangla or a regional dialect. The user
turn also carries the **tool result** the KrishiNexus agent got for that question, so the prompts are tool-grounded
(prompts v4). The reference answer is the one KrishiNexus's deterministic engines give, and it follows from the
question and the tool result alone. The tools are:
- `get_daily_commodity_spread`: DAM-modelled market prices;
- `financial_circuit_breaker`: the ΔΠ cold-storage circuit breaker;
- `calculate_haor_flash_flood_risk`: the Sentinel-1 haor flood-breach model;
- `crag_retrieval`: retrieval over the BARI/BAU storage knowledge base.

The data is **synthetic and deterministic**: `training/prepare_data.py` (seed 20261109) regenerates it exactly. It
contains no real farmer conversations and no personal data.

## Files

| File | Rows | Contents |
|---|---|---|
| `train.jsonl` | 2,434 | the training split |
| `val.jsonl` | 125 | the validation split, used only to pick the checkpoint |
| `test.jsonl` | 641 | the frozen test split, with three out-of-distribution families |
| `split_report.json` | – | counts, holdout rules, the leakage-check result, a SHA-256 and the system prompt |

## Row format

Each line is one JSON object:

```json
{"messages": [{"role": "system", "content": "You are KrishiNexus, a Bangla-speaking agricultural market and storage advisor."},
              {"role": "user", "content": "<farmer question>\n<tool_result name=\"<tool>\">{...}</tool_result>"},
              {"role": "assistant", "content": "<reference answer>"}],
 "example_id": "KBL-00001", "category": "market_negotiation", "dialect": "Rangpuri", "subset": "iid"}
```

| Field | Type | Meaning |
|---|---|---|
| `messages` | list of `{role, content}` | system prompt, farmer question with its tool result, and reference answer, ready for a chat template |
| `example_id` | string | stable id, `KBL-00001` to `KBL-03200` |
| `category` | string | `market_negotiation`, `storage_qa`, `arbitrage_math` or `flood_harvest` |
| `dialect` | string | `Standard Bangla`, `Rangpuri`, `Bogura (Varendri)`, `Sylheti` or `Chittagonian` |
| `subset` | string | test rows: `iid`, `ood_dialect`, `ood_months` or `ood_upazila`; always `iid` in train and val |

The longest example (system, user turn and answer together) is 1,468 characters, a storage chat with three retrieved
passages. The mean is 675.

## The four tasks

| Task | Rows | The user turn gives | The reference answer gives |
|---|---|---|---|
| `market_negotiation` | 1,200 | quantity, crop and a middleman's offer, in one of five dialects. The tool gives that day's farm-gate, wholesale and retail prices at the market | the three prices; whether the offer is fair, meaning at least 95% of farm-gate; if not, the gap and pooled-truck advice |
| `storage_qa` | 800 | a question about a topic and crop. The tool gives three retrieved passages: one from the topic's document and two from other documents | the matching passage, quoted, and its `[doc-id]` |
| `arbitrage_math` | 700 | quantity, today's price, expected price after N months, tariff, handling cost and rot rate. The tool gives the production-cost floor and the storage value, spot value and ΔΠ | the ΔΠ trace, then a verdict with Bangla advice: `BLOCK_SPOT_SALE` if today's price is below the floor and ΔΠ > 0, `ALLOW_STORAGE` if ΔΠ > 0, otherwise `ALLOW_SPOT_SALE` |
| `flood_harvest` | 500 | the haor, the month, upstream 72-hour rainfall and Sentinel-1 radar backscatter. The tool gives the embankment-breach probability | the probability, an alert (RED ≥ 70%, ORANGE ≥ 45%, YELLOW ≥ 20%, otherwise GREEN) and harvest advice |

Labels are balanced by construction. Each example draws a target label, then re-samples its inputs until the engine
gives that label. In test:
- 154 of 340 offers are fair.
- The arbitrage verdicts are 63 BLOCK_SPOT_SALE, 73 ALLOW_STORAGE and 55 ALLOW_SPOT_SALE.
- The flood alerts are 17 RED, 19 ORANGE, 18 YELLOW and 16 GREEN.

### One example per task (from train; the glosses are translations)

**market_negotiation** (Bogura)
- User turn:
  ```text
  হামি 21 মণ বেগুন লিয়া বসি আছি, পাইকার 38 টাকা কয়। ক্যাংকা করমু?
  <tool_result name="get_daily_commodity_spread">{"crop": "Brinjal", "district": "Rangpur", "market_date": "2026-10-25", "grower_price_tk_per_kg": 35, "wholesale_price_tk_per_kg": 47, "retail_price_tk_per_kg": 63}</tool_result>
  ```
  - *Gloss of the question:* "I'm sitting with 21 maunds of brinjal and the paikar says Tk 38. What should I do?"
- Answer: 25 Oct তারিখে Rangpur বাজারে খামার দাম কেজি 35 টাকা, পাইকারি 47 টাকা, খুচরা 63 টাকা। এই দাম ন্যায্য, বিক্রি করতে পারেন।
  - *Gloss:* "On 25 Oct at Rangpur market, farm-gate is Tk 35/kg, wholesale 47, retail 63. This price is fair; you can
    sell."

**storage_qa**
- User turn:
  ```text
  post-harvest loss নিয়ে বারি/বাউর পরামর্শ কী?
  <tool_result name="crag_retrieval">[{"doc_id": "FFWC-HAOR-01", "title": "Haor flash floods, embankment breaches and early warning", "text": "Alerts 72 hours ahead allow emergency harvest of mature plots."}, {"doc_id": "BAU-PHL-02", "title": "Post-harvest loss along fruit and vegetable value chains", "text": "Losses accumulate at every hand-off: 25-43.5% of fruit and vegetable output is lost between field and consumer."}, {"doc_id": "DAM-TRANS-01", "title": "Truck freight corridors to Dhaka terminal markets", "text": "Perishables should move at night to avoid heat, and pooling smallholder lots to fill a truck cuts freight to Tk 2-4 per kg."}]</tool_result>
  ```
  - *Gloss of the question:* "What do BARI/BAU advise about post-harvest loss?"
- Answer: Losses accumulate at every hand-off: 25-43.5% of fruit and vegetable output is lost between field and
  consumer. [BAU-PHL-02]

**arbitrage_math**
- User turn:
  ```text
  4300 কেজি আলু আছে। আজ দাম 32.9 টাকা, 4 মাস পর 29.9 টাকা আশা করছি। হিমাগার ভাড়া 8.0 টাকা, হ্যান্ডলিং 0.71 টাকা, পচনের হার 0.09। রাখব না বেচব?
  <tool_result name="financial_circuit_breaker">{"production_cost_floor_bdt": 15.0, "storage_branch_value_bdt": 79546, "spot_branch_value_bdt": 141470, "delta_pi_bdt": -61924}</tool_result>
  ```
- Answer: `<arbitrage_math_trace>storage = 4300*(1-0.09)*29.9 - 4300*(8.0+0.71) = 79546; spot = 4300*32.9 = 141470;
  dPi = -61924</arbitrage_math_trace>` ALLOW_SPOT_SALE: এখন বিক্রি করাই লাভজনক।
  - *Gloss of the advice:* "Selling now pays more."

**flood_harvest**
- User turn:
  ```text
  ইটনা হাওরে মে মাসে উজানে ৭২ ঘণ্টায় ৪০২ মিমি বৃষ্টি, রাডারে পানির সংকেত -৮.৮ ডিবি। ধান কাটব কখন?
  <tool_result name="calculate_haor_flash_flood_risk">{"upazila": "Itna", "embankment_breach_probability_pct": 95}</tool_result>
  ```
  - *Gloss of the question:* "Itna haor, May: 402 mm of rain upstream in 72 h, radar water signal −8.8 dB. When
    should I harvest?"
- Answer: ইটনা হাওরে বাঁধ ভাঙার সম্ভাবনা ৯৫% (RED)। এখনই ৮০% পাকা ধান কেটে উঁচু জায়গায় সরান।
  - *Gloss:* "Breach probability 95% (RED). Harvest the 80%-ripe paddy now and move it to high ground."

## Splits and held-out families

| Task | train | val | test |
|---|---|---|---|
| `market_negotiation` | 830 | 30 | 340 |
| `storage_qa` | 747 | 13 | 40 |
| `arbitrage_math` | 458 | 51 | 191 |
| `flood_harvest` | 399 | 31 | 70 |
| **total** | **2,434** | **125** | **641** |

The split is **family-aware**: whole families move together, so no near-duplicate can leak from train into test.
Negotiation is split by (dialect, crop, market) cell, and the other tasks by identical answer. The exporter re-checks
this on every run. The current result: 1,170 answer families and 56 negotiation cells, none of them in two splits.

Three families are held out of training entirely and appear only in test:

| `subset` | Test rows | What is held out |
|---|---|---|
| `ood_dialect` | 240 | every Chittagonian negotiation, a dialect never seen in training |
| `ood_months` | 128 | every arbitrage case with a 7-month holding period |
| `ood_upazila` | 33 | every flood case for Khaliajuri (খালিয়াজুরী) haor |
| `iid` | 240 | the rest of test, from families that are not in train or val |

Dialect counts per split:

| Dialect | train | val | test |
|---|---|---|---|
| Standard Bangla | 1,637 | 90 | 263 |
| Sylheti | 427 | 15 | 48 |
| Rangpuri | 150 | 10 | 80 |
| Bogura (Varendri) | 220 | 10 | 10 |
| Chittagonian | 0 | 0 | 240 |

## How it was made

- **Generator.** `backend/edge_node/ollama_local.build_sft_dataset` (seed 20261109, family-aware split salted
  `split-v4`, tool-grounded prompts v4). The exporter, `training/prepare_data.py`, writes these files and re-asserts
  that nothing leaks.
- **Why tool-grounded (prompts v4, 2026-11-09).** The first training run, on prompts v3 (2026-11-08), showed that a
  1.5B adapter cannot compute prices, ΔΠ or breach probabilities from memory. It collapsed to one label per task and
  scored below the prompt-blind baseline on three tasks. In KrishiNexus the agents compute these numbers with tools,
  so the model now reads them and decides.
- **A fresh test batch.** The seed and the split salt are new. No v4 test question appears in the v3 test split.
- **Verified:**
  - A rule reader recovers every one of the 3,200 labels from its own user turn.
  - Replaying each input through the engines reproduces every tool result.
- **Engines:**
  - *negotiation:* the DAM-modelled seasonal price model (`dam-market-mcp market_prices`), rounded to whole taka;
  - *arbitrage:* the ΔΠ financial circuit breaker;
  - *flood:* `agri-weather-sar-mcp breach_probability`, rounded to a whole percent before the alert is ruled;
  - *storage:* sentences from the project's 18-passage BARI/BAU/BCSA knowledge seed.
- **Prices** are modelled on DAM benchmarks. They are not live market data.
- **Reproducibility.** The generator's canonical dump of all 3,200 examples hashes to
  `794becfc999b64a8f6af8f3b819c3d11c230ab0b1a3f4413ebe71f31ebbb87a1` (`split_report.json → jsonl_sha256`).

## Known limitations (measured)

Read these before you trust a score.

1. **Tool results are always right here.** Every tool result is the engine's exact, complete output. The model learns
   to read and decide, not to doubt a tool. In the app, a retrieval miss or a stale price would pass straight through.
2. **Storage citation is decided by the question.** Each question names its document's topic, and every document has
   a topic of its own. A model that ignores the passages can still cite the right document: the prompt-blind baseline
   scores 1.000. Use chrF to see whether it quoted the right passage. The distractors are random passages from other
   documents, not hard negatives, and all 40 test questions also appear in train with different passages.
3. **Fair/unfair turns on a 95% line the model must learn.** The tool gives the farm-gate price, not the threshold.
   Offers near 95% of farm-gate are the hard cases.
4. **Arbitrage uses 3 of its 5 verdicts.** `WARN_STORAGE_LOSES_VALUE` and `WARN_NO_STORAGE_CAPACITY` never occur.
5. **Dialects are templated.** Each dialect has a single question template written by the project team. No native
   speaker has reviewed them, so Chittagonian generalisation is measured on one template.
6. **Validation is small.** It has 125 rows, only 30 of them negotiation, because whole negotiation cells move
   together.
7. **It is small and synthetic.** It teaches the advisor's format and its decision policy over tool results. It is not
   a corpus of real farmer speech.

## How to evaluate on it

- **Freeze the test split.** Use train to fit, val to pick checkpoints, and test once at the end. Never tune prompts,
  data or hyper-parameters on test.
- **Score deterministically.** The companion notebook parses each answer and compares it with the reference: the
  decision, verdict, alert, prices, the ΔΠ values (within max(1 Tk, 0.5%)), the probability (within ±2 points), the
  citation, and chrF2 on the storage sentence. Report `iid` and each `ood_*` subset separately.
- **Always show a prompt-blind baseline.** The one below is built from train alone: the majority label per task, or
  the train answer to the same storage question (read without its tool result). It clears one of the project's
  targets:

| Metric | Project target | Prompt-blind baseline (full test) |
|---|---|---|
| negotiation decision accuracy | ≥ 0.90 | 0.547 |
| negotiation balanced accuracy | – | 0.500 |
| negotiation price fidelity | ≥ 0.85 | 0.000 |
| arbitrage verdict exact match | ≥ 0.90 | 0.288 |
| arbitrage trace fidelity | ≥ 0.80 | 0.000 |
| flood alert accuracy | ≥ 0.90 | 0.229 |
| flood probability within ±2 points | ≥ 0.85 | 0.000 |
| storage citation accuracy | ≥ 0.90 | **1.000** |
| storage chrF2 | ≥ 60 | 21.52 |

## A model trained on it (measured)

`krishi-bangla-lora-v1` is QLoRA on Qwen2.5-1.5B-Instruct.
- It was trained for 3 epochs on a Kaggle T4 with the companion notebook, on data sha256 `794becfc…87a1`.
- It was scored once on the full test split, with greedy decoding.
- The deployed copy merges the adapter into the de-quantised NF4 base it trained against, as a Q8_0 GGUF. It was
  scored through Ollama on an RTX 3050.

| Metric | Target | 4-bit model as trained | Deployed Q8_0 GGUF | Prompt-blind baseline |
|---|---|---|---|---|
| negotiation decision accuracy | ≥ 0.90 | 0.909 | 0.915 | 0.547 |
| negotiation price fidelity | ≥ 0.85 | 0.985 | 0.979 | 0.000 |
| arbitrage verdict exact match | ≥ 0.90 | 1.000 | 1.000 | 0.288 |
| arbitrage trace fidelity | ≥ 0.80 | 1.000 | 1.000 | 0.000 |
| flood alert accuracy | ≥ 0.90 | 1.000 | 1.000 | 0.229 |
| flood probability within ±2 points | ≥ 0.85 | 1.000 | 1.000 | 0.000 |
| storage citation accuracy | ≥ 0.90 | 0.925 | 0.925 | 1.000 |
| storage chrF2 | ≥ 60 | 93.28 | 93.28 | 21.52 |

Read these with care:
- With the tool result in the prompt, arbitrage and flood are copy-and-threshold tasks. Their scores show faithful
  reading of the tool result, not forecasting.
- The export matters. The same adapter merged into the bf16 base and quantised to Q4_K_M scored 0.757 on flood alerts.
  The NF4 merge at Q8_0 gives the same answer as the 4-bit model on 97.7% of the test questions.
- Questions worded outside the four templates can still get wrong answers, e.g. a flood question that gives no
  rainfall or radar readings.

## Use it

```python
import pandas as pd

train = pd.read_json("/kaggle/input/krishinexus-bangla-agri-sft/train.jsonl", lines=True)  # adjust to your mount path

from datasets import load_dataset

ds = load_dataset("json", data_files={"train": "train.jsonl", "validation": "val.jsonl"})
# For TRL's SFTTrainer: {"prompt": messages[:-1], "completion": messages[-1:]} gives completion-only loss.
```

The companion Kaggle notebook (`training/kaggle/krishinexus_lora_kaggle.ipynb` in the repository) fine-tunes
Qwen2.5-1.5B-Instruct with QLoRA on this data. It then scores the base model and the adapter on the frozen test split
and exports a Q8_0 GGUF for Ollama.

## Provenance and citation

- **Code, generator and notebook:** https://github.com/HTanvir0011/KrishiNexus
  (`backend/edge_node/ollama_local.py`, `training/prepare_data.py`)
- **Project:** KrishiNexus OS, International AI Builders Congress 2026, Daffodil International University
  (showcase on 26 December 2026)

```bibtex
@misc{krishinexus_sft_2026,
  title  = {KrishiNexus Bangla Agri-Advisor SFT},
  author = {{KrishiNexus OS team}},
  year   = {2026},
  note   = {Synthetic, deterministic; generated by training/prepare_data.py with seed 20261109},
  url    = {https://github.com/HTanvir0011/KrishiNexus}
}
```
