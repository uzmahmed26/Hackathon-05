"""
Redis-based message queue system for Customer Success AI
Implements Redis Streams with consumer groups, retry logic, and dead letter queue
"""

import redis.asyncio as aioredis
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional
from enum import Enum


class StreamNames(Enum):
    """Enumeration of Redis stream names."""
    TICKETS_INCOMING = "tickets:incoming"
    TICKETS_EMAIL = "tickets:email"
    TICKETS_WHATSAPP = "tickets:whatsapp"
    TICKETS_WEBFORM = "tickets:webform"
    ESCALATIONS = "escalations"
    METRICS = "metrics"
    DLQ = "dlq"


class RedisQueue:
    """
    Redis-based message queue system using Redis Streams.
    
    Example usage:
    ```python
    async with RedisQueue() as queue:
        # Publish a message
        msg_id = await queue.publish(StreamNames.TICKETS_INCOMING.value, {
            'ticket_id': '123',
            'customer_id': '456',
            'content': 'Customer needs help'
        })
        
        # Consume messages
        async def process_message(stream_name, message_data):
            print(f"Processing message from {stream_name}: {message_data}")
            # Your processing logic here
        
        await queue.consume(
            stream=StreamNames.TICKETS_INCOMING.value,
            group='ticket_processors',
            consumer='processor_1',
            callback=process_message
        )
    ```
    """
    
    def __init__(self, redis_url: str = None, max_retries: int = 3):
        """
        Initialize the Redis queue.
        
        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var)
            max_retries: Maximum number of retries before moving to DLQ
        """
        self.redis_url = redis_url or "redis://localhost:6379"
        self.max_retries = max_retries
        self.client = None
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self):
        """Enter the async context manager."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        if self.client:
            await self.client.close()
    
    async def connect(self):
        """Establish connection to Redis and create consumer groups."""
        try:
            self.client = aioredis.from_url(self.redis_url, decode_responses=True)
            
            # Test connection
            await self.client.ping()
            self.logger.info("Connected to Redis successfully")
            
            # Create consumer groups for all streams
            for stream in StreamNames:
                await self.create_consumer_group(stream.value, f"group_{stream.name.lower()}")
            
            self.logger.info("Redis queue system initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def publish(self, stream: str, message: dict) -> str:
        """
        Publish a message to a Redis stream.
        
        Args:
            stream: Name of the stream to publish to
            message: Dictionary containing the message data
            
        Returns:
            Message ID assigned by Redis
        """
        try:
            # Add metadata to the message
            message['_timestamp'] = datetime.utcnow().isoformat()
            message['_message_id'] = str(uuid.uuid4())
            message['_retry_count'] = 0
            
            # Publish to Redis stream
            message_id = await self.client.xadd(
                stream,
                fields=message,
                maxlen=10000,  # Keep last 10k messages
                approximate=True
            )
            
            # Log the publication
            await self._log_metric('messages_published', {
                'stream': stream,
                'message_id': message_id,
                'timestamp': message['_timestamp']
            })
            
            self.logger.debug(f"Published message to {stream}: {message_id}")
            return message_id
        except Exception as e:
            self.logger.error(f"Failed to publish message to {stream}: {e}")
            raise
    
    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        callback: Callable,
        count: int = 10,
        block: int = 5000
    ):
        """
        Consume messages from a Redis stream using consumer groups.
        
        Args:
            stream: Name of the stream to consume from
            group: Consumer group name
            consumer: Consumer name
            callback: Async function to process messages
            count: Max number of messages to read per call
            block: Milliseconds to block waiting for messages
        """
        self.logger.info(f"Starting consumer {consumer} in group {group} for stream {stream}")
        
        while True:
            try:
                # Read messages from the consumer group
                messages = await self.client.xreadgroup(
                    groupname=group,
                    consumername=consumer,
                    streams={stream: '>'},  # '>' means read new messages only
                    count=count,
                    block=block
                )
                
                # Process messages if any were returned
                if messages:
                    for stream_name, message_list in messages:
                        for message_id, message_data in message_list:
                            try:
                                await callback(stream_name, message_data)
                                
                                # Acknowledge successful processing
                                await self.client.xack(stream_name, group, message_id)
                                
                                # Log successful processing
                                await self._log_metric('messages_processed', {
                                    'stream': stream_name,
                                    'message_id': message_id,
                                    'consumer': consumer,
                                    'timestamp': datetime.utcnow().isoformat()
                                })
                                
                                self.logger.debug(f"Successfully processed message {message_id} from {stream_name}")
                                
                            except Exception as e:
                                self.logger.error(f"Error processing message {message_id}: {e}")
                                await self._handle_error(stream_name, message_id, message_data, e)
                
            except Exception as e:
                self.logger.error(f"Error in consumer loop: {e}")
                # Wait before retrying to avoid tight loop
                await asyncio.sleep(1)
    
    async def _handle_error(self, stream: str, message_id: str, message: dict, error: Exception):
        """
        Handle errors during message processing.
        
        Args:
            stream: Stream name where the error occurred
            message_id: ID of the message that failed
            message: The message data
            error: The exception that occurred
        """
        try:
            retry_count = int(message.get('_retry_count', 0)) + 1
            
            if retry_count < self.max_retries:
                # Increment retry count and re-publish to the same stream
                message['_retry_count'] = retry_count
                message['_last_error'] = str(error)
                message['_last_error_timestamp'] = datetime.utcnow().isoformat()
                
                # Add a small delay before retrying
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                
                await self.publish(stream, message)
                
                self.logger.warning(f"Message {message_id} failed, retrying ({retry_count}/{self.max_retries}): {error}")
                
                # Log retry
                await self._log_metric('messages_retried', {
                    'stream': stream,
                    'message_id': message_id,
                    'retry_count': retry_count,
                    'error': str(error),
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                # Move to dead letter queue
                message['_final_error'] = str(error)
                message['_failed_stream'] = stream
                message['_failure_timestamp'] = datetime.utcnow().isoformat()
                
                await self.publish(StreamNames.DLQ.value, message)
                
                self.logger.error(f"Message {message_id} failed permanently after {retry_count} retries, moved to DLQ: {error}")
                
                # Log DLQ entry
                await self._log_metric('messages_dlq', {
                    'stream': stream,
                    'message_id': message_id,
                    'retry_count': retry_count,
                    'error': str(error),
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        except Exception as e:
            self.logger.error(f"Error handling failed message {message_id}: {e}")
    
    async def create_consumer_group(self, stream: str, group: str):
        """
        Create a consumer group for a stream if it doesn't exist.
        
        Args:
            stream: Stream name
            group: Consumer group name
        """
        try:
            # Try to create the consumer group
            await self.client.xgroup_create(stream, group, id='0', mkstream=True)
            self.logger.info(f"Created consumer group '{group}' for stream '{stream}'")
        except aioredis.exceptions.ResponseError as e:
            if 'BUSYGROUP' in str(e):
                # Group already exists, which is fine
                self.logger.debug(f"Consumer group '{group}' already exists for stream '{stream}'")
            else:
                raise
    
    async def get_stream_info(self, stream: str) -> dict:
        """
        Get information about a Redis stream.
        
        Args:
            stream: Stream name
            
        Returns:
            Dictionary with stream information
        """
        try:
            info = await self.client.xinfo_stream(stream)
            return {
                'length': info['length'],
                'groups': info['groups'],
                'first_entry': info['first-entry'],
                'last_entry': info['last-entry'],
                'radix_tree_keys': info['radix-tree-keys'],
                'radix_tree_nodes': info['radix-tree-nodes']
            }
        except Exception as e:
            self.logger.error(f"Error getting stream info for {stream}: {e}")
            return {}
    
    async def get_pending_messages(self, stream: str, group: str) -> List[dict]:
        """
        Get messages that are pending acknowledgment in a consumer group.
        
        Args:
            stream: Stream name
            group: Consumer group name
            
        Returns:
            List of pending messages with ID and metadata
        """
        try:
            pending = await self.client.xpending_range(
                stream, group, min='-',
                max='+', count=100  # Limit to 100 pending messages
            )
            
            result = []
            for msg in pending:
                result.append({
                    'message_id': msg['id'],
                    'consumer': msg['consumer'],
                    'idle_time_ms': msg['time_since_delivered'],
                    'deliveries': msg['times_delivered']
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error getting pending messages for {stream}/{group}: {e}")
            return []
    
    async def claim_pending(
        self,
        stream: str,
        group: str,
        consumer: str,
        min_idle_time: int = 60000  # 1 minute in milliseconds
    ) -> List[dict]:
        """
        Claim messages that have been pending for too long.
        
        Args:
            stream: Stream name
            group: Consumer group name
            consumer: Consumer name to claim for
            min_idle_time: Minimum idle time in milliseconds
            
        Returns:
            List of claimed messages
        """
        try:
            # Get IDs of messages that have been idle for at least min_idle_time
            pending = await self.client.xpending(
                stream, group, min_idle_time, '-', '+', 100
            )
            
            if not pending:
                return []
            
            # Extract message IDs
            message_ids = [msg['id'] for msg in pending]
            
            # Claim the messages
            claimed = await self.client.xclaim(
                stream, group, consumer, min_idle_time,
                message_ids, justid=True
            )
            
            self.logger.info(f"Claimed {len(claimed)} pending messages for {consumer}")
            return claimed
        except Exception as e:
            self.logger.error(f"Error claiming pending messages for {stream}/{group}: {e}")
            return []
    
    async def _log_metric(self, metric_name: str, data: dict):
        """
        Log a metric to the metrics stream.
        
        Args:
            metric_name: Name of the metric
            data: Metric data to log
        """
        try:
            metric_data = {
                'metric_name': metric_name,
                'data': str(data),  # Convert to string to ensure serializability
                'timestamp': datetime.utcnow().isoformat()
            }
            await self.publish(StreamNames.METRICS.value, metric_data)
        except Exception as e:
            self.logger.error(f"Error logging metric {metric_name}: {e}")


class RedisProducer:
    """
    Simplified interface for publishing messages to Redis streams.
    
    Example usage:
    ```python
    producer = RedisProducer()
    await producer.publish('tickets:incoming', {'ticket_id': '123'})
    ```
    """
    
    def __init__(self, redis_url: str = None):
        """
        Initialize the Redis producer.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url or "redis://localhost:6379"
        self.client = None
        self._connected = False
        self.logger = logging.getLogger(__name__)
    
    async def connect(self):
        """Establish connection to Redis."""
        await self._ensure_connection()

    async def disconnect(self):
        """Close the Redis connection."""
        if self.client:
            await self.client.aclose()
            self._connected = False

    async def _ensure_connection(self):
        """Ensure Redis connection is established."""
        if not self._connected or not self.client:
            self.client = aioredis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            self._connected = True
    
    async def publish(self, stream: str, message: dict) -> str:
        """
        Publish a single message to a stream.
        
        Args:
            stream: Stream name
            message: Message data
            
        Returns:
            Message ID
        """
        await self._ensure_connection()
        
        try:
            # Add metadata
            message['_timestamp'] = datetime.utcnow().isoformat()
            message['_message_id'] = str(uuid.uuid4())
            message['_producer'] = 'RedisProducer'
            
            # Publish
            message_id = await self.client.xadd(stream, fields=message)
            self.logger.debug(f"Published message to {stream}: {message_id}")
            return message_id
        except Exception as e:
            self.logger.error(f"Failed to publish message to {stream}: {e}")
            raise
    
    async def publish_batch(self, stream: str, messages: List[dict]) -> List[str]:
        """
        Publish multiple messages to a stream using a pipeline.
        
        Args:
            stream: Stream name
            messages: List of message dictionaries
            
        Returns:
            List of message IDs
        """
        await self._ensure_connection()
        
        try:
            # Add metadata to each message
            for msg in messages:
                msg['_timestamp'] = datetime.utcnow().isoformat()
                msg['_message_id'] = str(uuid.uuid4())
                msg['_producer'] = 'RedisProducerBatch'
            
            # Use pipeline for efficiency
            pipe = self.client.pipeline()
            message_ids = []
            
            for msg in messages:
                pipe.xadd(stream, fields=msg)
            
            results = await pipe.execute()
            
            for i, result in enumerate(results):
                self.logger.debug(f"Published batch message to {stream}: {result}")
                message_ids.append(result)
            
            return message_ids
        except Exception as e:
            self.logger.error(f"Failed to publish batch to {stream}: {e}")
            raise


