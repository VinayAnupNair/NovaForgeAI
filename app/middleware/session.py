from typing import Dict, Optional
import secrets

# Simple in-memory session store
_sessions: Dict[str, str] = {}  # {session_id: username}


def create_session(username: str) -> str:
    """Create a new session and return session ID"""
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = username
    return session_id


def get_username(session_id: Optional[str]) -> Optional[str]:
    """Get username from session ID"""
    if not session_id:
        return None
    return _sessions.get(session_id)


def delete_session(session_id: Optional[str]) -> None:
    """Delete a session"""
    if session_id and session_id in _sessions:
        del _sessions[session_id]
