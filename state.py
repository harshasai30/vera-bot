"""
In-memory context store with versioned upsert.
Scopes: merchant | customer | trigger | session
"""
from typing import Any, Dict, Optional

class ContextStore:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}   # scope:id -> {version, payload}
        self._sessions: Dict[str, Any] = {}

    def _key(self, scope: str, context_id: str) -> str:
        return f"{scope}:{context_id}"

    def upsert(self, scope: str, context_id: str, version: int,
               payload: Dict[str, Any], delivered_at: str) -> str:
        k = self._key(scope, context_id)
        existing = self._store.get(k)
        if existing and existing["version"] >= version:
            return "ignored"
        self._store[k] = {"version": version, "payload": payload,
                          "delivered_at": delivered_at}
        return "stored"

    def get(self, scope: str, context_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not context_id:
            return None
        entry = self._store.get(self._key(scope, context_id))
        return entry["payload"] if entry else None

    def save_session(self, session_id: str, data: Any):
        self._sessions[session_id] = data

    def get_session(self, session_id: str) -> Optional[Any]:
        return self._sessions.get(session_id)
