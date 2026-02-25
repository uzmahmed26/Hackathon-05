"""
Main FastAPI application for Customer Success AI
Ties together all components: webhooks, channels, database, and Redis
"""

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
from datetime import datetime
import time
import asyncio
from typing import Dict, Any, Optional
import asyncpg
import redis.asyncio as redis

# Import routers
from channels.gmail_webhook import router as gmail_router
from channels.whatsapp_webhook import router as whatsapp_router
from channels.web_form_handler import router as webform_router

# Import infrastructure
from infrastructure.redis_queue import RedisProducer
from database.queries import DatabaseManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    
    Startup:
    - Initialize database connection pool
    - Initialize Redis producer
    - Verify all services are reachable
    
    Shutdown:
    - Close database connections
    - Close Redis connections
    - Flush any pending operations
    """
    logger.info("Starting up application...")
    
    # Startup
    app.state.db_manager = None
    app.state.redis_producer = None

    try:
        # Initialize database manager
        import os
        db_url = os.getenv('DATABASE_URL', 'postgresql://fte_user:fte_password@localhost:5432/fte_db')
        app.state.db_manager = DatabaseManager(dsn=db_url)
        await app.state.db_manager.connect()
        logger.info("Database manager initialized")
    except Exception as e:
        logger.warning(f"Database unavailable (running in degraded mode): {e}")
        app.state.db_manager = None

    try:
        # Initialize Redis producer
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        app.state.redis_producer = RedisProducer(redis_url=redis_url)
        await app.state.redis_producer._ensure_connection()
        logger.info("Redis producer initialized")
    except Exception as e:
        logger.warning(f"Redis unavailable (running in degraded mode): {e}")
        app.state.redis_producer = None

    logger.info("Application startup complete")
    
    yield  # Application is running
    
    # Shutdown
    logger.info("Shutting down application...")
    
    try:
        # Close database manager
        await app.state.db_manager.close()
        logger.info("Database manager closed")
        
        # Close Redis producer
        if hasattr(app.state.redis_producer, 'client') and app.state.redis_producer.client:
            await app.state.redis_producer.client.close()
        logger.info("Redis producer closed")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")
    
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Customer Success FTE API",
    description="24/7 AI-powered customer support across Email, WhatsApp, and Web Form",
    version="2.0.0",
    lifespan=lifespan
)

# Set default state values so endpoints work even when lifespan hasn't run
# (e.g., in tests that use ASGITransport without triggering lifespan events)
app.state.db_manager = None
app.state.redis_producer = None

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    start_time = time.time()
    
    # Generate request ID
    request_id = f"{datetime.utcnow().timestamp()}-{id(request)}"
    
    logger.info(f"Request started: {request.method} {request.url.path}", extra={
        'request_id': request_id,
        'method': request.method,
        'path': request.url.path,
        'client': request.client.host if request.client else None
    })
    
    # Process request
    try:
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(f"Request completed: {request.method} {request.url.path}", extra={
            'request_id': request_id,
            'status_code': response.status_code,
            'duration_ms': duration_ms
        })
        
        # Add headers
        response.headers['X-Request-ID'] = request_id
        response.headers['X-Process-Time'] = f"{duration_ms:.2f}ms"
        
        return response
        
    except Exception as e:
        logger.error(f"Request failed: {e}", extra={
            'request_id': request_id,
            'error': str(e)
        }, exc_info=True)
        raise


# Error handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    import json

    def _make_serializable(obj):
        if isinstance(obj, dict):
            return {k: _make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_make_serializable(i) for i in obj]
        if isinstance(obj, Exception):
            return str(obj)
        try:
            json.dumps(obj)
            return obj
        except TypeError:
            return str(obj)

    errors = _make_serializable(exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if app.debug else "An error occurred"
        }
    )


# Include routers (routers already define their own prefixes internally)
app.include_router(gmail_router)
app.include_router(whatsapp_router)
app.include_router(webform_router, prefix="/api", tags=["support"])


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Checks:
    - API is responding
    - Database is reachable
    - Redis is reachable
    
    Returns:
    - 200 OK if all healthy
    - 503 Service Unavailable if any dependency down
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "services": {}
    }
    
    # Check database
    try:
        if app.state.db_manager is None:
            raise RuntimeError("Database manager not initialized")
        # Test database connection
        async with app.state.db_manager.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        health["services"]["database"] = "healthy"
    except Exception as e:
        health["services"]["database"] = f"unhealthy: {str(e)}"
        health["status"] = "unhealthy"

    # Check Redis
    try:
        if app.state.redis_producer is None:
            raise RuntimeError("Redis producer not initialized")
        await app.state.redis_producer.client.ping()
        health["services"]["redis"] = "healthy"
    except Exception as e:
        health["services"]["redis"] = f"unhealthy: {str(e)}"
        health["status"] = "unhealthy"
    
    # Check channels
    health["services"]["channels"] = {
        "email": "active",
        "whatsapp": "active",
        "web_form": "active"
    }
    
    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(content=health, status_code=status_code)


# Readiness check (for Kubernetes)
@app.get("/ready")
async def readiness_check():
    """
    Readiness check for Kubernetes.
    Returns 200 when application is ready to serve traffic.
    """
    try:
        # Quick check - just verify we can access dependencies
        async with app.state.db_manager.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="Not ready")


# Liveness check (for Kubernetes)
@app.get("/live")
async def liveness_check():
    """
    Liveness check for Kubernetes.
    Returns 200 as long as the process is running.
    """
    return {"status": "alive"}


# Metrics endpoint (for Prometheus)
@app.get("/metrics")
async def metrics():
    """
    Expose metrics for monitoring.
    
    Returns:
    - Message processing stats
    - Channel breakdown
    - Error rates
    - Latency percentiles
    """
    if app.state.db_manager is None:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    async with app.state.db_manager.pool.acquire() as conn:
        # Last 24 hours stats
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(*) FILTER (WHERE channel = 'email') as email_count,
                COUNT(*) FILTER (WHERE channel = 'whatsapp') as whatsapp_count,
                COUNT(*) FILTER (WHERE channel = 'web_form') as webform_count,
                AVG(latency_ms) as avg_latency_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms
            FROM messages
            WHERE created_at > NOW() - INTERVAL '24 hours'
              AND direction = 'outbound'
        """)
        
        # Ticket stats
        tickets = await conn.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'open') as open_tickets,
                COUNT(*) FILTER (WHERE status = 'escalated') as escalated_tickets,
                COUNT(*) FILTER (WHERE status = 'resolved') as resolved_tickets
            FROM tickets
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "messages": {
            "total": stats['total_messages'],
            "by_channel": {
                "email": stats['email_count'],
                "whatsapp": stats['whatsapp_count'],
                "web_form": stats['webform_count']
            }
        },
        "performance": {
            "avg_latency_ms": float(stats['avg_latency_ms'] or 0),
            "p95_latency_ms": float(stats['p95_latency_ms'] or 0)
        },
        "tickets": {
            "open": tickets['open_tickets'],
            "escalated": tickets['escalated_tickets'],
            "resolved": tickets['resolved_tickets']
        }
    }


