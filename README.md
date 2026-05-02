# Vera Bot — magicpin AI Challenge

A deterministic message engine for Vera, magicpin's merchant growth AI.

## Architecture

```
POST /v1/context   →  ContextStore (versioned, idempotent)
POST /v1/tick      →  compose() → Gemini Pro → structured JSON response
POST /v1/reply     →  compose() with conversation history → follow-up
GET  /v1/healthz   →  health check
GET  /v1/metadata  →  bot capabilities
```

## Core Design: compose()

```python
compose(merchant, trigger, customer?) → {
    message, cta, send_as, suppression_key, rationale
}
```

**Signal priority:**
1. **Trigger type** (spike / dip / recall / festival / research) → pick the moment
2. **Merchant state** (views, orders, rating, offers) → ground every number
3. **Category profile** (tone, voice, offer patterns) → match the vertical
4. **Customer context** (if present) → personalize the outreach

**Fallback:** If LLM is unavailable, a rule-based engine covers all 5 trigger types.

## Model Choice

- **Primary**: Gemini 1.5 Flash (fast, free tier available, strong instruction following)
- **Fallback**: Rule-based engine (zero-latency, no API dependency)
- **Alternative**: GPT-4o-mini (set `LLM_PROVIDER=openai`)

## Setup

```bash
git clone <your-repo>
cd vera-bot
pip install -r requirements.txt
cp .env.example .env
# Edit .env: add GEMINI_API_KEY
uvicorn main:app --reload
```

## Deploy to Railway (free, public URL)

1. Push code to GitHub
2. Go to railway.app → New Project → Deploy from GitHub
3. Add environment variable: `GEMINI_API_KEY=your_key`
4. Railway auto-assigns a public URL like `https://vera-bot-production.up.railway.app`
5. Submit that URL to magicpin

## Tradeoffs

| Choice | Reason |
|---|---|
| Gemini 1.5 Flash | Free tier, low latency, good JSON compliance |
| Pydantic v2 | Strict schema validation catches bad judge inputs early |
| Rule-based fallback | Zero-latency, always-available safety net |
| In-memory store | Sufficient for 3-day eval window; swap Redis for persistence |
| Versioned context upsert | Atomic replace prevents stale context bugs |

## Testing locally

```bash
# Health check
curl http://localhost:8000/v1/healthz

# Push merchant context
curl -X POST http://localhost:8000/v1/context \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "merchant",
    "context_id": "m_001_drmeera",
    "version": 1,
    "payload": {
      "identity": {"id":"m_001_drmeera","name":"Dr Meera Dental","category":"dentist"},
      "performance": {"profile_views_today":190,"orders_today":3,"rating":4.7},
      "offers": [{"name":"Dental Check-up","price":"₹299"}]
    },
    "delivered_at": "2026-05-02T10:00:00Z"
  }'

# Fire a tick
curl -X POST http://localhost:8000/v1/tick \
  -H "Content-Type: application/json" \
  -d '{
    "tick_id": "tick_001",
    "merchant_id": "m_001_drmeera",
    "trigger_id": null,
    "customer_id": null,
    "delivered_at": "2026-05-02T10:01:00Z"
  }'
```
