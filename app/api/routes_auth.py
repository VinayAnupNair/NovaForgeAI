from fastapi import APIRouter, Cookie, HTTPException, Response
from typing import Optional

from app.middleware import session
from app.schemas.auth import LoginRequest, MessageResponse, RegisterRequest, UserResponse
from app.storage.user_store import UserStore

router = APIRouter()
_user_store = UserStore()


@router.post("/auth/register", response_model=MessageResponse)
def register(request: RegisterRequest, response: Response) -> MessageResponse:
    if len(request.username) < 3 or len(request.password) < 3:
        raise HTTPException(status_code=400, detail="Username and password must be at least 3 characters")
    
    if not _user_store.create_user(request.username, request.password):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Auto-login after registration
    session_id = session.create_session(request.username)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=86400 * 30,  # 30 days
        samesite="lax",
    )
    
    return MessageResponse(message="Registration successful")


@router.post("/auth/login", response_model=MessageResponse)
def login(request: LoginRequest, response: Response) -> MessageResponse:
    if not _user_store.verify_user(request.username, request.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    session_id = session.create_session(request.username)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=86400 * 30,  # 30 days
        samesite="lax",
    )
    
    return MessageResponse(message="Login successful")


@router.post("/auth/logout", response_model=MessageResponse)
def logout(response: Response, session_id: Optional[str] = Cookie(default=None)) -> MessageResponse:
    session.delete_session(session_id)
    response.delete_cookie("session_id")
    return MessageResponse(message="Logged out")


@router.get("/auth/me", response_model=UserResponse)
def get_current_user(session_id: Optional[str] = Cookie(default=None)) -> UserResponse:
    username = session.get_username(session_id)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return UserResponse(username=username)
