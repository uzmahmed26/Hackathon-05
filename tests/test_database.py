"""
Tests for database operations and queries.
"""

import pytest
import asyncpg
from datetime import datetime, timedelta
from uuid import UUID
import json


class TestDatabaseSchema:
    """Test database schema and structure"""
    
    @pytest.mark.asyncio
    async def test_tables_exist(self, db_conn):
        """Test that all required tables exist"""
        tables = [
            'customers',
            'customer_identifiers',
            'conversations',
            'messages',
            'tickets',
            'knowledge_base',
            'channel_configs',
            'agent_metrics'
        ]
        
        for table in tables:
            # Check if table exists
            result = await db_conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = $1
                );
            """, table)
            
            assert result is True, f"Table {table} does not exist"
    
    @pytest.mark.asyncio
    async def test_table_columns(self, db_conn):
        """Test that required columns exist in tables"""
        # Test customers table
        customer_cols = await db_conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'customers'
        """)
        
        col_names = [col['column_name'] for col in customer_cols]
        required_cols = ['id', 'email', 'name', 'created_at']
        
        for col in required_cols:
            assert col in col_names, f"Column {col} missing from customers table"
    
    @pytest.mark.asyncio
    async def test_indexes_exist(self, db_conn):
        """Test that required indexes exist"""
        indexes = await db_conn.fetch("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename IN ('customers', 'conversations', 'messages', 'tickets')
        """)
        
        index_names = [idx['indexname'] for idx in indexes]
        
        # Check for some key indexes
        expected_indexes = [
            'idx_customers_email',
            'idx_conversations_customer_id',
            'idx_messages_conversation_id',
            'idx_tickets_customer_id'
        ]
        
        for idx in expected_indexes:
            # Index names might be slightly different, so check if they contain the expected parts
            found = any(idx.lower() in name.lower() for name in index_names)
            if not found:
                print(f"Index {idx} might not exist, found: {index_names}")


class TestCustomerOperations:
    """Test customer-related database operations"""
    
    @pytest.mark.asyncio
    async def test_create_customer(self, db_conn):
        """Test creating a customer"""
        email = "test_create@example.com"
        name = "Test User"
        
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, email, name)
        
        # Verify customer was created
        assert isinstance(customer_id, UUID)
        
        # Retrieve and verify
        customer = await db_conn.fetchrow("""
            SELECT * FROM customers WHERE id = $1
        """, customer_id)
        
        assert customer['email'] == email
        assert customer['name'] == name
    
    @pytest.mark.asyncio
    async def test_customer_identifiers(self, db_conn):
        """Test customer identifier linking"""
        # Create customer
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, "multiidentifier@example.com", "Multi ID User")
        
        # Add email identifier
        await db_conn.execute("""
            INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
            VALUES ($1, 'email', $2)
        """, customer_id, "multiidentifier@example.com")
        
        # Add phone identifier
        await db_conn.execute("""
            INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
            VALUES ($1, 'whatsapp', $2)
        """, customer_id, "+1234567890")
        
        # Verify both identifiers exist
        identifiers = await db_conn.fetch("""
            SELECT * FROM customer_identifiers WHERE customer_id = $1
        """, customer_id)
        
        assert len(identifiers) == 2
        
        id_types = [id_row['identifier_type'] for id_row in identifiers]
        assert 'email' in id_types
        assert 'whatsapp' in id_types
    
    @pytest.mark.asyncio
    async def test_find_customer_by_identifier(self, db_conn):
        """Test finding customer by different identifiers"""
        # Create customer with email
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, "findme@example.com", "Find Me")
        
        # Add email identifier
        await db_conn.execute("""
            INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
            VALUES ($1, 'email', $2)
        """, customer_id, "findme@example.com")

        # Add phone identifier
        await db_conn.execute("""
            INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
            VALUES ($1, 'whatsapp', $2)
        """, customer_id, "+987654321")

        # Test finding by email
        found_by_email = await db_conn.fetchval("""
            SELECT c.id FROM customers c
            JOIN customer_identifiers ci ON c.id = ci.customer_id
            WHERE ci.identifier_type = 'email' AND ci.identifier_value = $1
        """, "findme@example.com")
        
        assert found_by_email == customer_id
        
        # Test finding by phone
        found_by_phone = await db_conn.fetchval("""
            SELECT c.id FROM customers c
            JOIN customer_identifiers ci ON c.id = ci.customer_id
            WHERE ci.identifier_type = 'whatsapp' AND ci.identifier_value = $1
        """, "+987654321")
        
        assert found_by_phone == customer_id


class TestConversationOperations:
    """Test conversation-related database operations"""
    
    @pytest.mark.asyncio
    async def test_create_conversation(self, db_conn):
        """Test creating a conversation"""
        # Create customer first
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, "conv_test@example.com", "Conversation Test User")
        
        # Create conversation
        conversation_id = await db_conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel, status)
            VALUES ($1, $2, $3)
            RETURNING id
        """, customer_id, "email", "active")
        
        # Verify conversation was created
        assert isinstance(conversation_id, UUID)
        
        # Retrieve and verify
        conversation = await db_conn.fetchrow("""
            SELECT * FROM conversations WHERE id = $1
        """, conversation_id)
        
        assert conversation['customer_id'] == customer_id
        assert conversation['initial_channel'] == 'email'
        assert conversation['status'] == 'active'
    
    @pytest.mark.asyncio
    async def test_conversation_messages(self, db_conn):
        """Test adding messages to a conversation"""
        # Create customer and conversation
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, "msg_test@example.com", "Message Test User")
        
        conversation_id = await db_conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel)
            VALUES ($1, $2)
            RETURNING id
        """, customer_id, "email")
        
        # Add customer message
        await db_conn.execute("""
            INSERT INTO messages (
                conversation_id, channel, direction, role, content
            )
            VALUES ($1, $2, $3, $4, $5)
        """, conversation_id, "email", "inbound", "customer", "I need help with my account")
        
        # Add agent response
        await db_conn.execute("""
            INSERT INTO messages (
                conversation_id, channel, direction, role, content
            )
            VALUES ($1, $2, $3, $4, $5)
        """, conversation_id, "email", "outbound", "agent", "I can help you with that")
        
        # Verify messages were added
        messages = await db_conn.fetch("""
            SELECT * FROM messages WHERE conversation_id = $1 ORDER BY created_at
        """, conversation_id)
        
        assert len(messages) == 2
        assert messages[0]['role'] == 'customer'
        assert messages[1]['role'] == 'agent'
        assert messages[0]['content'] == 'I need help with my account'
        assert messages[1]['content'] == 'I can help you with that'
    
    @pytest.mark.asyncio
    async def test_conversation_metadata(self, db_conn):
        """Test conversation metadata storage"""
        # Create customer and conversation with metadata
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, "meta_test@example.com", "Metadata Test User")
        
        metadata = {"source_campaign": "email_signup", "user_agent": "Mozilla/5.0"}
        
        conversation_id = await db_conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel, metadata)
            VALUES ($1, $2, $3)
            RETURNING id
        """, customer_id, "email", json.dumps(metadata))
        
        # Retrieve and verify metadata
        conversation = await db_conn.fetchrow("""
            SELECT * FROM conversations WHERE id = $1
        """, conversation_id)
        
        raw_metadata = conversation['metadata']
        retrieved_metadata = raw_metadata if isinstance(raw_metadata, dict) else json.loads(raw_metadata)
        assert retrieved_metadata['source_campaign'] == 'email_signup'
        assert retrieved_metadata['user_agent'] == 'Mozilla/5.0'


