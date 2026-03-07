from typing import Dict

from app.domain.models import GameSession


class MemoryGameStore:
    def __init__(self) -> None:
        self._games: Dict[str, GameSession] = {}

    def create(self, game_id: str, session: GameSession) -> None:
        self._games[game_id] = session

    def get(self, game_id: str) -> GameSession | None:
        return self._games.get(game_id)

    def exists(self, game_id: str) -> bool:
        return game_id in self._games
