"""
Unified Message Processor Worker
Processes messages from all channels (email, whatsapp, web_form) through the customer success agent
"""

import asyncio
import asyncpg
import logging
import json
import sys
import signal
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

from agent.production_agent import CustomerSuccessAgent
from channels.gmail_handler import GmailHandler
from channels.whatsapp_handler import WhatsAppHandler
from infrastructure.redis_queue import RedisConsumer
from database.queries import DatabaseManager


# Initialize logger
logger = logging.getLogger(__name__)


class UnifiedMessageProcessor:
    """
    Unified message processor that handles incoming messages from all channels.
    
    Example usage:
    ```python
    processor = UnifiedMessageProcessor()
    await processor.start()
    ```
    """
    
    def __init__(self):
        """Initialize the message processor with all required components."""
        self.agent = CustomerSuccessAgent()
        self.redis_consumer = RedisConsumer()
        self.gmail_handler = GmailHandler(credentials_path="path/to/credentials.json")
        self.whatsapp_handler = WhatsAppHandler()
        self.db_manager = DatabaseManager(dsn="postgresql://username:password@localhost/customer_success_db")
        self.running = False
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
    
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing message processor...")
        
        # Connect to database
        await self.db_manager.connect()
        
        # Connect to Redis
        # In a real implementation, we would initialize the Redis consumer
        
        logger.info("Message processor initialized successfully")
    
    async def start(self):
        """Start the message processor worker."""
        logger.info("Starting message processor worker...")
        
        self.running = True
        
        # Set up graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutdown signal received")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start consuming messages
        await self._consume_messages()
    
    async def _consume_messages(self):
        """Main message consumption loop."""
        logger.info("Starting message consumption from 'tickets:incoming' stream")
        
        # In a real implementation, we would use the Redis consumer
        # For now, we'll simulate the consumption
        while self.running:
            try:
                # Simulate message consumption
                # In a real implementation, this would be:
                # await self.redis_consumer.start('tickets:incoming', self.process_message)
                
                # For demo purposes, we'll just sleep
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in message consumption loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retrying
    
    async def process_message(self, stream: str, message: dict):
        """
        Main processing pipeline for incoming messages.
        
        Flow:
        1. Extract channel and message data
        2. Resolve or create customer (unified across channels)
        3. Get or create active conversation
        4. Store incoming message in database
        5. Load conversation history
        6. Build context for agent
        7. Run agent with tools
        8. Store agent response
        9. Calculate and publish metrics
        10. Handle escalations if needed
        
        Handles all errors gracefully - no message loss.
        """
        start_time = datetime.utcnow()
        
        try:
            # Extract channel
            channel = message.get('channel', 'unknown')
            message_id = message.get('channel_message_id', 'unknown')
            logger.info(f"Processing {channel} message", extra={'message_id': message_id})
            
            # Step 1: Resolve customer
            customer_id = await self.resolve_customer(message)
            logger.debug(f"Customer resolved: {customer_id}")
            
            # Step 2: Get or create conversation
            conversation_id = await self.get_or_create_conversation(
                customer_id=customer_id,
                channel=channel,
                message=message
            )
            logger.debug(f"Conversation: {conversation_id}")
            
            # Step 3: Store incoming message
            await self.store_message(
                conversation_id=conversation_id,
                channel=channel,
                direction='inbound',
                role='customer',
                content=message.get('content', ''),
                channel_message_id=message.get('channel_message_id'),
                metadata=message.get('metadata', {})
            )
            
            # Step 4: Load conversation history
            history = await self.load_conversation_history(conversation_id)
            
            # Step 5: Build agent context
            context = {
                'customer_id': customer_id,
                'conversation_id': conversation_id,
                'channel': channel,
                'ticket_subject': message.get('subject', 'Support Request'),
                'metadata': message.get('metadata', {})
            }
            
            # Step 6: Run agent
            logger.info(f"Running agent for conversation {conversation_id}")
            result = await self.agent.run(
                messages=history,
                context=context
            )
            
            # Step 7: Store agent response
            await self.store_message(
                conversation_id=conversation_id,
                channel=channel,
                direction='outbound',
                role='agent',
                content=result['output'],
                tool_calls=result.get('tool_calls', []),
                metadata={'escalated': result.get('escalated', False)}
            )
            
            # Step 8: Calculate metrics
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Step 9: Publish metrics
            await self.publish_metrics({
                'event_type': 'message_processed',
                'channel': channel,
                'latency_ms': latency_ms,
                'escalated': result.get('escalated', False),
                'tool_calls_count': len(result.get('tool_calls', [])),
                'customer_id': customer_id,
                'conversation_id': conversation_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Message processed successfully in {latency_ms:.0f}ms")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await self.handle_error(message, e)
    
    async def resolve_customer(self, message: dict) -> str:
        """
        Identify or create customer from message identifiers.
        
        Logic:
        - Email messages: Use email address as primary identifier
        - WhatsApp: Use phone number
        - Web form: Use email address
        
        If customer exists with that identifier → return existing customer_id
        If not → create new customer
        
        Handle cross-channel identification:
        - If email matches existing customer → link phone to that customer
        - If phone matches existing customer → link email to that customer
        """
        async with self.db_manager.pool.acquire() as conn:
            email = message.get('customer_email')
            phone = message.get('customer_phone')
            name = message.get('customer_name', '')
            
            # Try email first
            if email:
                customer = await conn.fetchrow(
                    "SELECT id FROM customers WHERE email = $1", 
                    email.lower()
                )
                if customer:
                    # Link phone if provided and not already linked
                    if phone:
                        await conn.execute("""
                            INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
                            VALUES ($1, 'whatsapp', $2)
                            ON CONFLICT (identifier_type, identifier_value) DO NOTHING
                        """, customer['id'], phone)
                    return str(customer['id'])
            
            # Try phone
            if phone:
                identifier = await conn.fetchrow("""
                    SELECT customer_id FROM customer_identifiers
                    WHERE identifier_type = 'whatsapp' AND identifier_value = $1
                """, phone)
                if identifier:
                    # Link email if provided and not already linked
                    if email:
                        await conn.execute(
                            "UPDATE customers SET email = $1 WHERE id = $2 AND email IS NULL",
                            email.lower(), identifier['customer_id']
                        )
                    return str(identifier['customer_id'])
            
            # Create new customer
            customer_id = await conn.fetchval("""
                INSERT INTO customers (email, phone, name)
                VALUES ($1, $2, $3)
                RETURNING id
            """, email.lower() if email else None, phone, name)
            
            # Add identifiers
            if email:
                await conn.execute("""
                    INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
                    VALUES ($1, 'email', $2)
                """, customer_id, email.lower())
            
            if phone:
                await conn.execute("""
                    INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
                    VALUES ($1, 'whatsapp', $2)
                """, customer_id, phone)
            
            logger.info(f"Created new customer: {customer_id}")
            return str(customer_id)
    
    async def get_or_create_conversation(self, customer_id: str, channel: str, message: dict) -> str:
        """
        Get active conversation or create new one.
        
        Active conversation = started within last 24 hours and status is 'active'
        If no active conversation exists, create new one.
        """
        async with self.db_manager.pool.acquire() as conn:
            # Check for active conversation
            conversation = await conn.fetchrow("""
                SELECT id FROM conversations
                WHERE customer_id = $1
                  AND status = 'active'
                  AND started_at > NOW() - INTERVAL '24 hours'
                ORDER BY started_at DESC
                LIMIT 1
            """, customer_id)
            
            if conversation:
                return str(conversation['id'])
            
            # Create new conversation
            conversation_id = await conn.fetchval("""
                INSERT INTO conversations (customer_id, initial_channel, status)
                VALUES ($1, $2, 'active')
                RETURNING id
            """, customer_id, channel)
            
            logger.info(f"Created new conversation: {conversation_id}")
            return str(conversation_id)
    
    async def load_conversation_history(self, conversation_id: str) -> List[dict]:
        """
        Load conversation history in OpenAI message format.
        
        Returns:
        [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            ...
        ]
        """
        async with self.db_manager.pool.acquire() as conn:
            messages = await conn.fetch("""
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
            """, conversation_id)
        
        history = []
        for msg in messages:
            # Map our roles to OpenAI roles
            role = 'user' if msg['role'] == 'customer' else 'assistant'
            history.append({
                'role': role,
                'content': msg['content']
            })
        
        return history
    
    async def store_message(
        self,
        conversation_id: str,
        channel: str,
        direction: str,
        role: str,
        content: str,
        channel_message_id: str = None,
        tool_calls: List = None,
        metadata: Dict = None
    ):
        """Store message in database with all metadata"""
        async with self.db_manager.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO messages (
                    conversation_id,
                    channel,
                    direction,
                    role,
                    content,
                    channel_message_id,
                    tool_calls,
                    metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, conversation_id, channel, direction, role, content,
                 channel_message_id, json.dumps(tool_calls or []), json.dumps(metadata or {}))
    
    async def publish_metrics(self, metrics: dict):
        """Publish metrics to Redis metrics stream"""
        try:
            # In a real implementation, we would publish to Redis
            # For now, just log the metrics
            logger.info(f"Metrics: {json.dumps(metrics)}")
        except Exception as e:
            logger.error(f"Failed to publish metrics: {e}")
            # Don't fail the whole pipeline if metrics fail
    
    async def handle_error(self, message: dict, error: Exception):
        """
        Handle processing errors gracefully.
        
        Actions:
        1. Log detailed error
        2. Send apologetic response to customer
        3. Create escalation ticket
        4. Publish error metric
        """
        logger.error(f"Message processing failed: {error}", extra={
            'message': message,
            'error_type': type(error).__name__
        })
        
        # Send apologetic response
        channel = message.get('channel', 'unknown')
        customer_email = message.get('customer_email', 'unknown')
        customer_phone = message.get('customer_phone', 'unknown')
        
        apology = "I apologize, but I'm having trouble processing your request right now. A human support agent will follow up with you shortly."
        
        try:
            if channel == 'email' and customer_email != 'unknown':
                await self.gmail_handler.send_reply(
                    to_email=customer_email,
                    subject=message.get('subject', 'Support Request'),
                    body=apology
                )
            elif channel == 'whatsapp' and customer_phone != 'unknown':
                await self.whatsapp_handler.send_message(
                    to_phone=customer_phone,
                    body=apology
                )
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")
        
        # Publish to escalations
        try:
            # In a real implementation, we would publish to Redis
            logger.info(f"Escalation published: {message}")
        except Exception as e:
            logger.error(f"Failed to publish escalation: {e}")
        
        # Publish error metric
        await self.publish_metrics({
            'event_type': 'processing_error',
            'channel': channel,
            'error_type': type(error).__name__,
            'timestamp': datetime.utcnow().isoformat()
        })


async def main():
    """Main entry point for the worker"""
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize processor
    processor = UnifiedMessageProcessor()
    
    # Graceful shutdown handling
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        # Cleanup code here
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start processing
    logger.info("Starting message processor worker...")
    await processor.start()


if __name__ == "__main__":
    asyncio.run(main())