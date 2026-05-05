"""
Clean Compose Engine (v3)
- No dependency on old "identity/performance" format
- Works with flat merchant JSON
- Category-aware + trigger-aware
"""

from typing import Dict, Any, Optional, List
import datetime

# ───────── STOP / AUTO REPLY ─────────

STOP_WORDS = [
    "stop", "unsubscribe", "cancel", "quit", "no", "not interested"
]

AUTO_REPLY_MARKERS = [
    "out of office", "on vacation", "auto reply",
    "i am busy", "in a meeting", "call later"
]


def is_stop(message: str) -> bool:
    if not message:
        return False
    msg = message.lower()
    return any(word in msg for word in STOP_WORDS)


def is_auto_reply(message: str) -> bool:
    if not message:
        return False
    msg = message.lower()
    return any(word in msg for word in AUTO_REPLY_MARKERS)


# ───────── CATEGORY LOGIC ─────────

def get_category_config(category: str):
    category = (category or "").lower()

    if category == "dentist":
        return {
            "service": "dental checkups and cleanings",
            "offer": "₹199 first consultation"
        }
    elif category == "salon":
        return {
            "service": "haircuts and grooming",
            "offer": "20% off haircut"
        }
    elif category == "restaurant":
        return {
            "service": "dinner orders",
            "offer": "Buy 1 Get 1 free"
        }
    elif category == "gym":
        return {
            "service": "fitness memberships",
            "offer": "Free 3-day trial"
        }
    elif category == "pharmacy":
        return {
            "service": "medicine orders",
            "offer": "10% off essentials"
        }

    return {
        "service": "your services",
        "offer": "special discount"
    }


# ───────── MAIN COMPOSE FUNCTION ─────────

def compose(
    merchant: Dict[str, Any],
    trigger: Optional[Dict[str, Any]] = None,
    customer: Optional[Dict[str, Any]] = None,
    reply_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:

    merchant = merchant or {}

    name = merchant.get("name", "your business")
    category = merchant.get("category", "general")
    views = merchant.get("views", 0)
    orders = merchant.get("orders", 0)
    rating = merchant.get("rating", 0)

    trigger_type = None
    if trigger:
        trigger_type = trigger.get("type")

    config = get_category_config(category)
    service = config["service"]
    offer = config["offer"]

    # ───────── TRIGGER LOGIC ─────────

    if trigger_type == "spike":
        body = f"{views} people searched for {service} near you today. High demand — don't miss it."
        cta = f"Start '{offer}' campaign now?"

    elif trigger_type == "dip":
        body = f"Orders dropped to {orders} today. You may be losing customers."
        cta = f"Activate '{offer}' to recover demand?"

    elif trigger_type == "festival":
        body = f"Festival demand is rising for {service}. Great chance to attract new customers."
        cta = f"Launch festive offer '{offer}'?"

    elif trigger_type == "inactive":
        body = f"Your store activity is low recently. Customers may be forgetting your business."
        cta = f"Restart engagement with '{offer}'?"

    elif trigger_type == "recall":
        body = f"Customers who viewed your profile haven’t returned."
        cta = f"Bring them back with '{offer}'?"

    elif trigger_type == "research":
        body = f"Customers are comparing options for {service} nearby."
        cta = f"Stand out with '{offer}'?"

    else:
        body = f"{views} people are exploring {service} near you."
        cta = f"Promote '{offer}' now?"

    # ───────── OUTPUT ─────────

    return {
        "body": body,
        "cta": cta,
        "send_as": "vera",
        "suppression_key": f"{name}_{trigger_type}",
        "rationale": f"{category} + {trigger_type} optimization"
    }
