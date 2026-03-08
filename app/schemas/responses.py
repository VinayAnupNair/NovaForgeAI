from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class ModelStateResponse(BaseModel):
    name: str
    capability: int
    safety: int
    efficiency: int
    market: int
    quarters_live: int


class WorldEventResponse(BaseModel):
    key: str
    title: str
    description: str
    impact: str


class CompanyStateResponse(BaseModel):
    name: str
    quarter: int
    year: int
    cash: float
    valuation: float
    reputation: float
    compliance: float
    last_quarter_revenue: float
    last_quarter_profit: float
    total_incidents: int
    active_event: Optional[WorldEventResponse] = None
    models: List[ModelStateResponse]


class BudgetResponse(BaseModel):
    cap: int
    spent: int
    remaining: int
    actions: List[str]


class QuarterOutcomeResponse(BaseModel):
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


class QuarterHistoryPointResponse(BaseModel):
    tick: int
    year: int
    quarter: int
    revenue: float
    net_profit: float
    reputation: float
    compliance: float
    incidents: int
    score: float
    competitive_pressure: float


class ModelPerformanceResponse(BaseModel):
    name: str
    performance: float
    reliability: float
    risk: float
    balance: float


class PendingRoundResponse(BaseModel):
    quarter_outcome: QuarterOutcomeResponse


class GameSessionResponse(BaseModel):
    game_id: str
    status: Literal["active", "bankrupt", "completed", "shutdown"]
    state: CompanyStateResponse
    budget: BudgetResponse
    upgrade_effects: Dict[str, Dict[str, float]]
    history: List[QuarterHistoryPointResponse]
    model_metrics: List[ModelPerformanceResponse]
    challenge_flags: List[str]
    pending_round: Optional[PendingRoundResponse] = None


class RootResponse(BaseModel):
    message: str
    docs: str
