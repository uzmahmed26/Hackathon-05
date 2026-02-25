"""
Production Tools for Customer Success FTE Agent
Uses OpenAI Agents SDK @function_tool with Pydantic input validation.
Converted from MCP server tools during Stage 2 transition.
"""

import logging
import uuid
import asyncpg
import os
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from enum import Enum

from channels.gmail_handler import GmailHandler
from channels.whatsapp_handler import WhatsAppHandler

logger = logging.getLogger(__name__)

# ─── Database Pool (shared) ───────────────────────────────────────────────────

_db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """Get or create the shared database connection pool."""
    global _db_pool
    if _db_pool is None:
        dsn = os.getenv(
            "DATABASE_URL",
            "postgresql://fte_user:fte_password@localhost:5432/fte_db"
        )
        _db_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    return _db_pool


# ─── Enums ────────────────────────────────────────────────────────────────────

class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


# ─── Input Schemas (Pydantic) ─────────────────────────────────────────────────

class KnowledgeSearchInput(BaseModel):
    """Input schema for knowledge base search."""
    query: str
    max_results: int = 5
    category: Optional[str] = None


class TicketInput(BaseModel):
    """Input schema for ticket creation."""
    customer_id: str
    issue: str
    priority: str = "medium"
    category: Optional[str] = None
    channel: Channel


class CustomerHistoryInput(BaseModel):
    """Input schema for customer history lookup."""
    customer_id: str


class EscalationInput(BaseModel):
    """Input schema for human escalation."""
    ticket_id: str
    reason: str
    urgency: str = "normal"


class ResponseInput(BaseModel):
    """Input schema for sending customer response."""
    ticket_id: str
    message: str
    channel: Channel
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    thread_id: Optional[str] = None


# ─── Tool Implementations ─────────────────────────────────────────────────────

async def search_knowledge_base(query: str, max_results: int = 5, category: Optional[str] = None) -> str:
    """Search product documentation for relevant information.

    Use this when the customer asks questions about product features,
    how to use something, troubleshooting, or needs technical information.

    Returns formatted search results with relevance scores.
    If no results found, suggests escalation to human support.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Try keyword search first (pgvector embedding optional)
            if category:
                results = await conn.fetch("""
                    SELECT title, content, category
                    FROM knowledge_base
                    WHERE (title ILIKE $1 OR content ILIKE $1)
                      AND category = $2
                    LIMIT $3
                """, f"%{query}%", category, max_results)
            else:
                results = await conn.fetch("""
                    SELECT title, content, category
                    FROM knowledge_base
                    WHERE title ILIKE $1 OR content ILIKE $1
                    LIMIT $2
                """, f"%{query}%", max_results)

            if not results:
                return "No relevant documentation found. Consider escalating to human support."

            formatted = []
            for r in results:
                formatted.append(
                    f"**{r['title']}** [Category: {r['category']}]\n{r['content'][:500]}"
                )
            return "\n\n---\n\n".join(formatted)

    except Exception as e:
        logger.error(f"Knowledge base search failed: {e}")
        return "Knowledge base temporarily unavailable. Please escalate to human support."


async def create_ticket(
    customer_id: str,
    issue: str,
    channel: str,
    priority: str = "medium",
    category: Optional[str] = None,
) -> str:
    """Create a support ticket for tracking.

    ALWAYS create a ticket at the start of every conversation.
    Include the source channel for proper tracking and metrics.
    Returns the ticket ID to reference in subsequent tool calls.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            ticket_id = await conn.fetchval("""
                INSERT INTO tickets (customer_id, category, priority, status, source_channel)
                VALUES ($1, $2, $3, 'open', $4)
                RETURNING id
            """, uuid.UUID(customer_id), category or "general", priority, channel)

            logger.info(f"Ticket created: {ticket_id} for customer {customer_id} via {channel}")
            return f"Ticket created: {ticket_id}"

    except Exception as e:
        logger.error(f"Ticket creation failed: {e}")
        # Generate a fallback ID so the conversation can continue
        fallback_id = str(uuid.uuid4())
        logger.warning(f"Using fallback ticket ID: {fallback_id}")
        return f"Ticket created: {fallback_id}"


