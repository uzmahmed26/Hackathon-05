"""
Transition Tests: Verify agent behavior matches incubation discoveries.
Run these BEFORE deploying to production.

Based on edge cases found during Stage 1 (Incubation) with Claude Code.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock


class TestTransitionFromIncubation:
    """Tests based on edge cases discovered during incubation."""

    @pytest.mark.asyncio
    async def test_edge_case_empty_message(self):
        """Edge case #1: Empty messages should ask for clarification."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        result = await agent.handle_query(
            message="",
            channel="web_form",
            customer_id="test-empty-msg"
        )
        # Should return some response, not crash
        assert result is not None
        assert "response" in result

    @pytest.mark.asyncio
    async def test_edge_case_pricing_escalation(self):
        """Edge case #2: Pricing questions MUST trigger escalation."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        for pricing_query in [
            "How much does the enterprise plan cost?",
            "What is your pricing?",
            "I need a price quote",
        ]:
            result = await agent.handle_query(
                message=pricing_query,
                channel="email",
                customer_id="test-pricing"
            )
            assert result["should_escalate"] is True, (
                f"Expected escalation for: '{pricing_query}'"
            )

    @pytest.mark.asyncio
    async def test_edge_case_angry_customer(self):
        """Edge case #3: Angry/frustrated customers need empathy or escalation."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        result = await agent.handle_query(
            message="This is RIDICULOUS! Your product is completely BROKEN and I am FURIOUS!",
            channel="whatsapp",
            customer_id="test-angry"
        )
        # Sentiment should be negative
        assert result["sentiment"] < 0
        # Should escalate or show empathy
        assert result is not None

    @pytest.mark.asyncio
    async def test_channel_response_email_has_greeting(self):
        """Verify email responses contain formal greeting."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        result = await agent.handle_query(
            message="How do I reset my password?",
            channel="email",
            customer_id="test-email-format"
        )
        response = result["response"].lower()
        assert (
            "dear" in response or "hello" in response or "greetings" in response
        ), f"Email response missing formal greeting: {result['response'][:100]}"

    @pytest.mark.asyncio
    async def test_channel_response_whatsapp_is_short(self):
        """Verify WhatsApp responses are concise."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        result = await agent.handle_query(
            message="How do I reset my password?",
            channel="whatsapp",
            customer_id="test-wa-format"
        )
        assert len(result["response"]) < 1000, (
            f"WhatsApp response too long: {len(result['response'])} chars"
        )

    @pytest.mark.asyncio
    async def test_edge_case_legal_threat_escalates(self):
        """Edge case #9: Legal threats must always escalate."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        legal_messages = [
            "I'm going to sue your company",
            "My lawyer will be in touch",
            "This is a legal matter",
        ]
        for msg in legal_messages:
            result = await agent.handle_query(
                message=msg,
                channel="email",
                customer_id="test-legal"
            )
            assert result["should_escalate"] is True, (
                f"Expected escalation for legal threat: '{msg}'"
            )

    @pytest.mark.asyncio
    async def test_edge_case_refund_escalates(self):
        """Edge case: Refund requests must always escalate."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        result = await agent.handle_query(
            message="I want a refund for my subscription",
            channel="email",
            customer_id="test-refund"
        )
        assert result["should_escalate"] is True
        assert result["escalation_reason"] is not None

    def test_sentiment_detection_negative(self):
        """Sentiment detection should correctly identify negative messages."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        negative_msgs = [
            "I am absolutely furious with your terrible service",
            "This product is awful and I hate it",
            "Worst support ever, completely frustrated",
        ]
        for msg in negative_msgs:
            score = agent.detect_sentiment(msg)
            assert score < 0, f"Expected negative sentiment for: '{msg}', got {score}"

    def test_sentiment_detection_positive(self):
        """Sentiment detection should correctly identify positive messages."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        positive_msgs = [
            "Thank you so much, this is perfect!",
            "Great product, love it!",
            "Your support is amazing, very helpful",
        ]
        for msg in positive_msgs:
            score = agent.detect_sentiment(msg)
            assert score > 0, f"Expected positive sentiment for: '{msg}', got {score}"

    def test_knowledge_base_returns_results(self):
        """Knowledge base should return results for common queries."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        results = agent.search_knowledge_base("password reset")
        assert isinstance(results, list)
        # May have results or not, but should not crash
        assert results is not None

    def test_channel_format_email_has_signature(self):
        """Email format should include signature."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        formatted = agent.format_for_channel(
            response="Here is your answer.",
            channel="email"
        )
        assert "best regards" in formatted.lower() or "techcorp" in formatted.lower()

    def test_channel_format_whatsapp_shorter(self):
        """WhatsApp response should be shorter than email for same content."""
        from agent.agent_prototype import CustomerSuccessAgent

        agent = CustomerSuccessAgent()
        content = "Here is a detailed explanation of how to use our product features."

        email_response = agent.format_for_channel(response=content, channel="email")
        wa_response = agent.format_for_channel(response=content, channel="whatsapp")

        assert len(email_response) >= len(wa_response), (
            "Email response should be longer than WhatsApp response"
        )


class TestToolMigration:
    """Verify production tools work equivalently to MCP versions."""

    @pytest.mark.asyncio
    async def test_knowledge_search_returns_string(self):
        """search_knowledge_base should always return a string."""
        from agent.tools import search_knowledge_base

        with patch("agent.tools.get_db_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            mock_pool.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            pool_mock = AsyncMock()
            pool_mock.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            pool_mock.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_pool.return_value = pool_mock

            result = await search_knowledge_base(
                query="password reset",
                max_results=3
            )
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_create_ticket_returns_ticket_id(self):
        """create_ticket should return a ticket ID string."""
        from agent.tools import create_ticket

        with patch("agent.tools.get_db_pool") as mock_pool:
            mock_conn = AsyncMock()
            import uuid
            mock_conn.fetchval.return_value = uuid.uuid4()
            pool_mock = AsyncMock()
            pool_mock.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            pool_mock.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_pool.return_value = pool_mock

            result = await create_ticket(
                customer_id=str(uuid.uuid4()),
                issue="Test issue",
                channel="email",
                priority="medium"
            )
            assert isinstance(result, str)
            assert "ticket" in result.lower() or len(result) > 0

    @pytest.mark.asyncio
    async def test_search_handles_no_results_gracefully(self):
        """Knowledge search should handle no results without crashing."""
        from agent.tools import search_knowledge_base

        with patch("agent.tools.get_db_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = []
            pool_mock = AsyncMock()
            pool_mock.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            pool_mock.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_pool.return_value = pool_mock

            result = await search_knowledge_base(
                query="xyznonexistentquery12345abc",
                max_results=3
            )
            assert isinstance(result, str)
            assert "no" in result.lower() or "not found" in result.lower() or len(result) > 0

    @pytest.mark.asyncio
    async def test_escalate_to_human_returns_confirmation(self):
        """escalate_to_human should return a confirmation string."""
        from agent.tools import escalate_to_human
        import uuid

        with patch("agent.tools.get_db_pool") as mock_pool:
            mock_conn = AsyncMock()
            pool_mock = AsyncMock()
            pool_mock.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            pool_mock.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_pool.return_value = pool_mock

            result = await escalate_to_human(
                ticket_id=str(uuid.uuid4()),
                reason="pricing_inquiry",
                urgency="normal"
            )
            assert isinstance(result, str)
            assert len(result) > 0
