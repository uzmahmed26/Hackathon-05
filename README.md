# TechCorp Customer Success FTE

> **24/7 AI-Powered Customer Support Agent** — Hackathon 05 Project
> Multi-channel support across Web Form, Email (Gmail), and WhatsApp with intelligent AI routing, sentiment analysis, and automated escalation.

**Live Demo:** https://web-form-olive.vercel.app
**GitHub:** https://github.com/uzmahmed26/Hackathon-05

---

## Features

- **Multi-Channel Support** — Web Form, Gmail webhooks, WhatsApp (Twilio)
- **AI Agent** — GPT-4o powered with 81% auto-resolve rate
- **Smart Escalation** — Sentiment-based auto-routing to human agents
- **Live Analytics** — Real-time dashboards with ticket trends & resolution rates
- **JWT Authentication** — Secure login/signup with demo mode fallback
- **Full Web UI** — Dashboard, Tickets, Analytics, Settings, FAQ
- **Kafka Streaming** — High-throughput message processing
- **Kubernetes Ready** — HPA, ingress, secrets, configmaps included

---

## Web UI Pages

| Page | Description |
|------|-------------|
| **Support** | Submit tickets, track status, FAQ section |
| **Dashboard** | KPI cards, recent tickets, channel status, AI stats |
| **Tickets** | Searchable/filterable table, ticket detail modal |
| **Analytics** | Channel breakdown, ticket status charts, performance metrics |
| **Settings** | Account info, API URL config, notification preferences |

> **Demo Mode:** On the live Vercel deployment, use any email + password to sign in. All features work with demo data when the backend API is offline.

---

## Architecture

```
Incoming Message (Web Form / Gmail / WhatsApp)
  -> Webhook Handler (channels/)
  -> Redis Queue (infrastructure/redis_queue.py)
     OR Kafka Topic (kafka_client.py)
  -> Worker (workers/message_processor.py)
  -> AI Agent (agent/customer_success_agent.py)
       - Customer Identification
       - Sentiment Analysis
       - Knowledge Retrieval
       - Escalation Decision
       - Channel Adaptation
  -> Response delivered via channel handler
  -> Logged to PostgreSQL
```

### Key Components

| Layer | Files | Description |
|-------|-------|-------------|
| **Agent** | `agent/customer_success_agent.py` | OpenAI Agents SDK, GPT-4o |
| **API** | `api/main.py` | FastAPI, JWT auth, CORS |
| **Channels** | `channels/` | Gmail, WhatsApp, Web Form handlers |
| **Workers** | `workers/message_processor.py` | Redis/Kafka consumer |
| **Database** | `database/queries.py` | PostgreSQL + pgvector |
| **Web UI** | `web-form/index.html` | Single-file SPA (Tailwind CSS) |
| **Infra** | `k8s/` | Kubernetes manifests |

---

## Quick Start

### Option 1 — Docker (Recommended)

```bash
git clone https://github.com/uzmahmed26/Hackathon-05.git
cd Hackathon-05/customer-success-fte

cp .env.example .env
# Edit .env with your API keys

make build
make up
```

API runs at `http://localhost:8000`
Web UI: open `web-form/index.html` in browser

### Option 2 — Local (No Docker)

```bash
pip install -r requirements.txt
cp .env.example .env

# Run API
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Open web UI
start web-form/index.html
```

---

## Environment Variables

```env
# LLM
OPENAI_API_KEY=sk-...

# Database (PostgreSQL + pgvector)
DATABASE_URL=postgresql://user:pass@localhost:5432/fte_db

# Redis
REDIS_URL=redis://localhost:6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Gmail OAuth
GMAIL_CREDENTIALS_PATH=./credentials/gmail_credentials.json
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Auth
JWT_SECRET_KEY=your-secret-key

# Hugging Face (prototype)
HF_TOKEN=hf_...
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/signup` | Register new user |
| `POST` | `/api/auth/login` | Login, returns JWT |
| `POST` | `/api/support/submit` | Submit support ticket |
| `GET` | `/api/support/ticket/:id` | Get ticket status + messages |
| `POST` | `/webhooks/gmail` | Gmail push notification |
| `POST` | `/webhooks/whatsapp` | Twilio WhatsApp webhook |
| `GET` | `/metrics` | Ticket & performance metrics |
| `GET` | `/metrics/channels` | Per-channel breakdown |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |

