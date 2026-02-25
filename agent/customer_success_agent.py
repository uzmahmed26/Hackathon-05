"""
Customer Success FTE - Production Agent (OpenAI Agents SDK)
Stage 2: Specialization Phase

Converted from incubation prototype to production-grade agent
using OpenAI Agents SDK with @function_tool decorators.
"""

import logging
import os
from enum import Enum
from typing import Optional
from pydantic import BaseModel

# OpenAI Agents SDK
from agents import Agent, Runner, function_tool

from agent.prompts import CUSTOMER_SUCCESS_SYSTEM_PROMPT
from agent.tools import (
    search_knowledge_base as _search_knowledge_base,
    create_ticket as _create_ticket,
    get_customer_history as _get_customer_history,
    escalate_to_human as _escalate_to_human,
    send_response as _send_response,
)

logger = logging.getLogger(__name__)


# ─── OpenAI Agents SDK Tool Definitions ───────────────────────────────────────

@function_tool
async def search_knowledge_base(query: str, max_results: int = 5, category: Optional[str] = None) -> str:
    """Search product documentation for relevant information.

    Use this when the customer asks questions about product features,
    how to use something, troubleshooting, or needs technical information.
    Call at most 2 times per conversation before escalating.

    Args:
        query: The search query based on customer's question
        max_results: Maximum number of results to return (default: 5)
        category: Optional category filter (technical, billing, general, etc.)

    Returns:
        Formatted search results with document titles and content excerpts.
    """
    return await _search_knowledge_base(query=query, max_results=max_results, category=category)


@function_tool
async def create_ticket(
    customer_id: str,
    issue: str,
    channel: str,
    priority: str = "medium",
    category: Optional[str] = None,
) -> str:
    """Create a support ticket for tracking.

    ALWAYS call this as the FIRST action in every conversation.
    Include the source channel (email/whatsapp/web_form) for metrics.

    Args:
        customer_id: The customer's unique ID
        issue: Brief description of the customer's issue
        channel: Source channel - must be 'email', 'whatsapp', or 'web_form'
        priority: Ticket priority - 'low', 'medium', or 'high'
        category: Issue category - 'technical', 'billing', 'general', 'bug_report', 'feedback'

    Returns:
        Ticket ID string to use in subsequent tool calls.
    """
    return await _create_ticket(
        customer_id=customer_id,
        issue=issue,
        channel=channel,
        priority=priority,
        category=category,
    )


@function_tool
async def get_customer_history(customer_id: str) -> str:
    """Get customer's complete interaction history across ALL channels.

    Call this as the SECOND action after creating the ticket.
    Shows history from email, WhatsApp, and web form interactions.
    Use this to avoid asking customers to repeat themselves.

    Args:
        customer_id: The customer's unique ID

    Returns:
        Formatted list of past interactions with timestamps and channels.
    """
    return await _get_customer_history(customer_id=customer_id)


@function_tool
async def escalate_to_human(ticket_id: str, reason: str, urgency: str = "normal") -> str:
    """Escalate conversation to human support.

    MUST use this when:
    - Customer asks about pricing, billing, or refunds
    - Customer mentions legal action ('lawyer', 'sue', 'legal', 'attorney')
    - Customer sentiment is very negative or uses profanity
    - Cannot find relevant information after 2 search attempts
    - Customer explicitly requests human help
    - WhatsApp customer sends 'human', 'agent', or 'representative'

    After calling this, do NOT call send_response. Human agent will handle it.

    Args:
        ticket_id: The ticket ID from create_ticket
        reason: Clear reason for escalation (e.g., 'pricing_inquiry', 'legal_issue',
                'negative_sentiment', 'knowledge_gap', 'customer_requested')
        urgency: Urgency level - 'low', 'normal', or 'high'

    Returns:
        Escalation confirmation with reference ID.
    """
    return await _escalate_to_human(ticket_id=ticket_id, reason=reason, urgency=urgency)


