"""Versioned in-memory context + session store."""
from typing import Any, Dict, Optional

class ContextStore:
    def __init__(self):
        self._store: Dict[str, Dict] = {}
        self._sessions: Dict[str, Any] = {}

    def _key(self, scope, cid): return f"{scope}:{cid}"

    def upsert(self, scope, context_id, version, payload, delivered_at):
        k = self._key(scope, context_id)
        ex = self._store.get(k)
        if ex and ex["version"] >= version:
            return "ignored"
        self._store[k] = {"version": version, "payload": payload, "delivered_at": delivered_at}
        return "stored"

    def get(self, scope, context_id) -> Optional[Dict]:
        if not context_id: return None
        e = self._store.get(self._key(scope, context_id))
        return e["payload"] if e else None

    def save_session(self, sid, data): self._sessions[sid] = data
    def get_session(self, sid): return self._sessions.get(sid)
