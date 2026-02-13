---
id: 1
title: Update Customer Success AI
stage: constitution
date: 2026-02-11
surface: agent
model: Qwen
feature: customer-success-ai
branch: main
user: user
command: /sp.constitution
labels: [constitution, customer-success, ai]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\.specify\\memory\\constitution.md
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\context\\company-profile.md
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\context\\product-docs.md
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\context\\sample-tickets.json
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\context\\escalation-rules.md
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\context\\brand-voice.md
tests:
 - null
---

## Prompt

```
$ARGUMENTS
```

TASK 1: Create Project Structure

Create this folder structure:
- /context (for company docs and sample data)
- /agent (for AI agent code)
- /agent/skills (for Speck Plus skill integrations)
- /channels (for Gmail, WhatsApp, Web Form handlers)
- /database (for PostgreSQL schema)
- /workers (for message processors)
- /api (for FastAPI backend)
- /web-form (for React support form)
- /tests (for test files)
- /specs (for documentation)

Then create these files in /context:

1. company-profile.md - Create a fake SaaS company called "TechCorp"
   - Product: Project Management Software
   - Target customers: Small to medium businesses
   - Key features: Task management, team collaboration, time tracking
   - Price range: $9-49/month per user

2. product-docs.md - Create 25 FAQ entries covering:
   - Getting started (5 questions)
   - Features (8 questions)
   - Pricing (3 questions)
   - Troubleshooting (6 questions)
   - Integrations (3 questions)

3. sample-tickets.json - Generate 50 realistic customer queries:
   - 20 email queries (formal, detailed)
   - 20 WhatsApp queries (casual, short)
   - 10 web form submissions (mixed tone)
   
   Include these categories:
   - Password reset requests (10)
   - Feature questions (15)
   - Bug reports (10)
   - Pricing inquiries (5)
   - Angry/frustrated customers (5)
   - General help (5)

4. escalation-rules.md - Define when to escalate:
   - Pricing/refund questions → Always escalate
   - Negative sentiment (< -0.3) → Escalate
   - Legal keywords (lawyer, sue) → Escalate
   - Customer requests human → Escalate
   - 3+ messages without resolution → Escalate

5. brand-voice.md - Communication guidelines:
   - Tone: Professional but friendly
   - Email: Formal with proper greetings
   - WhatsApp: Conversational, use "Hey" not "Dear"
   - Always empathize before solving
   - Never make promises we can't keep

Generate all these files with realistic, detailed content.

## Response snapshot

I've successfully created the project structure and all the requested context files for your Customer Success AI agent. Here's a summary of what was completed:

## Folder Structure Created:
- `/context` (for company docs and sample data)
- `/agent` (for AI agent code)
- `/agent/skills` (for Spec Plus skill integrations)
- `/channels` (for Gmail, WhatsApp, Web Form handlers)
- `/database` (for PostgreSQL schema)
- `/workers` (for message processors)
- `/api` (for FastAPI backend)
- `/web-form` (for React support form)
- `/tests` (for test files)
- `/specs` (for documentation)

## Files Created in /context:

1. **company-profile.md**: Detailed profile of TechCorp, a fake SaaS company with product details, target customers, and pricing structure.

2. **product-docs.md**: 25 FAQ entries covering:
   - Getting started (5 questions)
   - Features (8 questions)
   - Pricing (3 questions)
   - Troubleshooting (6 questions)
   - Integrations (3 questions)

3. **sample-tickets.json**: 50 realistic customer queries including:
   - 20 email queries (formal, detailed)
   - 20 WhatsApp queries (casual, short)
   - 10 web form submissions (mixed tone)
   
   Categories covered: Password reset requests (10), Feature questions (15), Bug reports (10), Pricing inquiries (5), Angry/frustrated customers (5), General help (5)

4. **escalation-rules.md**: Clear criteria for when to escalate issues, including pricing questions, negative sentiment, legal keywords, customer requests for humans, and unresolved queries.

5. **brand-voice.md**: Comprehensive communication guidelines covering tone, channel-specific instructions, empathy techniques, and handling difficult situations.

All files contain realistic, detailed content tailored to a Customer Success AI agent for TechCorp's project management software. The project is now ready for the next phase of development.

Additionally, I've updated the constitution file with specific principles and guidelines for the Customer Success AI agent project, replacing all the placeholder tokens with concrete content based on the project requirements.

## Outcome

- ✅ Impact: Project structure and context files created, constitution updated
- 🧪 Tests: No tests required for this task
- 📁 Files: 6 context files + 1 constitution file updated
- 🔁 Next prompts: Ready for specification and planning phases
- 🧠 Reflection: Successfully implemented the required project foundation

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Begin feature specification