"""
Core compose() — calls Gemini, returns structured action dict.
All 6 trigger types, STOP detection, auto-reply loop prevention.
"""
import os, json, re, logging
from typing import Optional, Dict, Any, List
from prompts import get_profile, SYSTEM_PROMPT, COMPOSE_USER, TRIGGER_TYPES

logger = logging.getLogger("vera.compose")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_PROVIDER   = os.getenv("LLM_PROVIDER", "gemini")

# ── STOP / hostile intent detection ─────────────────────────────────────────

STOP_WORDS = {
    "stop", "no", "nope", "unsubscribe", "cancel", "quit", "exit",
    "remove", "opt out", "opt-out", "do not contact", "don't contact",
    "not interested", "leave me alone", "go away", "block"
}

AUTO_REPLY_MARKERS = [
    "out of office", "on vacation", "automatic reply", "auto-reply",
    "autoreply", "i am away", "i'm away", "currently unavailable",
    "will be back", "on leave"
]

def is_stop(text: str) -> bool:
    t = text.lower().strip().strip(".,!?")
    return t in STOP_WORDS or any(sw in t for sw in STOP_WORDS)

def is_auto_reply(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in AUTO_REPLY_MARKERS)


# ── LLM callers ──────────────────────────────────────────────────────────────

def _gemini(system: str, user: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system)
    return model.generate_content(user).text.strip()

def _openai(system: str, user: str) -> str:
    from openai import OpenAI
    r = OpenAI(api_key=OPENAI_API_KEY).chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.3, max_tokens=500
    )
    return r.choices[0].message.content.strip()

def _call(system, user):
    if LLM_PROVIDER == "openai": return _openai(system, user)
    return _gemini(system, user)

def _extract_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ── Rule-based fallback ──────────────────────────────────────────────────────

def _fallback(merchant, trigger, customer) -> dict:
    identity     = merchant.get("identity", {})
    name         = identity.get("name", "your business")
    mid          = identity.get("id", "m_unknown")
    category     = identity.get("category", "restaurant")
    profile      = get_profile(category)
    perf         = merchant.get("performance", {})
    views        = perf.get("profile_views_today", 0)
    orders       = perf.get("orders_today", 0)
    offers       = merchant.get("offers", [])
    offer        = offers[0] if offers else {}
    offer_name   = offer.get("name", "special offer")
    offer_price  = offer.get("price", "")
    ttype        = (trigger or {}).get("type", "recall")
    count        = (trigger or {}).get("search_count", 0)
    intent       = (trigger or {}).get("search_intent", "your services")
    price_str    = f" at {offer_price}" if offer_price else ""

    messages = {
        "spike":             f"{count} people nearby just searched '{intent}'. Send them your {offer_name}{price_str}?",
        "dip":               f"Orders are slow today ({orders} so far). Flash {offer_name}{price_str} to boost evening walk-ins?",
        "recall":            f"{views} people viewed your profile but didn't book. Re-engage them with {offer_name}{price_str}?",
        "festival":          f"Festive season is here — push a special {offer_name}{price_str} to nearby customers today?",
        "research":          f"High-intent customers are browsing your category right now. Promote {offer_name}{price_str} to convert them?",
        "regulation_change": f"New regulations may affect your business. Send customers a reassurance update from {name}?",
    }

    body = messages.get(ttype, messages["recall"])
    from datetime import date
    return {
        "body": body[:280],
        "cta": profile.get("example_cta", "Reply YES to send now."),
        "send_as": "vera",
        "suppression_key": f"{mid}:{ttype}:{date.today().strftime('%Y-%m')}",
        "rationale": f"Trigger={ttype}, views={views}, orders={orders}, offer={offer_name}"
    }


# ── Main compose() ────────────────────────────────────────────────────────────

def compose(
    merchant: Dict[str, Any],
    trigger: Optional[Dict] = None,
    customer: Optional[Dict] = None,
    reply_history: Optional[List[Dict]] = None,
) -> dict:
    """Returns a validated action dict with body, cta, send_as, suppression_key, rationale."""

    identity = merchant.get("identity", {})
    category = identity.get("category", "restaurant")
    profile  = get_profile(category)

    # Ensure trigger type is one of the 6 known types
    if trigger:
        ttype = trigger.get("type", "recall")
        if ttype not in TRIGGER_TYPES:
            trigger = {**trigger, "type": "recall"}

    def _j(o): return json.dumps(o, indent=2) if o else "null"

    user = COMPOSE_USER.format(
        merchant_json=_j(merchant),
        trigger_json=_j(trigger),
        customer_json=_j(customer),
        history_json=_j(reply_history),
    )

    api_key = GEMINI_API_KEY if LLM_PROVIDER == "gemini" else OPENAI_API_KEY
    if not api_key:
        logger.warning("No API key — using rule-based fallback")
        return _fallback(merchant, trigger, customer)

    try:
        raw    = _call(SYSTEM_PROMPT, user)
        result = _extract_json(raw)
        for f in ["body", "cta", "send_as", "suppression_key", "rationale"]:
            if f not in result:
                raise ValueError(f"Missing: {f}")
        return result
    except Exception as e:
        logger.error(f"LLM failed: {e} — using fallback")
        return _fallback(merchant, trigger, customer)
