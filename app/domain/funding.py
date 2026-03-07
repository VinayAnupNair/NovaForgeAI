from typing import Tuple

from app.domain.models import CompanyState
from app.domain.simulation import clamp


def funding_offer(state: CompanyState, score: float, revenue: float) -> Tuple[float, float, float]:
    annualized_rev = revenue * 4
    market_multiple = 2.8 + (score / 38)
    revenue_anchored = annualized_rev * market_multiple
    prior_anchor = state.valuation * (0.9 + score / 350)

    pre_money = max(30_000_000, (revenue_anchored * 0.6) + (prior_anchor * 0.4))
    raise_amount = 3_000_000 + (score * 55_000)
    if state.cash < 2_500_000:
        raise_amount += 1_500_000

    raise_amount = clamp(raise_amount, 3_000_000, 12_000_000)
    dilution = raise_amount / (pre_money + raise_amount)
    return pre_money, raise_amount, dilution
