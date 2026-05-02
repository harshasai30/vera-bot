"""
Vera Bot - magicpin AI Challenge
FastAPI server — all 5 required endpoints
LLM Backend: Google Gemini Pro
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime, timezone
import uuid, logging

from state import ContextStore
from compose import compose

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vera-bot")

app = FastAPI(title="Vera Bot", version="1.0.0")
store = ContextStore()

# ── Schemas ──────────────────────────────────────────────────────────────────

class ContextPayload(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: str

class TickPayload(BaseModel):
    tick_id: str
    merchant_id: str
    trigger_id: Optional[str] = None
    customer_id: Optional[str] = None
    delivered_at: str

class ReplyPayload(BaseModel):
    session_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    message: str
    delivered_at: str

# ── GET /v1/healthz ──────────────────────────────────────────────────────────

@app.get("/v1/healthz")
async def healthz():
    return {"status": "ok", "bot": "vera-bot", "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat()}

# ── GET /v1/metadata ─────────────────────────────────────────────────────────

@app.get("/v1/metadata")
async def metadata():
    return {
        "name": "Vera",
        "description": "magicpin AI merchant growth assistant",
        "version": "1.0.0",
        "capabilities": ["context_storage", "tick_response", "reply_handling"],
        "supported_scopes": ["merchant", "customer", "trigger"],
        "supported_categories": ["dentist", "salon", "restaurant", "gym", "pharmacy"],
        "model": "gemini-pro"
    }

# ── POST /v1/context ─────────────────────────────────────────────────────────

@app.post("/v1/context")
async def receive_context(payload: ContextPayload):
    ack_id    = f"ack_{uuid.uuid4().hex[:12]}"
    stored_at = datetime.now(timezone.utc).isoformat()
    result    = store.upsert(payload.scope, payload.context_id,
                             payload.version, payload.payload, payload.delivered_at)
    if result == "ignored":
        return {"accepted": False, "reason": "same_or_older_version",
                "ack_id": ack_id, "stored_at": stored_at}
    logger.info(f"[ctx] scope={payload.scope} id={payload.context_id} v={payload.version}")
    return {"accepted": True, "ack_id": ack_id, "stored_at": stored_at}

# ── POST /v1/tick ────────────────────────────────────────────────────────────

@app.post("/v1/tick")
async def handle_tick(payload: TickPayload):
    merchant_ctx = store.get("merchant", payload.merchant_id)
    trigger_ctx  = store.get("trigger",  payload.trigger_id)  if payload.trigger_id  else None
    customer_ctx = store.get("customer", payload.customer_id) if payload.customer_id else None

    if not merchant_ctx:
        raise HTTPException(422, f"No merchant context for {payload.merchant_id}")

    result     = compose(merchant_ctx, trigger_ctx, customer_ctx)
    session_id = f"sess_{payload.tick_id}_{uuid.uuid4().hex[:8]}"
    store.save_session(session_id, {
        "merchant_id": payload.merchant_id,
        "history": [{"role": "assistant", "content": result["message"]}],
    })
    logger.info(f"[tick] merchant={payload.merchant_id} session={session_id}")
    return {**result, "session_id": session_id, "tick_id": payload.tick_id,
            "composed_at": datetime.now(timezone.utc).isoformat()}

# ── POST /v1/reply ───────────────────────────────────────────────────────────

@app.post("/v1/reply")
async def handle_reply(payload: ReplyPayload):
    session      = store.get_session(payload.session_id) or {}
    merchant_ctx = store.get("merchant", payload.merchant_id)
    customer_ctx = store.get("customer", payload.customer_id) if payload.customer_id else None

    if not merchant_ctx:
        raise HTTPException(422, f"No merchant context for {payload.merchant_id}")

    history = session.get("history", [])
    history.append({"role": "user", "content": payload.message})
    result  = compose(merchant_ctx, None, customer_ctx, reply_history=history)
    history.append({"role": "assistant", "content": result["message"]})
    store.save_session(payload.session_id, {**session, "history": history})

    logger.info(f"[reply] session={payload.session_id}")
    return {**result, "session_id": payload.session_id,
            "replied_at": datetime.now(timezone.utc).isoformat()}

@app.get("/")
async def root():
    return {"bot": "Vera", "status": "running", "docs": "/docs"}
