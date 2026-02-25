"""
Integration test for Customer Success Agent
Tests the complete flow from message to response using all components together.
"""

import asyncio
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from agent.agent_prototype import CustomerSuccessAgent
from agent.skills.knowledge_retrieval import KnowledgeRetrieval
from agent.skills.sentiment_analysis import SentimentAnalysis
from agent.skills.escalation_decision import EscalationDecision
from agent.skills.channel_adaptation import ChannelAdaptation
from agent.skills.customer_identification import CustomerIdentification


class MockDB:
    """Mock database for testing purposes."""
    
    def __init__(self):
        self.conversations = {}
        self.messages = {}
    
    async def create_conversation(self, customer_id, channel):
        """Create a new conversation record."""
        conversation_id = f"conv_{len(self.conversations) + 1}"
        self.conversations[conversation_id] = {
            'customer_id': customer_id,
            'channel': channel,
            'created_at': '2026-02-11'
        }
        self.messages[conversation_id] = []
        return conversation_id
    
    async def store_message(self, conversation_id, sender, content):
        """Store a message in the conversation."""
        message = {
            'sender': sender,
            'content': content,
            'timestamp': '2026-02-11'
        }
        self.messages[conversation_id].append(message)
    
    async def get_conversation_history(self, conversation_id):
        """Get conversation history."""
        return self.messages.get(conversation_id, [])


