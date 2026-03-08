from dataclasses import asdict
import random
from uuid import uuid4

from fastapi import HTTPException

from app.domain.funding import funding_offer
from app.domain.models import (
    CompanyState,
    FinalStats,
    GameSession,
    LeaderboardEntry,
    ModelPerformanceSnapshot,
    ModelUnit,
    PendingRound,
    QuarterHistoryPoint,
    QuarterOutcome,
    RivalAction,
    WorldEvent,
    UPGRADE_EFFECTS,
)
from app.domain.scoring import evaluate_company
from app.domain.simulation import quarter_budget_limit, simulate_model_outcome, state_status
from app.domain.simulation import start_quarter_event
from app.schemas.requests import ApplyUpgradesRequest, FundingDecisionRequest, NewGameRequest
from app.schemas.responses import (
    BudgetResponse,
    CompanyStateResponse,
    FinalStatsResponse,
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
from app.services.epilogue_service import EpilogueService
from app.services.rival_service import RivalService
from app.storage.memory_store import MemoryGameStore


class GameService:
    def __init__(self, store: MemoryGameStore) -> None:
        self.store = store
        self.rival_service = RivalService()
        self.epilogue_service = EpilogueService()

    def _session_status(self, session: GameSession) -> str:
        if session.game_completed:
            return "completed"
        return state_status(session.state)

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

    def generate_epilogue(self, game_id: str) -> GameSessionResponse:
        session = self.get_session(game_id)
        if not session.game_completed:
            raise HTTPException(status_code=400, detail="Epilogue is only available after run completion")
        if session.final_stats is None:
            raise HTTPException(status_code=400, detail="Final stats are not available")
        if not session.epilogue:
            session.epilogue = self.epilogue_service.generate(
                company_name=session.state.name,
                final_stats=session.final_stats,
                rival_name=session.rival_state.name,
            )
        return self.serialize_session(game_id, session)

    def apply_upgrades(self, game_id: str, request: ApplyUpgradesRequest) -> GameSessionResponse:
        session = self.get_session(game_id)

        if session.pending_round:
            raise HTTPException(status_code=400, detail="Resolve funding decision before more upgrades")

        if self._session_status(session) != "active":
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

        if self._session_status(session) != "active":
            raise HTTPException(status_code=400, detail="Game is not active")

        state.cash -= session.quarter_spent
        event = start_quarter_event(state)

        model_results = [simulate_model_outcome(model, state) for model in state.models]
        total_revenue = sum(m["revenue"] for m in model_results)
        total_gross_profit = sum(m["gross_profit"] for m in model_results)
        incidents = int(sum(m["incident"] for m in model_results))
        incident_costs = sum(m["incident_cost"] for m in model_results)

        rival_actions, rival_status = self.rival_service.choose_actions(state, event)
        session.rival_status = rival_status
        session.rival_actions_last_quarter = rival_actions

        demand_penalty = 0.0
        margin_penalty = 0.0
        burn_penalty = 0.0
        rival_rep_penalty = 0.0
        rival_comp_penalty = 0.0
        rival_risk_pressure = 0.0

        for action in rival_actions:
            if action.action_type == "predatory_pricing":
                demand_penalty += 0.07 * action.strength
                margin_penalty += 0.09 * action.strength
                rival_risk_pressure += 0.22 * action.strength
            elif action.action_type == "regulatory_lobbying":
                rival_rep_penalty += 1.25 * action.strength
                if state.compliance < 72:
                    rival_comp_penalty += 1.85 * action.strength
                burn_penalty += 120_000 * action.strength
            elif action.action_type == "moonshot_launch":
                demand_penalty += 0.045 * action.strength
                burn_penalty += 260_000 * action.strength
                rival_rep_penalty += 0.95 * action.strength
                rival_risk_pressure += 0.3 * action.strength
            elif action.action_type == "data_center_blitz":
                margin_penalty += 0.06 * action.strength
                burn_penalty += 180_000 * action.strength
                rival_risk_pressure += 0.18 * action.strength
            elif action.action_type == "upgrade_capability":
                margin_penalty += 0.018 * action.strength
                rival_rep_penalty += 0.32 * action.strength
            elif action.action_type == "upgrade_market":
                demand_penalty += 0.023 * action.strength
            elif action.action_type == "upgrade_efficiency":
                margin_penalty += 0.02 * action.strength
            elif action.action_type == "upgrade_safety" and state.compliance < 65:
                rival_comp_penalty += 0.55 * action.strength

        demand_penalty = min(0.3, demand_penalty)
        margin_penalty = min(0.24, margin_penalty)
        total_revenue *= max(0.68, 1 - demand_penalty)
        total_gross_profit *= max(0.66, 1 - margin_penalty)

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
        self._update_rival_state(session, total_revenue, rival_actions, rival_risk_pressure, event)
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
                    rival_valuation=session.rival_state.valuation,
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
                rival_valuation=session.rival_state.valuation,
            )
        )

        if state.year == 3 and state.quarter == 4:
            player_rank = 1
            rival_valuation = session.rival_state.valuation
            rival_score = session.rival_state.score
            for entry in session.leaderboard:
                if entry.is_player:
                    player_rank = entry.rank
                else:
                    rival_valuation = entry.valuation
                    rival_score = entry.score

            session.final_stats = FinalStats(
                year=state.year,
                quarter=state.quarter,
                valuation=state.valuation,
                cash=state.cash,
                reputation=state.reputation,
                compliance=state.compliance,
                incidents=state.total_incidents,
                revenue=total_revenue,
                net_profit=operating_profit,
                score=score,
                band=band,
                player_rank=player_rank,
                rival_valuation=rival_valuation,
                rival_score=rival_score,
            )
            session.epilogue = None
            session.game_completed = True
            session.pending_round = None
            return self.serialize_session(game_id, session)

        session.pending_round = PendingRound(outcome=outcome)

        return self.serialize_session(game_id, session)

    def decide_funding(self, game_id: str, request: FundingDecisionRequest) -> GameSessionResponse:
        session = self.get_session(game_id)
        state = session.state

        if session.game_completed:
            raise HTTPException(status_code=400, detail="Game is already completed")

        if not session.pending_round:
            raise HTTPException(status_code=400, detail="No pending funding offer")

        offer = session.pending_round.outcome
        if request.accept:
            state.cash += offer.raise_amount
            # Execution friction: headline post-money is discounted slightly.
            state.valuation = max(offer.pre_money, offer.post_money * 0.95)
        else:
            # Declining capital in a competitive market triggers stronger repricing.
            state.valuation = max(offer.pre_money * 0.92, state.valuation * 0.94)

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
            status=self._session_status(session),
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
            rival_status=session.rival_status,
            challenge_flags=challenge_flags,
            pending_round=pending_round,
            final_stats=(FinalStatsResponse(**asdict(session.final_stats)) if session.final_stats else None),
            epilogue=session.epilogue,
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
        risk_pressure: float,
        event: WorldEvent,
    ) -> None:
        rival = session.rival_state
        action_strength = sum(action.strength for action in rival_actions)
        action_strength = max(0.0, min(2.0, action_strength))

        valuation_growth = 0.012 + action_strength * 0.036
        rival.valuation = max(45_000_000, rival.valuation * (1 + valuation_growth) + player_revenue * 0.034)

        compliance_shift = 0.0
        reputation_shift = 0.0
        incident_risk = 0.09

        for action in rival_actions:
            if action.action_type == "predatory_pricing":
                reputation_shift += 1.35 * action.strength
                compliance_shift -= 0.95 * action.strength
                incident_risk += 0.04 * action.strength
            elif action.action_type == "regulatory_lobbying":
                investment_cost = 540_000 * action.strength
                rival.valuation = max(40_000_000, rival.valuation - investment_cost)
                compliance_shift += 1.2 * action.strength
                reputation_shift += 0.6 * action.strength
                incident_risk += 0.015 * action.strength
            elif action.action_type == "moonshot_launch":
                rival.valuation += 2_700_000 * action.strength
                reputation_shift += 2.0 * action.strength
                compliance_shift -= 1.45 * action.strength
                incident_risk += 0.075 * action.strength
            elif action.action_type == "data_center_blitz":
                rival.valuation += 950_000 * action.strength
                reputation_shift += 0.9 * action.strength
                incident_risk += 0.03 * action.strength
            elif action.action_type == "upgrade_capability":
                # Invest in AI model capability
                investment_cost = 610_000 * action.strength
                rival.valuation = max(40_000_000, rival.valuation - investment_cost)
                reputation_shift += 1.05 * action.strength
            elif action.action_type == "upgrade_safety":
                # Invest in safety and compliance infrastructure
                investment_cost = 460_000 * action.strength
                rival.valuation = max(40_000_000, rival.valuation - investment_cost)
                compliance_shift += 2.9 * action.strength
                reputation_shift += 1.3 * action.strength
                incident_risk -= 0.025 * action.strength
            elif action.action_type == "upgrade_efficiency":
                # Invest in operational efficiency
                investment_cost = 500_000 * action.strength
                rival.valuation = max(40_000_000, rival.valuation - investment_cost)
                reputation_shift += 0.85 * action.strength
                incident_risk -= 0.012 * action.strength
            elif action.action_type == "upgrade_market":
                # Invest in market reach and brand
                investment_cost = 560_000 * action.strength
                rival.valuation = max(40_000_000, rival.valuation - investment_cost)
                reputation_shift += 1.7 * action.strength

        rival.reputation = max(35.0, min(100.0, rival.reputation + reputation_shift))
        rival.compliance = max(30.0, min(98.5, rival.compliance + compliance_shift))

        incident_risk += min(0.1, risk_pressure * 0.22)
        incident_risk = max(0.03, min(0.42, incident_risk))
        if random.random() < incident_risk:
            rival.total_incidents += 1

        # Event momentum can trigger visible valuation spikes for rival.
        demand_impulse = max(0.0, event.demand_multiplier - 1.0) * 0.2
        margin_impulse = max(0.0, event.margin_shift) * 2.6
        trust_impulse = max(0.0, event.reputation_shift) * 0.03
        compliance_impulse = max(0.0, event.compliance_shift) * 0.02
        volatility_impulse = (
            abs(event.demand_multiplier - 1.0) * 0.07
            + abs(event.margin_shift) * 1.0
            + abs(event.incident_risk_shift) * 0.9
            + event.regulatory_pressure * 0.025
        )
        event_spike_factor = min(
            0.18,
            demand_impulse + margin_impulse + trust_impulse + compliance_impulse + (volatility_impulse * 0.45),
        )
        if event_spike_factor > 0:
            rival.valuation += rival.valuation * event_spike_factor

        # Fairness pass: give rival a funding-style repricing step each quarter,
        # similar to how player valuation gets reset by board funding outcomes.
        pre_round_valuation = rival.valuation

        strategy_score = max(
            20.0,
            min(
                98.0,
                rival.reputation * 0.5
                + rival.compliance * 0.4
                + action_strength * 12
                - rival.total_incidents * 2.2,
            ),
        )
        rival_revenue_proxy = player_revenue * (0.38 + action_strength * 0.14)
        rival_annualized_revenue = rival_revenue_proxy * 4
        rival_market_multiple = 1.35 + (strategy_score / 95)
        revenue_anchored = rival_annualized_revenue * rival_market_multiple
        prior_anchor = rival.valuation * (0.92 + strategy_score / 520)

        rival_pre_money = max(36_000_000, (revenue_anchored * 0.34) + (prior_anchor * 0.66))
        rival_raise = 1_900_000 + (strategy_score * 28_000) + (action_strength * 380_000)
        rival_raise = max(1_900_000, min(8_200_000, rival_raise))
        rival_post_money = rival_pre_money + rival_raise

        # Assume rival usually closes the round, but cap quarter-over-quarter spike.
        target_valuation = max(rival_pre_money, rival_post_money * 0.94)
        rival.valuation = min(target_valuation, pre_round_valuation * 1.34)

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

        # Leaderboard now prioritizes valuation over composite score.
        entries.sort(key=lambda entry: entry.valuation, reverse=True)
        for idx, entry in enumerate(entries, start=1):
            entry.rank = idx
        return entries
