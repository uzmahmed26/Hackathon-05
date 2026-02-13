.PHONY: help build up up-dev down logs logs-api logs-worker test clean db-migrate db-shell redis-shell restart-worker restart-api scale-workers prod-build prod-up prod-down prod-logs test-unit test-integration test-e2e test-load

# DEVELOPMENT COMMANDS

help:
	@echo "Customer Success AI Agent - Make Commands"
	@echo "=========================================="
	@echo ""
	@echo "DEVELOPMENT COMMANDS:"
	@echo "  make help            - Show all available commands"
	@echo "  make build           - Build Docker images"
	@echo "  make up              - Start all services (docker-compose up -d)"
	@echo "  make up-dev          - Start with dev tools (pgAdmin, Redis Commander)"
	@echo "  make down            - Stop all services"
	@echo "  make logs            - View all logs (docker-compose logs -f)"
	@echo "  make logs-api        - View API logs only"
	@echo "  make logs-worker     - View worker logs only"
	@echo "  make test            - Run pytest tests with coverage"
	@echo "  make clean           - Remove all containers and volumes"
	@echo "  make db-migrate      - Run database migrations"
	@echo "  make db-shell        - Open PostgreSQL shell"
	@echo "  make redis-shell     - Open Redis CLI"
	@echo "  make restart-worker  - Restart worker only"
	@echo "  make restart-api     - Restart API only"
	@echo "  make scale-workers   - Scale workers to 5 replicas"
	@echo ""
	@echo "PRODUCTION COMMANDS:"
	@echo "  make prod-build      - Build production images"
	@echo "  make prod-up         - Start production deployment"
	@echo "  make prod-down       - Stop production deployment"
	@echo "  make prod-logs       - View production logs"
	@echo ""
	@echo "TESTING COMMANDS:"
	@echo "  make test-unit       - Run unit tests"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-e2e        - Run end-to-end tests"
	@echo "  make test-load       - Run load tests with Locust"
	@echo ""

build:
	@echo "Building Docker images..."
	docker-compose build
	@echo "Docker images built successfully!"

up:
	@echo "Starting all services..."
	docker-compose up -d
	@echo "Services started. Check logs with: make logs"

up-dev:
	@echo "Starting all services with development tools..."
	docker-compose --profile dev up -d
	@echo "Services started with development tools. Check logs with: make logs"

down:
	@echo "Stopping all services..."
	docker-compose down
	@echo "All services stopped."

logs:
	@echo "Viewing all logs (Press Ctrl+C to stop)..."
	docker-compose logs -f

logs-api:
	@echo "Viewing API logs (Press Ctrl+C to stop)..."
	docker-compose logs -f api

logs-worker:
	@echo "Viewing worker logs (Press Ctrl+C to stop)..."
	docker-compose logs -f worker

test:
	@echo "Running tests with coverage..."
	docker-compose exec api python -m pytest tests/ -v --cov=agent --cov-report=html --cov-report=term

clean:
	@echo "Removing all containers and volumes..."
	docker-compose down -v
	@echo "Cleanup completed."

db-migrate:
	@echo "Running database migrations..."
	docker-compose exec postgres psql -U fte_user -d fte_db -f /docker-entrypoint-initdb.d/01-schema.sql || echo "Migration may have already run or schema file not found"
	@echo "Database migration attempted."

db-shell:
	@echo "Opening PostgreSQL shell..."
	docker-compose exec postgres psql -U fte_user -d fte_db

redis-shell:
	@echo "Opening Redis CLI..."
	docker-compose exec redis redis-cli

restart-worker:
	@echo "Restarting worker service..."
	docker-compose restart worker
	@echo "Worker service restarted."

restart-api:
	@echo "Restarting API service..."
	docker-compose restart api
	@echo "API service restarted."

scale-workers:
	@echo "Scaling workers to 5 replicas..."
	docker-compose up -d --scale worker=5
	@echo "Workers scaled to 5 replicas."

# PRODUCTION COMMANDS

prod-build:
	@echo "Building production Docker images..."
	docker-compose -f docker-compose.prod.yml build
	@echo "Production Docker images built successfully!"

prod-up:
	@echo "Starting production deployment..."
	docker-compose -f docker-compose.prod.yml up -d
	@echo "Production services started. Check logs with: make prod-logs"

prod-down:
	@echo "Stopping production deployment..."
	docker-compose -f docker-compose.prod.yml down
	@echo "Production services stopped."

prod-logs:
	@echo "Viewing production logs (Press Ctrl+C to stop)..."
	docker-compose -f docker-compose.prod.yml logs -f

# TESTING COMMANDS

test-unit:
	@echo "Running unit tests..."
	docker-compose exec api python -m pytest tests/test_prototype.py tests/test_agent.py -v

test-integration:
	@echo "Running integration tests..."
	docker-compose exec api python -m pytest tests/test_integration.py -v

test-e2e:
	@echo "Running end-to-end tests..."
	docker-compose exec api python -m pytest tests/test_e2e.py -v

test-load:
	@echo "Running load tests with Locust..."
	@echo "Starting Locust web UI on http://localhost:8089"
	docker-compose exec api locust -f tests/load_test.py --host=http://api:8000