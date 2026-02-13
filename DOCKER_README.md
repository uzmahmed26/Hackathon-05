# Customer Success AI Agent - Docker Setup

This repository contains a comprehensive customer support AI agent that handles queries across multiple channels (Email, WhatsApp, Web Form) with intelligent routing and response generation.

## Prerequisites

- Docker Desktop (with Docker Compose v2.18+)
- At least 4GB of RAM available to Docker
- 2GB of free disk space

## Quick Start (Development)

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd customer-success-fte
   ```

2. Create a `.env` file with your API keys:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

3. Start the development environment:
   ```bash
   docker-compose up -d
   ```

4. View logs:
   ```bash
   docker-compose logs -f
   ```

5. Access services:
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - pgAdmin: http://localhost:5050 (admin@example.com / admin)
   - Redis Commander: http://localhost:8081

## Production Deployment

For production deployment, use the production compose file:

```bash
# Create production .env file
cp .env.example .env.prod
# Edit .env.prod with your production values

# Deploy with production compose file
docker-compose -f docker-compose.prod.yml up -d
```

## Services

The setup includes:

- **API Service**: FastAPI application serving the customer success agent
- **Worker Service**: Processes incoming messages from all channels
- **PostgreSQL**: Database with pgvector extension for semantic search
- **Redis**: Message queue and caching
- **pgAdmin**: Web UI for PostgreSQL (dev only)
- **Redis Commander**: Web UI for Redis (dev only)
- **Nginx**: Reverse proxy (prod only)

## Configuration

### Environment Variables

Required environment variables in `.env`:

```bash
# Database
POSTGRES_USER=fte_user
POSTGRES_PASSWORD=fte_password
POSTGRES_DB=fte_db

# Redis
REDIS_PASSWORD=redis_password

# API Keys
OPENAI_API_KEY=your_openai_api_key
HF_TOKEN=your_huggingface_token

# Twilio (for WhatsApp)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=your_whatsapp_number

# Gmail
GMAIL_CLIENT_ID=your_gmail_client_id
GMAIL_CLIENT_SECRET=your_gmail_client_secret
```

### Volumes

- `postgres_data`: Persistent storage for PostgreSQL
- `redis_data`: Persistent storage for Redis

### Networks

- `fte-network`: Internal network for service communication

## Development

### Adding Dependencies

Update `requirements.txt` and rebuild the image:

```bash
docker-compose build
docker-compose up -d
```

### Running Tests

```bash
docker-compose exec api python -m pytest
```

### Accessing Services

```bash
# Access API container
docker-compose exec api bash

# Access PostgreSQL
docker-compose exec postgres psql -U fte_user -d fte_db

# Access Redis
docker-compose exec redis redis-cli
```

## Production Considerations

1. **Security**:
   - Use strong passwords in production
   - Enable SSL/TLS termination
   - Restrict network access
   - Regular security updates

2. **Monitoring**:
   - Set up logging aggregation
   - Configure health checks
   - Monitor resource usage

3. **Backup**:
   - Regular database backups
   - Backup Redis data
   - Test backup restoration

4. **Scaling**:
   - Adjust worker replicas based on load
   - Scale database resources as needed
   - Monitor performance metrics

## Troubleshooting

### Common Issues

1. **Port conflicts**: Make sure ports 8000, 5432, 6379, 5050, 8081 are available
2. **Insufficient memory**: Allocate at least 4GB to Docker
3. **Permission errors**: Ensure Docker has access to the project directory

### Useful Commands

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f api
docker-compose logs -f worker

# Restart specific service
docker-compose restart api

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: Data loss)
docker-compose down -v
```

## Architecture

The system follows a microservices architecture:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Email     │    │  WhatsApp   │    │  Web Form   │
│  Channel    │    │  Channel    │    │  Channel    │
└─────────────┘    └─────────────┘    └─────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                    ┌─────────────────┐
                    │   Redis Queue   │
                    │   (Messages)    │
                    └─────────────────┘
                             ▲
                             │
                    ┌─────────────────┐
                    │   Worker(s)     │
                    │ (Message Proc.) │
                    └─────────────────┘
                             ▲
                             │
                    ┌─────────────────┐
                    │     Agent       │
                    │  (LLM & Tools)  │
                    └─────────────────┘
                             ▲
                             │
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   (Storage)     │
                    └─────────────────┘
```

## Health Checks

- API Health: `GET /health`
- API Ready: `GET /ready`
- API Live: `GET /live`
- API Metrics: `GET /metrics`

## License

MIT