# Channel-specific metrics
@app.get("/metrics/channels")
async def channel_metrics():
    """
    Get detailed metrics broken down by channel.
    
    Returns:
    - Performance per channel
    - Escalation rate per channel
    - Average sentiment per channel
    """
    if app.state.db_manager is None:
        return JSONResponse(status_code=503, content={"error": "Database unavailable"})

    async with app.state.db_manager.pool.acquire() as conn:
        metrics = await conn.fetch("""
            SELECT
                c.initial_channel as channel,
                COUNT(DISTINCT c.id) as total_conversations,
                AVG(c.sentiment_score) as avg_sentiment,
                COUNT(*) FILTER (WHERE c.status = 'escalated') as escalations,
                COUNT(*) FILTER (WHERE c.status = 'resolved') as resolved,
                AVG(EXTRACT(EPOCH FROM (c.ended_at - c.started_at))) as avg_duration_seconds
            FROM conversations c
            WHERE c.started_at > NOW() - INTERVAL '24 hours'
            GROUP BY c.initial_channel
        """)
    
    result = {}
    for row in metrics:
        result[row['channel']] = {
            'total_conversations': row['total_conversations'],
            'avg_sentiment': float(row['avg_sentiment'] or 0.5),
            'escalations': row['escalations'],
            'resolved': row['resolved'],
            'escalation_rate': row['escalations'] / row['total_conversations'] if row['total_conversations'] > 0 else 0,
            'avg_duration_seconds': float(row['avg_duration_seconds'] or 0)
        }
    
    return result


# ─── Helper stubs (mockable by tests) ─────────────────────────────────────────

async def find_customer(email: str = None, phone: str = None) -> Optional[Dict[str, Any]]:
    """Look up a customer by email or phone."""
    if app.state.db_manager is None:
        return None
    async with app.state.db_manager.pool.acquire() as conn:
        if email:
            row = await conn.fetchrow("SELECT * FROM customers WHERE email = $1", email)
        elif phone:
            row = await conn.fetchrow("SELECT * FROM customers WHERE phone = $1", phone)
        else:
            return None
        return dict(row) if row else None


async def load_conversation_history(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Load conversation history by ID."""
    if app.state.db_manager is None:
        return None
    async with app.state.db_manager.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1", conversation_id
        )
        return dict(row) if row else None


# ─── Customer endpoints ────────────────────────────────────────────────────────

@app.get("/customers/lookup")
async def lookup_customer(email: str = None, phone: str = None):
    """Look up a customer by email or phone."""
    if not email and not phone:
        from fastapi.responses import JSONResponse as _JSONResponse
        return _JSONResponse(
            status_code=400,
            content={"detail": "email or phone query parameter required"}
        )
    customer = await find_customer(email=email, phone=phone)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history by ID."""
    history = await load_conversation_history(conversation_id)
    if not history:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return history


# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "Customer Success FTE API",
        "version": "2.0.0",
        "status": "operational",
        "channels": ["email", "whatsapp", "web_form"],
        "documentation": "/docs"
    }


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Only for development
        log_level="info"
    )