@function_tool
async def send_response(
    ticket_id: str,
    message: str,
    channel: str,
    customer_email: Optional[str] = None,
    customer_phone: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> str:
    """Send response to customer via their preferred channel.

    ALWAYS call this as the LAST step. Never skip this tool.
    The response is auto-formatted for the channel:
    - email: Formal with greeting/signature (up to 500 words)
    - whatsapp: Concise and conversational (< 300 chars preferred)
    - web_form: Semi-formal (up to 300 words)

    Args:
        ticket_id: The ticket ID from create_ticket
        message: The response message content (plain text, without channel formatting)
        channel: Target channel - 'email', 'whatsapp', or 'web_form'
        customer_email: Customer email address (required for email/web_form channels)
        customer_phone: Customer phone number (required for whatsapp channel)
        thread_id: Gmail thread ID for email replies (optional)

    Returns:
        Delivery status confirmation.
    """
    return await _send_response(
        ticket_id=ticket_id,
        message=message,
        channel=channel,
        customer_email=customer_email,
        customer_phone=customer_phone,
        thread_id=thread_id,
    )


# ─── Agent Definition ─────────────────────────────────────────────────────────

customer_success_agent = Agent(
    name="Customer Success FTE",
    model=os.getenv("OPENAI_MODEL", "gpt-4o"),
    instructions=CUSTOMER_SUCCESS_SYSTEM_PROMPT,
    tools=[
        search_knowledge_base,
        create_ticket,
        get_customer_history,
        escalate_to_human,
        send_response,
    ],
)


# ─── Runner Helper ────────────────────────────────────────────────────────────

async def run_agent(messages: list, context: dict) -> dict:
    """
    Run the customer success agent on a conversation.

    Args:
        messages: Conversation history in OpenAI format
                  [{"role": "user", "content": "..."}, ...]
        context: Runtime context dict with keys:
                 - customer_id: str
                 - conversation_id: str
                 - channel: str (email/whatsapp/web_form)
                 - ticket_subject: str
                 - customer_email: str (optional)
                 - customer_phone: str (optional)

    Returns:
        {
            'output': str,
            'tool_calls': list,
            'escalated': bool,
            'escalation_reason': str | None
        }
    """
    try:
        # Inject context into the last user message
        channel = context.get("channel", "web_form")
        customer_id = context.get("customer_id", "unknown")
        customer_email = context.get("customer_email")
        customer_phone = context.get("customer_phone")

        # Build context preamble for agent
        context_note = (
            f"\n\n[SYSTEM CONTEXT]\n"
            f"- customer_id: {customer_id}\n"
            f"- channel: {channel}\n"
            f"- conversation_id: {context.get('conversation_id', 'new')}\n"
        )
        if customer_email:
            context_note += f"- customer_email: {customer_email}\n"
        if customer_phone:
            context_note += f"- customer_phone: {customer_phone}\n"
        context_note += "[/SYSTEM CONTEXT]"

        # Append context to last user message
        enriched_messages = list(messages)
        if enriched_messages and enriched_messages[-1]["role"] == "user":
            enriched_messages[-1] = {
                "role": "user",
                "content": enriched_messages[-1]["content"] + context_note,
            }

        # Run via SDK Runner
        result = await Runner.run(
            starting_agent=customer_success_agent,
            input=enriched_messages[-1]["content"] if enriched_messages else "",
        )

        # Extract tool call names for tracking
        tool_calls = []
        escalated = False
        escalation_reason = None

        if hasattr(result, "new_items"):
            for item in result.new_items:
                if hasattr(item, "type") and item.type == "tool_call_item":
                    tool_calls.append(item.raw_item.name if hasattr(item.raw_item, "name") else str(item))
                    if "escalate" in str(item).lower():
                        escalated = True

        output = result.final_output if hasattr(result, "final_output") else str(result)

        return {
            "output": output,
            "tool_calls": tool_calls,
            "escalated": escalated,
            "escalation_reason": escalation_reason,
        }

    except Exception as e:
        logger.error(f"Agent run failed: {e}", exc_info=True)
        return {
            "output": (
                "I'm sorry, I encountered an error while processing your request. "
                "A human agent will follow up shortly."
            ),
            "tool_calls": [],
            "escalated": True,
            "escalation_reason": f"system_error: {str(e)}",
        }