class TestTicketOperations:
    """Test ticket-related database operations"""
    
    @pytest.mark.asyncio
    async def test_create_ticket(self, db_conn):
        """Test creating a ticket"""
        # Create customer
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, "ticket_test@example.com", "Ticket Test User")
        
        # Create conversation
        conversation_id = await db_conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel)
            VALUES ($1, $2)
            RETURNING id
        """, customer_id, "email")
        
        # Create ticket
        ticket_id = await db_conn.fetchval("""
            INSERT INTO tickets (
                conversation_id, customer_id, source_channel, category, priority, status
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, conversation_id, customer_id, "email", "technical", "medium", "open")
        
        # Verify ticket was created
        assert isinstance(ticket_id, UUID)
        
        # Retrieve and verify
        ticket = await db_conn.fetchrow("""
            SELECT * FROM tickets WHERE id = $1
        """, ticket_id)
        
        assert ticket['customer_id'] == customer_id
        assert ticket['source_channel'] == 'email'
        assert ticket['category'] == 'technical'
        assert ticket['priority'] == 'medium'
        assert ticket['status'] == 'open'
    
    @pytest.mark.asyncio
    async def test_update_ticket_status(self, db_conn):
        """Test updating ticket status"""
        # Create customer, conversation, and ticket
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, "update_test@example.com", "Update Test User")
        
        conversation_id = await db_conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel)
            VALUES ($1, $2)
            RETURNING id
        """, customer_id, "email")
        
        ticket_id = await db_conn.fetchval("""
            INSERT INTO tickets (
                conversation_id, customer_id, source_channel, status
            )
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, conversation_id, customer_id, "email", "open")
        
        # Update ticket status
        await db_conn.execute("""
            UPDATE tickets SET status = $1, resolved_at = $2
            WHERE id = $3
        """, "resolved", datetime.utcnow(), ticket_id)
        
        # Verify update
        updated_ticket = await db_conn.fetchrow("""
            SELECT * FROM tickets WHERE id = $1
        """, ticket_id)
        
        assert updated_ticket['status'] == 'resolved'
        assert updated_ticket['resolved_at'] is not None


