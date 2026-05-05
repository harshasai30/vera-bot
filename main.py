"""
Vera Bot v2 — magicpin AI Challenge
Fixed response schema: actions[], action field, STOP handling, auto-reply detection.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone
import uuid, logging

from state import ContextStore
from compose import compose, is_stop, is_auto_reply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vera")

app   = FastAPI(title="Vera Bot", version="2.0.0")
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

# ── Helpers ───────────────────────────────────────────────────────────────────

def now_iso(): return datetime.now(timezone.utc).isoformat()

def make_send_action(result: dict) -> dict:
    """Wrap compose result into the judge-expected action object."""
    return {
        "action":          "send",
        "body":            result.get("body", ""),
        "cta":             result.get("cta", ""),
        "send_as":         result.get("send_as", "vera"),
        "suppression_key": result.get("suppression_key", ""),
        "rationale":       result.get("rationale", ""),
    }

def make_end_action(reason: str = "conversation ended") -> dict:
    return {"action": "end", "body": "", "rationale": reason}

def make_noop_action(reason: str = "auto-reply detected") -> dict:
    return {"action": "noop", "body": "", "rationale": reason}

# ── GET /v1/healthz ───────────────────────────────────────────────────────────

@app.get("/v1/healthz")
async def healthz():
    return {"status": "ok", "bot": "vera-bot", "version": "2.0.0",
            "timestamp": now_iso()}

# ── GET /v1/metadata ──────────────────────────────────────────────────────────

@app.get("/v1/metadata")
async def metadata():
    return {
        "name":        "Vera",
        "description": "magicpin AI merchant growth assistant",
        "version":     "2.0.0",
        "capabilities": ["context_storage", "tick_response", "reply_handling",
                         "stop_handling", "auto_reply_detection"],
        "supported_scopes":      ["merchant", "customer", "trigger"],
        "supported_categories":  ["dentist", "salon", "restaurant", "gym", "pharmacy"],
        "supported_trigger_types": ["spike","dip","recall","festival","research","regulation_change"],
        "model": "gemini-1.5-flash",
    }

# ── POST /v1/context ──────────────────────────────────────────────────────────

@app.post("/v1/context")
async def receive_context(payload: ContextPayload):
    ack_id    = f"ack_{uuid.uuid4().hex[:12]}"
    stored_at = now_iso()
    result    = store.upsert(payload.scope, payload.context_id,
                             payload.version, payload.payload, payload.delivered_at)
    if result == "ignored":
        return {"accepted": False, "reason": "same_or_older_version",
                "ack_id": ack_id, "stored_at": stored_at}
    logger.info(f"[ctx] {payload.scope}/{payload.context_id} v{payload.version}")
    return {"accepted": True, "ack_id": ack_id, "stored_at": stored_at}

# ── POST /v1/tick ─────────────────────────────────────────────────────────────

@app.post("/v1/tick")
async def handle_tick(payload: TickPayload):
    """
    Returns:  { session_id, tick_id, actions: [...], composed_at }
    actions[] contains one action object with action="send"
    """
    merchant_ctx = store.get("merchant", payload.merchant_id)
    trigger_ctx  = store.get("trigger",  payload.trigger_id)  if payload.trigger_id  else None
    customer_ctx = store.get("customer", payload.customer_id) if payload.customer_id else None

    if not merchant_ctx:
        raise HTTPException(422, f"No merchant context for {payload.merchant_id}")

    result     = compose(merchant_ctx, trigger_ctx, customer_ctx)
    action     = make_send_action(result)
    session_id = f"sess_{payload.tick_id}_{uuid.uuid4().hex[:8]}"

    store.save_session(session_id, {
        "merchant_id": payload.merchant_id,
        "customer_id": payload.customer_id,
        "trigger_id":  payload.trigger_id,
        "history": [{"role": "assistant", "content": result.get("body", "")}],
        "auto_reply_count": 0,
    })

    logger.info(f"[tick] merchant={payload.merchant_id} session={session_id}")
    return {
        "session_id":  session_id,
        "tick_id":     payload.tick_id,
        "actions":     [action],          # ← judge expects actions[]
        "composed_at": now_iso(),
    }

# ── POST /v1/reply ────────────────────────────────────────────────────────────

@app.post("/v1/reply")
async def handle_reply(payload: ReplyPayload):
    """
    Returns: { session_id, action, body, cta, send_as, suppression_key, rationale, replied_at }
    action = "send" | "end" | "noop"
    """
    msg          = payload.message or ""
    session      = store.get_session(payload.session_id) or {}
    merchant_ctx = store.get("merchant", payload.merchant_id)
    customer_ctx = store.get("customer", payload.customer_id) if payload.customer_id else None

    if not merchant_ctx:
        raise HTTPException(422, f"No merchant context for {payload.merchant_id}")

    # ── STOP / hostile intent → end immediately ──────────────────────────────
    if is_stop(msg):
        logger.info(f"[reply] STOP detected session={payload.session_id}")
        action = make_end_action("User sent STOP or hostile intent — conversation ended")
        store.save_session(payload.session_id, {**session, "ended": True})
        return {**action, "session_id": payload.session_id, "replied_at": now_iso()}

    # ── Auto-reply loop prevention ────────────────────────────────────────────
    if is_auto_reply(msg):
        count = session.get("auto_reply_count", 0) + 1
        session["auto_reply_count"] = count
        store.save_session(payload.session_id, session)
        logger.info(f"[reply] auto-reply #{count} session={payload.session_id}")
        action = make_noop_action(f"Auto-reply detected (#{count}) — suppressing response")
        return {**action, "session_id": payload.session_id, "replied_at": now_iso()}

    # Reset auto-reply counter on real human message
    session["auto_reply_count"] = 0

    # ── Normal reply — compose follow-up ─────────────────────────────────────
    history = session.get("history", [])
    history.append({"role": "user", "content": msg})
    result  = compose(merchant_ctx, None, customer_ctx, reply_history=history)
    history.append({"role": "assistant", "content": result.get("body", "")})
    store.save_session(payload.session_id, {**session, "history": history})

    action = make_send_action(result)
    logger.info(f"[reply] session={payload.session_id} action=send")
    return {**action, "session_id": payload.session_id, "replied_at": now_iso()}

@app.get("/")
async def root():
    return {"bot": "Vera v2", "status": "running", "docs": "/docs"}
