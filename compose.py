"""
Core compose() function.
Calls Gemini Pro (or OpenAI as fallback) and returns structured output.
"""

import os, json, logging, re
from typing import Optional, Dict, Any, List
from prompts import get_category_profile, SYSTEM_PROMPT_TEMPLATE, COMPOSE_USER_TEMPLATE

logger = logging.getLogger("vera-bot.compose")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")   # "gemini" | "openai"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# ── LLM callers ──────────────────────────────────────────────────────────────

def _call_gemini(system: str, user: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system,
    )
    resp = model.generate_content(user)
    return resp.text.strip()


def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.3,
        max_tokens=500,
    )
    return resp.choices[0].message.content.strip()


def _call_llm(system: str, user: str) -> str:
    if LLM_PROVIDER == "openai":
        return _call_openai(system, user)
    return _call_gemini(system, user)


# ── JSON extractor ────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> Dict[str, Any]:
    """Pull JSON from LLM output even if wrapped in markdown fences."""
    raw = raw.strip()
    # strip ```json ... ```
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ── Fallback composer (no LLM) ────────────────────────────────────────────────

def _fallback_compose(merchant: Dict, trigger: Optional[Dict],
                      customer: Optional[Dict]) -> Dict[str, str]:
    """
    Rule-based fallback when LLM is unavailable.
    Uses trigger type + merchant offer + category to pick the best message.
    """
    identity  = merchant.get("identity", {})
    name      = identity.get("name", "your business")
    category  = identity.get("category", "restaurant")
    profile   = get_category_profile(category)

    perf      = merchant.get("performance", {})
    views     = perf.get("profile_views_today", 0)
    orders    = perf.get("orders_today", 0)
    rating    = perf.get("rating", 0)

    offers    = merchant.get("offers", [])
    best_offer = offers[0] if offers else {}
    offer_name  = best_offer.get("name", "special offer")
    offer_price = best_offer.get("price", "")

    trigger_type = (trigger or {}).get("type", "recall")
    trig_count   = (trigger or {}).get("search_count", 0)
    trig_intent  = (trigger or {}).get("search_intent", "general")

    cust_name = (customer or {}).get("name", "nearby customers")

    # Pick message by trigger type
    if trigger_type == "spike":
        msg = (f"{trig_count} people nearby searched '{trig_intent}' in the last hour. "
               f"Should I send them your {offer_name}"
               + (f" at {offer_price}" if offer_price else "") + "?")
    elif trigger_type == "dip":
        msg = (f"Your {category} orders are {orders} today vs your usual pace. "
               f"Flash {offer_name} to drive evening walk-ins?")
    elif trigger_type == "festival":
        msg = (f"Festive season spike — "
               f"send a {profile.get('seasonal',['special'])[0]} offer from {name}?")
    elif trigger_type == "research":
        msg = (f"High-intent searchers are browsing your category. "
               f"Promote {offer_name} now to convert them?")
    else:  # recall
        msg = (f"{name} had {views} profile views today but low conversions. "
               f"Want me to push {offer_name} to re-engage them?")

    merchant_id   = identity.get("id", "m_unknown")
    suppression_k = f"{merchant_id}:{trigger_type}:{__import__('datetime').date.today().strftime('%Y-%m')}"

    return {
        "message": msg[:300],
        "cta": profile.get("example_cta", "Reply YES to send now."),
        "send_as": "vera",
        "suppression_key": suppression_k,
        "rationale": f"Trigger={trigger_type}, views={views}, orders={orders}, offer={offer_name}"
    }


# ── Main compose() ────────────────────────────────────────────────────────────

def compose(
    merchant: Dict[str, Any],
    trigger: Optional[Dict[str, Any]] = None,
    customer: Optional[Dict[str, Any]] = None,
    reply_history: Optional[List[Dict]] = None,
) -> Dict[str, str]:
    """
    Deterministic compose function.
    Returns: {message, cta, send_as, suppression_key, rationale}
    """

    identity = merchant.get("identity", {})
    category = identity.get("category", "restaurant")
    profile  = get_category_profile(category)

    system = SYSTEM_PROMPT_TEMPLATE.format(
        tone=profile.get("tone", ""),
        voice=profile.get("voice", ""),
        offer_patterns=", ".join(profile.get("offer_patterns", [])),
        avoid=", ".join(profile.get("avoid", [])),
        example_cta=profile.get("example_cta", ""),
    )

    def _j(obj) -> str:
        return json.dumps(obj, indent=2) if obj else "null"

    user = COMPOSE_USER_TEMPLATE.format(
        merchant_json=_j(merchant),
        trigger_json=_j(trigger),
        customer_json=_j(customer),
        history_json=_j(reply_history),
    )

    # Try LLM; fall back to rule-based if API key missing or call fails
    api_key = GEMINI_API_KEY if LLM_PROVIDER == "gemini" else OPENAI_API_KEY
    if not api_key:
        logger.warning("No API key set — using rule-based fallback")
        return _fallback_compose(merchant, trigger, customer)

    try:
        raw    = _call_llm(system, user)
        result = _extract_json(raw)

        # Validate required fields
        required = ["message", "cta", "send_as", "suppression_key", "rationale"]
        for field in required:
            if field not in result:
                raise ValueError(f"Missing field: {field}")

        return result

    except Exception as e:
        logger.error(f"LLM compose failed: {e} — using fallback")
        return _fallback_compose(merchant, trigger, customer)