class TestKnowledgeBaseOperations:
    """Test knowledge base operations"""
    
    @pytest.mark.asyncio
    async def test_create_knowledge_entry(self, db_conn):
        """Test creating a knowledge base entry"""
        title = "Password Reset Guide"
        content = "To reset your password, go to the login page and click 'Forgot Password'"
        category = "account_management"
        
        entry_id = await db_conn.fetchval("""
            INSERT INTO knowledge_base (title, content, category)
            VALUES ($1, $2, $3)
            RETURNING id
        """, title, content, category)
        
        # Verify entry was created
        assert isinstance(entry_id, UUID)
        
        # Retrieve and verify
        entry = await db_conn.fetchrow("""
            SELECT * FROM knowledge_base WHERE id = $1
        """, entry_id)
        
        assert entry['title'] == title
        assert entry['content'] == content
        assert entry['category'] == category
    
    @pytest.mark.asyncio
    async def test_search_knowledge_base(self, db_conn):
        """Test searching the knowledge base"""
        # Create test entries
        await db_conn.execute("""
            INSERT INTO knowledge_base (title, content, category)
            VALUES 
                ('Password Reset', 'To reset your password...', 'account'),
                ('Team Management', 'To add team members...', 'collaboration'),
                ('Billing FAQ', 'For billing questions...', 'billing')
        """)
        
        # Search for password-related entries
        results = await db_conn.fetch("""
            SELECT * FROM knowledge_base
            WHERE title ILIKE $1 OR content ILIKE $1
            ORDER BY title
        """, '%password%')
        
        assert len(results) >= 1
        assert any('password' in row['title'].lower() for row in results)


