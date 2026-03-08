from fastapi import APIRouter, Cookie, HTTPException
from typing import Optional

from app.middleware import session
from app.schemas.requests import ApplyUpgradesRequest, FundingDecisionRequest, NewGameRequest
from app.schemas.responses import GameSessionResponse, RunHistoryItemResponse, RunHistoryResponse
from app.services.game_service import GameService
from app.storage.memory_store import MemoryGameStore
from app.storage.run_history_store import RunHistoryStore


router = APIRouter()
_store = MemoryGameStore()
_history_store = RunHistoryStore()
_service = GameService(_store, _history_store)


def get_current_user(session_id: Optional[str] = Cookie(default=None)) -> str:
    """Dependency to get current authenticated user"""
    username = session.get_username(session_id)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username


@router.post("/games", response_model=GameSessionResponse)
def create_game(request: NewGameRequest, session_id: Optional[str] = Cookie(default=None)) -> GameSessionResponse:
    username = get_current_user(session_id)
    return _service.create_game(username, request)


@router.get("/games/{game_id}", response_model=GameSessionResponse)
def get_game(game_id: str, session_id: Optional[str] = Cookie(default=None)) -> GameSessionResponse:
    username = get_current_user(session_id)
    return _service.get_game(username, game_id)


@router.post("/games/{game_id}/upgrades", response_model=GameSessionResponse)
def apply_upgrades(game_id: str, request: ApplyUpgradesRequest, session_id: Optional[str] = Cookie(default=None)) -> GameSessionResponse:
    username = get_current_user(session_id)
    return _service.apply_upgrades(username, game_id, request)


@router.post("/games/{game_id}/quarters/run", response_model=GameSessionResponse)
def run_quarter(game_id: str, session_id: Optional[str] = Cookie(default=None)) -> GameSessionResponse:
    username = get_current_user(session_id)
    return _service.run_quarter(username, game_id)


@router.post("/games/{game_id}/funding", response_model=GameSessionResponse)
def decide_funding(game_id: str, request: FundingDecisionRequest, session_id: Optional[str] = Cookie(default=None)) -> GameSessionResponse:
    username = get_current_user(session_id)
    return _service.decide_funding(username, game_id, request)


@router.post("/games/{game_id}/epilogue", response_model=GameSessionResponse)
def generate_epilogue(game_id: str, session_id: Optional[str] = Cookie(default=None)) -> GameSessionResponse:
    username = get_current_user(session_id)
    return _service.generate_epilogue(username, game_id)


@router.get("/history", response_model=RunHistoryResponse)
def get_history(limit: int = 15, session_id: Optional[str] = Cookie(default=None)) -> RunHistoryResponse:
    username = get_current_user(session_id)
    rows = _service.get_history(username, limit=limit)
    return RunHistoryResponse(items=[RunHistoryItemResponse(**row) for row in rows])
