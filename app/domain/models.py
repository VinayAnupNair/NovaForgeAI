from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, TypedDict


UpgradeType = Literal["capability", "safety", "efficiency", "market"]
ModelTrait = Literal["aggressive", "conservative", "ops-heavy", "consumer-friendly"]


class TraitProfile(TypedDict):
    incident_risk_shift: float
    growth_burst_bias: float
    recovery_speed: float
    debt_gain_multiplier: float


TRAIT_PROFILES: Dict[ModelTrait, TraitProfile] = {
    "aggressive": {
        "incident_risk_shift": 0.035,
        "growth_burst_bias": 0.2,
        "recovery_speed": 0.82,
        "debt_gain_multiplier": 1.28,
    },
    "conservative": {
        "incident_risk_shift": -0.03,
        "growth_burst_bias": -0.04,
        "recovery_speed": 1.22,
        "debt_gain_multiplier": 0.78,
    },
    "ops-heavy": {
        "incident_risk_shift": -0.02,
        "growth_burst_bias": 0.03,
        "recovery_speed": 1.34,
        "debt_gain_multiplier": 0.72,
    },
    "consumer-friendly": {
        "incident_risk_shift": 0.015,
        "growth_burst_bias": 0.14,
        "recovery_speed": 1.06,
        "debt_gain_multiplier": 1.0,
    },
}


UPGRADE_EFFECTS: Dict[str, Dict[str, float]] = {
    "capability": {"quality": 6.5, "demand": 4.0},
    "safety": {"reliability": 8.0, "trust": 1.2},
    "efficiency": {"margin": 0.025, "reliability": 2.0},
    "market": {"demand": 7.0, "price_power": 0.015},
}


@dataclass
class ModelUnit:
    name: str
    trait: ModelTrait = "conservative"
    capability: int = 1
    safety: int = 1
    efficiency: int = 1
    market: int = 1
    quarters_live: int = 0
    decision_debt: float = 0.0
    recovery_momentum: float = 0.0

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
    active_event: Optional["WorldEvent"] = None
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
class WorldEvent:
    key: str
    title: str
    description: str
    impact: str
    demand_multiplier: float = 1.0
    margin_shift: float = 0.0
    incident_risk_shift: float = 0.0
    operating_cost_multiplier: float = 1.0
    reputation_shift: float = 0.0
    compliance_shift: float = 0.0
    regulatory_pressure: float = 0.0


@dataclass
class PendingRound:
    outcome: QuarterOutcome


@dataclass
class QuarterHistoryPoint:
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


@dataclass
class ModelPerformanceSnapshot:
    name: str
    performance: float
    reliability: float
    risk: float
    balance: float


RivalActionType = Literal["price_cut", "lock_in", "safety_campaign", "talent_poach"]


@dataclass
class RivalAction:
    action_type: RivalActionType
    strength: float
    explanation: str


@dataclass
class RivalState:
    name: str = "Google Gemini"
    valuation: float = 68_000_000
    reputation: float = 74.0
    compliance: float = 70.0
    total_incidents: int = 0
    score: float = 58.0


@dataclass
class LeaderboardEntry:
    rank: int
    name: str
    is_player: bool
    score: float
    valuation: float
    compliance: float
    reputation: float
    incidents: int


@dataclass
class GameSession:
    state: CompanyState
    quarter_spent: int = 0
    quarter_actions: List[str] = field(default_factory=list)
    pending_round: Optional[PendingRound] = None
    history: List[QuarterHistoryPoint] = field(default_factory=list)
    model_metrics: List[ModelPerformanceSnapshot] = field(default_factory=list)
    rival_state: RivalState = field(default_factory=RivalState)
    rival_actions_last_quarter: List[RivalAction] = field(default_factory=list)
    leaderboard: List[LeaderboardEntry] = field(default_factory=list)