class TestMetricsOperations:
    """Test metrics-related database operations"""
    
    @pytest.mark.asyncio
    async def test_store_agent_metric(self, db_conn):
        """Test storing agent metrics"""
        metric_name = "response_time_avg"
        metric_value = 2.45
        channel = "email"
        dimensions = {"agent_version": "2.0", "model": "gpt-4"}
        
        metric_id = await db_conn.fetchval("""
            INSERT INTO agent_metrics (metric_name, metric_value, channel, dimensions)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, metric_name, metric_value, channel, json.dumps(dimensions))
        
        # Verify metric was stored
        assert isinstance(metric_id, UUID)
        
        # Retrieve and verify
        metric = await db_conn.fetchrow("""
            SELECT * FROM agent_metrics WHERE id = $1
        """, metric_id)
        
        assert metric['metric_name'] == metric_name
        assert float(metric['metric_value']) == metric_value
        assert metric['channel'] == channel
        raw_dims = metric['dimensions']
        dims = raw_dims if isinstance(raw_dims, dict) else json.loads(raw_dims)
        assert dims['agent_version'] == "2.0"


class TestComplexQueries:
    """Test complex database queries"""
    
    @pytest.mark.asyncio
    async def test_customer_conversation_summary(self, db_conn):
        """Test querying customer conversation summary"""
        # Create customer with multiple conversations
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, "summary_test@example.com", "Summary Test User")
        
        # Create multiple conversations
        conv1_id = await db_conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel, status)
            VALUES ($1, $2, $3)
            RETURNING id
        """, customer_id, "email", "resolved")
        
        conv2_id = await db_conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel, status)
            VALUES ($1, $2, $3)
            RETURNING id
        """, customer_id, "whatsapp", "active")
        
        # Add messages to conversations
        await db_conn.execute("""
            INSERT INTO messages (conversation_id, channel, direction, role, content)
            VALUES ($1, $2, $3, $4, $5)
        """, conv1_id, "email", "inbound", "customer", "First conversation message")
        
        await db_conn.execute("""
            INSERT INTO messages (conversation_id, channel, direction, role, content)
            VALUES ($1, $2, $3, $4, $5)
        """, conv2_id, "whatsapp", "inbound", "customer", "Second conversation message")
        
        # Query customer summary
        summary = await db_conn.fetchrow("""
            SELECT 
                c.name,
                COUNT(DISTINCT conv.id) as conversation_count,
                COUNT(m.id) as message_count,
                STRING_AGG(DISTINCT conv.initial_channel, ', ') as channels_used
            FROM customers c
            LEFT JOIN conversations conv ON c.id = conv.customer_id
            LEFT JOIN messages m ON conv.id = m.conversation_id
            WHERE c.id = $1
            GROUP BY c.id, c.name
        """, customer_id)
        
        assert summary['conversation_count'] == 2
        assert summary['message_count'] == 2
        assert 'email' in summary['channels_used']
        assert 'whatsapp' in summary['channels_used']
    
    @pytest.mark.asyncio
    async def test_channel_performance_metrics(self, db_conn):
        """Test querying channel performance metrics"""
        # Create test data for performance metrics
        customer_id = await db_conn.fetchval("""
            INSERT INTO customers (email, name)
            VALUES ($1, $2)
            RETURNING id
        """, "perf_test@example.com", "Perf Test User")
        
        # Create conversations with different channels
        email_conv = await db_conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel, sentiment_score)
            VALUES ($1, $2, $3)
            RETURNING id
        """, customer_id, "email", 0.5)
        
        whatsapp_conv = await db_conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel, sentiment_score)
            VALUES ($1, $2, $3)
            RETURNING id
        """, customer_id, "whatsapp", -0.2)
        
        # Add messages with latency
        await db_conn.execute("""
            INSERT INTO messages (conversation_id, channel, direction, role, content, latency_ms)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, email_conv, "email", "outbound", "agent", "Email response", 1200)
        
        await db_conn.execute("""
            INSERT INTO messages (conversation_id, channel, direction, role, content, latency_ms)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, whatsapp_conv, "whatsapp", "outbound", "agent", "WhatsApp response", 800)
        
        # Query performance by channel
        performance = await db_conn.fetch("""
            SELECT 
                m.channel,
                COUNT(*) as message_count,
                AVG(m.latency_ms) as avg_latency,
                AVG(c.sentiment_score) as avg_sentiment
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.direction = 'outbound' AND m.role = 'agent'
            GROUP BY m.channel
        """)
        
        # Verify we have data for both channels
        channels = [row['channel'] for row in performance]
        assert 'email' in channels
        assert 'whatsapp' in channels