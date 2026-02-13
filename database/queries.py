"""
Database queries for Customer Success AI
Contains async functions for common database operations using asyncpg
"""

import asyncpg
import uuid
from typing import Dict, List, Optional, Union
from datetime import datetime


class DatabaseManager:
    """
    Database manager for Customer Success AI system
    Handles all database operations with asyncpg
    """
    
    def __init__(self, dsn: str):
        """
        Initialize the database manager
        
        Args:
            dsn: Database connection string
        """
        self.dsn = dsn
        self.pool = None
    
    async def connect(self):
        """
        Establish connection pool to the database
        """
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=1,
            max_size=10,
            command_timeout=60
        )
    
    async def close(self):
        """
        Close the database connection pool
        """
        if self.pool:
            await self.pool.close()
    
    async def get_or_create_customer(self, email: str, phone: str = None, name: str = None) -> uuid.UUID:
        """
        Get existing customer or create new one if not found
        
        Args:
            email: Customer's email address
            phone: Customer's phone number (optional)
            name: Customer's name (optional)
            
        Returns:
            UUID of the customer record
        """
        async with self.pool.acquire() as conn:
            try:
                # Try to find existing customer
                query = """
                    SELECT id FROM customers 
                    WHERE email = $1
                """
                result = await conn.fetchrow(query, email)
                
                if result:
                    return result['id']
                
                # Create new customer
                query = """
                    INSERT INTO customers (email, phone, name)
                    VALUES ($1, $2, $3)
                    RETURNING id
                """
                result = await conn.fetchrow(query, email, phone, name)
                return result['id']
            
            except asyncpg.UniqueViolationError:
                # Handle race condition where another request created the customer
                query = """
                    SELECT id FROM customers 
                    WHERE email = $1
                """
                result = await conn.fetchrow(query, email)
                return result['id'] if result else None
    
    async def get_customer_by_identifier(self, identifier_type: str, value: str) -> Optional[Dict]:
        """
        Get customer by identifier (email, phone, whatsapp)
        
        Args:
            identifier_type: Type of identifier ('email', 'phone', 'whatsapp')
            value: Value of the identifier
            
        Returns:
            Customer record as dictionary or None if not found
        """
        async with self.pool.acquire() as conn:
            # First, get the customer_id from customer_identifiers
            query = """
                SELECT customer_id FROM customer_identifiers 
                WHERE identifier_type = $1 AND identifier_value = $2
            """
            result = await conn.fetchrow(query, identifier_type, value)
            
            if not result:
                # If not found in identifiers, try direct email match
                if identifier_type == 'email':
                    query = """
                        SELECT id FROM customers 
                        WHERE email = $1
                    """
                    result = await conn.fetchrow(query, value)
                    if not result:
                        return None
                    customer_id = result['id']
                else:
                    return None
            else:
                customer_id = result['customer_id']
            
            # Get full customer details
            query = """
                SELECT id, email, phone, name, created_at, metadata 
                FROM customers 
                WHERE id = $1
            """
            customer = await conn.fetchrow(query, customer_id)
            
            if customer:
                # Get all identifiers for this customer
                query = """
                    SELECT identifier_type, identifier_value, verified, created_at 
                    FROM customer_identifiers 
                    WHERE customer_id = $1
                """
                identifiers = await conn.fetch(query, customer_id)
                
                customer_dict = dict(customer)
                customer_dict['identifiers'] = [dict(row) for row in identifiers]
                return customer_dict
            
            return None
    
    async def create_conversation(self, customer_id: uuid.UUID, channel: str) -> uuid.UUID:
        """
        Create a new conversation record
        
        Args:
            customer_id: UUID of the customer
            channel: Channel of the conversation ('email', 'whatsapp', 'web_form')
            
        Returns:
            UUID of the created conversation
        """
        async with self.pool.acquire() as conn:
            query = """
                INSERT INTO conversations (customer_id, initial_channel)
                VALUES ($1, $2)
                RETURNING id
            """
            result = await conn.fetchrow(query, customer_id, channel)
            return result['id']
    
    async def get_conversation_history(self, conversation_id: uuid.UUID) -> List[Dict]:
        """
        Get all messages in a conversation
        
        Args:
            conversation_id: UUID of the conversation
            
        Returns:
            List of message dictionaries
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT id, channel, direction, role, content, created_at, 
                       tokens_used, latency_ms, tool_calls, channel_message_id, delivery_status
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
            """
            rows = await conn.fetch(query, conversation_id)
            return [dict(row) for row in rows]
    
    async def store_message(self, conversation_id: uuid.UUID, **kwargs) -> uuid.UUID:
        """
        Store a message in the database
        
        Args:
            conversation_id: UUID of the conversation
            **kwargs: Message properties (channel, direction, role, content, etc.)
            
        Returns:
            UUID of the created message
        """
        async with self.pool.acquire() as conn:
            # Extract message properties with defaults
            channel = kwargs.get('channel')
            direction = kwargs.get('direction')
            role = kwargs.get('role')
            content = kwargs.get('content')
            tokens_used = kwargs.get('tokens_used')
            latency_ms = kwargs.get('latency_ms')
            tool_calls = kwargs.get('tool_calls', [])
            channel_message_id = kwargs.get('channel_message_id')
            delivery_status = kwargs.get('delivery_status', 'pending')
            
            query = """
                INSERT INTO messages (
                    conversation_id, channel, direction, role, content,
                    tokens_used, latency_ms, tool_calls, channel_message_id, delivery_status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
            """
            result = await conn.fetchrow(
                query, conversation_id, channel, direction, role, content,
                tokens_used, latency_ms, tool_calls, channel_message_id, delivery_status
            )
            return result['id']
    
    async def create_ticket(self, customer_id: uuid.UUID, **kwargs) -> uuid.UUID:
        """
        Create a support ticket
        
        Args:
            customer_id: UUID of the customer
            **kwargs: Ticket properties (conversation_id, source_channel, category, etc.)
            
        Returns:
            UUID of the created ticket
        """
        async with self.pool.acquire() as conn:
            # Extract ticket properties with defaults
            conversation_id = kwargs.get('conversation_id')
            source_channel = kwargs.get('source_channel')
            category = kwargs.get('category')
            priority = kwargs.get('priority', 'medium')
            status = kwargs.get('status', 'open')
            resolution_notes = kwargs.get('resolution_notes')
            
            query = """
                INSERT INTO tickets (
                    conversation_id, customer_id, source_channel, category,
                    priority, status, resolution_notes
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """
            result = await conn.fetchrow(
                query, conversation_id, customer_id, source_channel, category,
                priority, status, resolution_notes
            )
            return result['id']
    
    async def search_knowledge_base(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """
        Semantic search in the knowledge base using vector similarity
        
        Args:
            query_embedding: Embedding vector of the search query
            limit: Maximum number of results to return
            
        Returns:
            List of knowledge base entries with similarity scores
        """
        async with self.pool.acquire() as conn:
            # Convert the embedding list to the format expected by PostgreSQL
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            query = """
                SELECT id, title, content, category, 
                       1 - (embedding <=> $1::vector) AS similarity
                FROM knowledge_base
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """
            rows = await conn.fetch(query, embedding_str, limit)
            
            results = []
            for row in rows:
                results.append({
                    'id': row['id'],
                    'title': row['title'],
                    'content': row['content'],
                    'category': row['category'],
                    'similarity': row['similarity']
                })
            
            return results


# Convenience functions for common operations
async def get_or_create_customer(db_manager: DatabaseManager, email: str, phone: str = None, name: str = None) -> uuid.UUID:
    """
    Get existing customer or create new one if not found
    """
    return await db_manager.get_or_create_customer(email, phone, name)


async def get_customer_by_identifier(db_manager: DatabaseManager, identifier_type: str, value: str) -> Optional[Dict]:
    """
    Get customer by identifier (email, phone, whatsapp)
    """
    return await db_manager.get_customer_by_identifier(identifier_type, value)


async def create_conversation(db_manager: DatabaseManager, customer_id: uuid.UUID, channel: str) -> uuid.UUID:
    """
    Create a new conversation record
    """
    return await db_manager.create_conversation(customer_id, channel)


async def get_conversation_history(db_manager: DatabaseManager, conversation_id: uuid.UUID) -> List[Dict]:
    """
    Get all messages in a conversation
    """
    return await db_manager.get_conversation_history(conversation_id)


async def store_message(db_manager: DatabaseManager, conversation_id: uuid.UUID, **kwargs) -> uuid.UUID:
    """
    Store a message in the database
    """
    return await db_manager.store_message(conversation_id, **kwargs)


async def create_ticket(db_manager: DatabaseManager, customer_id: uuid.UUID, **kwargs) -> uuid.UUID:
    """
    Create a support ticket
    """
    return await db_manager.create_ticket(customer_id, **kwargs)


async def search_knowledge_base(db_manager: DatabaseManager, query_embedding: List[float], limit: int = 5) -> List[Dict]:
    """
    Semantic search in the knowledge base using vector similarity
    """
    return await db_manager.search_knowledge_base(query_embedding, limit)