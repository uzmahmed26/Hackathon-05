# Customer Success AI Agent

A comprehensive customer support AI agent that handles queries across multiple channels (Email, WhatsApp, Web Form) with intelligent routing and response generation.

## Features

- Multi-channel support (Email, WhatsApp, Web Form)
- Knowledge base integration for automated responses
- Sentiment analysis to detect customer emotions
- Intelligent escalation to human agents
- Channel-adaptive response formatting
- Customer identification and profiling

## Project Structure

```
customer-success-ai/
├── agent/                 # Core AI agent implementation
│   ├── agent_prototype.py # Main agent class
│   ├── hf_client.py      # Hugging Face API client
│   └── skills/           # Individual AI skills
│       ├── knowledge_retrieval.py
│       ├── sentiment_analysis.py
│       ├── escalation_decision.py
│       ├── channel_adaptation.py
│       └── customer_identification.py
├── context/              # Company docs and sample data
├── specs/                # Feature specifications
├── tests/                # Test files
├── api/                  # API endpoints (future)
├── channels/             # Channel handlers (future)
├── database/             # Database schemas (future)
├── workers/              # Message processors (future)
└── web-form/             # React support form (future)
```

## Skills

The agent is composed of several specialized skills:

1. **Knowledge Retrieval**: Searches product documentation for relevant answers
2. **Sentiment Analysis**: Analyzes customer sentiment and emotional state
3. **Escalation Decision**: Determines if queries require human intervention
4. **Channel Adaptation**: Formats responses appropriately for each channel
5. **Customer Identification**: Identifies customer type and profile

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run tests:
```bash
python -m pytest tests/
```

## Usage

```python
from agent.agent_prototype import CustomerSuccessAgent

# Initialize the agent
agent = CustomerSuccessAgent(hf_token="your_hf_token_here")

# Handle a customer query
result = await agent.handle_query(
    message="How do I reset my password?",
    channel="email",
    customer_id="customer@example.com"
)

print(result['response'])
```

## Environment Variables

- `HF_TOKEN`: Hugging Face API token for Qwen model access
- `DATABASE_URL`: Database connection string (if using persistence)
- `API_HOST`: Host for the API server
- `API_PORT`: Port for the API server
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Testing

Run all tests:
```bash
python -m pytest tests/
```

Run specific test file:
```bash
python -m pytest tests/test_prototype.py
```

Run integration tests:
```bash
python -m pytest tests/test_integration.py
```

## Load Testing

The project includes a comprehensive load testing suite using Locust:

```bash
# Install locust
pip install locust

# Run with web UI
locust -f tests/load_test.py --host=http://localhost:8000

# Run headless (no UI)
locust -f tests/load_test.py QuickSmokeTest --headless -u 10 -r 2 -t 1m --host=http://localhost:8000
```

The load test suite includes multiple scenarios:
- Quick Smoke Test (10 users for 1 minute)
- Sustained Load Test (100 users for 1 hour)
- Stress Test (500 users for 10 minutes)
- Spike Test (1000 users for 5 minutes)

For detailed information about load testing, see [LOAD_TESTING.md](LOAD_TESTING.md).

## Development Commands

This project includes a Makefile with convenient commands for development and deployment:

```bash
# Show all available commands
make help

# Build and start services
make build
make up

# View logs
make logs
make logs-api
make logs-worker

# Run tests
make test
make test-unit
make test-integration

# Manage services
make down
make restart-api
make restart-worker
make scale-workers
```

For a complete list of commands, see the [Makefile](Makefile) or run `make help`.

## Documentation

- [Deployment Guide](DEPLOYMENT.md) - Complete instructions for deploying in various environments
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Solutions to common issues
- [Load Testing Guide](LOAD_TESTING.md) - Performance testing with Locust

## License

MIT