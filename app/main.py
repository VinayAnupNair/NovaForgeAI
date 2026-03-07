from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_games import router as games_router
from app.schemas.responses import RootResponse


app = FastAPI(title="NovaForge AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games_router)


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        message="NovaForge API is running",
        docs="/docs",
    )
