import json
from urllib import error, request

from app.domain.models import FinalStats


class EpilogueService:
    def __init__(self) -> None:
        self.url = "http://127.0.0.1:11434/api/generate"
        self.model = "qwen2.5:7b"

    def generate(self, company_name: str, final_stats: FinalStats, rival_name: str) -> str:
        prompt = self._build_prompt(company_name, final_stats, rival_name)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            req = request.Request(
                self.url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=12) as response:
                body = response.read().decode("utf-8")
            parsed = json.loads(body)
            text = str(parsed.get("response", "")).strip()
            if text:
                return text[:1800]
        except (TimeoutError, error.URLError, error.HTTPError, json.JSONDecodeError):
            pass

        return (
            f"By the end of Year {final_stats.year} Q{final_stats.quarter}, {company_name} closed at "
            f"${final_stats.valuation:,.0f} valuation with {final_stats.reputation:.1f} reputation and "
            f"{final_stats.compliance:.1f} compliance. The rivalry with {rival_name} shaped every quarter, "
            "forcing hard tradeoffs between speed, safety, and execution discipline."
        )

    def _build_prompt(self, company_name: str, final_stats: FinalStats, rival_name: str) -> str:
        outcome = "won" if final_stats.player_rank == 1 else "did not win"
        return (
            "Write a cinematic startup epilogue in 75-110 words, second person. "
            "Paint a vivid story with clear ending momentum. Do not use markdown.\n"
            "Branch by outcome: if player won, make it triumphant but costly; if player lost, make it bittersweet and forward-looking.\n"
            "Keep sentences punchy and image-rich.\n\n"
            f"Company: {company_name}\n"
            f"Final period: Year {final_stats.year} Q{final_stats.quarter}\n"
            f"Outcome: Player {outcome}\n"
            f"Valuation: ${final_stats.valuation:,.0f}\n"
            f"Cash: ${final_stats.cash:,.0f}\n"
            f"Reputation: {final_stats.reputation:.1f}\n"
            f"Compliance: {final_stats.compliance:.1f}\n"
            f"Incidents: {final_stats.incidents}\n"
            f"Last quarter revenue: ${final_stats.revenue:,.0f}\n"
            f"Last quarter net profit: ${final_stats.net_profit:,.0f}\n"
            f"Score: {final_stats.score:.1f} ({final_stats.band})\n"
            f"Leaderboard rank: #{final_stats.player_rank}\n"
            f"Rival: {rival_name} at ${final_stats.rival_valuation:,.0f}, score {final_stats.rival_score:.1f}.\n"
        )
