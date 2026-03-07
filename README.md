# AI Funding Simulator

An interactive terminal game where you run an AI startup quarter by quarter.

You choose which models to upgrade under a constrained R&D budget, then the game simulates revenue, incidents, board evaluation, and funding offers.

## What You Do

- Manage a portfolio of AI products (`Atlas Assist`, `Vision Copilot`, `Ops Automator`)
- Spend a limited quarterly budget on model upgrades
- Balance growth and safety to protect reputation and compliance
- Review quarterly performance and investor score
- Accept or reject funding rounds based on valuation and dilution
- Survive to Year 4 with strong cash and company health

## Core Mechanics

Each model has 4 upgrade tracks:

- `capability`: boosts quality and demand
- `safety`: improves reliability and trust
- `efficiency`: improves margins and reliability
- `market`: increases demand and pricing power

Every quarter:

1. You allocate upgrades (or skip)
2. The simulator computes business outcomes:
	- Revenue
	- Gross profit
	- Operating costs
	- Incident costs
	- Net profit
3. Board evaluation generates a company score (`0-100`)
4. Investors offer funding with terms:
	- Pre-money valuation
	- Capital offered
	- Dilution
5. You accept or decline and move to next quarter

## Requirements

- Python 3.9+ (recommended)

No external dependencies are required.

## Run

From the project root:

```bash
python3 main.py
```

## Example Input Flow

During a quarter you can enter:

- Model number (`1`, `2`, `3`)
- Upgrade number (`1` to `4`)
- `back` to return
- `done` to finish spending
- `y` / `n` for funding and continuation decisions

## Win / End Conditions

- Primary success horizon: reach `Year 4`
- Early failure: company cash falls to `0` or below
- Final outcome depends on:
  - Cash position
  - Reputation and compliance health

## Strategy Tips

- Do not over-index on growth upgrades early; safety prevents expensive incidents.
- Efficiency compounds through better margins and helps runway.
- Declining a funding round can preserve ownership, but increases financial risk.
- Watch quarterly runway and incident count as your main risk indicators.

## Project Structure

```text
.
├── main.py
└── README.md
```

## Notes

- The simulation includes randomness (`random`) to keep runs varied.
- If your system does not have `python` alias, use `python3`.