class TestIntegration:
    """Integration tests for the complete agent flow."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Initialize the database mock
        self.db = MockDB()
        
        # Initialize the agent with the database mock
        self.agent = CustomerSuccessAgent(db_client=self.db)
        
        # Store original methods to restore after test
        self.original_handle_query = self.agent.handle_query
        self.original_search_kb = self.agent.search_knowledge_base
        self.original_format_channel = self.agent.format_for_channel
        self.original_detect_sentiment = self.agent.detect_sentiment
        self.original_should_escalate = self.agent.should_escalate
    
    def teardown_method(self):
        """Clean up after each test method."""
        # Restore original methods
        self.agent.handle_query = self.original_handle_query
        self.agent.search_knowledge_base = self.original_search_kb
        self.agent.format_for_channel = self.original_format_channel
        self.agent.detect_sentiment = self.original_detect_sentiment
        self.agent.should_escalate = self.original_should_escalate
    
    @pytest.mark.asyncio
    async def test_complete_flow_single_message(self):
        """TEST FLOW 1: Customer sends email: 'How do I add team members to my project?'"""
        customer_id = "test@example.com"
        message = "How do I add team members to my project?"
        channel = "email"
        
        # Mock the knowledge base to return a team member answer
        with patch.object(self.agent.knowledge_retrieval, 'get_relevant_entries', return_value={
            'results': [{
                'id': 1,
                'title': 'Adding Team Members',
                'content': 'To add team members, go to your project settings and click "Invite Members". Enter their email addresses and select their permission level.',
                'confidence': 0.9,
                'source': 'product-docs.md'
            }],
            'query_understanding': 'adding team members'
        }):
            # Mock the Qwen client to return a specific response
            with patch.object(self.agent, 'qwen_client', None):  # No Qwen client in test
                # Mock the generate_response method to return a predictable response
                with patch.object(self.agent, 'generate_response', 
                                return_value="To add team members, go to your project settings and click 'Invite Members'. Enter their email addresses and select their permission level."):
                    
                    # Run the agent's handle_query method
                    result = await self.agent.handle_query(message, channel, customer_id)
        
        # Verify the response
        assert 'response' in result
        assert 'team members' in result['response'].lower()
        assert 'dear customer' in result['response'].lower()  # Formal email greeting
        assert 'invite' in result['response'].lower()
        
        # Verify conversation was stored in DB
        assert len(self.db.conversations) == 1
        conv_id = list(self.db.conversations.keys())[0]
        assert self.db.conversations[conv_id]['customer_id'] == customer_id
        assert self.db.conversations[conv_id]['channel'] == channel
        
        # Verify both messages were stored
        messages = self.db.messages[conv_id]
        assert len(messages) == 2  # Customer message + Agent response
        assert messages[0]['sender'] == 'customer'
        assert messages[0]['content'] == message
        assert messages[1]['sender'] == 'agent'
        assert 'team members' in messages[1]['content'].lower()
    
    @pytest.mark.asyncio
    async def test_complete_flow_follow_up_message(self):
        """TEST FLOW 2: Customer sends follow-up: 'Thanks! Is there a limit on team size?'"""
        customer_id = "test@example.com"
        first_message = "How do I add team members to my project?"
        follow_up_message = "Thanks! Is there a limit on team size?"
        channel = "email"
        
        # First interaction - create conversation and store messages
        with patch.object(self.agent.knowledge_retrieval, 'get_relevant_entries', return_value={
            'results': [{
                'id': 1,
                'title': 'Adding Team Members',
                'content': 'To add team members, go to your project settings and click "Invite Members". Enter their email addresses and select their permission level.',
                'confidence': 0.9,
                'source': 'product-docs.md'
            }],
            'query_understanding': 'adding team members'
        }):
            with patch.object(self.agent, 'qwen_client', None):  # No Qwen client in test
                with patch.object(self.agent, 'generate_response', 
                                return_value="To add team members, go to your project settings and click 'Invite Members'. Enter their email addresses and select their permission level."):
                    
                    # Run the agent's handle_query method for the first message
                    first_result = await self.agent.handle_query(first_message, channel, customer_id)
        
        # Verify first interaction
        assert 'response' in first_result
        assert 'team members' in first_result['response'].lower()
        assert 'dear customer' in first_result['response'].lower()  # Formal email greeting
        
        # Verify conversation was stored in DB
        assert len(self.db.conversations) == 1
        conv_id = first_result.get('conversation_id')  # Get conversation ID from the result
        assert conv_id is not None
        assert self.db.conversations[conv_id]['customer_id'] == customer_id
        assert self.db.conversations[conv_id]['channel'] == channel
        
        # Verify first messages were stored
        messages = self.db.messages[conv_id]
        assert len(messages) == 2  # Customer message + Agent response
        assert messages[0]['sender'] == 'customer'
        assert messages[0]['content'] == first_message
        assert messages[1]['sender'] == 'agent'
        assert 'team members' in messages[1]['content'].lower()
        
        # Second interaction - follow-up message using the same conversation ID
        with patch.object(self.agent.knowledge_retrieval, 'get_relevant_entries', return_value={
            'results': [{
                'id': 1,
                'title': 'Team Size Limits',
                'content': 'Free accounts have a limit of 5 team members. Pro accounts support up to 25 members, and Enterprise accounts have unlimited members.',
                'confidence': 0.95,
                'source': 'product-docs.md'
            }],
            'query_understanding': 'team size limits'
        }):
            # Mock the Qwen client to return a specific response
            with patch.object(self.agent, 'qwen_client', None):  # No Qwen client in test
                # Mock the generate_response method to return a predictable response
                with patch.object(self.agent, 'generate_response', 
                                return_value="Free accounts have a limit of 5 team members. Pro accounts support up to 25 members, and Enterprise accounts have unlimited members."):
                    
                    # Run the agent's handle_query method for the follow-up using the same conversation ID
                    follow_up_result = await self.agent.handle_query(follow_up_message, channel, customer_id, conversation_id=conv_id)
        
        # Verify the follow-up response
        assert 'response' in follow_up_result
        assert 'limit' in follow_up_result['response'].lower() or 'members' in follow_up_result['response'].lower()
        assert 'dear customer' in follow_up_result['response'].lower()  # Formal email greeting
        
        # Verify conversation continues in same thread (still only 1 conversation)
        assert len(self.db.conversations) == 1
        assert conv_id in self.db.conversations
        
        # Verify all messages were stored in the same conversation
        all_messages = self.db.messages[conv_id]
        assert len(all_messages) == 4  # 2 from first interaction + 2 from follow-up
        assert all_messages[2]['sender'] == 'customer'
        assert all_messages[2]['content'] == follow_up_message
        assert all_messages[3]['sender'] == 'agent'
        assert 'limit' in all_messages[3]['content'].lower() or 'members' in all_messages[3]['content'].lower()


# Additional helper test to verify all components are properly integrated
def test_component_integration():
    """Test that all components are properly integrated in the agent."""
    agent = CustomerSuccessAgent()
    
    # Verify all skills are properly initialized
    assert hasattr(agent, 'knowledge_retrieval')
    assert hasattr(agent, 'sentiment_analysis')
    assert hasattr(agent, 'escalation_decision')
    assert hasattr(agent, 'channel_adaptation')
    assert hasattr(agent, 'customer_identification')
    
    # Verify methods exist
    assert hasattr(agent, 'handle_query')
    assert hasattr(agent, 'search_knowledge_base')
    assert hasattr(agent, 'detect_sentiment')
    assert hasattr(agent, 'should_escalate')
    assert hasattr(agent, 'format_for_channel')


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "-s"])