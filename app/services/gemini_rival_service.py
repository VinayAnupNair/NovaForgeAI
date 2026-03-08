import json
import os
from pathlib import Path
from typing import List, Tuple
from urllib import error, request

from app.domain.models import CompanyState, RivalAction, RivalActionType, WorldEvent

_ALLOWED_ACTIONS: set[RivalActionType] = {
    "price_cut",
    "lock_in",
    "safety_campaign",
    "talent_poach",
}


class GeminiRivalService:
    def __init__(self) -> None:
        self.api_key = self._load_api_key()

    def _load_api_key(self) -> str | None:
        # Support local development where key is stored in .env.local.
        direct_key = os.getenv("GEMINI_API_KEY")
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
            if key.strip() == "GEMINI_API_KEY":
                return value.strip().strip("\"'")
        return None

    def choose_actions(self, state: CompanyState, event: WorldEvent) -> Tuple[List[RivalAction], str]:
        # Reload key each call so .env.local edits work immediately.
        self.api_key = self._load_api_key()
        if not self.api_key:
            return [], "missing-api-key"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": self._build_prompt(state, event),
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "response_mime_type": "application/json",
            },
        }

        api_url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/gemini-1.5-flash:generateContent?key={self.api_key}"
        )

        try:
            req = request.Request(
                api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=3.5) as response:
                body = response.read().decode("utf-8")
            parsed = json.loads(body)
            candidate_text = (
                parsed.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            actions = self._parse_actions(candidate_text)
            if actions:
                return actions, "gemini-live"
            return [], "gemini-empty-response"
        except (TimeoutError, error.URLError, error.HTTPError, json.JSONDecodeError):
            return [], "gemini-call-failed"

    def _build_prompt(self, state: CompanyState, event: WorldEvent) -> str:
        return (
            "You are Gemini, an AI rival strategist in a simulation game. "
            "Return strict JSON only with schema: {\"actions\":[{\"action_type\":string,\"strength\":number,\"explanation\":string}]}. "
            "Allowed action_type values: price_cut, lock_in, safety_campaign, talent_poach. "
            "Return 1 or 2 actions max. Keep strength between 0.2 and 0.95."
            "\n\n"
            f"Company metrics: cash={state.cash:.0f}, valuation={state.valuation:.0f}, "
            f"reputation={state.reputation:.1f}, compliance={state.compliance:.1f}."
            "\n"
            f"Current world event: {event.title}. Impact: {event.impact}."
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
        for item in action_items[:2]:
            if not isinstance(item, dict):
                continue
            action_type = item.get("action_type")
            if action_type not in _ALLOWED_ACTIONS:
                continue
            strength = item.get("strength", 0.5)
            if not isinstance(strength, (float, int)):
                continue
            explanation = str(item.get("explanation", "Gemini strategy move"))[:120]
            parsed.append(
                RivalAction(
                    action_type=action_type,
                    strength=max(0.2, min(0.95, float(strength))),
                    explanation=explanation,
                )
            )
        return parsed