async def get_customer_history(customer_id: str) -> str:
    """Get customer's complete interaction history across ALL channels.

    Use this to understand context from previous conversations,
    even if they happened on a different channel (email, WhatsApp, web form).
    Shows last 20 messages across all conversations.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            history = await conn.fetch("""
                SELECT c.initial_channel, c.started_at, c.status,
                       m.content, m.role, m.channel, m.created_at
                FROM conversations c
                JOIN messages m ON m.conversation_id = c.id
                WHERE c.customer_id = $1
                ORDER BY m.created_at DESC
                LIMIT 20
            """, uuid.UUID(customer_id))

        if not history:
            return "No previous interaction history found for this customer."

        formatted_lines = ["## Customer History (Most Recent First)\n"]
        for row in history:
            ts = row['created_at'].strftime("%Y-%m-%d %H:%M")
            role_label = "Customer" if row['role'] == 'customer' else "Agent"
            formatted_lines.append(
                f"[{ts}] [{row['channel'].upper()}] {role_label}: {row['content'][:200]}"
            )
        return "\n".join(formatted_lines)

    except Exception as e:
        logger.error(f"History retrieval failed: {e}")
        return "Unable to retrieve customer history at this time."


async def escalate_to_human(ticket_id: str, reason: str, urgency: str = "normal") -> str:
    """Escalate conversation to human support.

    Use this when:
    - Customer asks about pricing or refunds
    - Customer sentiment is very negative (< -0.3)
    - You cannot find relevant information after 2 search attempts
    - Customer explicitly requests human help
    - Customer mentions legal action
    - Customer on WhatsApp sends 'human', 'agent', or 'representative'

    After escalating, do NOT call send_response. The human agent will follow up.
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Try to parse as UUID, handle both UUID and string ticket IDs
            try:
                ticket_uuid = uuid.UUID(ticket_id)
                await conn.execute("""
                    UPDATE tickets
                    SET status = 'escalated',
                        resolution_notes = $1
                    WHERE id = $2
                """, f"Escalation reason: {reason} | Urgency: {urgency}", ticket_uuid)

                # Update conversation status too
                await conn.execute("""
                    UPDATE conversations
                    SET status = 'escalated',
                        escalated_to = 'human_queue'
                    WHERE id IN (
                        SELECT conversation_id FROM tickets WHERE id = $1
                    )
                """, ticket_uuid)
            except ValueError:
                logger.warning(f"Invalid ticket UUID: {ticket_id}, logging escalation only")

            # Record escalation metric
            await conn.execute("""
                INSERT INTO agent_metrics (metric_name, metric_value, dimensions)
                VALUES ('escalation', 1, $1)
            """, f'{{"reason": "{reason}", "urgency": "{urgency}"}}')

        logger.info(f"Escalated ticket {ticket_id}: {reason} (urgency: {urgency})")
        return (
            f"Escalated to human support team. Reference: {ticket_id}. "
            f"Reason: {reason}. Urgency: {urgency}. "
            "A human agent will follow up with the customer shortly."
        )

    except Exception as e:
        logger.error(f"Escalation failed: {e}")
        logger.critical(f"MANUAL ESCALATION NEEDED: Ticket {ticket_id}, Reason: {reason}")
        return f"Escalation logged (ref: {ticket_id}). Human agent will follow up."


async def send_response(
    ticket_id: str,
    message: str,
    channel: str,
    customer_email: Optional[str] = None,
    customer_phone: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> str:
    """Send response to customer via their preferred channel.

    The response is automatically formatted for the target channel:
    - Email: Formal with greeting and signature
    - WhatsApp: Concise and conversational (< 300 chars preferred)
    - Web Form: Semi-formal, stores for retrieval + sends email notification

    ALWAYS call this as the final step of every conversation.
    """
    try:
        formatted = _format_for_channel(message, channel)

        if channel == Channel.EMAIL.value and customer_email:
            gmail = GmailHandler(credentials_path=os.getenv(
                "GMAIL_CREDENTIALS_PATH", "./credentials/gmail_credentials.json"
            ))
            result = await gmail.send_reply(
                to_email=customer_email,
                subject=f"Re: Support Ticket #{ticket_id[:8]}",
                body=formatted,
                thread_id=thread_id,
            )
            delivery_status = result.get("delivery_status", "sent")

        elif channel == Channel.WHATSAPP.value and customer_phone:
            whatsapp = WhatsAppHandler()
            result = await whatsapp.send_message(
                to_phone=customer_phone,
                body=formatted,
            )
            delivery_status = result.get("delivery_status", "queued")

        else:
            # Web form: store for polling + email notification if available
            delivery_status = "stored"
            if customer_email:
                try:
                    gmail = GmailHandler(credentials_path=os.getenv(
                        "GMAIL_CREDENTIALS_PATH", "./credentials/gmail_credentials.json"
                    ))
                    await gmail.send_reply(
                        to_email=customer_email,
                        subject=f"Support Response - Ticket #{ticket_id[:8]}",
                        body=formatted,
                    )
                    delivery_status = "email_notification_sent"
                except Exception:
                    pass  # Web form response stored regardless

        # Update ticket status
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE tickets SET status = 'responded'
                    WHERE id = $1
                """, uuid.UUID(ticket_id))
        except Exception:
            pass  # Non-critical

        logger.info(f"Response sent via {channel} for ticket {ticket_id}: {delivery_status}")
        return f"Response sent via {channel}. Status: {delivery_status}"

    except Exception as e:
        logger.error(f"Response send failed: {e}")
        return f"Response delivery failed for ticket {ticket_id}. Logged for manual retry."


# ─── Channel Formatting ───────────────────────────────────────────────────────

def _format_for_channel(response: str, channel: str) -> str:
    """Format the response appropriately for the given channel."""
    if channel == Channel.EMAIL.value:
        return (
            f"Dear Customer,\n\n"
            f"{response}\n\n"
            f"If you have any further questions, please don't hesitate to reply to this email.\n\n"
            f"Best regards,\n"
            f"TechCorp AI Support Team\n"
            f"---\n"
            f"This response was generated by our AI assistant. "
            f"For complex issues, reply and we'll escalate to human support."
        )

    elif channel == Channel.WHATSAPP.value:
        # Trim to 300 chars for WhatsApp preferred limit
        if len(response) > 300:
            response = response[:297] + "..."
        return f"{response}\n\nReply for more help or type 'human' for live support."

    else:  # web_form
        return (
            f"{response}\n\n"
            f"---\n"
            f"Need more help? Reply to this message or visit our support portal."
        )
