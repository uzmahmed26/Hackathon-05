"""
MCP Server for Customer Success FTE
Stage 1: Incubation Phase

Exposes the customer success agent capabilities as Model Context Protocol tools.
This was built during incubation to explore and test the agent's capabilities.
The MCP tools were later converted to OpenAI Agents SDK @function_tool in production.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolResult

from agent.agent_prototype import CustomerSuccessAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shared agent instance
_agent = CustomerSuccessAgent()

# Channel enum
class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


# Create MCP server
server = Server("customer-success-fte")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return [
        Tool(
            name="search_knowledge_base",
            description=(
                "Search product documentation for relevant information. "
                "Use when customer asks product questions, how-to guidance, or troubleshooting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query based on customer question",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5)",
                        "default": 5,
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter",
                        "enum": ["technical", "billing", "general", "bug_report", "feedback"],
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="create_ticket",
            description=(
                "Create a support ticket in the system with channel tracking. "
                "ALWAYS call this first at the start of every conversation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Unique customer identifier",
                    },
                    "issue": {
                        "type": "string",
                        "description": "Brief description of the customer's issue",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "default": "medium",
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["email", "whatsapp", "web_form"],
                        "description": "The channel through which the customer contacted us",
                    },
                },
                "required": ["customer_id", "issue", "channel"],
            },
        ),
        Tool(
            name="get_customer_history",
            description=(
                "Get customer's interaction history across ALL channels. "
                "Call this second to understand cross-channel context."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer's unique ID",
                    },
                },
                "required": ["customer_id"],
            },
        ),
        Tool(
            name="escalate_to_human",
            description=(
                "Escalate conversation to human support. "
                "Use for pricing, refunds, legal issues, negative sentiment, or explicit human requests."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The ticket ID to escalate",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Clear reason for escalation",
                        "enum": [
                            "pricing_inquiry",
                            "refund_request",
                            "legal_issue",
                            "negative_sentiment",
                            "knowledge_gap",
                            "customer_requested",
                            "cancellation_request",
                            "other",
                        ],
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "normal", "high"],
                        "default": "normal",
                    },
                },
                "required": ["ticket_id", "reason"],
            },
        ),
        Tool(
            name="send_response",
            description=(
                "Send response to customer via their preferred channel. "
                "ALWAYS call this as the last step. Auto-formats for channel."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The ticket ID",
                    },
                    "message": {
                        "type": "string",
                        "description": "The response message (plain text, auto-formatted for channel)",
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["email", "whatsapp", "web_form"],
                    },
                    "customer_email": {
                        "type": "string",
                        "description": "Customer email (required for email/web_form)",
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "Customer phone (required for whatsapp)",
                    },
                },
                "required": ["ticket_id", "message", "channel"],
            },
        ),
        Tool(
            name="analyze_sentiment",
            description=(
                "Analyze the sentiment of a customer message. "
                "Returns a score from -1.0 (very negative) to 1.0 (very positive)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The customer message to analyze",
                    },
                },
                "required": ["message"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    """Handle tool invocations."""

    try:
        if name == "search_knowledge_base":
            result = await _handle_search_knowledge_base(arguments)

        elif name == "create_ticket":
            result = await _handle_create_ticket(arguments)

        elif name == "get_customer_history":
            result = await _handle_get_customer_history(arguments)

        elif name == "escalate_to_human":
            result = await _handle_escalate_to_human(arguments)

        elif name == "send_response":
            result = await _handle_send_response(arguments)

        elif name == "analyze_sentiment":
            result = await _handle_analyze_sentiment(arguments)

        else:
            result = f"Unknown tool: {name}"

        return CallToolResult(content=[TextContent(type="text", text=result)])

    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Tool error: {str(e)}")],
            isError=True,
        )


async def _handle_search_knowledge_base(args: dict) -> str:
    """Search knowledge base using prototype agent."""
    query = args["query"]
    results = _agent.search_knowledge_base(query)

    if not results:
        return "No relevant documentation found. Consider escalating to human support."

    formatted = []
    for r in results:
        formatted.append(
            f"**{r['title']}** (relevance: {r.get('relevance_score', 0.0):.2f})\n{r['content'][:500]}"
        )
    return "\n\n---\n\n".join(formatted)


async def _handle_create_ticket(args: dict) -> str:
    """Create a support ticket (in-memory during incubation)."""
    ticket_id = str(uuid.uuid4())
    logger.info(
        f"[MCP] Ticket created: {ticket_id} | "
        f"Customer: {args['customer_id']} | "
        f"Channel: {args['channel']} | "
        f"Priority: {args.get('priority', 'medium')}"
    )
    return f"Ticket created: {ticket_id}"


async def _handle_get_customer_history(args: dict) -> str:
    """Return customer history (stub during incubation)."""
    customer_id = args["customer_id"]
    return (
        f"Customer history for {customer_id}:\n"
        f"No previous interactions found (new customer or first contact via this channel)."
    )


async def _handle_escalate_to_human(args: dict) -> str:
    """Escalate ticket to human agent."""
    ticket_id = args["ticket_id"]
    reason = args["reason"]
    urgency = args.get("urgency", "normal")
    logger.warning(f"[MCP] Escalating ticket {ticket_id}: {reason} (urgency: {urgency})")
    return (
        f"Escalated to human support. Reference: {ticket_id}. "
        f"Reason: {reason}. Urgency: {urgency}."
    )


async def _handle_send_response(args: dict) -> str:
    """Send response via the appropriate channel."""
    ticket_id = args["ticket_id"]
    message = args["message"]
    channel = args["channel"]

    # Format for channel
    if channel == "email":
        formatted = f"Dear Customer,\n\n{message}\n\nBest regards,\nTechCorp Support"
    elif channel == "whatsapp":
        formatted = message[:300] + ("..." if len(message) > 300 else "")
        formatted += "\n\nReply for more help or type 'human' for live support."
    else:
        formatted = f"{message}\n\n---\nNeed more help? Visit our support portal."

    logger.info(f"[MCP] Response sent via {channel} for ticket {ticket_id}")
    return f"Response sent via {channel}. Status: sent"


async def _handle_analyze_sentiment(args: dict) -> str:
    """Analyze sentiment using prototype agent."""
    message = args["message"]
    score = _agent.detect_sentiment(message)

    if score < -0.5:
        emotion = "very_frustrated"
        recommendation = "ESCALATE immediately"
    elif score < -0.3:
        emotion = "frustrated"
        recommendation = "Monitor closely, consider escalation"
    elif score < 0.1:
        emotion = "neutral"
        recommendation = "Standard handling"
    elif score < 0.5:
        emotion = "satisfied"
        recommendation = "Standard handling"
    else:
        emotion = "happy"
        recommendation = "Customer is satisfied"

    return (
        f"Sentiment score: {score:.2f}\n"
        f"Detected emotion: {emotion}\n"
        f"Recommendation: {recommendation}"
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run())
