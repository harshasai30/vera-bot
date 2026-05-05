# Vera Bot v2 — magicpin AI Challenge

Fixed schema, all 6 trigger types, STOP handling, auto-reply detection.

## What changed in v2
- `/v1/tick` now returns `actions[]` array (judge requirement)
- `/v1/reply` returns `action` field: "send" | "end" | "noop"
- STOP/hostile messages → `action="end"` immediately
- Auto-reply detection → `action="noop"` with loop counter
- All 6 trigger types handled: spike, dip, recall, festival, research, regulation_change

## Response schemas

### /v1/tick response
```json
{
  "session_id": "sess_...",
  "tick_id": "tick_001",
  "actions": [
    {
      "action": "send",
      "body": "190 people nearby searched Dental Check-up...",
      "cta": "Should I send them your ₹299 offer?",
      "send_as": "vera",
      "suppression_key": "m_001:spike:2026-05",
      "rationale": "Spike trigger with 190 searches, matching active offer"
    }
  ]
}
```

### /v1/reply response
```json
{
  "session_id": "sess_...",
  "action": "send",
  "body": "Great! I'll send the offer to 190 nearby patients now.",
  "cta": "Confirm?",
  "send_as": "vera",
  "suppression_key": "m_001:spike:2026-05",
  "rationale": "Merchant confirmed — executing campaign"
}
```

### STOP → end
```json
{ "action": "end", "body": "", "rationale": "User sent STOP" }
```

## Setup
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key
uvicorn main:app --reload
```
