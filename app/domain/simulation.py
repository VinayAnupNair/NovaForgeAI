import random
from typing import Dict, List

from app.domain.models import CompanyState, ModelUnit, WorldEvent


WORLD_EVENTS: List[WorldEvent] = [
    WorldEvent(
        key="oss_rival_free_model",
        title="Open-Source Rival Launches Free Model",
        description=(
            "A high-quality open model gains viral adoption and compresses paid inference pricing."
        ),
        impact="Demand softens and pricing power drops across the market.",
        demand_multiplier=0.88,
        margin_shift=-0.03,
        reputation_shift=-0.5,
    ),
    WorldEvent(
        key="eu_explainability_audit",
        title="EU Regulator Audits AI Explainability",
        description=(
            "Regulators launch coordinated explainability audits for enterprise AI providers."
        ),
        impact="Compliance burden rises and incident fallout gets more expensive.",
        incident_risk_shift=0.03,
        operating_cost_multiplier=1.1,
        compliance_shift=-1.8,
        regulatory_pressure=1.2,
    ),
    WorldEvent(
        key="gpu_prices_spike",
        title="Cloud GPU Prices Spike",
        description=(
            "Major cloud providers raise accelerator pricing after supply disruptions."
        ),
        impact="Operating costs surge and margins tighten.",
        margin_shift=-0.025,
        operating_cost_multiplier=1.22,
    ),
    WorldEvent(
        key="fortune100_partnership_request",
        title="Fortune 100 Partnership Request",
        description=(
            "A global enterprise asks for a strategic integration with strict reliability targets."
        ),
        impact="Revenue upside increases, but delivery pressure raises operational risk.",
        demand_multiplier=1.2,
        margin_shift=0.02,
        incident_risk_shift=0.02,
        reputation_shift=1.4,
        compliance_shift=0.6,
    ),
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def quarter_budget_limit(state: CompanyState) -> int:
    return int(min(5_500_000, max(1_000_000, state.cash * 0.42)))


def state_status(state: CompanyState) -> str:
    if state.cash <= 0:
        return "bankrupt"
    if state.reputation < 50 and state.compliance < 50:
        return "shutdown"
    if state.year >= 4:
        return "completed"
    return "active"


def roll_world_event(state: CompanyState) -> WorldEvent:
    choices = WORLD_EVENTS
    if state.active_event and len(WORLD_EVENTS) > 1:
        choices = [event for event in WORLD_EVENTS if event.key != state.active_event.key]
    return random.choice(choices)


def start_quarter_event(state: CompanyState) -> WorldEvent:
    state.active_event = roll_world_event(state)
    return state.active_event


def simulate_model_outcome(model: ModelUnit, state: CompanyState) -> Dict[str, float]:
    # Competitive tradeoff model: aggressive capability scaling increases upside,
    # but creates stability pressure that harms reliability and margin.
    capability_pressure = max(0.0, model.capability - ((model.safety + model.efficiency) / 2))
    stability_bias = max(0.0, ((model.safety + model.efficiency) / 2) - model.capability)
    market_pressure = max(0.0, model.market - model.safety)

    event = state.active_event

    quality = 50 + model.capability * 7.0 + model.market * 2.6 - stability_bias * 1.4
    reliability = 46 + model.safety * 8.1 + model.efficiency * 2.4 - capability_pressure * 3.8
    demand = (
        30
        + model.market * 9.0
        + model.capability * 3.6
        - stability_bias * 1.2
        + random.uniform(-5, 6)
    )
    demand *= event.demand_multiplier if event else 1.0

    adoption_factor = clamp((state.reputation + state.compliance) / 180, 0.45, 1.1)
    adoption_factor *= clamp(1 - capability_pressure * 0.03, 0.7, 1.0)
    maturity_boost = 1 + min(model.quarters_live, 6) * 0.04
    revenue = max(0.0, demand * quality * adoption_factor * maturity_boost * 2500)

    gross_margin = clamp(
        0.50
        + model.efficiency * 0.028
        + model.market * 0.006
        - capability_pressure * 0.012
        + (event.margin_shift if event else 0.0),
        0.42,
        0.83,
    )
    gross_profit = revenue * gross_margin

    incident_prob = clamp(
        0.17
        + capability_pressure * 0.028
        + market_pressure * 0.01
        - (reliability / 380)
        - (model.safety * 0.012),
        0.03,
        0.45,
    )
    incident_prob = clamp(
        incident_prob + (event.incident_risk_shift if event else 0.0),
        0.03,
        0.45,
    )
    incident = random.random() < incident_prob
    incident_cost = 0.0
    trust_hit = 0.0
    compliance_hit = 0.0

    if incident:
        severity = random.uniform(0.6, 1.4)
        incident_cost = (
            220_000
            + max(0.0, 68 - reliability) * 14_000
            + capability_pressure * 55_000
        ) * severity
        if event and event.regulatory_pressure > 0:
            incident_cost *= 1 + event.regulatory_pressure * 0.18
        trust_hit = random.uniform(1.8, 4.6)
        compliance_hit = random.uniform(1.0, 3.2)

    model.quarters_live += 1
    return {
        "revenue": revenue,
        "gross_profit": gross_profit,
        "incident": 1.0 if incident else 0.0,
        "incident_prob": incident_prob,
        "incident_cost": incident_cost,
        "trust_hit": trust_hit,
        "compliance_hit": compliance_hit,
        "reliability": reliability,
        "quality": quality,
        "demand": demand,
        "capability_pressure": capability_pressure,
        "stability_bias": stability_bias,
    }
