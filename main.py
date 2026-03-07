import random
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


UpgradeType = Literal["capability", "safety", "efficiency", "market"]


@dataclass
class ModelUnit:
    name: str
    capability: int = 1
    safety: int = 1
    efficiency: int = 1
    market: int = 1
    quarters_live: int = 0

    def level_sum(self) -> int:
        return self.capability + self.safety + self.efficiency + self.market

    def next_upgrade_cost(self, upgrade_type: UpgradeType) -> int:
        current_level = getattr(self, upgrade_type)
        base_costs = {
            "capability": 700_000,
            "safety": 550_000,
            "efficiency": 600_000,
            "market": 650_000,
        }
        return int(base_costs[upgrade_type] * (1 + 0.16 * (current_level - 1)))


@dataclass
class CompanyState:
    name: str = "NovaForge AI"
    quarter: int = 1
    year: int = 1
    cash: float = 9_000_000
    valuation: float = 60_000_000
    reputation: float = 68.0
    compliance: float = 65.0
    last_quarter_revenue: float = 0.0
    last_quarter_profit: float = 0.0
    total_incidents: int = 0
    models: List[ModelUnit] = field(default_factory=list)

    def runway_quarters(self, burn: float) -> float:
        if burn <= 0:
            return 99.0
        return self.cash / burn


@dataclass
class QuarterOutcome:
    revenue: float
    gross_profit: float
    operating_costs: float
    incident_costs: float
    net_profit: float
    incidents: int
    score: float
    band: str
    runway_quarters: float
    pre_money: float
    raise_amount: float
    post_money: float
    dilution: float


@dataclass
class PendingRound:
    outcome: QuarterOutcome


@dataclass
class GameSession:
    state: CompanyState
    quarter_spent: int = 0
    quarter_actions: List[str] = field(default_factory=list)
    pending_round: Optional[PendingRound] = None


class NewGameRequest(BaseModel):
    company_name: str = "NovaForge AI"


class UpgradeAction(BaseModel):
    model_index: int = Field(ge=0)
    upgrade_type: UpgradeType


class ApplyUpgradesRequest(BaseModel):
    upgrades: List[UpgradeAction]


class FundingDecisionRequest(BaseModel):
    accept: bool


UPGRADE_EFFECTS: Dict[str, Dict[str, float]] = {
    "capability": {"quality": 6.5, "demand": 4.0},
    "safety": {"reliability": 8.0, "trust": 1.2},
    "efficiency": {"margin": 0.025, "reliability": 2.0},
    "market": {"demand": 7.0, "price_power": 0.015},
}

games: Dict[str, GameSession] = {}

