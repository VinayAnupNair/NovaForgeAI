from fastapi import APIRouter

from app.schemas.requests import ApplyUpgradesRequest, FundingDecisionRequest, NewGameRequest
from app.schemas.responses import GameSessionResponse
from app.services.game_service import GameService
from app.storage.memory_store import MemoryGameStore


router = APIRouter()
_store = MemoryGameStore()
_service = GameService(_store)


@router.post("/games", response_model=GameSessionResponse)
def create_game(request: NewGameRequest) -> GameSessionResponse:
    return _service.create_game(request)


@router.get("/games/{game_id}", response_model=GameSessionResponse)
def get_game(game_id: str) -> GameSessionResponse:
    return _service.get_game(game_id)


@router.post("/games/{game_id}/upgrades", response_model=GameSessionResponse)
def apply_upgrades(game_id: str, request: ApplyUpgradesRequest) -> GameSessionResponse:
    return _service.apply_upgrades(game_id, request)


@router.post("/games/{game_id}/quarters/run", response_model=GameSessionResponse)
def run_quarter(game_id: str) -> GameSessionResponse:
    return _service.run_quarter(game_id)


@router.post("/games/{game_id}/funding", response_model=GameSessionResponse)
def decide_funding(game_id: str, request: FundingDecisionRequest) -> GameSessionResponse:
    return _service.decide_funding(game_id, request)


@router.post("/games/{game_id}/epilogue", response_model=GameSessionResponse)
def generate_epilogue(game_id: str) -> GameSessionResponse:
    return _service.generate_epilogue(game_id)
