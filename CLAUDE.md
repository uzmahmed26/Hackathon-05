# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Customer Success FTE is a multi-channel AI customer support agent built with Python/FastAPI. It handles queries from Email (Gmail), WhatsApp, and Web Form channels, using AI to generate responses, analyze sentiment, and decide on escalations.

## Development Commands

### Local (without Docker)
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with actual credentials

# Run tests
python -m pytest tests/
python -m pytest tests/test_prototype.py        # unit tests (prototype)
python -m pytest tests/test_agent.py            # unit tests (agent)
python -m pytest tests/test_integration.py      # integration tests
python -m pytest tests/test_e2e.py              # end-to-end tests
python -m pytest tests/ -v --cov=agent          # with coverage
```

### Docker (primary workflow)
```bash
make build          # build images
make up             # start all services
make up-dev         # start with pgAdmin + Redis Commander
make down           # stop services
make logs           # tail all logs
make logs-api       # tail API logs only
make logs-worker    # tail worker logs only
make test           # run pytest inside api container with coverage
make test-unit      # run test_prototype.py + test_agent.py
make test-integration
make test-e2e
make db-shell       # psql into postgres container
make redis-shell    # redis-cli into redis container
make clean          # remove containers and volumes
make scale-workers  # scale worker to 5 replicas
```

### Load Testing
```bash
locust -f tests/load_test.py --host=http://localhost:8000   # web UI on :8089
locust -f tests/load_test.py QuickSmokeTest --headless -u 10 -r 2 -t 1m --host=http://localhost:8000
```

## Architecture

### Evolution Phases
The codebase reflects two development phases:
1. **Incubation (Stage 1)**: `agent/agent_prototype.py` + `mcp_server.py` — prototype using skills pattern + MCP tools
2. **Specialization (Stage 2)**: `agent/customer_success_agent.py` + `kafka_client.py` — production agent using OpenAI Agents SDK `@function_tool` decorators and Kafka instead of Redis

### Core Data Flow
```
Incoming message (Gmail/WhatsApp/WebForm)
  → Webhook handler (channels/)
  → Redis queue (infrastructure/redis_queue.py)  [Stage 1]
    OR Kafka topic (kafka_client.py)              [Stage 2]
  → Worker (workers/message_processor.py)
  → Agent processes with skills/tools
  → Response delivered via channel handler
  → Logged to PostgreSQL
```

### Key Components

**Agent Layer** (`agent/`)
- `agent_prototype.py` — `CustomerSuccessAgent` class; pipeline: identify customer → retrieve knowledge → analyze sentiment → decide escalation → adapt for channel → generate response
- `customer_success_agent.py` — production version using OpenAI Agents SDK `Agent` + `Runner`
- `production_agent.py` — intermediate version with `@tool` decorator pattern
- `skills/` — modular skills (knowledge_retrieval, sentiment_analysis, escalation_decision, channel_adaptation, customer_identification); each has a `.py` + `.yaml` config file
- `tools.py` — tool implementations shared between agent versions
- `prompts.py` — system prompt for the production agent
- `hf_client.py` — Hugging Face/Qwen API client (used in prototype)

**API Layer** (`api/main.py`)
- FastAPI app with lifespan managing DB pool (asyncpg) and Redis producer
- Mounts routers from `channels/` for `/gmail`, `/whatsapp`, `/webform`
- Exposes health check and metrics endpoints

**Channel Layer** (`channels/`)
- `gmail_webhook.py` / `gmail_handler.py` — Gmail push notification + send
- `whatsapp_webhook.py` / `whatsapp_handler.py` — Twilio webhook + send
- `web_form_handler.py` — direct web form submissions

**Worker Layer** (`workers/message_processor.py`)
- `UnifiedMessageProcessor` consumes from Redis queue, routes to agent, delivers response through correct channel handler

**Data Layer**
- PostgreSQL with `pgvector` extension for semantic/vector search (port 5433 locally)
- Redis for message queuing and caching (port 6379)
- `database/schema.sql` — bootstrapped on container init
- `database/queries.py` — `DatabaseManager` class with all DB operations

**Infrastructure**
- `infrastructure/redis_queue.py` — `RedisProducer` / `RedisConsumer` wrappers
- `kafka_client.py` — `KafkaProducer` / `KafkaConsumer` for Stage 2 (topics defined in `TOPICS` dict)
- `k8s/` — Kubernetes manifests (deployment, HPA, ingress, secrets, configmap)

**MCP Server** (`mcp_server.py`)
- Exposes agent capabilities as MCP tools (incubation-phase exploration tool, not production path)

### Environment Variables
Copy `.env.example` to `.env`. Key variables:
- `HF_TOKEN` — Hugging Face token (prototype/MCP server)
- `OPENAI_API_KEY` — OpenAI key (production agent)
- `TWILIO_*` — WhatsApp via Twilio
- `GMAIL_*` — Gmail OAuth credentials (credentials JSON at `GMAIL_CREDENTIALS_PATH`)
- `KAFKA_BOOTSTRAP_SERVERS` — defaults to `kafka:9092`
- PostgreSQL and Redis credentials match docker-compose defaults

### Testing Notes
- `pytest.ini` sets `asyncio_mode = auto` — all async tests run automatically
- `tests/conftest.py` contains shared fixtures
- Tests can run locally without Docker for unit/prototype tests; integration/e2e tests need running services
- `validate_tests.py` at root is a standalone test validation script
