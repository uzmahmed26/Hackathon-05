# Customer Success AI Agent - Deployment Guide

This guide provides comprehensive instructions for deploying the Customer Success AI Agent in various environments, from local development to production.

## SECTION 1: Prerequisites

### Required Services
- **PostgreSQL 16+** - For storing conversations, customer data, and knowledge base
- **Redis 7+** - For caching and message queuing
- **Docker** - For containerization and orchestration
- **Python 3.11+** - For local development and testing

### Required API Keys
- **HuggingFace Token** (HF_TOKEN) - For AI model access (free tier available)
- **OpenAI API Key** (OPENAI_API_KEY) - Alternative AI model access (optional)
- **Gmail API Credentials** - For email integration
- **Twilio Account SID and Auth Token** - For WhatsApp integration

### Optional Production Tools
- **Domain Name** - For custom URLs
- **Kubernetes Cluster** - For advanced deployments
- **Monitoring Tools** - Prometheus, Grafana, etc.
- **SSL Certificate** - For HTTPS

## SECTION 2: Local Development Setup

Follow these steps to set up the project locally:

### 1. Clone Repository
```bash
git clone https://github.com/your-username/customer-success-fte.git
cd customer-success-fte
```

### 2. Create .env File
Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```bash
HF_TOKEN=your_huggingface_token_here
OPENAI_API_KEY=your_openai_key_here  # Optional
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_WHATSAPP_NUMBER=your_twilio_whatsapp_number
```

### 3. Set Up Gmail API
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API" and click "Enable"
4. Create OAuth credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Select "Desktop application" as the application type
   - Download the credentials JSON file
5. Save the credentials:
   ```bash
   mkdir -p credentials
   mv downloaded_credentials.json credentials/gmail_credentials.json
   ```

