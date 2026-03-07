import random
from typing import Dict

from app.domain.models import CompanyState, ModelUnit


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


def simulate_model_outcome(model: ModelUnit, state: CompanyState) -> Dict[str, float]:
    # Competitive tradeoff model: aggressive capability scaling increases upside,
    # but creates stability pressure that harms reliability and margin.
    capability_pressure = max(0.0, model.capability - ((model.safety + model.efficiency) / 2))
    stability_bias = max(0.0, ((model.safety + model.efficiency) / 2) - model.capability)
    market_pressure = max(0.0, model.market - model.safety)

    quality = 50 + model.capability * 7.0 + model.market * 2.6 - stability_bias * 1.4
    reliability = 46 + model.safety * 8.1 + model.efficiency * 2.4 - capability_pressure * 3.8
    demand = (
        30
        + model.market * 9.0
        + model.capability * 3.6
        - stability_bias * 1.2
        + random.uniform(-5, 6)
    )

    adoption_factor = clamp((state.reputation + state.compliance) / 180, 0.45, 1.1)
    adoption_factor *= clamp(1 - capability_pressure * 0.03, 0.7, 1.0)
    maturity_boost = 1 + min(model.quarters_live, 6) * 0.04
    revenue = max(0.0, demand * quality * adoption_factor * maturity_boost * 2500)

    gross_margin = clamp(
        0.50 + model.efficiency * 0.028 + model.market * 0.006 - capability_pressure * 0.012,
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
