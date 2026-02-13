"""
Pytest configuration and shared fixtures.
"""

import pytest
import asyncio
import asyncpg
from httpx import AsyncClient
from typing import AsyncGenerator
import os
from datetime import datetime

# Set test environment
os.environ['TESTING'] = 'true'
os.environ['DATABASE_URL'] = 'postgresql://fte_user:fte_password@localhost:5432/fte_test_db'
os.environ['REDIS_URL'] = 'redis://localhost:6379/1'  # Use DB 1 for tests

from api.main import app
from database.queries import DatabaseManager
from infrastructure.redis_queue import RedisProducer

# Async test support
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Database fixtures
@pytest.fixture(scope="session")
async def db_manager():
    """Create database manager for tests"""
    manager = DatabaseManager(dsn=os.getenv('DATABASE_URL'))
    await manager.connect()
    
    # Create test schema
    async with manager.pool.acquire() as conn:
        # Run schema
        with open('database/schema.sql', 'r') as f:
            await conn.execute(f.read())
    
    yield manager
    
    # Cleanup
    await manager.close()

@pytest.fixture
async def db_conn(db_manager):
    """Get database connection for a single test"""
    async with db_manager.pool.acquire() as conn:
        # Start transaction
        tr = conn.transaction()
        await tr.start()
        
        yield conn
        
        # Rollback transaction (clean slate for next test)
        await tr.rollback()

# Redis fixtures
@pytest.fixture(scope="session")
async def redis_producer():
    """Create Redis producer for tests"""
    producer = RedisProducer()
    await producer.connect()
    
    yield producer
    
    # Cleanup
    await producer.disconnect()

@pytest.fixture
async def redis_clean(redis_producer):
    """Clean Redis streams before each test"""
    # Delete all test streams
    streams = ['tickets:incoming', 'tickets:email', 'escalations', 'metrics']
    for stream in streams:
        try:
            await redis_producer.client.delete(stream)
        except:
            pass
    
    yield
    
    # Cleanup after test
    for stream in streams:
        try:
            await redis_producer.client.delete(stream)
        except:
            pass

# API fixtures
@pytest.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """Create HTTP client for API testing"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

# Test data fixtures
@pytest.fixture
def sample_customer():
    """Sample customer data"""
    return {
        'email': 'test@example.com',
        'phone': '+1234567890',
        'name': 'Test Customer'
    }

@pytest.fixture
def sample_email_message():
    """Sample email message"""
    return {
        'channel': 'email',
        'channel_message_id': 'msg_123',
        'customer_email': 'test@example.com',
        'customer_name': 'Test Customer',
        'subject': 'Help with password reset',
        'content': 'I forgot my password and cannot log in. Can you help me reset it?',
        'received_at': datetime.utcnow().isoformat(),
        'metadata': {'thread_id': 'thread_abc'}
    }

@pytest.fixture
def sample_whatsapp_message():
    """Sample WhatsApp message"""
    return {
        'channel': 'whatsapp',
        'channel_message_id': 'SM123',
        'customer_phone': '+1234567890',
        'customer_name': 'Test User',
        'content': 'hey how do i add team members?',
        'received_at': datetime.utcnow().isoformat(),
        'metadata': {'wa_id': 'wa123'}
    }

@pytest.fixture
def sample_webform_message():
    """Sample web form submission"""
    return {
        'channel': 'web_form',
        'channel_message_id': 'ticket_456',
        'customer_email': 'user@example.com',
        'customer_name': 'Form User',
        'subject': 'Feature request',
        'content': 'It would be great if you could add dark mode to the app.',
        'category': 'feedback',
        'priority': 'low',
        'received_at': datetime.utcnow().isoformat(),
        'metadata': {}
    }

# Agent fixtures
@pytest.fixture
def mock_agent_response():
    """Mock agent response"""
    return {
        'output': 'Thank you for contacting us. To reset your password, please visit...',
        'tool_calls': [
            {'tool': 'create_ticket', 'status': 'success'},
            {'tool': 'search_knowledge_base', 'status': 'success'},
            {'tool': 'send_response', 'status': 'success'}
        ],
        'escalated': False,
        'escalation_reason': None
    }

# Cleanup fixture
@pytest.fixture(autouse=True)
async def cleanup():
    """Run before and after each test"""
    # Setup code here
    yield
    # Teardown code here
    pass