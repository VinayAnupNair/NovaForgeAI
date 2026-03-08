import json
import os
from pathlib import Path
from typing import List, Tuple
from urllib import error, request

from app.domain.models import CompanyState, RivalAction, RivalActionType, WorldEvent

_ALLOWED_ACTIONS: set[RivalActionType] = {
    "predatory_pricing",
    "regulatory_lobbying",
    "moonshot_launch",
    "data_center_blitz",
    "upgrade_capability",
    "upgrade_safety",
    "upgrade_efficiency",
    "upgrade_market",
}


class RivalService:
    def __init__(self) -> None:
        self.api_key = self._load_api_key()

    def _load_api_key(self) -> str | None:
        # Support direct env var and local development in .env.local.
        direct_key = os.getenv("RIVAL_API_KEY") or os.getenv("OPENAI_API_KEY")
        if direct_key:
            return direct_key

        env_local = Path(".env.local")
        if not env_local.exists():
            return None

        for line in env_local.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() in {"RIVAL_API_KEY", "OPENAI_API_KEY"}:
                return value.strip().strip("\"'")
        return None

    def choose_actions(self, state: CompanyState, event: WorldEvent) -> Tuple[List[RivalAction], str]:
        self.api_key = self._load_api_key()
        if not self.api_key:
            return self._fallback_actions(state, event), "rival-fallback-no-key"

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": self._build_prompt(state, event),
                },
            ],
            "temperature": 0.3,
            "response_format": {
                "type": "json_object",
            },
        }

        api_url = "https://api.openai.com/v1/chat/completions"

        try:
            req = request.Request(
                api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=3.5) as response:
                body = response.read().decode("utf-8")
            parsed = json.loads(body)
            candidate_text = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")
            actions = self._parse_actions(candidate_text)
            if actions:
                return actions, "rival-live"
            return self._fallback_actions(state, event), "rival-fallback-empty"
        except error.HTTPError as e:
            print(f"Rival HTTP error {e.code}: {e.reason}")
            print(f"Response: {e.read().decode()}")
            return self._fallback_actions(state, event), "rival-fallback-http"
        except (TimeoutError, error.URLError, json.JSONDecodeError) as e:
            print(f"Rival API error: {type(e).__name__}: {e}")
            return self._fallback_actions(state, event), "rival-fallback-transport"
        except Exception as e:
            print(f"Rival unexpected error: {type(e).__name__}: {e}")
            return self._fallback_actions(state, event), "rival-fallback-unexpected"

    def _build_prompt(self, state: CompanyState, event: WorldEvent) -> str:
        return (
            "You are a rival AI strategist in a simulation game. "
            "Return strict JSON only with schema: {\"actions\":[{\"action_type\":string,\"strength\":number,\"explanation\":string}]}. "
            "Allowed action_type values: predatory_pricing, regulatory_lobbying, moonshot_launch, data_center_blitz, upgrade_capability, upgrade_safety, upgrade_efficiency, upgrade_market. "
            "Return exactly 3 actions. Include at least 1 risky action from: predatory_pricing, moonshot_launch, data_center_blitz. "
            "Strength range is 0.65-0.98. Use bold, high-impact strategies with meaningful downside risk."
            "\n\n"
            f"Your metrics: cash={state.cash:.0f}, valuation={state.valuation:.0f}, "
            f"reputation={state.reputation:.1f}, compliance={state.compliance:.1f}."
            f"\nCompetitor: {len(state.models)} models, avg capability {(sum(m.capability for m in state.models) / len(state.models) if state.models else 1):.1f}."
            "\n"
            f"World event: {event.title}. Impact: {event.impact}."
            "\n\n"
            "Strategy: Force the player into difficult tradeoffs. Mix one growth move, one pressure move, and one stabilizer."
        )

    def _parse_actions(self, raw_json_text: str) -> List[RivalAction]:
        try:
            data = json.loads(raw_json_text)
        except json.JSONDecodeError:
            return []

        action_items = data.get("actions") if isinstance(data, dict) else None
        if not isinstance(action_items, list):
            return []

        parsed: List[RivalAction] = []
        used_actions: set[RivalActionType] = set()
        for item in action_items[:3]:
            if not isinstance(item, dict):
                continue
            action_type = item.get("action_type")
            if action_type not in _ALLOWED_ACTIONS:
                continue
            if action_type in used_actions:
                continue
            strength = item.get("strength", 0.5)
            if not isinstance(strength, (float, int)):
                continue
            explanation = str(item.get("explanation", "Rival strategy move"))[:120]
            used_actions.add(action_type)
            parsed.append(
                RivalAction(
                    action_type=action_type,
                    strength=max(0.65, min(0.98, float(strength))),
                    explanation=explanation,
                )
            )

        if not parsed:
            return []

        # Guarantee an aggressive trio when the model returns too few actions.
        if len(parsed) < 3:
            fallback_plan: list[tuple[RivalActionType, float, str]] = [
                ("predatory_pricing", 0.84, "Aggressive market share grab despite margin risk"),
                ("moonshot_launch", 0.82, "High-upside launch with meaningful execution risk"),
                ("upgrade_safety", 0.74, "Stabilize compliance after aggressive push"),
            ]
            used_types = {a.action_type for a in parsed}
            for fallback_type, fallback_strength, fallback_note in fallback_plan:
                if len(parsed) >= 3:
                    break
                if fallback_type in used_types:
                    continue
                parsed.append(
                    RivalAction(
                        action_type=fallback_type,
                        strength=fallback_strength,
                        explanation=fallback_note,
                    )
                )
                used_types.add(fallback_type)

        return parsed

    def _fallback_actions(self, state: CompanyState, event: WorldEvent) -> List[RivalAction]:
        # Deterministic, high-pressure fallback so rival always acts even without model output.
        base_strength = 0.86 if state.reputation >= 60 else 0.8
        if event.regulatory_pressure > 0.8 or event.incident_risk_shift > 0.015:
            return [
                RivalAction("regulatory_lobbying", 0.82, "Push regulatory leverage while market is unstable"),
                RivalAction("predatory_pricing", base_strength, "Force immediate share capture during uncertainty"),
                RivalAction("upgrade_safety", 0.74, "Stabilize downside risk after aggressive pressure"),
            ]

        if event.demand_multiplier > 1.05:
            return [
                RivalAction("moonshot_launch", 0.9, "Exploit demand surge with risky flagship launch"),
                RivalAction("data_center_blitz", 0.8, "Scale infrastructure to absorb market demand spike"),
                RivalAction("upgrade_market", 0.76, "Lock in demand while momentum is high"),
            ]

        return [
            RivalAction("predatory_pricing", base_strength, "Compress margins to force painful player tradeoffs"),
            RivalAction("moonshot_launch", 0.82, "Bet on breakout capability before player can respond"),
            RivalAction("upgrade_efficiency", 0.72, "Protect execution while maintaining offensive tempo"),
        ]