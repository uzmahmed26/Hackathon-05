# Customer Success FTE Specification

**Version**: 2.0
**Status**: Production Ready
**Created**: 2026-02-14
**Stage**: Crystallized from Incubation

---

## Purpose
Handle routine customer support queries with speed and consistency across multiple channels, operating 24/7 without human intervention for 80%+ of cases.

---

## Supported Channels

| Channel | Identifier | Response Style | Max Length | Webhook |
|---------|------------|----------------|------------|---------|
| Email (Gmail) | Email address | Formal, detailed | 500 words | Gmail Pub/Sub |
| WhatsApp | Phone number | Conversational, concise | 300 characters | Twilio webhook |
| Web Form | Email address | Semi-formal | 300 words | FastAPI POST |

---

## Scope

### In Scope
- Product feature questions
- How-to guidance and troubleshooting
- Bug report intake and triage
- Feedback collection
- Cross-channel conversation continuity
- Ticket creation and tracking

### Out of Scope (Escalate Immediately)
- Pricing negotiations or price inquiries
- Refund requests
- Legal/compliance questions
- Angry customers (sentiment < 0.3 sustained)
- Feature commitments not in docs

---

## Architecture

```
[Gmail] ──→ Pub/Sub → /webhooks/gmail ──→
[WhatsApp] → Twilio → /webhooks/whatsapp ─→  Kafka Queue → Message Processor → OpenAI Agent
[Web Form] ──────────→ /support/submit ──→
                                                              ↓
                                                    PostgreSQL (CRM)
```

---

## Tools

| Tool | Purpose | Constraints |
|------|---------|-------------|
| `search_knowledge_base` | Find relevant docs via semantic search | Max 5 results, 2 attempts max |
| `create_ticket` | Log all interactions with channel tag | Required for ALL conversations |
| `get_customer_history` | Cross-channel customer context | Last 20 messages |
| `escalate_to_human` | Hand off complex/sensitive issues | Include full context + reason |
| `send_response` | Reply via correct channel | Last step in every conversation |

---

## Agent Workflow (Required Order)
1. `create_ticket(channel=...)` — ALWAYS FIRST
2. `get_customer_history(customer_id=...)` — ALWAYS SECOND
3. `search_knowledge_base(query=...)` — For product questions (max 2 calls)
4. `escalate_to_human(...)` — If needed (skip step 5)
5. `send_response(channel=...)` — ALWAYS LAST (unless escalated)

---

## Performance Requirements

| Metric | Target |
|--------|--------|
| Response time | < 3 seconds (processing), < 30s (delivery) |
| Accuracy | > 85% on test set |
| Escalation rate | < 20% of conversations |
| Cross-channel ID accuracy | > 95% |
| Uptime | > 99.9% |
| P95 latency | < 3 seconds |

---

## Guardrails

- NEVER discuss competitor products
- NEVER promise features not in docs
- ALWAYS create ticket before responding
- ALWAYS check sentiment before closing
- ALWAYS use channel-appropriate tone
- NEVER share internal processes

---

## Escalation Rules (Finalized)

### Immediate Escalation (No Response Needed)
| Trigger | Reason Code |
|---------|-------------|
| Mentions "pricing", "price", "cost", "quote" | `pricing_inquiry` |
| Mentions "refund", "chargeback", "dispute" | `refund_request` |
| Mentions "lawyer", "legal", "sue", "attorney" | `legal_issue` |
| Mentions "cancel" + "subscription" | `cancellation_request` |

### Conditional Escalation (After Attempt)
| Trigger | Condition | Reason Code |
|---------|-----------|-------------|
| Negative sentiment | Score < -0.3 sustained for 2+ exchanges | `negative_sentiment` |
| No KB match | After 2 search attempts | `knowledge_gap` |
| Human request | Any explicit request for human | `customer_requested` |
| WhatsApp keywords | "human", "agent", "representative" | `customer_requested` |

---

## Channel Response Templates

### Email Template
```
Dear [Customer Name/Customer],

[Response content - formal, 200-500 words]

If you have any further questions, please don't hesitate to reply to this email.

Best regards,
TechCorp AI Support Team
---
Ticket Reference: [ticket_id]
```

### WhatsApp Template
```
[Concise response <300 chars]

Reply for more help or type 'human' for live support.
```

### Web Form Template
```
[Semi-formal response, 150-300 words]

---
Need more help? Reply to this message or visit our support portal.
```

---

## Database Schema (CRM)

Tables: `customers`, `customer_identifiers`, `conversations`, `messages`, `tickets`, `knowledge_base`, `channel_configs`, `agent_metrics`

Key relationships:
- One customer → many conversations (cross-channel)
- One conversation → many messages (with channel tag per message)
- One conversation → one ticket

---

## Kafka Topics

| Topic | Purpose |
|-------|---------|
| `fte.tickets.incoming` | Unified incoming from all channels |
| `fte.channels.email.inbound` | Gmail-specific |
| `fte.channels.whatsapp.inbound` | WhatsApp-specific |
| `fte.channels.webform.inbound` | Web form-specific |
| `fte.escalations` | Human agent escalations |
| `fte.metrics` | Agent performance metrics |
| `fte.dlq` | Dead letter queue for failures |

---

## Kubernetes Deployment

| Component | Replicas | Resources |
|-----------|----------|-----------|
| FastAPI API | 3 (min) – 20 (max) | 512Mi/250m → 1Gi/500m |
| Message Processor | 3 (min) – 30 (max) | 512Mi/250m → 1Gi/500m |
| PostgreSQL | 1 (StatefulSet) | 2Gi/500m |
| Redis | 1 | 256Mi/100m |

---

## Test Coverage Required

- Unit tests per tool function
- Integration tests per channel
- E2E tests for full conversation flows
- Load test: 100 concurrent users, 24 hours
- Chaos test: Pod kills every 2 hours
