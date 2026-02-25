"""
Gmail Webhook Handler for Customer Success AI
FastAPI endpoint for receiving Gmail push notifications
"""

import base64
import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import redis
import asyncio

from channels.gmail_handler import GmailHandler

# Initialize router
router = APIRouter(prefix="/webhooks", tags=["gmail"])

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize Redis connection (assuming it's running locally)
redis_client = redis.Redis(host='localhost', port=6379, db=0)


class GmailWebhookPayload(BaseModel):
    """Model for Gmail webhook payload."""
    message: Dict[str, Any]
    subscription: str


@router.post("/gmail")
async def gmail_webhook(request: Request):
    """
    Handle Gmail push notifications.
    
    Args:
        request: HTTP request object
        
    Returns:
        200 OK response
    """
    try:
        # Get the raw body
        body = await request.body()
        
        # Parse the JSON payload
        payload = json.loads(body.decode('utf-8'))
        
        # Validate the payload structure
        if 'message' not in payload:
            logger.warning("Invalid payload: missing 'message' field")
            raise HTTPException(status_code=400, detail="Invalid payload: missing 'message' field")
        
        # Process the notification asynchronously
        # In a real implementation, we would decode the Pub/Sub message
        # and call the GmailHandler to process it
        
        # Decode the Pub/Sub message data
        message_data = payload['message']
        data = message_data.get('data', '')
        
        if data:
            # Decode base64 encoded data
            decoded_data = base64.b64decode(data).decode('utf-8')
            notification = json.loads(decoded_data)
            
            # Log the received notification
            logger.info(f"Received Gmail notification: {notification}")
            
            # Publish to Redis queue for processing by the agent
            try:
                redis_client.lpush('gmail_notifications', json.dumps(notification))
            except Exception as redis_err:
                logger.warning(f"Redis unavailable, notification not queued: {redis_err}")
        else:
            logger.warning("Received notification with no data")
        
        # Return 200 OK to acknowledge receipt
        return {"status": "ok", "message": "Notification received and queued for processing"}
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error processing Gmail webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")


# Additional endpoint to test the webhook
@router.post("/gmail/test")
async def test_gmail_webhook():
    """
    Test endpoint to simulate a Gmail notification.
    
    Returns:
        200 OK response with test data
    """
    try:
        # Create a mock notification
        mock_notification = {
            "message": {
                "data": base64.b64encode(json.dumps({
                    "emailAddress": "test@example.com",
                    "historyId": "1234567890",
                    "labels": ["INBOX"],
                    "messages": [{"id": "test_msg_1", "threadId": "test_thread_1"}]
                }).encode('utf-8')).decode('utf-8'),
                "message_id": "test_message_id",
                "publish_time": "2026-02-11T10:00:00.000Z"
            },
            "subscription": "projects/test-project/subscriptions/test-subscription"
        }
        
        # Publish to Redis queue
        redis_client.lpush('gmail_notifications', json.dumps(mock_notification))
        
        return {
            "status": "ok", 
            "message": "Test notification sent to queue",
            "notification": mock_notification
        }
    
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error in test endpoint: {str(e)}")


# Health check endpoint
@router.get("/gmail/health")
async def gmail_webhook_health():
    """
    Health check for the Gmail webhook endpoint.
    
    Returns:
        200 OK response
    """
    try:
        # Check if Redis is reachable
        redis_client.ping()
        
        return {
            "status": "healthy",
            "service": "gmail_webhook",
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
    except Exception as e:
        logger.error(f"Gmail webhook health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


# Utility function to process queued notifications
async def process_gmail_notifications(gmail_handler: GmailHandler):
    """
    Process Gmail notifications from the Redis queue.
    
    Args:
        gmail_handler: Initialized GmailHandler instance
    """
    while True:
        try:
            # Block and wait for a notification
            result = redis_client.brpop(['gmail_notifications'], timeout=5)
            
            if result:
                _, notification_json = result
                notification = json.loads(notification_json)
                
                # Process the notification
                messages = await gmail_handler.process_notification(notification)
                
                # Log the processed messages
                logger.info(f"Processed {len(messages)} messages from notification")
                
                # In a real implementation, you would now pass these messages
                # to the customer success agent for processing
                # For example: await agent.handle_messages(messages)
                
        except Exception as e:
            logger.error(f"Error processing Gmail notification: {e}")
            # Continue processing other notifications
            continue
        
        # Small delay to prevent busy-waiting
        await asyncio.sleep(0.1)


# Helper function to start the notification processor
def start_notification_processor(gmail_handler: GmailHandler):
    """
    Start the Gmail notification processor in the background.
    
    Args:
        gmail_handler: Initialized GmailHandler instance
    """
    import threading
    
    def run_processor():
        # Create a new event loop for the background thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the processor
        loop.run_until_complete(process_gmail_notifications(gmail_handler))
    
    # Start the processor in a background thread
    processor_thread = threading.Thread(target=run_processor, daemon=True)
    processor_thread.start()
    
    logger.info("Gmail notification processor started")