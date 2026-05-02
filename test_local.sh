#!/bin/bash
# Quick local smoke test — run after: uvicorn main:app --reload

BASE="http://localhost:8000"
echo "=== Healthz ==="
curl -s $BASE/v1/healthz | python3 -m json.tool

echo -e "\n=== Push merchant context ==="
curl -s -X POST $BASE/v1/context \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "merchant",
    "context_id": "m_001_drmeera",
    "version": 1,
    "payload": {
      "identity": {
        "id": "m_001_drmeera",
        "name": "Dr Meera Dental Clinic",
        "category": "dentist",
        "locality": "Indiranagar, Bengaluru"
      },
      "performance": {
        "profile_views_today": 190,
        "orders_today": 3,
        "conversion_rate": 0.016,
        "rating": 4.7,
        "rating_count": 312
      },
      "offers": [
        {"name": "Dental Check-up", "price": "₹299", "validity": "May 2026"},
        {"name": "Teeth Whitening", "price": "₹1499", "validity": "May 2026"}
      ],
      "conversation_history": []
    },
    "delivered_at": "2026-05-02T10:00:00Z"
  }' | python3 -m json.tool

echo -e "\n=== Push trigger context ==="
curl -s -X POST $BASE/v1/context \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "trigger",
    "context_id": "t_001",
    "version": 1,
    "payload": {
      "type": "spike",
      "search_intent": "Dental Check Up",
      "search_count": 190,
      "locality": "Indiranagar, Bengaluru",
      "time_window": "last 2 hours"
    },
    "delivered_at": "2026-05-02T10:00:00Z"
  }' | python3 -m json.tool

echo -e "\n=== Tick (compose message) ==="
curl -s -X POST $BASE/v1/tick \
  -H "Content-Type: application/json" \
  -d '{
    "tick_id": "tick_001",
    "merchant_id": "m_001_drmeera",
    "trigger_id": "t_001",
    "customer_id": null,
    "delivered_at": "2026-05-02T10:01:00Z"
  }' | python3 -m json.tool
