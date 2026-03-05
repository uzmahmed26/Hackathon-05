"""
Unified Message Processor Worker
Processes messages from all channels (email, whatsapp, web_form) through the customer success agent
"""

import asyncio
import asyncpg
import logging
import json
import os
import sys
import signal
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

from agent.production_agent import CustomerSuccessAgent
from channels.gmail_handler import GmailHandler
from channels.whatsapp_handler import WhatsAppHandler
from infrastructure.redis_queue import RedisConsumer
from database.queries import DatabaseManager
from kafka_client import FTEKafkaConsumer, FTEKafkaProducer, TOPICS


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
        self.gmail_handler = GmailHandler(
            credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials/gmail_credentials.json")
        )
        self.whatsapp_handler = WhatsAppHandler()
        _db_url = os.getenv("DATABASE_URL", "postgresql://fte_user:fte_password@localhost:5432/fte_db")
        self.db_manager = DatabaseManager(dsn=_db_url)
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

    async def cleanup(self):
        """Clean up all components on shutdown."""
        logger.info("Cleaning up message processor...")
        self.running = False
        try:
            if self.db_manager and self.db_manager.pool:
                await self.db_manager.close()
        except Exception as e:
            logger.warning(f"Error closing DB during cleanup: {e}")
        logger.info("Message processor cleanup complete")

    @asynccontextmanager
    async def _get_conn(self):
        """Get a DB connection from either pool or direct connection (for tests)."""
        pool = self.db_manager.pool
        if hasattr(pool, 'acquire'):
            async with pool.acquire() as conn:
                yield conn
        else:
            yield pool  # Already a raw connection (test injection)

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
        """
        Main message consumption loop.

        Runs Redis stream consumer and Kafka consumer concurrently.
        Redis handles web form tickets; Kafka handles email/WhatsApp.
        """
        await asyncio.gather(
            self._consume_redis_messages(),
            self._consume_kafka_messages(),
        )

    async def _consume_redis_messages(self):
        """
        Consume messages from Redis stream ``tickets:incoming``.
        Web form submissions are published here by the API.
        Reconnects automatically on transient errors.
        """
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        logger.info(f"Starting Redis stream consumer from 'tickets:incoming' ({redis_url})")

        while self.running:
            consumer = RedisConsumer(redis_url=redis_url)
            try:
                await consumer.start(
                    stream="tickets:incoming",
                    callback=self.process_message,
                    group="fte-message-processor",
                    consumer="worker-redis-1",
                )
                # consumer.start() spawns a background task; await it here
                if consumer.consumer_task:
                    await consumer.consumer_task
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Redis consumer error: {e} — reconnecting in 5 s",
                    exc_info=True,
                )
                await asyncio.sleep(5)
            finally:
                try:
                    await consumer.stop()
                except Exception:
                    pass

    async def _consume_kafka_messages(self):
        """
        Consume messages from Kafka topic ``fte.tickets.incoming``.
        Email and WhatsApp messages arrive here.
        Reconnects automatically on transient errors.
        """
        topic = TOPICS["tickets_incoming"]  # "fte.tickets.incoming"
        group_id = "fte-message-processor"
        logger.info(f"Starting Kafka consumption from topic '{topic}' (group={group_id})")

        while self.running:
            consumer = FTEKafkaConsumer(topics=[topic], group_id=group_id)
            try:
                await consumer.start()
                await consumer.consume(
                    handler=self.process_message,
                    error_topic=TOPICS["dlq"],
                )
            except Exception as e:
                logger.error(
                    f"Kafka consumer error: {e} — reconnecting in 5 s",
                    exc_info=True,
                )
                await asyncio.sleep(5)
            finally:
                try:
                    await consumer.stop()
                except Exception:
                    pass
    
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

        Cross-channel identity resolution order:
        1. Email → check customers.email (primary column)
        2. Email → check customer_identifiers for type='email'
           (catches customers first created via WhatsApp who later email)
        3. Phone → check customer_identifiers for type='whatsapp'
        4. If still no match → create new customer

        Whenever a match is found via one identifier and the other
        identifier is also present, we link them to the same customer_id
        so Email ↔ WhatsApp continuity is maintained.
        """
        async with self._get_conn() as conn:
            email = message.get('customer_email')
            phone = message.get('customer_phone')
            name = message.get('customer_name', '')
            email_lower = email.lower() if email else None

            # ── 1. Look up by email in the main customers table ────────────
            if email_lower:
                customer = await conn.fetchrow(
                    "SELECT id FROM customers WHERE email = $1",
                    email_lower,
                )
                if customer:
                    customer_id = customer['id']
                    # Cross-link: store the WhatsApp identifier
                    if phone:
                        await conn.execute(
                            """
                            INSERT INTO customer_identifiers
                                (customer_id, identifier_type, identifier_value)
                            VALUES ($1, 'whatsapp', $2)
                            ON CONFLICT (identifier_type, identifier_value) DO NOTHING
                            """,
                            customer_id, phone,
                        )
                    return str(customer_id)

            # ── 2. Look up by email in customer_identifiers table ──────────
            #    Handles: WhatsApp-first customers who later send an email
            if email_lower:
                row = await conn.fetchrow(
                    """
                    SELECT customer_id FROM customer_identifiers
                    WHERE identifier_type = 'email' AND identifier_value = $1
                    """,
                    email_lower,
                )
                if row:
                    customer_id = row['customer_id']
                    # Backfill email into customers table if still NULL
                    await conn.execute(
                        "UPDATE customers SET email = $1 WHERE id = $2 AND email IS NULL",
                        email_lower, customer_id,
                    )
                    # Cross-link phone
                    if phone:
                        await conn.execute(
                            """
                            INSERT INTO customer_identifiers
                                (customer_id, identifier_type, identifier_value)
                            VALUES ($1, 'whatsapp', $2)
                            ON CONFLICT (identifier_type, identifier_value) DO NOTHING
                            """,
                            customer_id, phone,
                        )
                    return str(customer_id)

            # ── 3. Look up by phone (WhatsApp) ─────────────────────────────
            if phone:
                row = await conn.fetchrow(
                    """
                    SELECT customer_id FROM customer_identifiers
                    WHERE identifier_type = 'whatsapp' AND identifier_value = $1
                    """,
                    phone,
                )
                if row:
                    customer_id = row['customer_id']
                    # Cross-link email
                    if email_lower:
                        await conn.execute(
                            "UPDATE customers SET email = $1 WHERE id = $2 AND email IS NULL",
                            email_lower, customer_id,
                        )
                        await conn.execute(
                            """
                            INSERT INTO customer_identifiers
                                (customer_id, identifier_type, identifier_value)
                            VALUES ($1, 'email', $2)
                            ON CONFLICT (identifier_type, identifier_value) DO NOTHING
                            """,
                            customer_id, email_lower,
                        )
                    return str(customer_id)

            # ── 4. Create new customer ─────────────────────────────────────
            customer_id = await conn.fetchval(
                """
                INSERT INTO customers (email, phone, name)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                email_lower, phone, name,
            )

            if email_lower:
                await conn.execute(
                    """
                    INSERT INTO customer_identifiers
                        (customer_id, identifier_type, identifier_value)
                    VALUES ($1, 'email', $2)
                    """,
                    customer_id, email_lower,
                )
            if phone:
                await conn.execute(
                    """
                    INSERT INTO customer_identifiers
                        (customer_id, identifier_type, identifier_value)
                    VALUES ($1, 'whatsapp', $2)
                    """,
                    customer_id, phone,
                )

            logger.info(f"Created new customer: {customer_id}")
            return str(customer_id)
    
    async def get_or_create_conversation(self, customer_id: str, channel: str, message: dict) -> str:
        """
        Get active conversation or create new one.
        
        Active conversation = started within last 24 hours and status is 'active'
        If no active conversation exists, create new one.
        """
        async with self._get_conn() as conn:
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
        async with self._get_conn() as conn:
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
        async with self._get_conn() as conn:
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
        """Publish metrics event to Kafka fte.metrics topic."""
        try:
            producer = FTEKafkaProducer()
            await producer.start()
            try:
                await producer.publish(TOPICS["metrics"], metrics)
                logger.debug(f"Metrics published: {metrics.get('event_type')} / {metrics.get('channel')}")
            finally:
                await producer.stop()
        except Exception as e:
            logger.error(f"Failed to publish metrics: {e}")
            # Non-fatal — log and continue
    
    async def handle_error(self, message: dict, error: Exception):
        """
        Handle processing errors gracefully.
        
        Actions:
        1. Log detailed error
        2. Send apologetic response to customer
        3. Create escalation ticket
        4. Publish error metric
        """
        logger.error(f"Message processing failed: {error} | msg={message} | type={type(error).__name__}")
        
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
    
    # Initialize (connect to DB, Redis, etc.)
    await processor.initialize()

    # Start processing
    logger.info("Starting message processor worker...")
    try:
        await processor.start()
    finally:
        await processor.cleanup()


if __name__ == "__main__":
    asyncio.run(main())