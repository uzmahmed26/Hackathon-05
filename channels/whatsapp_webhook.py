"""
WhatsApp Webhook Handler for Customer Success AI
FastAPI endpoints for receiving WhatsApp messages from Twilio
"""

import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import redis
import json
from datetime import datetime

from channels.whatsapp_handler import whatsapp_handler

# Initialize router
router = APIRouter(prefix="/webhooks", tags=["whatsapp"])

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize Redis connection (assuming it's running locally)
redis_client = redis.Redis(host='localhost', port=6379, db=0)


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Handle incoming WhatsApp messages from Twilio.
    
    Args:
        request: HTTP request object from Twilio
        
    Returns:
        Empty TwiML response (200 OK)
    """
    try:
        # Validate the webhook signature for security
        is_valid = await whatsapp_handler.validate_webhook(request)
        
        if not is_valid:
            logger.warning("Invalid Twilio signature in WhatsApp webhook")
            raise HTTPException(status_code=403, detail="Forbidden: Invalid signature")
        
        # Get form data from the request
        form_data = await request.form()
        
        # Process the webhook payload
        normalized_message = await whatsapp_handler.process_webhook(dict(form_data))
        
        # Log the received message
        logger.info(f"Received WhatsApp message from {normalized_message['customer_phone']}: {normalized_message['content'][:50]}...")
        
        # Publish to Redis queue for processing by the agent
        try:
            redis_client.lpush('whatsapp_messages', json.dumps(normalized_message))
        except Exception as redis_err:
            logger.warning(f"Redis unavailable, message not queued: {redis_err}")
        
        # Return empty TwiML response as required by Twilio
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/whatsapp/status")
async def whatsapp_status_callback(request: Request):
    """
    Handle WhatsApp message delivery status updates.
    
    Args:
        request: HTTP request object from Twilio with status update
        
    Returns:
        200 OK response
    """
    try:
        # Get form data from the request
        form_data = await request.form()
        
        # Extract message SID and status
        message_sid = form_data.get('MessageSid', '')
        status = form_data.get('MessageStatus', '')
        to_phone = form_data.get('To', '')
        from_phone = form_data.get('From', '')
        
        # Log the status update
        logger.info(f"WhatsApp message {message_sid} status update: {status}")
        
        # In a real implementation, you would update the message status in the database
        # For now, we'll just publish the status update to Redis
        status_update = {
            'channel_message_id': message_sid,
            'delivery_status': status,
            'to': to_phone,
            'from': from_phone,
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'channel': 'whatsapp'
        }
        
        # Publish to Redis queue for status tracking
        redis_client.lpush('whatsapp_status_updates', json.dumps(status_update))
        
        # Return 200 OK to acknowledge receipt
        return {"status": "ok", "message": "Status callback received"}
    
    except Exception as e:
        logger.error(f"Error processing WhatsApp status callback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Additional endpoint to test the webhook
@router.post("/whatsapp/test")
async def test_whatsapp_webhook():
    """
    Test endpoint to simulate a WhatsApp message.
    
    Returns:
        200 OK response with test data
    """
    try:
        # Create a mock Twilio webhook payload
        mock_payload = {
            'MessageSid': 'SMtest1234567890abcdef',
            'From': 'whatsapp:+1234567890',
            'To': 'whatsapp:+0987654321',
            'Body': 'This is a test message from the WhatsApp webhook',
            'ProfileName': 'Test User',
            'NumMedia': '0',
            'WaId': '+1234567890',
            'SmsStatus': 'received'
        }
        
        # Process the mock payload
        normalized_message = await whatsapp_handler.process_webhook(mock_payload)
        
        # Publish to Redis queue
        redis_client.lpush('whatsapp_messages', json.dumps(normalized_message))
        
        return {
            "status": "ok", 
            "message": "Test message sent to queue",
            "normalized_message": normalized_message
        }
    
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error in test endpoint: {str(e)}")


# Health check endpoint
@router.get("/whatsapp/health")
async def whatsapp_webhook_health():
    """
    Health check for the WhatsApp webhook endpoint.
    
    Returns:
        200 OK response
    """
    try:
        # Check if Redis is reachable
        redis_client.ping()
        
        return {
            "status": "healthy",
            "service": "whatsapp_webhook",
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
    except Exception as e:
        logger.error(f"WhatsApp webhook health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


# Utility class for Response
from starlette.responses import Response