"""
Web Form Handler for Customer Success AI
FastAPI endpoints for handling web form submissions
"""

import re
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
import uuid
import logging
import redis
import json
from enum import Enum

from database.queries import (
    get_or_create_customer,
    create_conversation,
    store_message,
    create_ticket
)

class WebFormHandler:
    """Handler for processing web form submissions."""

    def process_form_data(self, form_data: dict) -> dict:
        """
        Normalize raw web form data into a standard message dict.

        Args:
            form_data: Raw form submission dict with name, email, subject, etc.

        Returns:
            Normalized dict with customer_name, customer_email, content, and metadata keys
        """
        return {
            'channel': 'web_form',
            'customer_name': form_data.get('name', ''),
            'customer_email': form_data.get('email', ''),
            'subject': form_data.get('subject', ''),
            'content': form_data.get('message', ''),
            'category': form_data.get('category', 'general'),
            'metadata': {
                'form_version': '1.0',
            },
        }


# Initialize router
router = APIRouter(prefix="/support", tags=["web_form"])

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0)


# Enums for validation
class CategoryEnum(str, Enum):
    GENERAL = "general"
    TECHNICAL = "technical"
    BILLING = "billing"
    FEEDBACK = "feedback"
    BUG_REPORT = "bug_report"


class PriorityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Pydantic models
class SupportFormSubmission(BaseModel):
    """Request model for support form submission."""
    name: str
    email: str
    subject: str
    category: CategoryEnum
    priority: PriorityEnum = PriorityEnum.MEDIUM
    message: str
    attachments: Optional[List[str]] = []

    @validator('email')
    def validate_email(cls, v):
        """Validate email format."""
        v = v.strip()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError('Invalid email address')
        return v.lower()

    @validator('name')
    def validate_name(cls, v):
        """Validate name length."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError('Name must be at least 2 characters')
        if len(v) > 255:
            raise ValueError('Name must be less than 255 characters')
        return v

    @validator('subject')
    def validate_subject(cls, v):
        """Validate subject length."""
        v = v.strip()
        if len(v) < 5:
            raise ValueError('Subject must be at least 5 characters')
        if len(v) > 200:
            raise ValueError('Subject must be less than 200 characters')
        return v

    @validator('message')
    def validate_message(cls, v):
        """Validate message length."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError('Message must be at least 10 characters')
        if len(v) > 5000:
            raise ValueError('Message must be less than 5000 characters')
        return v


class SupportFormResponse(BaseModel):
    """Response model for support form submission."""
    ticket_id: str
    message: str
    estimated_response_time: str


class TicketStatusResponse(BaseModel):
    """Response model for ticket status."""
    ticket_id: str
    status: str
    messages: List[dict]
    created_at: str
    last_updated: str


# Background task to process the submission
async def process_support_submission(submission: SupportFormSubmission, ticket_id: str, db_manager=None):
    """
    Background task to process support form submission.

    Args:
        submission: The validated submission data
        ticket_id: The generated ticket ID
        db_manager: DatabaseManager instance (optional, used when available)
    """
    if db_manager is None:
        logger.warning("db_manager unavailable, skipping DB operations for web form submission")
        return

    try:
        # 1. Get or create customer
        customer_id = await get_or_create_customer(
            db_manager,
            email=submission.email,
            name=submission.name
        )
        logger.info(f"Customer retrieved/created with ID: {customer_id}")

        # 2. Create conversation
        conversation_id = await create_conversation(
            db_manager,
            customer_id=customer_id,
            channel='web_form'
        )
        logger.info(f"Conversation created with ID: {conversation_id}")

        # 3. Store message
        await store_message(
            db_manager,
            conversation_id=conversation_id,
            channel='web_form',
            direction='inbound',
            role='customer',
            content=submission.message
        )
        logger.info(f"Message stored for conversation: {conversation_id}")

        # 4. Create ticket
        ticket = await create_ticket(
            db_manager,
            customer_id=customer_id,
            conversation_id=conversation_id,
            source_channel='web_form',
            category=submission.category.value,
            priority=submission.priority.value
        )
        logger.info(f"Ticket created with ID: {ticket}")

        # 5. Publish to Redis queue
        message_data = {
            'channel': 'web_form',
            'channel_message_id': ticket_id,
            'customer_email': submission.email,
            'customer_name': submission.name,
            'subject': submission.subject,
            'content': submission.message,
            'category': submission.category.value,
            'priority': submission.priority.value,
            'received_at': datetime.utcnow().isoformat(),
            'metadata': {
                'form_version': '1.0',
                'attachments': submission.attachments or []
            }
        }

        # Publish to Redis queue
        redis_client.lpush('tickets:incoming', json.dumps(message_data))
        logger.info(f"Message published to Redis queue for ticket: {ticket_id}")

    except Exception as e:
        logger.error(f"Error processing support submission: {e}")
        # In a real implementation, you might want to store the error
        # and retry the operation or notify an admin