class RedisConsumer:
    """
    Simplified interface for consuming messages from Redis streams.
    
    Example usage:
    ```python
    async def process_message(stream_name, message_data):
        print(f"Processing: {message_data}")
    
    consumer = RedisConsumer()
    await consumer.start('tickets:incoming', process_message)
    ```
    """
    
    def __init__(self, redis_url: str = None, max_retries: int = 3):
        """
        Initialize the Redis consumer.
        
        Args:
            redis_url: Redis connection URL
            max_retries: Maximum number of retries before DLQ
        """
        self.redis_url = redis_url or "redis://localhost:6379"
        self.max_retries = max_retries
        self.client = None
        self.running = False
        self.consumer_task = None
        self.logger = logging.getLogger(__name__)
    
    async def start(self, stream: str, callback: Callable, group: str = None, consumer: str = None):
        """
        Start consuming messages from a stream.
        
        Args:
            stream: Stream name to consume from
            callback: Async function to process messages
            group: Consumer group name (auto-generated if None)
            consumer: Consumer name (auto-generated if None)
        """
        if self.running:
            self.logger.warning("Consumer is already running")
            return
        
        self.running = True
        
        # Generate default group and consumer names if not provided
        if not group:
            group = f"group_{stream.replace(':', '_')}"
        if not consumer:
            consumer = f"consumer_{uuid.uuid4().hex[:8]}"
        
        # Initialize Redis connection
        self.client = aioredis.from_url(self.redis_url, decode_responses=True)
        await self.client.ping()
        
        # Create consumer group
        try:
            await self.client.xgroup_create(stream, group, id='0', mkstream=True)
        except aioredis.exceptions.ResponseError as e:
            if 'BUSYGROUP' not in str(e):
                raise
        
        # Start the consumption loop
        self.consumer_task = asyncio.create_task(
            self._consume_loop(stream, group, consumer, callback)
        )
        
        self.logger.info(f"Started consumer {consumer} in group {group} for stream {stream}")
    
    async def _consume_loop(self, stream: str, group: str, consumer: str, callback: Callable):
        """
        Internal consumption loop.
        
        Args:
            stream: Stream name
            group: Consumer group name
            consumer: Consumer name
            callback: Message processing function
        """
        while self.running:
            try:
                # Read messages
                messages = await self.client.xreadgroup(
                    groupname=group,
                    consumername=consumer,
                    streams={stream: '>'},
                    count=10,
                    block=5000  # 5 seconds
                )
                
                # Process messages if any were returned
                if messages:
                    for stream_name, message_list in messages:
                        for message_id, message_data in message_list:
                            try:
                                await callback(stream_name, message_data)
                                
                                # Acknowledge successful processing
                                await self.client.xack(stream_name, group, message_id)
                                
                                self.logger.debug(f"Successfully processed message {message_id}")
                                
                            except Exception as e:
                                self.logger.error(f"Error processing message {message_id}: {e}")
                                await self._handle_error(stream_name, message_id, message_data, e)
                
            except Exception as e:
                self.logger.error(f"Error in consumer loop: {e}")
                if self.running:
                    # Wait before retrying to avoid tight loop
                    await asyncio.sleep(1)
    
    async def _handle_error(self, stream: str, message_id: str, message: dict, error: Exception):
        """
        Handle errors during message processing (simplified version for consumer).
        """
        retry_count = int(message.get('_retry_count', 0)) + 1
        
        if retry_count < self.max_retries:
            # Increment retry count and re-publish to the same stream
            message['_retry_count'] = retry_count
            message['_last_error'] = str(error)
            message['_last_error_timestamp'] = datetime.utcnow().isoformat()
            
            # Add a small delay before retrying
            await asyncio.sleep(2 ** retry_count)  # Exponential backoff
            
            # Re-publish to the same stream
            await self.client.xadd(stream, fields=message)
            
            self.logger.warning(f"Message {message_id} failed, retrying ({retry_count}/{self.max_retries}): {error}")
        else:
            # Move to dead letter queue
            message['_final_error'] = str(error)
            message['_failed_stream'] = stream
            message['_failure_timestamp'] = datetime.utcnow().isoformat()
            
            # Publish to DLQ
            await self.client.xadd('dlq', fields=message)
            
            self.logger.error(f"Message {message_id} failed permanently after {retry_count} retries, moved to DLQ: {error}")
    
    async def stop(self):
        """
        Stop the consumer gracefully.
        """
        if not self.running:
            return
        
        self.running = False
        
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass  # Expected when cancelling
        
        if self.client:
            await self.client.close()
        
        self.logger.info("Consumer stopped gracefully")