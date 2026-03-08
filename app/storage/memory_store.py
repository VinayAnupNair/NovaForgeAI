from typing import Dict

from app.domain.models import GameSession


class MemoryGameStore:
    def __init__(self) -> None:
        self._games: Dict[str, Dict[str, GameSession]] = {}  # {username: {game_id: GameSession}}

    def create(self, username: str, game_id: str, session: GameSession) -> None:
        if username not in self._games:
            self._games[username] = {}
        self._games[username][game_id] = session

    def get(self, username: str, game_id: str) -> GameSession | None:
        user_games = self._games.get(username, {})
        return user_games.get(game_id)

    def exists(self, username: str, game_id: str) -> bool:
        user_games = self._games.get(username, {})
        return game_id in user_games
