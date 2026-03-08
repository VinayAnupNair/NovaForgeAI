from dataclasses import asdict
import random
from uuid import uuid4

from fastapi import HTTPException

from app.domain.funding import funding_offer
from app.domain.models import (
    CompanyState,
    GameSession,
    LeaderboardEntry,
    ModelPerformanceSnapshot,
    ModelUnit,
    PendingRound,
    QuarterHistoryPoint,
    QuarterOutcome,
    RivalAction,
    UPGRADE_EFFECTS,
)
from app.domain.scoring import evaluate_company
from app.domain.simulation import quarter_budget_limit, simulate_model_outcome, state_status
from app.domain.simulation import start_quarter_event
from app.schemas.requests import ApplyUpgradesRequest, FundingDecisionRequest, NewGameRequest
from app.schemas.responses import (
    BudgetResponse,
    CompanyStateResponse,
    GameSessionResponse,
    LeaderboardEntryResponse,
    ModelPerformanceResponse,
    ModelStateResponse,
    PendingRoundResponse,
    QuarterHistoryPointResponse,
    QuarterOutcomeResponse,
    RivalActionResponse,
    WorldEventResponse,
)
from app.services.gemini_rival_service import GeminiRivalService
from app.storage.memory_store import MemoryGameStore


class GameService:
    def __init__(self, store: MemoryGameStore) -> None:
        self.store = store
        self.rival_service = GeminiRivalService()

    def create_game(self, request: NewGameRequest) -> GameSessionResponse:
        trait_pool = ["aggressive", "conservative", "ops-heavy", "consumer-friendly"]
        random.shuffle(trait_pool)
        state = CompanyState(
            name=request.company_name,
            models=[
                ModelUnit(name="Atlas Assist", trait=trait_pool[0]),
                ModelUnit(name="Vision Copilot", trait=trait_pool[1]),
                ModelUnit(name="Ops Automator", trait=trait_pool[2]),
            ],
        )

        game_id = str(uuid4())
        self.store.create(game_id, GameSession(state=state))
        session = self.get_session(game_id)
        session.leaderboard = self._build_leaderboard(session, score_hint=0.0)
        return self.serialize_session(game_id, session)

    def get_game(self, game_id: str) -> GameSessionResponse:
        session = self.get_session(game_id)
        return self.serialize_session(game_id, session)

    def apply_upgrades(self, game_id: str, request: ApplyUpgradesRequest) -> GameSessionResponse:
        session = self.get_session(game_id)

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

        return self.serialize_session(game_id, session)

    def run_quarter(self, game_id: str) -> GameSessionResponse:
        session = self.get_session(game_id)
        state = session.state

        if session.pending_round:
            raise HTTPException(status_code=400, detail="Funding decision already pending")

        if state_status(state) != "active":
            raise HTTPException(status_code=400, detail="Game is not active")

        state.cash -= session.quarter_spent
        event = start_quarter_event(state)

        model_results = [simulate_model_outcome(model, state) for model in state.models]
        total_revenue = sum(m["revenue"] for m in model_results)
        total_gross_profit = sum(m["gross_profit"] for m in model_results)
        incidents = int(sum(m["incident"] for m in model_results))
        incident_costs = sum(m["incident_cost"] for m in model_results)

        rival_actions, gemini_status = self.rival_service.choose_actions(state, event)
        session.gemini_status = gemini_status
        session.rival_actions_last_quarter = rival_actions

        demand_penalty = 0.0
        margin_penalty = 0.0
        burn_penalty = 0.0
        rival_rep_penalty = 0.0
        rival_comp_penalty = 0.0

        for action in rival_actions:
            if action.action_type == "price_cut":
                demand_penalty += 0.025 * action.strength
                margin_penalty += 0.035 * action.strength
            elif action.action_type == "lock_in":
                demand_penalty += 0.045 * action.strength
            elif action.action_type == "safety_campaign":
                rival_rep_penalty += 0.9 * action.strength
                if state.compliance < 60:
                    rival_comp_penalty += 1.2 * action.strength
            elif action.action_type == "talent_poach":
                burn_penalty += 210_000 * action.strength

        demand_penalty = min(0.22, demand_penalty)
        margin_penalty = min(0.19, margin_penalty)
        total_revenue *= max(0.75, 1 - demand_penalty)
        total_gross_profit *= max(0.72, 1 - margin_penalty)

        avg_capability = sum(m.capability for m in state.models) / len(state.models)
        avg_safety = sum(m.safety for m in state.models) / len(state.models)
        avg_efficiency = sum(m.efficiency for m in state.models) / len(state.models)
        avg_market = sum(m.market for m in state.models) / len(state.models)

        safety_efficiency_base = (avg_safety + avg_efficiency) / 2
        market_overreach = max(0.0, avg_market - safety_efficiency_base)
        capability_overreach = max(0.0, avg_capability - safety_efficiency_base)
        competitive_pressure = market_overreach + capability_overreach

        base_burn = 1_050_000 + sum(model.level_sum() for model in state.models) * 68_000
        base_burn *= event.operating_cost_multiplier
        base_burn += burn_penalty

        # Force strategic tradeoffs: aggressive market/capability without safety+efficiency
        # causes regulatory pressure, extra burn, and trust/compliance penalties.
        regulatory_penalty = competitive_pressure * 320_000
        pressure_burn = competitive_pressure * 140_000
        regulatory_penalty += event.regulatory_pressure * 180_000

        operating_profit = total_gross_profit - base_burn - incident_costs - regulatory_penalty - pressure_burn
        state.cash += operating_profit

        avg_reliability = sum(m["reliability"] for m in model_results) / len(model_results)
        total_trust_hit = sum(m["trust_hit"] for m in model_results)
        total_compliance_hit = sum(m["compliance_hit"] for m in model_results)

        trust_gain = min(2.2, max(0.2, (total_revenue / 2_200_000) * 0.38))
        trust_gain *= max(0.35, 1 - competitive_pressure * 0.16)

        compliance_gain = min(1.7, max(0.1, (avg_reliability - 60) * 0.04))
        compliance_gain *= max(0.25, 1 - competitive_pressure * 0.2)

        pressure_trust_hit = competitive_pressure * 1.3
        pressure_compliance_hit = competitive_pressure * 1.8

        if state.compliance < 60 and competitive_pressure > 0.6:
            pressure_compliance_hit += 1.4
            regulatory_penalty += 280_000
            operating_profit -= 280_000
            state.cash -= 280_000

        state.reputation = max(
            15.0,
            min(
                100.0,
                state.reputation
                + trust_gain
                - total_trust_hit
                - pressure_trust_hit
                - rival_rep_penalty
                + event.reputation_shift,
            ),
        )
        state.compliance = max(
            10.0,
            min(
                100.0,
                state.compliance
                + compliance_gain
                - total_compliance_hit
                - pressure_compliance_hit
                - rival_comp_penalty
                + event.compliance_shift,
            ),
        )
        state.total_incidents += incidents

        state.last_quarter_revenue = total_revenue
        state.last_quarter_profit = operating_profit

        model_metrics: list[ModelPerformanceSnapshot] = []
        for model, result in zip(state.models, model_results):
            quality_score = max(0.0, min(100.0, (result["quality"] - 40) * 1.6))
            reliability_score = max(0.0, min(100.0, (result["reliability"] - 35) * 1.5))
            demand_score = max(0.0, min(100.0, (result["demand"] - 20) * 1.8))
            risk_score = max(0.0, min(100.0, result["incident_prob"] * 170))
            balance_penalty = abs(model.capability - model.safety) + abs(model.market - model.efficiency)
            balance_score = max(0.0, min(100.0, 100 - balance_penalty * 7.0))

            performance = (
                quality_score * 0.35
                + reliability_score * 0.35
                + demand_score * 0.2
                + balance_score * 0.1
            )

            model_metrics.append(
                ModelPerformanceSnapshot(
                    name=model.name,
                    performance=round(performance, 2),
                    reliability=round(reliability_score, 2),
                    risk=round(risk_score, 2),
                    balance=round(balance_score, 2),
                )
            )

        session.model_metrics = model_metrics
        self._update_rival_state(session, total_revenue, rival_actions)
        session.leaderboard = self._build_leaderboard(session, score_hint=0.0)

        # If company health collapses, end the run immediately without a funding round.
        if state_status(state) != "active":
            session.history.append(
                QuarterHistoryPoint(
                    tick=len(session.history) + 1,
                    year=state.year,
                    quarter=state.quarter,
                    revenue=total_revenue,
                    net_profit=operating_profit,
                    reputation=state.reputation,
                    compliance=state.compliance,
                    incidents=incidents,
                    score=0.0,
                    competitive_pressure=round(competitive_pressure, 3),
                )
            )
            session.pending_round = None
            return self.serialize_session(game_id, session)

        score, band = evaluate_company(
            state=state,
            revenue=total_revenue,
            profit=operating_profit,
            burn=base_burn,
            avg_reliability=avg_reliability,
        )
        session.leaderboard = self._build_leaderboard(session, score_hint=score)

        pre_money, raise_amount, dilution = funding_offer(state, score, total_revenue)
        post_money = pre_money + raise_amount

        outcome = QuarterOutcome(
            revenue=total_revenue,
            gross_profit=total_gross_profit,
            operating_costs=base_burn + pressure_burn,
            incident_costs=incident_costs + regulatory_penalty,
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

        session.history.append(
            QuarterHistoryPoint(
                tick=len(session.history) + 1,
                year=state.year,
                quarter=state.quarter,
                revenue=total_revenue,
                net_profit=operating_profit,
                reputation=state.reputation,
                compliance=state.compliance,
                incidents=incidents,
                score=score,
                competitive_pressure=round(competitive_pressure, 3),
            )
        )

        session.pending_round = PendingRound(outcome=outcome)

        return self.serialize_session(game_id, session)

    def decide_funding(self, game_id: str, request: FundingDecisionRequest) -> GameSessionResponse:
        session = self.get_session(game_id)
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

        return self.serialize_session(game_id, session)

    def get_session(self, game_id: str) -> GameSession:
        session = self.store.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game session not found")
        return session

    def serialize_state(self, state: CompanyState) -> CompanyStateResponse:
        return CompanyStateResponse(
            name=state.name,
            quarter=state.quarter,
            year=state.year,
            cash=state.cash,
            valuation=state.valuation,
            reputation=state.reputation,
            compliance=state.compliance,
            last_quarter_revenue=state.last_quarter_revenue,
            last_quarter_profit=state.last_quarter_profit,
            total_incidents=state.total_incidents,
            active_event=(
                WorldEventResponse(
                    key=state.active_event.key,
                    title=state.active_event.title,
                    description=state.active_event.description,
                    impact=state.active_event.impact,
                )
                if state.active_event
                else None
            ),
            models=[
                ModelStateResponse(
                    name=m.name,
                    capability=m.capability,
                    safety=m.safety,
                    efficiency=m.efficiency,
                    market=m.market,
                    quarters_live=m.quarters_live,
                )
                for m in state.models
            ],
        )

    def serialize_session(self, game_id: str, session: GameSession) -> GameSessionResponse:
        budget_cap = quarter_budget_limit(session.state)
        remaining = max(0, budget_cap - session.quarter_spent)

        pending_round = None
        if session.pending_round:
            pending_round = PendingRoundResponse(
                quarter_outcome=QuarterOutcomeResponse(**asdict(session.pending_round.outcome))
            )

        challenge_flags: list[str] = []
        state = session.state
        avg_safety = sum(m.safety for m in state.models) / len(state.models)
        avg_efficiency = sum(m.efficiency for m in state.models) / len(state.models)
        avg_market = sum(m.market for m in state.models) / len(state.models)
        avg_capability = sum(m.capability for m in state.models) / len(state.models)

        if avg_market > avg_safety + 0.8:
            challenge_flags.append("Market growth is outpacing safety")
        if avg_capability > avg_efficiency + 0.8:
            challenge_flags.append("Capability is outpacing efficiency")
        if state.compliance < 58:
            challenge_flags.append("Compliance is in the danger zone")
        if state.reputation < 58:
            challenge_flags.append("Reputation is in the danger zone")
        if not challenge_flags:
            challenge_flags.append("Portfolio is currently balanced")

        return GameSessionResponse(
            game_id=game_id,
            status=state_status(session.state),
            state=self.serialize_state(session.state),
            budget=BudgetResponse(
                cap=budget_cap,
                spent=session.quarter_spent,
                remaining=remaining,
                actions=session.quarter_actions,
            ),
            upgrade_effects=UPGRADE_EFFECTS,
            history=[QuarterHistoryPointResponse(**asdict(point)) for point in session.history],
            model_metrics=[ModelPerformanceResponse(**asdict(m)) for m in session.model_metrics],
            rival_actions_last_quarter=[
                RivalActionResponse(**asdict(action)) for action in session.rival_actions_last_quarter
            ],
            leaderboard=[LeaderboardEntryResponse(**asdict(entry)) for entry in session.leaderboard],
            gemini_status=session.gemini_status,
            challenge_flags=challenge_flags,
            pending_round=pending_round,
        )

    def _score_for_leaderboard(
        self,
        valuation: float,
        compliance: float,
        reputation: float,
        incidents: int,
        growth_signal: float,
    ) -> float:
        valuation_score = max(0.0, min(100.0, (valuation / 120_000_000) * 100))
        incident_penalty = min(30.0, incidents * 2.4)
        score = (
            valuation_score * 0.35
            + compliance * 0.25
            + reputation * 0.2
            + growth_signal * 0.2
            - incident_penalty
        )
        return max(0.0, min(100.0, score))

    def _update_rival_state(
        self,
        session: GameSession,
        player_revenue: float,
        rival_actions: list[RivalAction],
    ) -> None:
        rival = session.rival_state
        action_strength = sum(action.strength for action in rival_actions)
        action_strength = max(0.0, min(1.9, action_strength))

        valuation_growth = 0.006 + action_strength * 0.028
        rival.valuation = max(45_000_000, rival.valuation * (1 + valuation_growth) + player_revenue * 0.026)

        compliance_shift = 0.0
        reputation_shift = 0.0
        incident_risk = 0.09

        for action in rival_actions:
            if action.action_type == "safety_campaign":
                compliance_shift += 1.3 * action.strength
                reputation_shift += 0.8 * action.strength
                incident_risk -= 0.02 * action.strength
            elif action.action_type == "price_cut":
                reputation_shift += 0.35 * action.strength
                incident_risk += 0.02 * action.strength
            elif action.action_type == "lock_in":
                reputation_shift += 0.45 * action.strength
                incident_risk += 0.015 * action.strength
            elif action.action_type == "talent_poach":
                compliance_shift += 0.3 * action.strength
                incident_risk += 0.03 * action.strength

        rival.reputation = max(35.0, min(100.0, rival.reputation + reputation_shift))
        rival.compliance = max(30.0, min(97.0, rival.compliance + compliance_shift))

        incident_risk = max(0.03, min(0.32, incident_risk))
        if random.random() < incident_risk:
            rival.total_incidents += 1

    def _build_leaderboard(self, session: GameSession, score_hint: float) -> list[LeaderboardEntry]:
        state = session.state
        rival = session.rival_state

        if len(session.history) >= 2:
            prev = session.history[-2].revenue
            curr = session.history[-1].revenue
            growth_rate = (curr - prev) / max(prev, 1.0)
            growth_signal = max(0.0, min(100.0, 50 + growth_rate * 120))
        elif len(session.history) == 1:
            growth_signal = max(0.0, min(100.0, 50 + (session.history[-1].revenue / 4_000_000) * 8))
        else:
            growth_signal = 50.0

        player_score = score_hint if score_hint > 0 else self._score_for_leaderboard(
            valuation=state.valuation,
            compliance=state.compliance,
            reputation=state.reputation,
            incidents=state.total_incidents,
            growth_signal=growth_signal,
        )
        rival.score = self._score_for_leaderboard(
            valuation=rival.valuation,
            compliance=rival.compliance,
            reputation=rival.reputation,
            incidents=rival.total_incidents,
            growth_signal=min(100.0, growth_signal + 8.0),
        )

        entries = [
            LeaderboardEntry(
                rank=0,
                name=state.name,
                is_player=True,
                score=round(player_score, 2),
                valuation=state.valuation,
                compliance=state.compliance,
                reputation=state.reputation,
                incidents=state.total_incidents,
            ),
            LeaderboardEntry(
                rank=0,
                name=rival.name,
                is_player=False,
                score=round(rival.score, 2),
                valuation=rival.valuation,
                compliance=rival.compliance,
                reputation=rival.reputation,
                incidents=rival.total_incidents,
            ),
        ]

        entries.sort(key=lambda entry: entry.score, reverse=True)
        for idx, entry in enumerate(entries, start=1):
            entry.rank = idx
        return entries
