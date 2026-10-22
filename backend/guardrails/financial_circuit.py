"""Deterministic financial and agronomic circuit-breakers.

1. ``validate_arbitrage_recommendation`` evaluates the net farmer surplus of storing
   versus selling at spot (AGENTS.md section 5):

       dPi = [Q(1 - lambda_rot) E[P_future] - Q(C_storage + C_handling) - C_transport_storage]
             - [Q P_spot - C_transport_market]

   If P_spot is below the crop's production-cost floor AND open smallholder cold-storage
   quota can absorb Q AND dPi > 0, the breaker trips: a distress spot sale is BLOCKED and
   storage plus warehouse-receipt working-capital credit is enforced instead.

2. ``validate_agronomic_dosage`` blocks banned chemicals and food adulterants, products not
   registered for the crop, label overdoses and pre-harvest-interval (PHI) violations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from config import now_bdt
from mcp_servers import bd_geo
from mcp_servers.coldchain_iot_mcp import FACILITIES, open_farmer_quota_mt, power_state
from mcp_servers.dam_market_mcp import SEASONAL_CURVES, pooled_truck_leg
from schemas.mcp_models import Crop, CropField, PowerSource

# ---------------------------------------------------------------------------
# Financial circuit-breaker
# ---------------------------------------------------------------------------

WAREHOUSE_RECEIPT_LTV = 0.70
AGRI_CREDIT_ANNUAL_RATE = 0.09
STORAGE_SEARCH_RADIUS_KM = 80.0


class ArbitrageVerdict(StrEnum):
    BLOCK_SPOT_SALE = "BLOCK_SPOT_SALE"
    ALLOW_SPOT_SALE = "ALLOW_SPOT_SALE"
    ALLOW_STORAGE = "ALLOW_STORAGE"
    WARN_NO_STORAGE_CAPACITY = "WARN_NO_STORAGE_CAPACITY"
    WARN_STORAGE_LOSES_VALUE = "WARN_STORAGE_LOSES_VALUE"


class ProposedAction(StrEnum):
    SELL_SPOT = "SELL_SPOT"
    STORE = "STORE"


class ArbitrageCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: CropField
    quantity_kg: float = Field(gt=0, le=2_000_000, description="Q, lot size in kg.")
    spot_price_bdt: float = Field(ge=0, description="P_spot, Tk/kg offered today.")
    expected_future_price_bdt: float = Field(ge=0, description="E[P_future], Tk/kg at planned release.")
    storage_tariff_bdt: float = Field(ge=0, description="C_storage, Tk/kg for the season.")
    handling_cost_bdt: float = Field(ge=0, description="C_handling, Tk/kg (loading, bags, sorting).")
    lambda_rot: float = Field(ge=0, le=0.5, description="Fractional spoilage over the holding period.")
    transport_to_storage_bdt: float = Field(default=0.0, ge=0, description="C_transport_storage, Tk total.")
    transport_to_market_bdt: float = Field(default=0.0, ge=0, description="C_transport_market, Tk total.")
    district: str | None = Field(default=None, description="District used to check open cold-storage quota.")
    holding_months: int = Field(default=6, ge=1, le=10)
    proposed_action: ProposedAction = ProposedAction.SELL_SPOT


class MicroCreditOffer(BaseModel):
    collateral: str
    collateral_value_bdt: float
    loan_to_value: float
    credit_limit_bdt: float
    annual_rate: float
    tenor_months: int
    interest_cost_bdt: float


class ArbitrageCheckResult(BaseModel):
    crop: Crop
    verdict: ArbitrageVerdict
    circuit_tripped: bool
    enforced_action: str
    production_cost_floor_bdt: float
    spot_below_floor: bool
    storage_branch_value_bdt: float = Field(description="Q(1-lambda)E[P] - Q(Cs+Ch) - C_ts")
    spot_branch_value_bdt: float = Field(description="Q P_spot - C_tm")
    delta_pi_bdt: float
    delta_pi_per_kg_bdt: float
    break_even_future_price_bdt: float
    open_storage_quota_tons: float
    storage_quota_scope: str
    storage_can_absorb_lot: bool
    micro_credit: MicroCreditOffer | None
    net_surplus_after_credit_bdt: float
    equation: str
    rationale: list[str]


def _open_quota_tons(district_name: str | None) -> tuple[float, str]:
    at = now_bdt()
    usable = [f for f in FACILITIES.values() if power_state(f, None, at).source is not PowerSource.OUTAGE]
    if district_name is None:
        return round(sum(open_farmer_quota_mt(f) for f in usable), 1), "all seeded BCSA facilities"
    origin = bd_geo.resolve_district(district_name)
    nearby = [
        f for f in usable
        if pooled_truck_leg(origin, bd_geo.district_by_name(f.district), f.lat, f.lon).road_km <= STORAGE_SEARCH_RADIUS_KM
    ]
    return round(sum(open_farmer_quota_mt(f) for f in nearby), 1), f"BCSA facilities within {STORAGE_SEARCH_RADIUS_KM:.0f} km of {origin.name}"


# ---------------------------------------------------------------------------
# Agronomic circuit-breaker
# ---------------------------------------------------------------------------


class DosageVerdict(StrEnum):
    APPROVED = "APPROVED"
    BLOCK_BANNED_SUBSTANCE = "BLOCK_BANNED_SUBSTANCE"
    BLOCK_NOT_REGISTERED = "BLOCK_NOT_REGISTERED"
    BLOCK_NOT_REGISTERED_FOR_CROP = "BLOCK_NOT_REGISTERED_FOR_CROP"
    BLOCK_INVALID_UNIT = "BLOCK_INVALID_UNIT"
    BLOCK_OVERDOSE = "BLOCK_OVERDOSE"
    BLOCK_PHI_VIOLATION = "BLOCK_PHI_VIOLATION"


@dataclass(frozen=True, slots=True)
class BannedSubstance:
    name: str
    legal_basis: str
    safer_alternative: str


@dataclass(frozen=True, slots=True)
class LabelRule:
    active_ingredient: str
    target: str
    crops: frozenset[Crop]
    max_dose: float
    unit: str
    phi_days: int
    max_applications: int


_POTATOES = frozenset({Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO})

BANNED_SUBSTANCES: dict[str, BannedSubstance] = {
    "formalin": BannedSubstance("Formalin (formaldehyde)", "Formalin Control Act 2015: banned as a food preservative",
                                "Cold chain at 8-10 deg C, MAP packaging, or approved food-grade preservatives"),
    "calcium carbide": BannedSubstance("Calcium carbide", "Bangladesh Food Safety Act 2013: banned fruit-ripening agent",
                                       "Ethylene ripening chambers or label-dose ethephon in licensed facilities"),
    "lead chromate": BannedSubstance("Lead chromate", "BFSA / BSTI: toxic adulterant (turmeric, lentil colouring)",
                                     "Unadulterated produce; no colouring agents"),
    "sudan dye": BannedSubstance("Sudan I-IV textile dyes", "BFSA: non-permitted food colour", "No colouring agents"),
    "ddt": BannedSubstance("DDT", "Pesticide Ordinance / Stockholm Convention POP: banned",
                           "IPM with DAE-registered insecticides"),
    "endosulfan": BannedSubstance("Endosulfan", "Stockholm Convention POP: registration cancelled",
                                  "Emamectin benzoate or spinosad per label"),
    "heptachlor": BannedSubstance("Heptachlor", "Stockholm Convention POP: banned", "IPM soil-pest management"),
    "aldrin": BannedSubstance("Aldrin / dieldrin", "Stockholm Convention POP: banned", "IPM soil-pest management"),
    "methyl parathion": BannedSubstance("Methyl parathion", "Rotterdam Convention Annex III: deregistered",
                                        "Imidacloprid or emamectin benzoate per label"),
}

LABEL_RULES: dict[str, LabelRule] = {
    "mancozeb": LabelRule("Mancozeb 80WP", "Late blight / early blight", _POTATOES | {Crop.GREEN_CHILI, Crop.BRINJAL}, 2.0, "g/L", 7, 6),
    "metalaxyl+mancozeb": LabelRule("Metalaxyl 4% + Mancozeb 64% WP", "Late blight (curative)", _POTATOES, 2.0, "g/L", 7, 4),
    "cymoxanil+mancozeb": LabelRule("Cymoxanil 8% + Mancozeb 64% WP", "Late blight (curative)", _POTATOES, 2.0, "g/L", 7, 4),
    "tricyclazole": LabelRule("Tricyclazole 75WP", "Rice blast", frozenset({Crop.BORO_RICE}), 0.8, "g/L", 21, 2),
    "azoxystrobin": LabelRule("Azoxystrobin 25SC", "Anthracnose / blast", frozenset({Crop.GREEN_CHILI, Crop.BORO_RICE}), 1.0, "ml/L", 7, 3),
    "carbendazim": LabelRule("Carbendazim 50WP", "Phomopsis blight / fruit rot", frozenset({Crop.BRINJAL, Crop.GREEN_CHILI}), 1.0, "g/L", 14, 3),
    "emamectin benzoate": LabelRule("Emamectin benzoate 5SG", "Fruit and shoot borer", frozenset({Crop.BRINJAL, Crop.GREEN_CHILI}), 1.0, "g/L", 3, 4),
    "imidacloprid": LabelRule("Imidacloprid 200SL", "Aphid / whitefly / jassid", _POTATOES | {Crop.GREEN_CHILI, Crop.BRINJAL}, 0.5, "ml/L", 7, 3),
    "chlorpyrifos": LabelRule("Chlorpyrifos 20EC", "Cutworm / stem borer", _POTATOES | {Crop.BORO_RICE}, 2.0, "ml/L", 21, 2),
}

CHEMICAL_ALIASES: dict[str, str] = {
    "formaldehyde": "formalin", "formol": "formalin", "ফরমালিন": "formalin",
    "carbide": "calcium carbide", "কার্বাইড": "calcium carbide", "ক্যালসিয়াম কার্বাইড": "calcium carbide",
    "sudan red": "sudan dye", "dieldrin": "aldrin",
    "dithane m-45": "mancozeb", "dithane": "mancozeb", "indofil m-45": "mancozeb", "ডায়থেন": "mancozeb",
    "ridomil gold": "metalaxyl+mancozeb", "ridomil gold mz": "metalaxyl+mancozeb", "metalaxyl": "metalaxyl+mancozeb",
    "curzate": "cymoxanil+mancozeb", "cymoxanil": "cymoxanil+mancozeb",
    "trooper": "tricyclazole", "amistar": "azoxystrobin", "bavistin": "carbendazim", "autostin": "carbendazim",
    "proclaim": "emamectin benzoate", "emamectin": "emamectin benzoate",
    "admire": "imidacloprid", "confidor": "imidacloprid", "dursban": "chlorpyrifos",
}


class DosageCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chemical: str = Field(min_length=2, max_length=60, description="Active ingredient or trade name.")
    crop: CropField
    dose: float = Field(ge=0, description="Dose per litre of spray solution.")
    dose_unit: str = Field(default="g/L", description="'g/L' or 'ml/L'.")
    days_until_harvest: int = Field(ge=0, le=365)
    applications_this_season: int = Field(default=1, ge=1, le=30)


class DosageCheckResult(BaseModel):
    chemical: str
    resolved_name: str | None
    crop: Crop
    verdict: DosageVerdict
    circuit_tripped: bool
    label_max_dose: float | None
    dose_unit: str | None
    phi_days: int | None
    earliest_safe_harvest: date | None
    legal_basis: str | None
    safer_alternative: str | None
    rationale: list[str]


def _normalize_chemical(name: str) -> str:
    key = re.sub(r"\s+", " ", name.strip().lower())
    key = re.sub(r"\s*\d+\s*(wp|wg|ec|sc|sl|sg|%)\b.*$", "", key).strip()
    return CHEMICAL_ALIASES.get(key, key)


# ---------------------------------------------------------------------------
# Breaker
# ---------------------------------------------------------------------------


class FinancialCircuitBreaker:
    def validate_arbitrage_recommendation(self, params: ArbitrageCheckInput) -> ArbitrageCheckResult:
        q = params.quantity_kg
        floor = SEASONAL_CURVES[params.crop].production_cost_floor
        storage_value = (
            q * (1 - params.lambda_rot) * params.expected_future_price_bdt
            - q * (params.storage_tariff_bdt + params.handling_cost_bdt)
            - params.transport_to_storage_bdt
        )
        spot_value = q * params.spot_price_bdt - params.transport_to_market_bdt
        delta_pi = storage_value - spot_value
        break_even = (spot_value + q * (params.storage_tariff_bdt + params.handling_cost_bdt) + params.transport_to_storage_bdt) / (
            q * (1 - params.lambda_rot)
        )
        open_tons, scope = _open_quota_tons(params.district)
        can_absorb = open_tons * 1000 >= q
        below_floor = params.spot_price_bdt < floor

        credit: MicroCreditOffer | None = None
        rationale = [
            f"dPi = Tk {storage_value:,.0f} (store) - Tk {spot_value:,.0f} (spot) = Tk {delta_pi:,.0f} "
            f"(Tk {delta_pi / q:.2f}/kg).",
            f"Storage breaks even if the release price is at least Tk {break_even:.2f}/kg.",
            f"Open smallholder quota: {open_tons:,.1f} t ({scope}).",
        ]
        if below_floor and can_absorb and delta_pi > 0:
            verdict = ArbitrageVerdict.BLOCK_SPOT_SALE
            collateral_value = q * (1 - params.lambda_rot) * max(params.spot_price_bdt, floor)
            limit = WAREHOUSE_RECEIPT_LTV * collateral_value
            interest = limit * AGRI_CREDIT_ANNUAL_RATE * params.holding_months / 12
            credit = MicroCreditOffer(
                collateral="HMAC-signed digital warehouse receipt (reserve_collective_storage_slot)",
                collateral_value_bdt=round(collateral_value, 2),
                loan_to_value=WAREHOUSE_RECEIPT_LTV,
                credit_limit_bdt=round(limit, 2),
                annual_rate=AGRI_CREDIT_ANNUAL_RATE,
                tenor_months=params.holding_months,
                interest_cost_bdt=round(interest, 2),
            )
            enforced = "STORE_AND_FINANCE"
            rationale.insert(0, f"CIRCUIT TRIPPED: spot Tk {params.spot_price_bdt:.2f}/kg is below the Tk {floor:.2f}/kg production-cost floor.")
            rationale.append(
                f"Distress sale blocked; reserve storage and draw up to Tk {limit:,.0f} working capital against the receipt "
                f"(interest Tk {interest:,.0f} over {params.holding_months} months)."
            )
        elif below_floor and delta_pi > 0:
            verdict = ArbitrageVerdict.WARN_NO_STORAGE_CAPACITY
            enforced = "ESCALATE_STORAGE_SEARCH"
            rationale.insert(0, "Spot price is below cost and storage pays, but nearby open quota cannot absorb the lot.")
        elif delta_pi > 0:
            verdict = ArbitrageVerdict.ALLOW_STORAGE
            enforced = "STORE_RECOMMENDED" if params.proposed_action is ProposedAction.SELL_SPOT else "STORE"
            rationale.insert(0, "Spot price covers production cost; storage is more profitable but the sale is not blocked.")
        elif params.proposed_action is ProposedAction.STORE:
            verdict = ArbitrageVerdict.WARN_STORAGE_LOSES_VALUE
            enforced = "SELL_SPOT_RECOMMENDED"
            rationale.insert(0, "Storing destroys value at these prices; selling now is better.")
        else:
            verdict = ArbitrageVerdict.ALLOW_SPOT_SALE
            enforced = "SELL_SPOT"
            rationale.insert(0, "Selling now yields more than storing.")

        return ArbitrageCheckResult(
            crop=params.crop,
            verdict=verdict,
            circuit_tripped=verdict is ArbitrageVerdict.BLOCK_SPOT_SALE,
            enforced_action=enforced,
            production_cost_floor_bdt=floor,
            spot_below_floor=below_floor,
            storage_branch_value_bdt=round(storage_value, 2),
            spot_branch_value_bdt=round(spot_value, 2),
            delta_pi_bdt=round(delta_pi, 2),
            delta_pi_per_kg_bdt=round(delta_pi / q, 3),
            break_even_future_price_bdt=round(break_even, 2),
            open_storage_quota_tons=open_tons,
            storage_quota_scope=scope,
            storage_can_absorb_lot=can_absorb,
            micro_credit=credit,
            net_surplus_after_credit_bdt=round(delta_pi - (credit.interest_cost_bdt if credit else 0.0), 2),
            equation="dPi = [Q(1-lambda_rot)E[P_future] - Q(C_storage+C_handling) - C_transport_storage] - [Q P_spot - C_transport_market]",
            rationale=rationale,
        )

    def validate_agronomic_dosage(self, params: DosageCheckInput) -> DosageCheckResult:
        key = _normalize_chemical(params.chemical)
        today = now_bdt().date()

        def result(verdict: DosageVerdict, rationale: list[str], rule: LabelRule | None = None,
                   banned: BannedSubstance | None = None) -> DosageCheckResult:
            return DosageCheckResult(
                chemical=params.chemical,
                resolved_name=(rule.active_ingredient if rule else banned.name if banned else None),
                crop=params.crop,
                verdict=verdict,
                circuit_tripped=verdict is not DosageVerdict.APPROVED,
                label_max_dose=rule.max_dose if rule else None,
                dose_unit=rule.unit if rule else None,
                phi_days=rule.phi_days if rule else None,
                earliest_safe_harvest=today + timedelta(days=rule.phi_days) if rule else None,
                legal_basis=banned.legal_basis if banned else None,
                safer_alternative=banned.safer_alternative if banned else None,
                rationale=rationale,
            )

        banned = BANNED_SUBSTANCES.get(key)
        if banned is not None:
            return result(DosageVerdict.BLOCK_BANNED_SUBSTANCE,
                          [f"{banned.name} is prohibited: {banned.legal_basis}.", f"Use instead: {banned.safer_alternative}."],
                          banned=banned)
        rule = LABEL_RULES.get(key)
        if rule is None:
            return result(DosageVerdict.BLOCK_NOT_REGISTERED,
                          [f"'{params.chemical}' is not in the DAE-registered product list for KrishiNexus advisories."])
        if params.crop not in rule.crops:
            return result(DosageVerdict.BLOCK_NOT_REGISTERED_FOR_CROP,
                          [f"{rule.active_ingredient} is not registered for {params.crop.value}."], rule)
        unit = params.dose_unit.strip().lower().replace(" ", "")
        if unit != rule.unit.lower():
            return result(DosageVerdict.BLOCK_INVALID_UNIT,
                          [f"{rule.active_ingredient} is dosed in {rule.unit}; '{params.dose_unit}' cannot be validated."], rule)
        if params.dose > rule.max_dose * 1.05:
            return result(DosageVerdict.BLOCK_OVERDOSE,
                          [f"Dose {params.dose:g} {rule.unit} exceeds the label maximum {rule.max_dose:g} {rule.unit} "
                           f"for {rule.target}."], rule)
        if params.applications_this_season > rule.max_applications:
            return result(DosageVerdict.BLOCK_OVERDOSE,
                          [f"{params.applications_this_season} applications exceed the seasonal limit of {rule.max_applications}."], rule)
        if params.days_until_harvest < rule.phi_days:
            return result(DosageVerdict.BLOCK_PHI_VIOLATION,
                          [f"Harvest in {params.days_until_harvest} days violates the {rule.phi_days}-day pre-harvest interval; "
                           "delay harvest or skip this spray."], rule)
        return result(DosageVerdict.APPROVED,
                      [f"{rule.active_ingredient} at {params.dose:g} {rule.unit} on {params.crop.value} for {rule.target} "
                       f"is within label; respect the {rule.phi_days}-day PHI."], rule)


CIRCUIT_BREAKER = FinancialCircuitBreaker()
