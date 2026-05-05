"""Category profiles and prompt templates."""

CATEGORY_PROFILES = {
    "dentist": {
        "tone": "clinical, reassuring, trust-first",
        "offer_patterns": ["free consultation", "discounted check-up", "EMI on treatment"],
        "avoid": "aggressive discounts, scare tactics",
        "voice": "professional, empathetic",
        "example_cta": "Should I book a ₹299 check-up slot for nearby patients?",
    },
    "salon": {
        "tone": "aspirational, visual, trend-forward",
        "offer_patterns": ["combo deals", "seasonal hair packages", "bridal prep"],
        "avoid": "clinical language, generic discount framing",
        "voice": "friendly, style-savvy",
        "example_cta": "Want me to push a festive makeover package to 40 customers nearby?",
    },
    "restaurant": {
        "tone": "appetite-first, local, urgent",
        "offer_patterns": ["lunch combos", "happy hour", "free delivery", "loyalty rewards"],
        "avoid": "generic 50% off — use specific dish names",
        "voice": "warm, craveable",
        "example_cta": "Flash '2 Naan free with any curry' to 80 dinner-hour searchers?",
    },
    "gym": {
        "tone": "energetic, data-driven, motivational",
        "offer_patterns": ["trial passes", "quarterly membership", "transformation challenges"],
        "avoid": "shame-based messaging, vague wellness claims",
        "voice": "coach-like, direct",
        "example_cta": "Send '7-day free trial' to 25 people who searched gym near me today?",
    },
    "pharmacy": {
        "tone": "helpful, informational, reliable",
        "offer_patterns": ["health packages", "free BP/sugar check", "medicine delivery"],
        "avoid": "prescription drug promotions, unverified health claims",
        "voice": "knowledgeable, community-care",
        "example_cta": "Alert nearby diabetics about your free HbA1c camp this weekend?",
    },
}

TRIGGER_TYPES = ["spike", "dip", "recall", "festival", "research", "regulation_change"]

def get_profile(category: str) -> dict:
    cat = (category or "restaurant").lower().rstrip("s")
    for k, v in CATEGORY_PROFILES.items():
        if k in cat or cat in k:
            return v
    return CATEGORY_PROFILES["restaurant"]


SYSTEM_PROMPT = """
You are Vera, magicpin's AI assistant for merchant growth.
Compose ONE precise outreach message for a specific merchant.

SCORING (each 0-10):
1. Decision quality  — pick the BEST signal: trigger type + merchant state + category
2. Specificity       — use REAL numbers, offer names, dates from context (no invented data)
3. Category fit      — match the exact voice for this business type
4. Merchant fit      — personalize to THIS merchant's metrics and offers
5. Engagement        — ONE yes/no CTA, strong reason to reply NOW

TRIGGER TYPES you must handle:
- spike: high search volume nearby right now
- dip: orders or views dropped below normal
- recall: lapsed customers or low conversion
- festival: seasonal/festive opportunity
- research: high-intent browsing in category
- regulation_change: new regulation affecting the business

HARD RULES:
- ONE CTA per message, phrased as a yes/no question
- No fake numbers — only use data given in context
- Message body ≤ 280 chars
- suppression_key format: merchantId:triggerType:YYYY-MM

RESPOND ONLY IN THIS JSON — no markdown, no extra text:
{
  "body": "<the outreach message — specific, useful, easy to reply to>",
  "cta": "<one yes/no action>",
  "send_as": "<vera or merchant brand name>",
  "suppression_key": "<merchantId:triggerType:YYYY-MM>",
  "rationale": "<under 40 words: which signal drove this and why now>"
}
""".strip()

COMPOSE_USER = """
MERCHANT:
{merchant_json}

TRIGGER:
{trigger_json}

CUSTOMER (optional):
{customer_json}

CONVERSATION HISTORY (for reply mode):
{history_json}

Compose the best next message. Return ONLY the JSON object.
""".strip()
