import random
from typing import Tuple

from app.domain.models import CompanyState
from app.domain.simulation import clamp


def evaluate_company(
    state: CompanyState,
    revenue: float,
    profit: float,
    burn: float,
    avg_reliability: float,
) -> Tuple[float, str]:
    growth = 0.0
    if state.last_quarter_revenue > 0:
        growth = (revenue - state.last_quarter_revenue) / state.last_quarter_revenue

    runway = state.runway_quarters(max(300_000, burn))
    profitability = clamp((profit / max(1, revenue)) * 100, -50, 50)

    score = 50.0
    score += clamp(growth * 100, -20, 25) * 0.5
    score += clamp(runway * 4.2, 0, 18)
    score += (state.reputation - 60) * 0.35
    score += (state.compliance - 60) * 0.3
    score += (avg_reliability - 62) * 0.35
    score += profitability * 0.25
    score += random.uniform(-3.0, 3.0)
    score = clamp(score, 0, 100)

    if score >= 82:
        band = "Outstanding"
    elif score >= 68:
        band = "Strong"
    elif score >= 55:
        band = "Stable"
    elif score >= 42:
        band = "Risky"
    else:
        band = "Critical"

    return score, band
