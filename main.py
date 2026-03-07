import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


def money(value: float) -> str:
    return f"${value:,.0f}"


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

    def next_upgrade_cost(self, upgrade_type: str) -> int:
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


UPGRADE_EFFECTS: Dict[str, Dict[str, float]] = {
    "capability": {"quality": 6.5, "demand": 4.0},
    "safety": {"reliability": 8.0, "trust": 1.2},
    "efficiency": {"margin": 0.025, "reliability": 2.0},
    "market": {"demand": 7.0, "price_power": 0.015},
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def show_dashboard(state: CompanyState) -> None:
    print("\n" + "=" * 70)
    print(f"{state.name} | Year {state.year} Quarter {state.quarter}")
    print("=" * 70)
    print(f"Cash: {money(state.cash)}")
    print(f"Valuation (mark): {money(state.valuation)}")
    print(f"Reputation: {state.reputation:.1f}/100")
    print(f"Compliance: {state.compliance:.1f}/100")
    print(f"Last Quarter Revenue: {money(state.last_quarter_revenue)}")
    print(f"Last Quarter Profit : {money(state.last_quarter_profit)}")
    print(f"Total Incidents: {state.total_incidents}")

    print("\nModel Portfolio")
    for idx, model in enumerate(state.models, start=1):
        print(
            f"{idx}. {model.name:<14}"
            f" Cap:{model.capability} Saf:{model.safety}"
            f" Eff:{model.efficiency} Mkt:{model.market}"
            f" Live:{model.quarters_live}Q"
        )


def quarter_budget_limit(state: CompanyState) -> int:
    # Constrained budget: spend only a fraction of cash each quarter.
    return int(min(5_500_000, max(1_000_000, state.cash * 0.42)))


def choose_upgrades(state: CompanyState) -> Tuple[int, List[str]]:
    budget = quarter_budget_limit(state)
    spent = 0
    actions: List[str] = []
    upgrade_keys = ["capability", "safety", "efficiency", "market"]

    print("\nCapital Planning")
    print(f"Quarterly R&D budget cap: {money(budget)}")
    print("You can apply upgrades until you type 'done'.")

    while True:
        remaining = budget - spent
        print(f"\nBudget remaining: {money(remaining)}")
        print("Select model number, or type 'done':")

        for idx, model in enumerate(state.models, start=1):
            print(f"{idx}. {model.name}")

        model_choice = input("> ").strip().lower()
        if model_choice == "done":
            break
        if not model_choice.isdigit() or not (1 <= int(model_choice) <= len(state.models)):
            print("Invalid model choice. Try again.")
            continue

        model = state.models[int(model_choice) - 1]

        print(f"\nUpgrades for {model.name}:")
        for i, key in enumerate(upgrade_keys, start=1):
            cost = model.next_upgrade_cost(key)
            effects = UPGRADE_EFFECTS[key]
            effect_text = ", ".join([f"{k}+{v}" for k, v in effects.items()])
            print(f"{i}. {key:<10} Cost {money(cost):>11} | {effect_text}")

        upgrade_choice = input("Pick upgrade (1-4), or 'back': ").strip().lower()
        if upgrade_choice == "back":
            continue
        if not upgrade_choice.isdigit() or not (1 <= int(upgrade_choice) <= 4):
            print("Invalid upgrade choice. Try again.")
            continue

        upgrade_key = upgrade_keys[int(upgrade_choice) - 1]
        cost = model.next_upgrade_cost(upgrade_key)
        if cost > remaining:
            print("Not enough budget left for that upgrade.")
            continue

        setattr(model, upgrade_key, getattr(model, upgrade_key) + 1)
        spent += cost
        actions.append(f"{model.name}: upgraded {upgrade_key} for {money(cost)}")
        print(f"Applied. {model.name} {upgrade_key} is now level {getattr(model, upgrade_key)}.")

    return spent, actions


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


def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    suffix = " [Y/n]: " if default_yes else " [y/N]: "
    while True:
        answer = input(prompt + suffix).strip().lower()
        if not answer:
            return default_yes
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer y or n.")


def run_quarter(state: CompanyState) -> bool:
    show_dashboard(state)

    spend, actions = choose_upgrades(state)
    state.cash -= spend

    print("\nUpgrade Summary")
    if actions:
        for line in actions:
            print(f"- {line}")
    else:
        print("- No upgrades purchased this quarter.")
    print(f"Total upgrade spend: {money(spend)}")

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

    print("\nQuarter Results")
    print(f"Revenue         : {money(total_revenue)}")
    print(f"Gross Profit    : {money(total_gross_profit)}")
    print(f"Operating Costs : {money(base_burn)}")
    print(f"Incident Costs  : {money(incident_costs)}")
    print(f"Net Profit      : {money(operating_profit)}")
    print(f"Incidents       : {incidents}")

    score, band = evaluate_company(
        state=state,
        revenue=total_revenue,
        profit=operating_profit,
        burn=base_burn,
        avg_reliability=avg_reliability,
    )

    print("\nQuarterly Board Evaluation")
    print(f"Score: {score:.1f}/100 ({band})")
    print(f"Runway: {state.runway_quarters(base_burn):.1f} quarters")

    pre_money, raise_amount, dilution = funding_offer(state, score, total_revenue)
    post_money = pre_money + raise_amount

    print("\nFunding Term Sheet")
    print(f"Pre-money valuation: {money(pre_money)}")
    print(f"Capital offered    : {money(raise_amount)}")
    print(f"Post-money         : {money(post_money)}")
    print(f"Dilution           : {dilution * 100:.2f}%")

    if ask_yes_no("Accept this funding round?", default_yes=state.cash < 3_000_000):
        state.cash += raise_amount
        state.valuation = post_money
        print("Funding accepted.")
    else:
        state.valuation = max(pre_money, state.valuation * 0.98)
        print("Funding declined. Investors are watching execution closely.")

    state.last_quarter_revenue = total_revenue
    state.last_quarter_profit = operating_profit

    state.quarter += 1
    if state.quarter > 4:
        state.quarter = 1
        state.year += 1

    if state.cash <= 0:
        print("\nCompany is out of cash. Simulation ended.")
        return False

    return True


def print_intro() -> None:
    print("=" * 70)
    print("AI Funding Simulator")
    print("=" * 70)
    print("Manage an AI startup across quarters.")
    print("- Choose which models to upgrade")
    print("- Stay within a constrained quarterly budget")
    print("- Review quarter-end performance and board evaluation")
    print("- Accept or reject funding offers")
    print("Goal: reach Year 4 with healthy cash and high company score.")


def main() -> None:
    random.seed()
    print_intro()

    state = CompanyState(
        models=[
            ModelUnit(name="Atlas Assist"),
            ModelUnit(name="Vision Copilot"),
            ModelUnit(name="Ops Automator"),
        ]
    )

    while True:
        keep_going = run_quarter(state)
        if not keep_going:
            break

        if state.year >= 4:
            print("\nYou reached Year 4.")
            final_health = (state.reputation + state.compliance) / 2
            if state.cash > 5_000_000 and final_health > 72:
                print("Result: Strong outcome. You built a resilient company.")
            elif state.cash > 1_000_000:
                print("Result: Survived with mixed performance.")
            else:
                print("Result: Growth happened, but finances remain fragile.")
            break

        if not ask_yes_no("Continue to next quarter?", default_yes=True):
            print("Simulation ended by player.")
            break


if __name__ == "__main__":
    main()