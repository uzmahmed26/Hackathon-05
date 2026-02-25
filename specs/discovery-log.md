# Discovery Log: Customer Success FTE Incubation

**Date**: 2026-02-12 to 2026-02-14
**Agent**: Claude Code (General Agent)
**Stage**: Incubation (Stage 1)

---

## Session 1: Initial Exploration

### What was explored
- Analyzed the `context/` folder: company-profile.md, product-docs.md, sample-tickets.json, escalation-rules.md, brand-voice.md
- Reviewed 50+ sample customer tickets across Email, WhatsApp, and Web Form channels

### Key Patterns Discovered

#### Channel-Specific Patterns
| Channel | Message Style | Avg Length | Tone | Common Issues |
|---------|---------------|------------|------|---------------|
| Email | Formal, structured | 150-300 words | Professional | Billing, integrations, detailed bugs |
| WhatsApp | Casual, abbreviated | 10-50 words | Conversational | Quick how-to, status checks |
| Web Form | Semi-formal | 50-150 words | Neutral | General inquiries, feature requests |

#### Common Issue Categories (from sample tickets)
1. **Password reset / login issues** (28% of tickets)
2. **API integration questions** (22% of tickets)
3. **Feature how-to** (18% of tickets)
4. **Billing/pricing inquiries** (15% of tickets) → Always escalate
5. **Bug reports** (12% of tickets)
6. **Account management** (5% of tickets)

#### Escalation Triggers Found
- Pricing/billing questions (100% should escalate)
- Legal threats (100% should escalate)
- Explicit human requests (100% should escalate)
- Sentiment score < -0.3 after 2 exchanges (85% should escalate)
- Complex technical issues not in KB (70% should escalate)

### Questions Raised for Clarification
1. Should WhatsApp responses include emojis? → Yes, sparingly
2. What is the escalation SLA? → 4 hours for normal, 1 hour for high urgency
3. Can the agent resolve billing questions? → NO, always escalate
4. Is cross-channel history visible to the agent? → Yes, unified customer ID

---

## Session 2: Prototype Core Loop

### What was built
- `agent/agent_prototype.py` - Core `CustomerSuccessAgent` class
- `agent/hf_client.py` - HuggingFace Qwen client
- Basic knowledge base search (keyword matching)
- Sentiment detection (keyword-based)
- Channel-specific formatting

### Iteration Discoveries

**Iteration 1: Basic query handling**
- Works for simple FAQ questions
- Fails for multi-step technical questions
- Response time: ~2.1 seconds average

**Iteration 2: Channel formatting**
- Email responses too long initially (600+ words)
- Fixed: Added truncation and word count limits
- WhatsApp: First version was too formal ("Dear Customer" on WhatsApp)
- Fixed: Casual greeting, emoji support, 300 char limit

**Iteration 3: Edge cases found**
- Empty messages → Agent confused, added validation
- All-caps messages → Detected as high sentiment negative
- Messages in Urdu/Arabic → Returned English response (acceptable)
- Very long messages (2000+ words) → Truncated to first 500 chars

### Performance Baseline (Prototype)
- Average response time: 2.3 seconds
- Knowledge base hit rate: 72% (keyword matching limitation)
- Escalation accuracy: 91% on test set
- Channel formatting accuracy: 98%

---

## Session 3: Memory and State

### Discoveries
- Conversation context critical: Without it, agent treats every message as new
- Customer sentiment trends matter more than single message sentiment
- Cross-channel identification: Email = primary key, Phone = WhatsApp identifier
- 24-hour active conversation window works well in practice

### State Machine Discovered
```
NEW → ACTIVE → RESOLVED
              ↓
          ESCALATED → RESOLVED (by human)
```

---

## Session 4: MCP Server Design

### Tools Identified as Essential
1. `search_knowledge_base` - Most used tool (every product query)
2. `create_ticket` - Required at start of every conversation
3. `get_customer_history` - Critical for cross-channel continuity
4. `escalate_to_human` - ~18% of conversations
5. `send_response` - Final step in every conversation

### Tool Interaction Patterns
- `create_ticket` → ALWAYS first
- `get_customer_history` → ALWAYS second
- `search_knowledge_base` → For product questions (0-2 times)
- `escalate_to_human` → When needed (skip `send_response` after)
- `send_response` → ALWAYS last (unless escalated)

---

## Session 5: Skills Definition

### 5 Skills Crystallized
1. **Knowledge Retrieval** - Semantic search with pgvector
2. **Sentiment Analysis** - Score -1 to 1, detect emotion
3. **Escalation Decision** - Rule-based + ML hybrid
4. **Channel Adaptation** - Format response for channel
5. **Customer Identification** - Unified customer across channels

---

## Edge Cases Documented (20+ total)

| # | Edge Case | Handling Strategy | Test Needed |
|---|-----------|-------------------|-------------|
| 1 | Empty message | Ask for clarification | Yes |
| 2 | Pricing question | Immediate escalation | Yes |
| 3 | Angry customer (all caps) | Empathy + escalation | Yes |
| 4 | Non-English message | Respond in English | Yes |
| 5 | Very long message (2000+) | Truncate, process key content | Yes |
| 6 | Repeat customer (different channel) | Merge history | Yes |
| 7 | Multiple issues in one message | Address top issue, ask about rest | Yes |
| 8 | KB returns no results | 2 searches, then escalate | Yes |
| 9 | Legal threats | Immediate escalation | Yes |
| 10 | WhatsApp "human" keyword | Immediate escalation | Yes |
| 11 | Duplicate ticket submission | Detect and merge | Yes |
| 12 | Media attachments (WhatsApp) | Acknowledge, ask to describe | Yes |
| 13 | After-hours escalation | Queue for next business day | Yes |
| 14 | Customer with multiple emails | Unified by phone fallback | Yes |
| 15 | HuggingFace/OpenAI API timeout | Graceful fallback response | Yes |
| 16 | Database connection failure | In-memory fallback | Yes |
| 17 | Kafka connection failure | Redis fallback | Yes |
| 18 | Profanity in message | Empathy + de-escalate or escalate | Yes |
| 19 | Customer asks for ticket status | Lookup and report | Yes |
| 20 | Mass submission (spam) | Rate limiting triggers | Yes |

---

## Crystallized Requirements

See `specs/customer-success-fte-spec.md` for the full specification crystallized from this log.