@router.post("/submit", response_model=SupportFormResponse)
async def submit_support_form(
    request: Request,
    submission: SupportFormSubmission,
    background_tasks: BackgroundTasks
):
    """
    Handle web form submission.

    Flow:
    1. Validate submission (Pydantic does this automatically)
    2. Generate ticket_id (UUID)
    3. Get or create customer in database
    4. Create conversation record
    5. Store initial message
    6. Create ticket record
    7. Publish to Redis tickets:incoming queue
    8. Return ticket_id immediately (don't wait for agent)

    Returns:
    - ticket_id: For tracking
    - message: Confirmation message
    - estimated_response_time: Set expectation
    """
    try:
        # Generate ticket ID
        ticket_id = str(uuid.uuid4())
        logger.info(f"Processing support form submission with ticket ID: {ticket_id}")

        # Get db_manager from app state if available
        db_manager = getattr(request.app.state, 'db_manager', None)

        # Add background task to process the submission
        background_tasks.add_task(process_support_submission, submission, ticket_id, db_manager)

        # Return response immediately
        return SupportFormResponse(
            ticket_id=ticket_id,
            message="Thank you for contacting us. Your support request has been received.",
            estimated_response_time="Usually within 5 minutes"
        )

    except Exception as e:
        logger.error(f"Error in submit_support_form: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ticket/{ticket_id}", response_model=TicketStatusResponse)
async def get_ticket_status(ticket_id: str):
    """
    Get ticket status and conversation history.
    
    Returns:
    - Current ticket status
    - All messages in conversation
    - Timestamps
    
    If ticket not found: 404
    """
    try:
        # In a real implementation, you would fetch from the database
        # For now, we'll return a mock response
        # This would involve querying the database for the ticket and conversation history
        
        # Mock response for now
        # In a real implementation, you would:
        # 1. Query the tickets table for the ticket
        # 2. Query the conversations table for the conversation
        # 3. Query the messages table for all messages in the conversation
        # 4. Return the appropriate response
        
        # For now, return a mock response
        return TicketStatusResponse(
            ticket_id=ticket_id,
            status="open",
            messages=[
                {
                    "id": "msg_1",
                    "content": "Customer submitted a support request via web form",
                    "role": "system",
                    "timestamp": datetime.utcnow().isoformat()
                },
                {
                    "id": "msg_2",
                    "content": "Our AI assistant is reviewing your request",
                    "role": "agent",
                    "timestamp": datetime.utcnow().isoformat()
                }
            ],
            created_at=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat()
        )
    
    except Exception as e:
        logger.error(f"Error in get_ticket_status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Additional endpoint to test the submission
@router.post("/submit/test")
async def test_submit_support_form(background_tasks: BackgroundTasks):
    """
    Test endpoint to simulate a support form submission.
    
    Returns:
    - ticket_id: For tracking
    - message: Confirmation message
    - estimated_response_time: Set expectation
    """
    try:
        # Create a mock submission
        mock_submission = SupportFormSubmission(
            name="Test User",
            email="test@example.com",
            subject="Test Subject",
            category=CategoryEnum.GENERAL,
            message="This is a test message for the web form handler."
        )
        
        # Generate ticket ID
        ticket_id = str(uuid.uuid4())
        logger.info(f"Processing test support form submission with ticket ID: {ticket_id}")

        # Add background task to process the submission
        background_tasks.add_task(process_support_submission, mock_submission, ticket_id)

        # Return response immediately
        return SupportFormResponse(
            ticket_id=ticket_id,
            message="Thank you for contacting us. Your support request has been received.",
            estimated_response_time="Usually within 5 minutes"
        )

    except Exception as e:
        logger.error(f"Error in test_submit_support_form: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Health check endpoint
@router.get("/health")
async def web_form_handler_health():
    """
    Health check for the web form handler.
    
    Returns:
        200 OK response
    """
    try:
        # Check if Redis is reachable
        redis_client.ping()
        
        return {
            "status": "healthy",
            "service": "web_form_handler",
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
    except Exception as e:
        logger.error(f"Web form handler health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")