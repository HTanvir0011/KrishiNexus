"""Versioned XML prompt registry with a DSPy-style (BootstrapFewShot + instruction search) optimiser.

Every agent prompt is assembled from structured sections and rendered as XML::

    <system_prompt agent="..." version="...">
      <role_definition/> <agronomy_constraints/> <dam_market_context/> <decision_rule/>
      <few_shot_bangla_examples/> <chain_of_thought_schema/> <output_json_contract/>
    </system_prompt>

Prompts are treated as programs: each instruction variant declares machine-readable decision
parameters (thresholds, circuit-breaker conditions) that the deterministic agents execute, and
each few-shot demo carries an output that must satisfy the agent's JSON contract. The optimiser
scores candidates (instruction variant x demo subset) on a labelled dev set:

    score = 0.5 * decision_accuracy + 0.3 * json_validity + 0.1 * label_coverage + 0.1 * token_efficiency

``v1.0`` is the hand-written baseline; ``v1.2-dspy-optimized`` is the best candidate found. Agents
read their decision parameters from the *active* (optimised) version.
"""

from __future__ import annotations

import difflib
import hashlib
import itertools
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from guardrails.financial_circuit import ArbitrageVerdict
from optimization.token_compressor import estimate_tokens
from schemas.mcp_models import FloodAlertLevel

BASELINE_VERSION = "v1.0"
OPTIMIZED_VERSION = "v1.2-dspy-optimized"
TOKEN_BUDGET = 2_500
MAX_DEMOS = 3
SCORE_WEIGHTS = {"decision_accuracy": 0.5, "json_validity": 0.3, "label_coverage": 0.1, "token_efficiency": 0.1}

Params = Mapping[str, float | bool]


class FewShotExample(BaseModel):
    model_config = ConfigDict(frozen=True)

    example_id: str
    dialect: str
    farmer_utterance: str
    reasoning: tuple[str, ...]
    output: dict[str, Any]
    label: str


