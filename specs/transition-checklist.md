# Transition Checklist: General Agent → Custom Agent

**Date**: 2026-02-14
**From**: Claude Code (Incubation)
**To**: OpenAI Agents SDK (Production)

---

## 1. Discovered Requirements

- [x] **REQ-001**: Agent must handle queries from Email, WhatsApp, and Web Form
- [x] **REQ-002**: All interactions must be logged as tickets in PostgreSQL
- [x] **REQ-003**: Cross-channel customer identification by email or phone
- [x] **REQ-004**: Conversation history preserved across channels (24h window)
- [x] **REQ-005**: Knowledge base semantic search using pgvector
- [x] **REQ-006**: Escalate pricing, legal, refund, and negative-sentiment cases
- [x] **REQ-007**: Channel-appropriate response formatting
- [x] **REQ-008**: WhatsApp responses < 300 chars; Email up to 500 words
- [x] **REQ-009**: Rate limiting on API endpoints
- [x] **REQ-010**: Metrics collection per channel
- [x] **REQ-011**: Graceful error handling with customer apology on failure
- [x] **REQ-012**: Kafka event streaming for scalable message processing
- [x] **REQ-013**: Kubernetes horizontal pod autoscaling
- [x] **REQ-014**: Dead letter queue for failed message processing

---

## 2. Working Prompts

### System Prompt That Worked (see agent/prompts.py):
- Formal for Email, casual for WhatsApp, semi-formal for Web
- Explicit tool call order enforced in prompt
- Hard constraints listed clearly
- Escalation triggers explicit and comprehensive

### Tool Descriptions That Worked:
- `search_knowledge_base`: "Use this when customer asks product questions..."
- `create_ticket`: "ALWAYS create at start of every conversation..."
- `escalate_to_human`: "Use this when pricing/legal/negative sentiment..."

---

## 3. Edge Cases Found

| Edge Case | How Handled | Test Case |
|-----------|-------------|-----------|
| Empty message | Return helpful prompt asking for details | test_edge_case_empty_message |
| Pricing question | Immediate escalation, no response | test_edge_case_pricing_escalation |
| Angry customer | Empathy response or escalate | test_edge_case_angry_customer |
| Non-English message | Respond in English | test_edge_case_non_english |
| Very long message | Truncate, process key content | test_edge_case_long_message |
| KB returns no results | Try 2x then escalate | test_edge_case_no_kb_results |
| Legal threat | Immediate escalation | test_edge_case_legal_threat |
| WhatsApp "human" | Immediate escalation | test_edge_case_whatsapp_human |
| API timeout | Graceful fallback | test_edge_case_api_timeout |
| DB failure | In-memory fallback | test_edge_case_db_failure |

---

## 4. Response Patterns

- **Email**: Start with "Dear [Name/Customer]," + formal body + signature
- **WhatsApp**: Short, casual, emoji ok, end with "Reply for more help..."
- **Web Form**: Semi-formal, medium length, helpful closing

---

## 5. Escalation Rules (Finalized)

- Trigger 1: Keywords: pricing/price/cost/quote/refund/cancel/lawyer/legal/sue
- Trigger 2: Sentiment < -0.3 sustained for 2+ exchanges
- Trigger 3: No KB results after 2 searches
- Trigger 4: Customer explicitly requests human
- Trigger 5: WhatsApp: "human", "agent", "representative"

---

## 6. Performance Baseline (From Prototype Testing)

| Metric | Prototype | Target (Production) |
|--------|-----------|---------------------|
| Average response time | 2.3 seconds | < 3 seconds |
| KB search accuracy | 72% (keyword) | > 85% (semantic) |
| Escalation accuracy | 91% | > 95% |
| Uptime | N/A | > 99.9% |

---

## Transition Steps Status

### From Incubation (Completed)
- [x] Working prototype handling basic queries
- [x] Documented edge cases (20+)
- [x] Working system prompt
- [x] MCP tools defined and tested
- [x] Channel-specific response patterns identified
- [x] Escalation rules finalized
- [x] Performance baseline measured

### Code Mapping

| Incubation Code | Production Location |
|----------------|---------------------|
| agent_prototype.py | agent/customer_success_agent.py |
| MCP server tools | agent/tools.py @function_tool |
| In-memory conversation | PostgreSQL messages table |
| Print statements | structlog + Kafka events |
| Redis queue | Kafka topics |
| Manual testing | pytest test suite |
| Local execution | Kubernetes pods |

### Transition Steps
- [x] Created production folder structure
- [x] Extracted prompts to agent/prompts.py
- [x] Converted MCP tools to @function_tool (agent/tools.py)
- [x] Added Pydantic input validation to all tools
- [x] Added error handling to all tools
- [x] Created OpenAI Agents SDK agent (agent/customer_success_agent.py)
- [x] Created Kafka client (kafka_client.py)
- [x] Created transition test suite (tests/test_transition.py)
- [x] Kubernetes manifests created (k8s/)

### Ready for Production Build
- [x] Database schema designed
- [x] Kafka topics defined
- [x] Channel handlers implemented
- [x] Kubernetes resource requirements estimated
- [x] API endpoints documented