app = FastAPI(title="NovaForge AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def quarter_budget_limit(state: CompanyState) -> int:
    return int(min(5_500_000, max(1_000_000, state.cash * 0.42)))


def state_status(state: CompanyState) -> str:
    if state.cash <= 0:
        return "bankrupt"
    if state.year >= 4:
        return "completed"
    return "active"


def simulate_model_outcome(model: ModelUnit, state: CompanyState) -> Dict[str, float]:
    quality = 52 + model.capability * 6.2 + model.market * 3.1
    reliability = 50 + model.safety * 7.5 + model.efficiency * 2.2
    demand = 34 + model.market * 8.5 + model.capability * 3.0 + random.uniform(-5, 6)

    adoption_factor = clamp((state.reputation + state.compliance) / 180, 0.45, 1.1)
    maturity_boost = 1 + min(model.quarters_live, 6) * 0.04
    revenue = max(0.0, demand * quality * adoption_factor * maturity_boost * 2500)

    gross_margin = clamp(0.48 + model.efficiency * 0.03 + model.market * 0.008, 0.50, 0.84)
    gross_profit = revenue * gross_margin

    incident_prob = clamp(0.24 - (reliability / 360) - (model.safety * 0.015), 0.02, 0.30)
    incident = random.random() < incident_prob
    incident_cost = 0.0
    trust_hit = 0.0
    compliance_hit = 0.0

    if incident:
        severity = random.uniform(0.6, 1.4)
        incident_cost = (220_000 + max(0, 68 - reliability) * 14_000) * severity
        trust_hit = random.uniform(1.8, 4.6)
        compliance_hit = random.uniform(1.0, 3.2)

    model.quarters_live += 1
    return {
        "revenue": revenue,
        "gross_profit": gross_profit,
        "incident": 1.0 if incident else 0.0,
        "incident_cost": incident_cost,
        "trust_hit": trust_hit,
        "compliance_hit": compliance_hit,
        "reliability": reliability,
        "quality": quality,
    }


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


def serialize_state(state: CompanyState) -> Dict[str, object]:
    return {
        "name": state.name,
        "quarter": state.quarter,
        "year": state.year,
        "cash": state.cash,
        "valuation": state.valuation,
        "reputation": state.reputation,
        "compliance": state.compliance,
        "last_quarter_revenue": state.last_quarter_revenue,
        "last_quarter_profit": state.last_quarter_profit,
        "total_incidents": state.total_incidents,
        "models": [
            {
                "name": m.name,
                "capability": m.capability,
                "safety": m.safety,
                "efficiency": m.efficiency,
                "market": m.market,
                "quarters_live": m.quarters_live,
            }
            for m in state.models
        ],
    }


def serialize_session(game_id: str, session: GameSession) -> Dict[str, object]:
    budget_cap = quarter_budget_limit(session.state)
    remaining = max(0, budget_cap - session.quarter_spent)
    payload: Dict[str, object] = {
        "game_id": game_id,
        "status": state_status(session.state),
        "state": serialize_state(session.state),
        "budget": {
            "cap": budget_cap,
            "spent": session.quarter_spent,
            "remaining": remaining,
            "actions": session.quarter_actions,
        },
        "upgrade_effects": UPGRADE_EFFECTS,
    }

    if session.pending_round:
        payload["pending_round"] = {
            "quarter_outcome": session.pending_round.outcome.__dict__,
        }

    return payload


def get_session(game_id: str) -> GameSession:
    session = games.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game session not found")
    return session


@app.get("/")
def root() -> Dict[str, str]:
    return {
        "message": "NovaForge API is running",
        "docs": "/docs",
    }


@app.post("/games")
def create_game(request: NewGameRequest) -> Dict[str, object]:
    state = CompanyState(
        name=request.company_name,
        models=[
            ModelUnit(name="Atlas Assist"),
            ModelUnit(name="Vision Copilot"),
            ModelUnit(name="Ops Automator"),
        ],
    )

    game_id = str(uuid4())
    games[game_id] = GameSession(state=state)
    return serialize_session(game_id, games[game_id])


@app.get("/games/{game_id}")
def get_game(game_id: str) -> Dict[str, object]:
    session = get_session(game_id)
    return serialize_session(game_id, session)


@app.post("/games/{game_id}/upgrades")
def apply_upgrades(game_id: str, request: ApplyUpgradesRequest) -> Dict[str, object]:
    session = get_session(game_id)

    if session.pending_round:
        raise HTTPException(status_code=400, detail="Resolve funding decision before more upgrades")

    if state_status(session.state) != "active":
        raise HTTPException(status_code=400, detail="Game is not active")

    budget_cap = quarter_budget_limit(session.state)

    for action in request.upgrades:
        if action.model_index >= len(session.state.models):
            raise HTTPException(status_code=400, detail=f"Invalid model_index: {action.model_index}")

        model = session.state.models[action.model_index]
        cost = model.next_upgrade_cost(action.upgrade_type)
        if session.quarter_spent + cost > budget_cap:
            raise HTTPException(status_code=400, detail="Quarterly budget exceeded")

        setattr(model, action.upgrade_type, getattr(model, action.upgrade_type) + 1)
        session.quarter_spent += cost
        session.quarter_actions.append(
            f"{model.name}: upgraded {action.upgrade_type} for {cost}"
        )

    return serialize_session(game_id, session)


@app.post("/games/{game_id}/quarters/run")
def run_quarter(game_id: str) -> Dict[str, object]:
    session = get_session(game_id)
    state = session.state

    if session.pending_round:
        raise HTTPException(status_code=400, detail="Funding decision already pending")

    if state_status(state) != "active":
        raise HTTPException(status_code=400, detail="Game is not active")

    state.cash -= session.quarter_spent

    model_results = [simulate_model_outcome(model, state) for model in state.models]
    total_revenue = sum(m["revenue"] for m in model_results)
    total_gross_profit = sum(m["gross_profit"] for m in model_results)
    incidents = int(sum(m["incident"] for m in model_results))
    incident_costs = sum(m["incident_cost"] for m in model_results)

    base_burn = 1_050_000 + sum(model.level_sum() for model in state.models) * 68_000
    operating_profit = total_gross_profit - base_burn - incident_costs
    state.cash += operating_profit

    avg_reliability = sum(m["reliability"] for m in model_results) / len(model_results)
    total_trust_hit = sum(m["trust_hit"] for m in model_results)
    total_compliance_hit = sum(m["compliance_hit"] for m in model_results)

    trust_gain = min(2.2, max(0.2, (total_revenue / 2_200_000) * 0.38))
    compliance_gain = min(1.7, max(0.1, (avg_reliability - 60) * 0.04))

    state.reputation = clamp(state.reputation + trust_gain - total_trust_hit, 15, 100)
    state.compliance = clamp(state.compliance + compliance_gain - total_compliance_hit, 10, 100)
    state.total_incidents += incidents

    score, band = evaluate_company(
        state=state,
        revenue=total_revenue,
        profit=operating_profit,
        burn=base_burn,
        avg_reliability=avg_reliability,
    )

    pre_money, raise_amount, dilution = funding_offer(state, score, total_revenue)
    post_money = pre_money + raise_amount

    outcome = QuarterOutcome(
        revenue=total_revenue,
        gross_profit=total_gross_profit,
        operating_costs=base_burn,
        incident_costs=incident_costs,
        net_profit=operating_profit,
        incidents=incidents,
        score=score,
        band=band,
        runway_quarters=state.runway_quarters(base_burn),
        pre_money=pre_money,
        raise_amount=raise_amount,
        post_money=post_money,
        dilution=dilution,
    )

    state.last_quarter_revenue = total_revenue
    state.last_quarter_profit = operating_profit
    session.pending_round = PendingRound(outcome=outcome)

    return serialize_session(game_id, session)


@app.post("/games/{game_id}/funding")
def decide_funding(game_id: str, request: FundingDecisionRequest) -> Dict[str, object]:
    session = get_session(game_id)
    state = session.state

    if not session.pending_round:
        raise HTTPException(status_code=400, detail="No pending funding offer")

    offer = session.pending_round.outcome
    if request.accept:
        state.cash += offer.raise_amount
        state.valuation = offer.post_money
    else:
        state.valuation = max(offer.pre_money, state.valuation * 0.98)

    state.quarter += 1
    if state.quarter > 4:
        state.quarter = 1
        state.year += 1

    session.quarter_spent = 0
    session.quarter_actions = []
    session.pending_round = None

    return serialize_session(game_id, session)
