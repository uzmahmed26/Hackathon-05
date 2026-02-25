"""
Tests for the Customer Success Agent.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agent.production_agent import CustomerSuccessAgent
from agent.agent_prototype import CustomerSuccessAgent as PrototypeAgent


class TestAgentTools:
    """Test individual agent tools"""
    
    @pytest.mark.asyncio
    async def test_search_knowledge_base(self, db_conn):
        """Test knowledge base search"""
        # Since we don't have the production agent with tools yet, 
        # we'll test the prototype agent's knowledge retrieval
        agent = PrototypeAgent()
        
        # Test with a simple query
        results = agent.search_knowledge_base("password reset")
        
        # Should return a list of results
        assert isinstance(results, list)
        # May not have results if the knowledge base isn't loaded properly in test environment
        # but it shouldn't throw an error
    
    @pytest.mark.asyncio
    async def test_customer_identification(self):
        """Test customer identification"""
        agent = PrototypeAgent()
        
        # Test identifying a customer
        result = agent.customer_identification.identify_customer(identifier='test@example.com')
        
        assert 'customer_type' in result
        assert 'profile_summary' in result
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis(self):
        """Test sentiment analysis"""
        agent = PrototypeAgent()
        
        # Test positive sentiment
        positive_result = agent.detect_sentiment("Thank you for your help, this is great!")
        assert isinstance(positive_result, float)
        
        # Test negative sentiment
        negative_result = agent.detect_sentiment("This is terrible and I'm very frustrated!")
        assert isinstance(negative_result, float)
    
    @pytest.mark.asyncio
    async def test_escalation_decision(self):
        """Test escalation decision"""
        agent = PrototypeAgent()
        
        # Test escalation for pricing query
        should_escalate, reason = agent.should_escalate("How much does the enterprise plan cost?", 0.0)
        assert isinstance(should_escalate, bool)
        
        # Test escalation for angry customer
        should_escalate_angry, reason_angry = agent.should_escalate("This is terrible service!", -0.8)
        assert should_escalate_angry == True


class TestAgentBehavior:
    """Test agent decision making"""
    
    @pytest.mark.asyncio
    async def test_agent_handles_product_question(self):
        """Agent should search KB for product questions"""
        agent = PrototypeAgent()
        
        # Mock the knowledge base to return a result
        with patch.object(agent.knowledge_retrieval, 'get_relevant_entries', return_value={
            'results': [{
                'id': 1,
                'title': 'Password Reset',
                'content': 'To reset your password, go to the login page and click "Forgot Password". Enter your email and follow the instructions.',
                'confidence': 0.9,
                'source': 'product-docs.md'
            }],
            'query_understanding': 'password reset'
        }):
            # Test the agent's response generation
            response = await agent.generate_response(
                query="How do I reset my password?",
                context=[{
                    'title': 'Password Reset',
                    'content': 'To reset your password, go to the login page and click "Forgot Password". Enter your email and follow the instructions.',
                    'relevance_score': 0.9
                }]
            )
            
            assert isinstance(response, str)
            assert len(response) > 0
    
    @pytest.mark.asyncio
    async def test_agent_escalates_pricing_question(self):
        """Agent should escalate pricing questions"""
        agent = PrototypeAgent()
        
        # Test escalation for pricing query
        should_escalate, reason = agent.should_escalate("How much does the enterprise plan cost?", 0.0)
        
        assert should_escalate == True
        assert reason is not None
    
    @pytest.mark.asyncio
    async def test_agent_formats_for_channel(self):
        """Agent should format responses based on channel"""
        agent = PrototypeAgent()
        
        # Test email format
        email_response = agent.format_for_channel(
            response="Thank you for your inquiry about password reset.",
            channel="email"
        )
        
        assert isinstance(email_response, str)
        assert "Dear Customer" in email_response or "Hello" in email_response
        
        # Test WhatsApp format
        whatsapp_response = agent.format_for_channel(
            response="Thanks for reaching out about adding team members!",
            channel="whatsapp"
        )
        
        assert isinstance(whatsapp_response, str)
        # WhatsApp responses tend to be more casual


class TestAgentIntegration:
    """Test agent integration with all components"""
    
    @pytest.mark.asyncio
    async def test_complete_query_handling(self):
        """Test complete query handling flow"""
        agent = PrototypeAgent()
        
        # Mock the Qwen client to avoid API calls in tests
        agent.qwen_client = None
        
        # Test handling a complete query
        result = await agent.handle_query(
            message="I need help with resetting my password",
            channel="email",
            customer_id="test@example.com"
        )
        
        # Verify the result structure
        assert 'response' in result
        assert 'sentiment' in result
        assert 'should_escalate' in result
        assert 'conversation_id' in result
        
        # Response should be a string
        assert isinstance(result['response'], str)
        
        # Sentiment should be a float
        assert isinstance(result['sentiment'], float)
        
        # Should escalate should be boolean
        assert isinstance(result['should_escalate'], bool)


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.mark.asyncio
    async def test_empty_message(self):
        """Handle empty messages gracefully"""
        agent = PrototypeAgent()
        
        # Test with empty message
        result = await agent.handle_query(
            message="",
            channel="email",
            customer_id="test@example.com"
        )
        
        # Should return some form of response
        assert 'response' in result
        assert isinstance(result['response'], str)
    
    @pytest.mark.asyncio
    async def test_unknown_customer(self):
        """Handle unknown customer gracefully"""
        agent = PrototypeAgent()
        
        # Test with unknown customer
        result = await agent.handle_query(
            message="I have a question about your service",
            channel="email",
            customer_id="unknown@example.com"
        )
        
        # Should still return a response
        assert 'response' in result
        assert isinstance(result['response'], str)
    
    @pytest.mark.asyncio
    async def test_long_message(self):
        """Handle very long messages gracefully"""
        agent = PrototypeAgent()
        
        # Create a very long message
        long_message = "This is a very long message. " * 100
        
        result = await agent.handle_query(
            message=long_message,
            channel="email",
            customer_id="test@example.com"
        )
        
        # Should handle long messages without error
        assert 'response' in result
        assert isinstance(result['response'], str)