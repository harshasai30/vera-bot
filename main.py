from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime, timezone
import uuid, logging

from state import ContextStore
from compose import compose, is_stop, is_auto_reply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vera")

app = FastAPI(title="Vera Bot", version="3.0.0")
store = ContextStore()

# ── Schemas ─────────────────────────────────────────────────────

class TickPayload(BaseModel):
    tick_id: str
    merchant_id: str
    delivered_at: str
    merchant: Optional[Dict[str, Any]] = None   
    signals: Optional[Dict[str, Any]] = None    
    trigger_id: Optional[str] = None
    customer_id: Optional[str] = None


class ReplyPayload(BaseModel):
    session_id: str
    merchant_id: str
    message: str
    delivered_at: str
    customer_id: Optional[str] = None


# ── Helpers ─────────────────────────────────────────────────────

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_send_action(result: dict) -> dict:
    return {
        "action": "send",
        "body": result.get("body", ""),
        "cta": result.get("cta", ""),
        "send_as": "vera",
    }


def make_end_action():
    return {"action": "end", "body": ""}


def make_noop_action():
    return {"action": "noop", "body": ""}


# ── Health ─────────────────────────────────────────────────────

@app.get("/v1/healthz")
async def healthz():
    return {
        "status": "ok",
        "bot": "vera-bot",
        "version": "3.0.0",
        "timestamp": now_iso(),
    }


# ── Tick (MAIN LOGIC) ──────────────────────────────────────────

@app.post("/v1/tick")
async def handle_tick(payload: TickPayload):

    # ✅ FIX 1 — REMOVE HARD DEPENDENCY ON CONTEXT
    merchant_ctx = store.get("merchant", payload.merchant_id)

    if not merchant_ctx:
        # fallback → use request data directly
        merchant_ctx = payload.merchant or {
            "name": "Unknown",
            "category": "general",
            "rating": 0,
            "orders": 0,
            "views": 0
        }

    trigger_ctx = payload.signals or {}

    result = compose(merchant_ctx, trigger_ctx, None)

    action = make_send_action(result)

    session_id = f"sess_{payload.tick_id}_{uuid.uuid4().hex[:6]}"

    store.save_session(session_id, {
        "merchant_id": payload.merchant_id,
        "history": [{"role": "assistant", "content": result.get("body", "")}],
        "auto_reply_count": 0
    })

    return {
        "session_id": session_id,
        "tick_id": payload.tick_id,
        "actions": [action],
        "composed_at": now_iso()
    }


# ── Reply ─────────────────────────────────────────────────────

@app.post("/v1/reply")
async def handle_reply(payload: ReplyPayload):

    msg = payload.message
    session = store.get_session(payload.session_id) or {}

    merchant_ctx = store.get("merchant", payload.merchant_id)

    if not merchant_ctx:
        merchant_ctx = {"name": "Unknown"}

    # STOP handling
    if is_stop(msg):
        return {
            **make_end_action(),
            "session_id": payload.session_id,
            "replied_at": now_iso()
        }

    # auto-reply detection
    if is_auto_reply(msg):
        return {
            **make_noop_action(),
            "session_id": payload.session_id,
            "replied_at": now_iso()
        }

    history = session.get("history", [])
    history.append({"role": "user", "content": msg})

    result = compose(merchant_ctx, None, None, reply_history=history)

    history.append({"role": "assistant", "content": result.get("body", "")})

    store.save_session(payload.session_id, {
        **session,
        "history": history
    })

    return {
        **make_send_action(result),
        "session_id": payload.session_id,
        "replied_at": now_iso()
    }


@app.get("/")
async def root():
    return {"bot": "Vera v3", "status": "running"}