---

## Docker Commands

```bash
make build          # Build all images
make up             # Start all services
make up-dev         # Start with pgAdmin + Redis Commander
make down           # Stop all services
make logs           # Tail all logs
make logs-api       # API logs only
make logs-worker    # Worker logs only
make test           # Run tests inside container
make scale-workers  # Scale workers to 5 replicas
make clean          # Remove containers + volumes
```

---

## Testing

```bash
# All tests (excludes load tests)
PYTHONPATH="." ./venv/Scripts/pytest.exe tests/ --ignore=tests/load_test.py -q

# Unit tests only
python -m pytest tests/test_prototype.py tests/test_agent.py

# Integration tests (requires Docker)
python -m pytest tests/test_integration.py

# Load testing (Locust)
locust -f tests/load_test.py --host=http://localhost:8000
# Web UI at http://localhost:8089
```

**Test Status:** 0 failed, 58+ passed (4 skipped — require Docker infra)

---

## Project Structure

```
customer-success-fte/
├── agent/                        # AI Agent layer
│   ├── customer_success_agent.py # Production agent (OpenAI Agents SDK)
│   ├── agent_prototype.py        # Prototype agent (skills pattern)
│   ├── prompts.py                # System prompts
│   ├── tools.py                  # Function tools
│   └── skills/                   # Modular skills
│       ├── knowledge_retrieval.py
│       ├── sentiment_analysis.py
│       ├── escalation_decision.py
│       ├── channel_adaptation.py
│       └── customer_identification.py
├── api/
│   ├── main.py                   # FastAPI app, routes, middleware
│   ├── auth.py                   # JWT auth endpoints
│   └── rate_limiter.py
├── channels/
│   ├── gmail_webhook.py          # Gmail push notifications
│   ├── gmail_handler.py          # Gmail send/receive
│   ├── whatsapp_webhook.py       # Twilio webhook
│   ├── whatsapp_handler.py       # WhatsApp send/receive
│   └── web_form_handler.py       # Web form submissions
├── workers/
│   ├── message_processor.py      # Main worker (Redis/Kafka consumer)
│   └── metrics_collector.py      # Prometheus metrics
├── database/
│   ├── schema.sql                # PostgreSQL + pgvector schema
│   └── queries.py                # DatabaseManager class
├── infrastructure/
│   └── redis_queue.py            # RedisProducer / RedisConsumer
├── k8s/                          # Kubernetes manifests
│   ├── deployment.yaml
│   ├── hpa.yaml
│   ├── ingress.yaml
│   └── ...
├── web-form/
│   ├── index.html                # Full SPA (Support, Dashboard, Tickets, Analytics, Settings)
│   ├── SupportForm.jsx           # React component
│   └── api.js                    # API client
├── tests/                        # Test suite (58+ tests)
├── kafka_client.py               # Kafka producer/consumer
├── mcp_server.py                 # MCP tools server
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── requirements.txt
```

---

## Deployment

### Vercel (Web UI)

```bash
cd web-form
vercel --prod
```

### Docker Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes

```bash
kubectl apply -f k8s/
```

Full deployment guide: [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) — Production deployment guide
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common issues & fixes
- [LOAD_TESTING.md](LOAD_TESTING.md) — Locust performance testing
- [DOCKER_README.md](DOCKER_README.md) — Docker setup details
- [specs/](specs/) — Feature specifications & discovery log

---

## License

MIT