class InstructionVariant(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    rule_text: str
    params: dict[str, float | bool]


class DevScenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    inputs: dict[str, float | bool]
    gold: str


@dataclass(frozen=True, slots=True)
class AgentPromptSpec:
    agent: str
    title: str
    role: str
    agronomy: str
    market: str
    cot_steps: tuple[str, ...]
    contract: type[BaseModel]
    few_shot_pool: tuple[FewShotExample, ...]
    variants: tuple[InstructionVariant, ...]
    dev_set: tuple[DevScenario, ...]
    predictor: Callable[[Params, Mapping[str, float | bool]], str]
    baseline_variant: str
    baseline_demos: tuple[str, ...]

    def variant(self, variant_id: str) -> InstructionVariant:
        return next(v for v in self.variants if v.variant_id == variant_id)

    def demos(self, ids: tuple[str, ...]) -> list[FewShotExample]:
        by_id = {d.example_id: d for d in self.few_shot_pool}
        return [by_id[i] for i in ids]


class PromptMetrics(BaseModel):
    decision_accuracy: float
    json_validity: float
    label_coverage: float
    token_estimate: int
    token_efficiency: float
    score: float


class PromptVersion(BaseModel):
    agent: str
    version: str
    parent_version: str | None
    variant_id: str
    rule_text: str
    params: dict[str, float | bool]
    demo_ids: list[str]
    xml: str
    sha256: str
    metrics: PromptMetrics


class OptimizationTrial(BaseModel):
    variant_id: str
    demo_ids: list[str]
    metrics: PromptMetrics


class OptimizationReport(BaseModel):
    agent: str
    method: str
    baseline_version: str
    optimized_version: str
    baseline_score: float
    optimized_score: float
    improvement: float
    trials_evaluated: int
    top_trials: list[OptimizationTrial]
    diff: list[str]


class RegistryAgentView(BaseModel):
    agent: str
    title: str
    active_version: str
    versions: list[PromptVersion]
    optimization: OptimizationReport


class RegistryListing(BaseModel):
    agents: list[RegistryAgentView]
    score_weights: dict[str, float]


def render_xml(spec: AgentPromptSpec, version: str, variant: InstructionVariant, demos: list[FewShotExample]) -> str:
    def block(tag: str, body: str, indent: str = "  ") -> str:
        return f"{indent}<{tag}>{escape(body)}</{tag}>"

    lines = [f"<system_prompt agent={quoteattr(spec.agent)} version={quoteattr(version)}>"]
    lines.append(block("role_definition", spec.role))
    lines.append(block("agronomy_constraints", spec.agronomy))
    lines.append(block("dam_market_context", spec.market))
    lines.append(f"  <decision_rule id={quoteattr(variant.variant_id)} params={quoteattr(json.dumps(variant.params, sort_keys=True))}>"
                 f"{escape(variant.rule_text)}</decision_rule>")
    lines.append("  <few_shot_bangla_examples>")
    for demo in demos:
        lines.append(f"    <example id={quoteattr(demo.example_id)} dialect={quoteattr(demo.dialect)}>")
        lines.append(block("farmer", demo.farmer_utterance, "      "))
        lines.append("      <reasoning>" + "".join(f"<step>{escape(s)}</step>" for s in demo.reasoning) + "</reasoning>")
        lines.append(block("output", json.dumps(demo.output, ensure_ascii=False, sort_keys=True), "      "))
        lines.append("    </example>")
    lines.append("  </few_shot_bangla_examples>")
    lines.append("  <chain_of_thought_schema>" + "".join(
        f'<step n="{n}">{escape(s)}</step>' for n, s in enumerate(spec.cot_steps, start=1)) + "</chain_of_thought_schema>")
    lines.append(block("output_json_contract", json.dumps(spec.contract.model_json_schema(), sort_keys=True)))
    lines.append("</system_prompt>")
    return "\n".join(lines)


def evaluate(spec: AgentPromptSpec, variant: InstructionVariant, demos: list[FewShotExample], xml: str) -> PromptMetrics:
    correct = sum(spec.predictor(variant.params, s.inputs) == s.gold for s in spec.dev_set)
    accuracy = correct / len(spec.dev_set)
    valid = 0
    for demo in demos:
        try:
            spec.contract.model_validate(demo.output)
            valid += 1
        except ValidationError:
            continue
    validity = valid / len(demos) if demos else 0.0
    gold_labels = {s.gold for s in spec.dev_set}
    coverage = len({d.label for d in demos} & gold_labels) / len(gold_labels)
    tokens = estimate_tokens(xml)
    efficiency = max(0.0, 1 - tokens / TOKEN_BUDGET)
    score = (SCORE_WEIGHTS["decision_accuracy"] * accuracy + SCORE_WEIGHTS["json_validity"] * validity
             + SCORE_WEIGHTS["label_coverage"] * coverage + SCORE_WEIGHTS["token_efficiency"] * efficiency)
    return PromptMetrics(decision_accuracy=round(accuracy, 4), json_validity=round(validity, 4),
                         label_coverage=round(coverage, 4), token_estimate=tokens,
                         token_efficiency=round(efficiency, 4), score=round(score, 4))


def build_version(spec: AgentPromptSpec, version: str, parent: str | None, variant: InstructionVariant,
                  demo_ids: tuple[str, ...]) -> PromptVersion:
    demos = spec.demos(demo_ids)
    xml = render_xml(spec, version, variant, demos)
    return PromptVersion(
        agent=spec.agent, version=version, parent_version=parent, variant_id=variant.variant_id,
        rule_text=variant.rule_text, params=dict(variant.params), demo_ids=list(demo_ids), xml=xml,
        sha256=hashlib.sha256(xml.encode("utf-8")).hexdigest(), metrics=evaluate(spec, variant, demos, xml),
    )


class DSPyPromptOptimizer:
    """Exhaustive instruction x few-shot-subset search (DSPy BootstrapFewShotWithRandomSearch semantics,
    enumerated deterministically because the candidate space is small)."""

    method = "DSPy-style BootstrapFewShot + instruction search (deterministic enumeration)"

    def optimize(self, spec: AgentPromptSpec, baseline: PromptVersion) -> tuple[PromptVersion, OptimizationReport]:
        trials: list[tuple[PromptMetrics, InstructionVariant, tuple[str, ...]]] = []
        pool_ids = [d.example_id for d in spec.few_shot_pool]
        for variant in spec.variants:
            for size in range(1, min(MAX_DEMOS, len(pool_ids)) + 1):
                for demo_ids in itertools.combinations(pool_ids, size):
                    demos = spec.demos(demo_ids)
                    xml = render_xml(spec, OPTIMIZED_VERSION, variant, demos)
                    trials.append((evaluate(spec, variant, demos, xml), variant, demo_ids))
        trials.sort(key=lambda t: (-t[0].score, t[0].token_estimate))
        _, best_variant, best_demos = trials[0]
        optimized = build_version(spec, OPTIMIZED_VERSION, baseline.version, best_variant, best_demos)
        diff = list(difflib.unified_diff(baseline.xml.splitlines(), optimized.xml.splitlines(),
                                         fromfile=f"{spec.agent}@{baseline.version}",
                                         tofile=f"{spec.agent}@{optimized.version}", lineterm="", n=0))
        report = OptimizationReport(
            agent=spec.agent,
            method=self.method,
            baseline_version=baseline.version,
            optimized_version=optimized.version,
            baseline_score=baseline.metrics.score,
            optimized_score=optimized.metrics.score,
            improvement=round(optimized.metrics.score - baseline.metrics.score, 4),
            trials_evaluated=len(trials),
            top_trials=[OptimizationTrial(variant_id=v.variant_id, demo_ids=list(d), metrics=m) for m, v, d in trials[:5]],
            diff=diff,
        )
        return optimized, report


class PromptRegistry:
    def __init__(self, specs: tuple[AgentPromptSpec, ...], optimizer: DSPyPromptOptimizer | None = None) -> None:
        self.specs = {s.agent: s for s in specs}
        self.optimizer = optimizer or DSPyPromptOptimizer()
        self._versions: dict[str, dict[str, PromptVersion]] = {}
        self._reports: dict[str, OptimizationReport] = {}
        self._active: dict[str, str] = {}
        for spec in specs:
            baseline = build_version(spec, BASELINE_VERSION, None, spec.variant(spec.baseline_variant), spec.baseline_demos)
            optimized, report = self.optimizer.optimize(spec, baseline)
            self._versions[spec.agent] = {baseline.version: baseline, optimized.version: optimized}
            self._reports[spec.agent] = report
            self._active[spec.agent] = optimized.version if optimized.metrics.score >= baseline.metrics.score else baseline.version

    def active(self, agent: str) -> PromptVersion:
        return self._versions[agent][self._active[agent]]

    def get(self, agent: str, version: str) -> PromptVersion:
        return self._versions[agent][version]

    def params(self, agent: str) -> dict[str, float | bool]:
        return self.active(agent).params

    def listing(self) -> RegistryListing:
        return RegistryListing(
            agents=[
                RegistryAgentView(agent=agent, title=self.specs[agent].title, active_version=self._active[agent],
                                  versions=list(versions.values()), optimization=self._reports[agent])
                for agent, versions in self._versions.items()
            ],
            score_weights=SCORE_WEIGHTS,
        )


# ---------------------------------------------------------------------------
# Output JSON contracts
# ---------------------------------------------------------------------------


class SupervisorContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: list[str] = Field(min_length=1)
    circuit_breaker: Literal["TRIPPED", "CLEAR"]
    requires_farmer_approval: bool
    summary_bn: str = Field(min_length=5)


class VisionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade: Literal["A", "B", "C"]
    reasons: list[str] = Field(min_length=1)
    storage_protocol_cited: bool


class SyndicateContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anomaly: bool
    markup_pct: float = Field(ge=0)
    recommended_channel: str
    pooled_net_tk_per_kg: float = Field(ge=0)


class ColdChainContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: ArbitrageVerdict
    delta_pi_bdt: float
    enforced_action: str
    reserve_slot: bool


class ClimateContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_level: FloodAlertLevel
    trigger_early_harvest: bool
    credit_score: int = Field(ge=300, le=850)
    loan_eligible: bool


# ---------------------------------------------------------------------------
# Decision rules executed by the agents (the "program" each prompt declares)
# ---------------------------------------------------------------------------


def arbitrage_rule(p: Params, x: Mapping[str, float | bool]) -> str:
    """BLOCK a sale below the production-cost floor, subject to the variant's conditions."""
    below = float(x["spot"]) < float(p["floor_tk"])
    quota_ok = bool(x["quota_ok"]) or not bool(p["require_open_quota"])
    dpi_ok = float(x["dpi"]) > 0 or not bool(p["require_positive_dpi"])
    return "BLOCK" if below and quota_ok and dpi_ok else "ALLOW"


def grade_rule(p: Params, x: Mapping[str, float | bool]) -> str:
    u, b, r = float(x["uniformity"]), float(x["bruising"]), float(x["rot"])
    if u >= float(p["a_uniformity"]) and b <= float(p["a_bruising"]) and r <= float(p["a_rot"]):
        return "A"
    if u >= float(p["b_uniformity"]) and b <= float(p["b_bruising"]) and r <= float(p["b_rot"]):
        return "B"
    return "C"


def markup_rule(p: Params, x: Mapping[str, float | bool]) -> str:
    return "ANOMALY" if float(x["markup"]) > float(p["anomaly_threshold_pct"]) else "NORMAL"


def alert_rule(p: Params, x: Mapping[str, float | bool]) -> str:
    prob = float(x["probability"])
    if prob >= float(p["red"]):
        return "RED"
    if prob >= float(p["orange"]):
        return "ORANGE"
    if prob >= float(p["yellow"]):
        return "YELLOW"
    return "GREEN"


def _labelled(rule: Callable[[Params, Mapping[str, float | bool]], str], canonical: Params,
              rows: list[dict[str, float | bool]]) -> tuple[DevScenario, ...]:
    return tuple(DevScenario(scenario_id=f"dev-{i:02d}", inputs=row, gold=rule(canonical, row)) for i, row in enumerate(rows, 1))


ARBITRAGE_VARIANTS = (
    InstructionVariant(variant_id="floor-only", params={"floor_tk": 15.0, "require_open_quota": False, "require_positive_dpi": False},
                       rule_text="Block any sale priced below the Tk 15/kg production-cost floor."),
    InstructionVariant(variant_id="floor-and-dpi", params={"floor_tk": 15.0, "require_open_quota": False, "require_positive_dpi": True},
                       rule_text="Block a sale below the Tk 15/kg floor when storing yields dPi > 0."),
    InstructionVariant(variant_id="floor-quota-dpi", params={"floor_tk": 15.0, "require_open_quota": True, "require_positive_dpi": True},
                       rule_text="Block a sale below the Tk 15/kg floor only when open smallholder cold-storage quota can absorb "
                                 "the lot AND dPi > 0; then enforce storage plus warehouse-receipt working-capital credit."),
)
ARBITRAGE_CANONICAL = ARBITRAGE_VARIANTS[2].params
ARBITRAGE_DEV = _labelled(arbitrage_rule, ARBITRAGE_CANONICAL, [
    {"spot": 10, "dpi": 274_150, "quota_ok": True}, {"spot": 11, "dpi": 5_000, "quota_ok": True},
    {"spot": 12, "dpi": -3_000, "quota_ok": True}, {"spot": 13, "dpi": 8_000, "quota_ok": False},
    {"spot": 18, "dpi": 40_000, "quota_ok": True}, {"spot": 9, "dpi": -500, "quota_ok": False},
    {"spot": 14.5, "dpi": 1_200, "quota_ok": True}, {"spot": 25, "dpi": -9_000, "quota_ok": True},
    {"spot": 8, "dpi": 20_000, "quota_ok": False}, {"spot": 14, "dpi": 0.0, "quota_ok": True},
])
FULL_ROUTE = ["pii_guardrail", "token_compression", "crag_retrieval", "vision_grading", "syndicate_bypass",
              "coldchain_arbitrage", "climate_credit", "voice_synthesizer"]

SUPERVISOR_SPEC = AgentPromptSpec(
    agent="supervisor",
    title="LangGraph Supervisor",
    role="You are the KrishiNexus Supervisor, a hierarchical orchestrator for Bangladeshi smallholder decisions. Route every "
         "request through PII scrubbing, compression, CRAG retrieval and the four specialist agents, and never let a "
         "below-cost distress sale through when storage pays.",
    agronomy="Respect BARI storage (48-50 F / 9-10 C, 92-95% RH), DAE pesticide labels and BRRI 80%-maturity haor harvest rules.",
    market="Potato production-cost floor Tk 15/kg; BCSA tariff Tk 8.00-9.50/kg; traders and owners hold 77.32% of storage "
           "quota; 5-tier syndicate markups reach 116%.",
    cot_steps=("Scrub PII and restate the request", "Retrieve and CRAG-grade evidence", "Grade the lot",
               "Price the syndicate-free channel", "Compute dPi and apply the circuit-breaker",
               "Check 72-hour climate risk and credit", "Synthesize a Bangla voice reply and ask for approval"),
    contract=SupervisorContract,
    few_shot_pool=(
        FewShotExample(example_id="SUP-1", dialect="Standard Bangla", label="BLOCK",
                       farmer_utterance="আমার ৫ টন কার্ডিনাল আলু আছে, ফড়িয়া ১০ টাকা কেজি বলছে, কী করব?",
                       reasoning=("spot Tk 10 < floor Tk 15", "open quota 2,379 t within 60 km", "dPi = +Tk 274,150",
                                  "circuit-breaker TRIPPED"),
                       output={"route": FULL_ROUTE, "circuit_breaker": "TRIPPED", "requires_farmer_approval": True,
                               "summary_bn": "১০ টাকায় বিক্রি করবেন না; হিমাগারে রাখুন এবং রসিদের বিপরীতে ঋণ নিন।"}),
        FewShotExample(example_id="SUP-2", dialect="Rangpuri", label="ALLOW",
                       farmer_utterance="বাহে, আলু ১৮ টাকা কেজি, বেচমু?",
                       reasoning=("spot Tk 18 >= floor",), output={"route": "all", "circuit_breaker": "CLEAR"}),
        FewShotExample(example_id="SUP-3", dialect="Banglish", label="ALLOW",
                       farmer_utterance="alu 12 taka, kintu himagar e jaiga nai",
                       reasoning=("spot Tk 12 < floor", "no open quota within 60 km", "circuit-breaker cannot enforce storage",
                                  "escalate to pooled B2B truck"),
                       output={"route": FULL_ROUTE, "circuit_breaker": "CLEAR", "requires_farmer_approval": True,
                               "summary_bn": "হিমাগারে জায়গা নেই; ৫ টনের যৌথ ট্রাকে সরাসরি ঢাকায় বিক্রি করুন।"}),
        FewShotExample(example_id="SUP-4", dialect="Sylheti", label="ALLOW",
                       farmer_utterance="ধান কিতা করমু, ঢল আইতাছে?",
                       reasoning=("haor flood intent", "climate agent first", "no sale proposed"),
                       output={"route": ["pii_guardrail", "crag_retrieval", "climate_credit", "voice_synthesizer"],
                               "circuit_breaker": "CLEAR", "requires_farmer_approval": True,
                               "summary_bn": "ঢল আসার আগে ৮০% পাকা ধান কেটে উঁচু জায়গায় নিন।"}),
    ),
    variants=ARBITRAGE_VARIANTS,
    dev_set=ARBITRAGE_DEV,
    predictor=arbitrage_rule,
    baseline_variant="floor-only",
    baseline_demos=("SUP-1", "SUP-2"),
)

VISION_VARIANTS = (
    InstructionVariant(variant_id="lenient", rule_text="Grade A if uniformity >= 85%, bruising <= 5%, rot <= 3%; Grade B if "
                       "uniformity >= 70%, bruising <= 10%, rot <= 6%; otherwise Grade C.",
                       params={"a_uniformity": 85, "a_bruising": 5, "a_rot": 3, "b_uniformity": 70, "b_bruising": 10, "b_rot": 6}),
    InstructionVariant(variant_id="strict-rot", rule_text="Grade A if uniformity >= 90%, bruising <= 5%, rot <= 2%; Grade B if "
                       "uniformity >= 75%, bruising <= 10%, rot <= 5%; otherwise Grade C.",
                       params={"a_uniformity": 90, "a_bruising": 5, "a_rot": 2, "b_uniformity": 75, "b_bruising": 10, "b_rot": 5}),
    InstructionVariant(variant_id="bari-standard", rule_text="BARI grading: Grade A (export/supermarket) needs uniformity >= 90%, "
                       "bruising <= 3% and blight/rot risk <= 2%; Grade B (wholesale) needs uniformity >= 75%, bruising <= 8%, "
                       "rot <= 5%; everything else is Grade C (processing only, never long-term storage).",
                       params={"a_uniformity": 90, "a_bruising": 3, "a_rot": 2, "b_uniformity": 75, "b_bruising": 8, "b_rot": 5}),
)
VISION_SPEC = AgentPromptSpec(
    agent="vision_grading",
    title="Agent 1 - Vision & Quality Grading",
    role="You are the Vision & Quality Grading Agent. Read optical-scan metrics of a harvested lot, assign the official grade, "
         "attach verified BARI/BAU curing, storage and packaging rules, and sign a digital quality certificate.",
    agronomy="Cure potatoes 10-14 days before storage; store at 48-50 F / 92-95% RH; Grade C lots go to processing.",
    market="Graded, MAP-packed lots earn about 32% (+US$947 per season) more; supermarket DCs accept Grade A only.",
    cot_steps=("Validate metric ranges", "Compare uniformity, bruising and rot risk with grade thresholds",
               "Check the crop's moisture band", "Assign grade with reasons", "Attach verified storage and packaging rules",
               "Sign the certificate"),
    contract=VisionContract,
    few_shot_pool=(
        FewShotExample(example_id="VIS-1", dialect="Standard Bangla", label="A",
                       farmer_utterance="আমার আলু সব একই সাইজের, কোনো দাগ নাই।",
                       reasoning=("uniformity 94%", "bruising 2%", "rot risk 1%", "all within Grade A"),
                       output={"grade": "A", "reasons": ["uniformity 94%", "bruising 2%", "rot 1%"], "storage_protocol_cited": True}),
        FewShotExample(example_id="VIS-2", dialect="Standard Bangla", label="A",
                       farmer_utterance="আলু ভালো আছে।", reasoning=("looks good",), output={"grade": "Grade-A"}),
        FewShotExample(example_id="VIS-3", dialect="Bogura (Varendri)", label="B",
                       farmer_utterance="কিছু আলু কাটা, দু-তিনটা পচা আছে।",
                       reasoning=("uniformity 82%", "bruising 6%", "rot 3%", "fails A, meets B"),
                       output={"grade": "B", "reasons": ["bruising 6% > 3%", "rot 3% > 2%"], "storage_protocol_cited": True}),
        FewShotExample(example_id="VIS-4", dialect="Banglish", label="C",
                       farmer_utterance="chhoto alu beshi, kichu pocha ache",
                       reasoning=("uniformity 68%", "rot 6%", "below Grade B"),
                       output={"grade": "C", "reasons": ["uniformity 68% < 75%", "rot 6% > 5%"], "storage_protocol_cited": True}),
    ),
    variants=VISION_VARIANTS,
    dev_set=_labelled(grade_rule, VISION_VARIANTS[2].params, [
        {"uniformity": 94, "bruising": 2, "rot": 1}, {"uniformity": 88, "bruising": 2, "rot": 1},
        {"uniformity": 92, "bruising": 4, "rot": 1}, {"uniformity": 91, "bruising": 2, "rot": 2.5},
        {"uniformity": 80, "bruising": 7, "rot": 4}, {"uniformity": 72, "bruising": 6, "rot": 3},
        {"uniformity": 78, "bruising": 9, "rot": 4}, {"uniformity": 95, "bruising": 1, "rot": 0.5},
        {"uniformity": 76, "bruising": 5, "rot": 5.5}, {"uniformity": 90, "bruising": 3, "rot": 2},
    ]),
    predictor=grade_rule,
    baseline_variant="lenient",
    baseline_demos=("VIS-1", "VIS-2"),
)

SYNDICATE_VARIANTS = (
    InstructionVariant(variant_id="threshold-60", params={"anomaly_threshold_pct": 60.0},
                       rule_text="Flag a syndicate anomaly when the producer-to-retail markup exceeds 60%."),
    InstructionVariant(variant_id="threshold-50", params={"anomaly_threshold_pct": 50.0},
                       rule_text="Flag a syndicate anomaly when the producer-to-retail markup exceeds 50%."),
    InstructionVariant(variant_id="threshold-40", params={"anomaly_threshold_pct": 40.0},
                       rule_text="Flag a syndicate anomaly when the producer-to-retail markup exceeds 40% (fair logistics "
                                 "and handling justify at most 22-45%); break the margin down across all five tiers."),
)
SYNDICATE_SPEC = AgentPromptSpec(
    agent="syndicate_bypass",
    title="Agent 2 - Syndicate-Bypass & 5-Ton Truck Pooling",
    role="You are the Syndicate-Bypass Market Agent. Expose intermediary markups with DAM data and route graded micro-lots "
         "into pooled 5-ton trucks that sell directly to arats, supermarket DCs or WFP aggregation centres.",
    agronomy="Only Grade A/B lots go to supermarket DCs and WFP centres; move perishables at night.",
    market="Faria -> Bepari -> Aratdar -> Paiker -> Retailer capture 50-55% of the consumer taka; markups reach 116% on green "
           "chili; Aratdars take 62.35% of the Bepari's marketing cost and spend Tk 0 on grading; pooled freight is "
           "Tk 68/km per 5-ton truck.",
    cot_steps=("Fetch today's DAM spread", "Compute markup and tier capture", "Classify against the anomaly threshold",
               "Rank direct buyers by net Tk/kg after pooled freight", "Match the lot to a pool within a 5 km union radius",
               "Quote the Faria shortfall"),
    contract=SyndicateContract,
    few_shot_pool=(
        FewShotExample(example_id="SYN-1", dialect="Bogura (Varendri)", label="ANOMALY",
                       farmer_utterance="বগুড়ায় মরিচ ৫৫ টাকা কেজি, অথচ ঢাকায় ১২৫ টাকা!",
                       reasoning=("markup (125-55)/55 = 127%", "> 40% threshold", "pool to Mirpur DC"),
                       output={"anomaly": True, "markup_pct": 127.3, "recommended_channel": "URBAN_RETAIL_CHAIN",
                               "pooled_net_tk_per_kg": 93.3}),
        FewShotExample(example_id="SYN-2", dialect="Standard Bangla", label="ANOMALY",
                       farmer_utterance="দাম কম দিচ্ছে।", reasoning=("unclear",), output={"anomaly": "yes"}),
        FewShotExample(example_id="SYN-3", dialect="Banglish", label="NORMAL",
                       farmer_utterance="begun 40 taka, dhaka te 56 taka",
                       reasoning=("markup 40%", "not above threshold", "sell locally"),
                       output={"anomaly": False, "markup_pct": 40.0, "recommended_channel": "WHOLESALE_ARAT",
                               "pooled_net_tk_per_kg": 38.5}),
        FewShotExample(example_id="SYN-4", dialect="Rangpuri", label="ANOMALY",
                       farmer_utterance="বাহে, আলু ৩৬ টাকা কেজি নেয়, ঢাকায় ৮০ টাকা।",
                       reasoning=("markup 122%", "CRITICAL", "join 5-ton pool"),
                       output={"anomaly": True, "markup_pct": 122.2, "recommended_channel": "URBAN_RETAIL_CHAIN",
                               "pooled_net_tk_per_kg": 63.2}),
    ),
    variants=SYNDICATE_VARIANTS,
    dev_set=_labelled(markup_rule, SYNDICATE_VARIANTS[2].params, [
        {"markup": 116}, {"markup": 45}, {"markup": 41}, {"markup": 39}, {"markup": 52},
        {"markup": 30}, {"markup": 85}, {"markup": 40}, {"markup": 48}, {"markup": 22},
    ]),
    predictor=markup_rule,
    baseline_variant="threshold-60",
    baseline_demos=("SYN-1", "SYN-2"),
)

COLDCHAIN_SPEC = AgentPromptSpec(
    agent="coldchain_arbitrage",
    title="Agent 3 - Cold-Storage Quota Clearinghouse & Arbitrage",
    role="You are the Cold-Storage Quota Clearinghouse & Arbitrage Agent. Compare a pooled B2B sale today with holding the "
         "lot in a BCSA cold storage using the exact dPi equation, live chamber telemetry and open smallholder quota.",
    agronomy="Store only cured Grade A/B potatoes at 48-50 F (9-10 C) and 92-95% RH; lambda_rot comes from the shelf-life model.",
    market="BCSA tariff Tk 8.00-9.50/kg; traders (45%) and owners (32.32%) hold 77.32% of quota; production-cost floor "
           "Tk 15/kg; harvest distress Tk 5-14/kg versus Tk 80-90/kg off-season retail.",
    cot_steps=("List Q, P_spot, E[P_future], C_storage, C_handling, lambda_rot, transport costs",
               "storage = Q(1-lambda)E[P_future] - Q(C_storage + C_handling) - C_transport_storage",
               "spot = Q P_spot - C_transport_market", "dPi = storage - spot", "Apply the circuit-breaker rule",
               "Compare storage with the pooled B2B sale; reserve a slot only if storing wins"),
    contract=ColdChainContract,
    few_shot_pool=(
        FewShotExample(example_id="CCA-1", dialect="Standard Bangla", label="BLOCK",
                       farmer_utterance="মার্চ মাসে ফড়িয়া ১০ টাকা কেজি দিচ্ছে, আমার ৫ টন আলু।",
                       reasoning=("Q=5000, P_spot=10, E=78, Cs=8.5, Ch=3.5, lambda=0.015",
                                  "storage = 384,150 - 60,000 = 324,150", "spot = 50,000", "dPi = +274,150",
                                  "below floor, quota open, dPi > 0: BLOCK"),
                       output={"verdict": "BLOCK_SPOT_SALE", "delta_pi_bdt": 274150.0, "enforced_action": "STORE_AND_FINANCE",
                               "reserve_slot": True}),
        FewShotExample(example_id="CCA-2", dialect="Standard Bangla", label="BLOCK",
                       farmer_utterance="দাম কম, রাখব?", reasoning=("store",), output={"verdict": "BLOCK", "delta_pi_bdt": "high"}),
        FewShotExample(example_id="CCA-3", dialect="Banglish", label="ALLOW",
                       farmer_utterance="October e bepari 42 taka dicche, 2 ton, rakhbo naki?",
                       reasoning=("E[P] in January falls to about Tk 18", "dPi = -55,000", "selling now wins"),
                       output={"verdict": "ALLOW_SPOT_SALE", "delta_pi_bdt": -55000.0, "enforced_action": "SELL_SPOT",
                               "reserve_slot": False}),
        FewShotExample(example_id="CCA-4", dialect="Standard Bangla", label="ALLOW",
                       farmer_utterance="হিমাগারে জায়গা নাই, ফড়িয়া ১২ টাকা দিচ্ছে।",
                       reasoning=("spot below floor", "no open quota", "cannot enforce storage", "escalate pooled B2B"),
                       output={"verdict": "WARN_NO_STORAGE_CAPACITY", "delta_pi_bdt": 41000.0,
                               "enforced_action": "ESCALATE_STORAGE_SEARCH", "reserve_slot": False}),
    ),
    variants=ARBITRAGE_VARIANTS,
    dev_set=ARBITRAGE_DEV,
    predictor=arbitrage_rule,
    baseline_variant="floor-only",
    baseline_demos=("CCA-1", "CCA-2"),
)

CLIMATE_VARIANTS = (
    InstructionVariant(variant_id="late-trigger", params={"red": 0.85, "orange": 0.60, "yellow": 0.30},
                       rule_text="RED at breach probability >= 85%, ORANGE >= 60%, YELLOW >= 30%; trigger early harvest at RED."),
    InstructionVariant(variant_id="mid-trigger", params={"red": 0.80, "orange": 0.50, "yellow": 0.25},
                       rule_text="RED at breach probability >= 80%, ORANGE >= 50%, YELLOW >= 25%; trigger early harvest at ORANGE."),
    InstructionVariant(variant_id="ffwc-trigger", params={"red": 0.70, "orange": 0.45, "yellow": 0.20},
                       rule_text="FFWC-aligned: RED at breach probability >= 70%, ORANGE >= 45%, YELLOW >= 20%; trigger the "
                                 "72-hour early-harvest window at ORANGE or RED and discount credit by climate risk."),
)
CLIMATE_SPEC = AgentPromptSpec(
    agent="climate_credit",
    title="Agent 4 - SAR-Weather Harvest Shield & Parametric Credit",
    role="You are the SAR-Weather Harvest Shield & Parametric Credit Underwriter. Fuse Sentinel-1 flood evidence with 72-hour "
         "forecasts, trigger early harvest when needed, and compute a 300-850 alternative agri-credit score from verifiable evidence.",
    agronomy="Harvest haor Boro at 80% maturity when flash-flood risk rises; fungal risk from VPD informs storage readiness.",
    market="2017 Boro losses: 65% Sunamganj, 44% Kishoreganj, 21% Netrokona. Credit is modelled on collateral-free 6% agri-loans "
           "and iFarmer-style underwriting; warehouse receipts and pooled B2B contracts are collateral evidence.",
    cot_steps=("Read 72-hour weather and storm warnings", "Fuse SAR backscatter with upstream rain for haor upazilas",
               "Decide the early-harvest trigger", "Score grade, market linkage, collateral, climate and agronomic risk",
               "Map the score to loan eligibility"),
    contract=ClimateContract,
    few_shot_pool=(
        FewShotExample(example_id="CLM-1", dialect="Sylheti", label="RED",
                       farmer_utterance="পাহাড়ি ঢল আইতাছে, তাহিরপুরে ধান পাকছে, কিতা করমু?",
                       reasoning=("upstream 320 mm/72 h", "SAR -19.5 dB = open water", "breach 99%", "RED: harvest now"),
                       output={"alert_level": "RED", "trigger_early_harvest": True, "credit_score": 640, "loan_eligible": True}),
        FewShotExample(example_id="CLM-2", dialect="Standard Bangla", label="RED",
                       farmer_utterance="বন্যা হবে?", reasoning=("maybe",),
                       output={"alert_level": "RED", "trigger_early_harvest": True, "credit_score": 920, "loan_eligible": True}),
        FewShotExample(example_id="CLM-3", dialect="Banglish", label="GREEN",
                       farmer_utterance="Bogura te brishti nai, alu himagare rakhsi",
                       reasoning=("no storms in 72 h", "not a haor upazila", "receipt collateral", "score 780"),
                       output={"alert_level": "GREEN", "trigger_early_harvest": False, "credit_score": 780, "loan_eligible": True}),
        FewShotExample(example_id="CLM-4", dialect="Standard Bangla", label="ORANGE",
                       farmer_utterance="কিশোরগঞ্জের হাওরে পানি বাড়ছে।",
                       reasoning=("breach 52%", "ORANGE", "pre-book harvesters"),
                       output={"alert_level": "ORANGE", "trigger_early_harvest": True, "credit_score": 690, "loan_eligible": True}),
    ),
    variants=CLIMATE_VARIANTS,
    dev_set=_labelled(alert_rule, CLIMATE_VARIANTS[2].params, [
        {"probability": 0.997}, {"probability": 0.75}, {"probability": 0.62}, {"probability": 0.48}, {"probability": 0.30},
        {"probability": 0.22}, {"probability": 0.10}, {"probability": 0.05}, {"probability": 0.71}, {"probability": 0.46},
    ]),
    predictor=alert_rule,
    baseline_variant="late-trigger",
    baseline_demos=("CLM-1", "CLM-2"),
)

PROMPT_REGISTRY = PromptRegistry((SUPERVISOR_SPEC, VISION_SPEC, SYNDICATE_SPEC, COLDCHAIN_SPEC, CLIMATE_SPEC))