### 4. Set Up Twilio WhatsApp
1. Create a [Twilio account](https://www.twilio.com/try-twilio)
2. Get your Account SID and Auth Token from the Twilio Console
3. Join the WhatsApp Sandbox:
   - Go to Programmable Messaging > WhatsApp > Getting Started
   - Follow the instructions to join the sandbox
4. Configure webhook URL in Twilio Console:
   - For local development: Use ngrok to expose your local server
   - For production: Use your actual server URL

### 5. Start Services with Docker Compose
Build and start all services:
```bash
make build
make up
```

View logs to monitor startup:
```bash
make logs
```

### 6. Verify Installation
Check the health endpoint:
```bash
curl http://localhost:8000/health
```

Expected output:
```json
{
  "status": "healthy",
  "timestamp": "2023-10-01T12:00:00Z",
  "services": {
    "database": "connected",
    "redis": "connected"
  }
}
```

Open the API documentation:
- Visit http://localhost:8000/docs in your browser

### 7. Run Tests
Run the test suite:
```bash
make test
```

Run load tests:
```bash
# Install locust if not already installed
pip install locust

# Run quick smoke test
locust -f tests/load_test.py QuickSmokeTest --headless -u 10 -r 2 -t 1m --host=http://localhost:8000
```

## SECTION 3: Production Deployment Options

### OPTION A: Docker Compose (Simple Production)

For production deployments using Docker Compose:

1. Create a production `.env` file with secure values:
```bash
# Production environment variables
DATABASE_URL=postgresql://user:password@postgres:5432/dbname
REDIS_URL=redis://redis:6379
HF_TOKEN=your_production_hf_token
LOG_LEVEL=INFO
DEBUG=false
```

2. Build and start production services:
```bash
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

3. Set up Nginx with SSL:
```bash
# Install certbot for SSL certificates
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Configure nginx.conf for proxy to your app
sudo nano /etc/nginx/sites-available/your-app
```

Example nginx configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### OPTION B: Railway.app (Free Tier)

Deploy to Railway for a managed solution:

1. Install Railway CLI:
```bash
# Install via npm
npm install -g @railway/cli

# Or via Homebrew (macOS)
brew install railwayapp/railway/railway
```

2. Login to Railway:
```bash
railway login
```

3. Initialize a new project:
```bash
railway init
```

4. Add PostgreSQL and Redis plugins:
```bash
railway add postgresql
railway add redis
```

5. Set environment variables:
```bash
railway var set HF_TOKEN=your_hf_token
railway var set OPENAI_API_KEY=your_openai_key
railway var set TWILIO_ACCOUNT_SID=your_twilio_sid
railway var set TWILIO_AUTH_TOKEN=your_twilio_token
railway var set TWILIO_WHATSAPP_NUMBER=your_whatsapp_number
```

6. Deploy:
```bash
railway up
```

Result: Your app will be accessible at `https://your-app.up.railway.app`

### OPTION C: Render.com (Free Tier)

Deploy to Render for another managed solution:

1. Create a `render.yaml` configuration file:
```yaml
services:
  - type: web
    name: customer-success-agent
    env: docker
    repo: https://github.com/your-username/your-repo
    plan: free
    branch: main
    envVars:
      - key: HF_TOKEN
        sync: false
      - key: OPENAI_API_KEY
        sync: false
      - key: DATABASE_URL
        fromDatabase: customer-db
      - key: REDIS_URL
        fromService:
          name: customer-redis
          property: REDIS_URL
    healthCheckPath: /health

databases:
  - name: customer-db
    plan: free

services:
  - type: redis
    name: customer-redis
    plan: free
```

2. Connect your GitHub repository to Render
3. Configure the environment variables in Render dashboard
4. Enable auto-deploy from the render.yaml file

### OPTION D: Kubernetes (Advanced)

For enterprise-grade deployments:

1. Build and push Docker image to a registry:
```bash
# Build the image
docker build -t your-registry/customer-success-agent:latest .

# Push to registry
docker push your-registry/customer-success-agent:latest
```

2. Apply Kubernetes manifests:
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/deployment-api.yaml
kubectl apply -f k8s/deployment-worker.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml
```

3. Set up ingress with SSL:
```bash
# Install cert-manager for SSL certificates
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Create a ClusterIssuer for Let's Encrypt
kubectl apply -f k8s/cluster-issuer.yaml
```

## SECTION 4: Environment Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@host:port/dbname` |
| `REDIS_URL` | Redis connection string | `redis://host:port` |
| `HF_TOKEN` | HuggingFace API token | `hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `OPENAI_API_KEY` | OpenAI API key (optional) | `sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_WHATSAPP_NUMBER` | Twilio WhatsApp number | `whatsapp:+1234567890` |
| `GMAIL_CREDENTIALS_PATH` | Path to Gmail credentials | `/app/credentials/gmail_credentials.json` |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level | `INFO` |
| `DEBUG` | Debug mode | `false` |
| `API_HOST` | API host | `0.0.0.0` |
| `API_PORT` | API port | `8000` |
| `WORKER_CONCURRENCY` | Number of worker processes | `4` |

## SECTION 5: Database Setup

### Manual Setup Instructions

Connect to PostgreSQL and run manual setup:
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U fte_user -d fte_db

# Create tables manually (if needed)
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255),
    channel VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    sender VARCHAR(50),
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Docker Auto-Setup

The Docker Compose setup automatically initializes the database using schema files in `./database/schema.sql`.

### Backup and Restore Commands

Backup database:
```bash
# Backup to file
docker-compose exec postgres pg_dump -U fte_user fte_db > backup.sql

# Restore from file
docker-compose exec -T postgres psql -U fte_user -d fte_db < backup.sql
```

## SECTION 6: Channel Configuration

### Gmail Webhook Setup

#### For Production (using Pub/Sub):
1. Enable Google Cloud Pub/Sub API
2. Create a topic for Gmail notifications
3. Configure Gmail to publish notifications to the topic
4. Set up a subscriber to process the notifications

#### For Local Development (using ngrok):
1. Install ngrok: `npm install -g ngrok`
2. Start your local server: `make up`
3. Expose your local server: `ngrok http 8000`
4. Use the ngrok URL as your webhook endpoint in Gmail settings

### WhatsApp Webhook Setup

Configure webhook in Twilio Console:
1. Go to Twilio Console > Programmable Messaging > WhatsApp
2. Click on "Settings" for your WhatsApp sandbox
3. Set the webhook URL to your server endpoint:
   - Production: `https://your-domain.com/api/webhooks/whatsapp`
   - Local: `https://your-ngrok-url.ngrok.io/api/webhooks/whatsapp`
4. Select "HTTP POST" as the method
5. Save the configuration

### Web Form Configuration

The web form integration is already included in the API. No additional setup required.

## SECTION 7: Monitoring

### Health Check Endpoints

- Health: `GET /health` - Returns system status
- Metrics: `GET /metrics` - Returns Prometheus metrics

### Log Viewing Commands

#### Docker Compose:
```bash
# View all logs
make logs

# View API logs
make logs-api

# View worker logs
make logs-worker

# View specific service logs
docker-compose logs -f api
```

#### Kubernetes:
```bash
# View API logs
kubectl logs -f deployment/api-deployment

# View worker logs
kubectl logs -f deployment/worker-deployment

# View logs with label selector
kubectl logs -f -l app=customer-success-agent
```

### Prometheus Metrics Configuration

The application exposes metrics at `/metrics` endpoint in Prometheus format. Configure your Prometheus server to scrape this endpoint.

## SECTION 8: Scaling

### Horizontal Scaling with Docker Compose

Scale worker instances:
```bash
# Scale workers to 5 instances
docker-compose up -d --scale worker=5

# Scale API to 3 instances
docker-compose up -d --scale api=3
```

### Kubernetes Auto-Scaling (HPA)

Horizontal Pod Autoscaler is configured in `k8s/hpa.yaml`:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-deployment
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Performance Tuning

#### Database Pool:
Adjust connection pool size in your database configuration:
```python
# In your database client
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True
)
```

#### Worker Replicas:
Increase worker replicas based on expected load:
```bash
# For Docker Compose
docker-compose up -d --scale worker=10

# For Kubernetes
kubectl scale deployment worker-deployment --replicas=10
```

#### Redis Memory:
Configure Redis with appropriate memory limits:
```yaml
# In docker-compose.yml
redis:
  image: redis:7-alpine
  command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
```

## SECTION 9: Troubleshooting

For troubleshooting information, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### Common Issues

1. **Database Connection Errors**:
   - Check that PostgreSQL is running and accessible
   - Verify `DATABASE_URL` is correctly set
   - Ensure the database schema is properly initialized

2. **Redis Connection Errors**:
   - Check that Redis is running and accessible
   - Verify `REDIS_URL` is correctly set
   - Ensure Redis has sufficient memory allocated

3. **API Key Issues**:
   - Verify all required API keys are set in environment variables
   - Check that API keys have the necessary permissions
   - Ensure API keys are not expired

4. **Docker Build Failures**:
   - Check that Docker is installed and running
   - Verify Docker has sufficient resources (memory, disk space)
   - Clear Docker cache if needed: `docker system prune`

5. **Performance Issues**:
   - Monitor resource usage (CPU, memory, disk I/O)
   - Scale services as needed
   - Check for database query bottlenecks
   - Review Redis memory usage

For additional support, check the logs using the commands in Section 7 or open an issue in the repository.