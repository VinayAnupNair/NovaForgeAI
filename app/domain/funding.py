from typing import Tuple

from app.domain.models import CompanyState
from app.domain.simulation import clamp


def funding_offer(state: CompanyState, score: float, revenue: float) -> Tuple[float, float, float]:
    annualized_rev = revenue * 3.5
    market_multiple = 1.7 + (score / 60)
    revenue_anchored = annualized_rev * market_multiple
    prior_anchor = state.valuation * (0.82 + score / 560)

    # Valuation gets discounted more when governance and trust are weak.
    governance_penalty = max(0.0, (62 - state.compliance) * 0.0065)
    trust_penalty = max(0.0, (60 - state.reputation) * 0.0045)
    incident_penalty = min(0.2, state.total_incidents * 0.015)
    market_haircut = min(0.42, governance_penalty + trust_penalty + incident_penalty)

    pre_money_raw = (revenue_anchored * 0.52) + (prior_anchor * 0.48)
    pre_money = max(18_000_000, pre_money_raw * (1 - market_haircut))

    raise_amount = 1_900_000 + (score * 36_000)
    if state.cash < 2_500_000:
        raise_amount += 900_000

    raise_amount = clamp(raise_amount, 1_600_000, 8_500_000)
    dilution = raise_amount / (pre_money + raise_amount)
    return pre_money, raise_amount, dilution
