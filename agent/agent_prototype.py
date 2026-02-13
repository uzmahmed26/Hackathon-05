"""
Customer Success Agent Prototype
Implements the core functionality for a customer support AI agent.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

# Import the skills
from agent.skills.knowledge_retrieval import KnowledgeRetrieval
from agent.skills.sentiment_analysis import SentimentAnalysis
from agent.skills.escalation_decision import EscalationDecision
from agent.skills.channel_adaptation import ChannelAdaptation
from agent.skills.customer_identification import CustomerIdentification
from agent.hf_client import QwenClient


class CustomerSuccessAgent:
    def __init__(self, hf_token: Optional[str] = None, db_client=None):
        """
        Initialize the customer success agent with required skills.
        
        Args:
            hf_token: Hugging Face API token for Qwen model (optional for testing)
            db_client: Database client for storing conversations (optional for testing)
        """
        # Initialize all required skills
        self.knowledge_retrieval = KnowledgeRetrieval()
        self.sentiment_analysis = SentimentAnalysis()
        self.escalation_decision = EscalationDecision()
        self.channel_adaptation = ChannelAdaptation()
        self.customer_identification = CustomerIdentification()
        
        # Initialize Qwen client if token is provided
        self.qwen_client = None
        if hf_token:
            self.qwen_client = QwenClient(hf_token)
        
        # Initialize database client
        self.db_client = db_client
    
    async def handle_query(self, message: str, channel: str, customer_id: str, conversation_id: str = None) -> Dict[str, Any]:
        """
        Main method to handle a customer query.
        
        Args:
            message: Customer's message
            channel: Communication channel ('email', 'whatsapp', 'web_form')
            customer_id: Customer identifier
            conversation_id: Existing conversation ID (optional, creates new if not provided)
            
        Returns:
            Dictionary with response, sentiment, escalation info
        """
        # Step 0: Create conversation in DB if available and no conversation_id provided
        if conversation_id is None and self.db_client:
            conversation_id = await self.create_conversation(customer_id, channel)
        
        # Step 1: Store customer message in DB if available
        if self.db_client:
            await self.store_message(conversation_id, 'customer', message)
        
        # Step 2: Identify customer
        customer_info = self.customer_identification.identify_customer(
            identifier=customer_id
        )
        
        # Step 3: Analyze sentiment
        sentiment_result = self.sentiment_analysis.detect_sentiment(
            message=message
        )
        
        # Step 4: Get conversation history if DB is available
        conversation_history = []
        if self.db_client:
            conversation_history = await self.get_conversation_history(conversation_id)
        
        # Step 5: Search knowledge base
        knowledge_results = self.knowledge_retrieval.get_relevant_entries(
            query=message,
            context=f"Customer type: {customer_info['customer_type']}",
            max_results=3
        )
        
        # Step 6: Generate response using Qwen if client is available
        if self.qwen_client:
            try:
                # Format context from knowledge base results
                context_str = ""
                for entry in knowledge_results['results']:
                    context_str += f"Q: {entry['title']}\nA: {entry['content']}\n\n"
                
                # Create prompt for Qwen
                prompt = f"""You are a helpful customer support agent for TechCorp. 
Context from documentation: 
{context_str}

Customer question: {message}
Provide a helpful, accurate answer based on the documentation."""
                
                # Generate response using Qwen
                ai_response = await self.qwen_client.generate_with_retry(
                    prompt=prompt,
                    max_tokens=500,
                    temperature=0.7
                )
            except Exception as e:
                print(f"Error with Qwen API: {e}")
                # Fallback to knowledge base response
                if knowledge_results['results']:
                    ai_response = f"Based on our documentation: {knowledge_results['results'][0]['content']}"
                else:
                    ai_response = "I'm sorry, I couldn't find specific information about your query. Let me connect you with a human agent."
        else:
            # Fallback when Qwen client is not initialized
            if knowledge_results['results']:
                ai_response = f"Based on our documentation: {knowledge_results['results'][0]['content']}"
            else:
                ai_response = "I'm sorry, I couldn't find specific information about your query. Let me connect you with a human agent."
        
        # Step 7: Check if escalation is needed
        escalation_result = self.escalation_decision.should_escalate(
            customer_message=message,
            conversation_history=conversation_history,
            customer_profile=customer_info['profile_summary'],
            sentiment_result=sentiment_result,
            resolution_attempts=0  # In a real implementation, this would track actual attempts
        )
        
        # Step 8: Format response for channel
        if escalation_result['should_escalate']:
            # Generate escalation message
            ai_response = f"I understand this is important. A human agent will contact you within {escalation_result['recommended_wait_time']} minutes."
        
        adapted_response = self.channel_adaptation.adapt_response(
            original_response=ai_response,
            channel=channel,
            customer_profile=customer_info['profile_summary'],
            sentiment_context=sentiment_result
        )
        
        # Step 9: Store agent response in DB if available
        if self.db_client:
            await self.store_message(conversation_id, 'agent', adapted_response['adapted_response'])
        
        # Step 10: Return complete response
        return {
            'response': adapted_response['adapted_response'],
            'sentiment': sentiment_result['sentiment_score'],
            'should_escalate': escalation_result['should_escalate'],
            'conversation_id': conversation_id,  # Return conversation ID for follow-ups
            'escalation_reason': escalation_result['reasons'][0] if escalation_result['reasons'] else None
        }
    
    async def create_conversation(self, customer_id: str, channel: str):
        """
        Create a new conversation record in the database.
        
        Args:
            customer_id: Customer identifier
            channel: Communication channel
            
        Returns:
            Conversation ID
        """
        if self.db_client:
            return await self.db_client.create_conversation(customer_id, channel)
        else:
            # For testing purposes, return a mock conversation ID
            return f"mock_conv_{customer_id}_{channel}"
    
    async def store_message(self, conversation_id: str, sender: str, content: str):
        """
        Store a message in the conversation.
        
        Args:
            conversation_id: ID of the conversation
            sender: Who sent the message ('customer' or 'agent')
            content: Content of the message
        """
        if self.db_client:
            await self.db_client.store_message(conversation_id, sender, content)
    
    async def get_conversation_history(self, conversation_id: str):
        """
        Get the conversation history.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            List of messages in the conversation
        """
        if self.db_client:
            return await self.db_client.get_conversation_history(conversation_id)
        else:
            # For testing purposes, return an empty list
            return []
    
    def search_knowledge_base(self, query: str) -> List[Dict[str, Any]]:
        """
        Search the knowledge base for relevant information.
        
        Args:
            query: Search query string
            
        Returns:
            List of relevant FAQ entries with title, content, and relevance score
        """
        results = self.knowledge_retrieval.get_relevant_entries(
            query=query,
            max_results=3
        )
        
        formatted_results = []
        for entry in results['results']:
            formatted_results.append({
                'title': entry['title'],
                'content': entry['content'],
                'relevance_score': entry['confidence']
            })
        
        return formatted_results
    
    async def generate_response(self, query: str, context: List[Dict[str, Any]]) -> str:
        """
        Generate a response using the Qwen model with provided context.
        
        Args:
            query: Customer's question
            context: List of relevant knowledge base entries
            
        Returns:
            Generated response string
        """
        if not self.qwen_client:
            # Fallback if Qwen client is not initialized
            if context:
                return f"Based on our documentation: {context[0]['content']}"
            else:
                return "I'm sorry, I couldn't find specific information about your query."
        
        # Format context for the prompt
        context_str = ""
        for entry in context:
            context_str += f"Q: {entry['title']}\nA: {entry['content']}\n\n"
        
        # Create prompt for Qwen
        prompt = f"""You are a helpful customer support agent for TechCorp. 
Context from documentation: 
{context_str}

Customer question: {query}
Provide a helpful, accurate answer based on the documentation."""
        
        # Generate response using Qwen
        response = await self.qwen_client.generate_with_retry(
            prompt=prompt,
            max_tokens=500,
            temperature=0.7
        )
        
        return response
    
    def format_for_channel(self, response: str, channel: str) -> str:
        """
        Format the response appropriately for the given channel.
        
        Args:
            response: Raw response text
            channel: Communication channel ('email', 'whatsapp', 'web_form')
            
        Returns:
            Formatted response string
        """
        adapted = self.channel_adaptation.adapt_response(
            original_response=response,
            channel=channel
        )
        return adapted['adapted_response']
    
    def detect_sentiment(self, message: str) -> float:
        """
        Detect sentiment in a customer message.
        
        Args:
            message: Customer message to analyze
            
        Returns:
            Sentiment score from -1 (very negative) to 1 (very positive)
        """
        result = self.sentiment_analysis.detect_sentiment(message)
        return result['sentiment_score']
    
    def should_escalate(self, message: str, sentiment: float) -> tuple[bool, Optional[str]]:
        """
        Determine if a query should be escalated to a human agent.
        
        Args:
            message: Customer message
            sentiment: Sentiment score from detect_sentiment
            
        Returns:
            Tuple of (should_escalate: bool, reason: str or None)
        """
        # Create a mock sentiment result to pass to the escalation decision skill
        sentiment_result = {
            'sentiment_score': sentiment
        }
        
        # Create mock customer profile (in a real implementation, this would come from customer identification)
        customer_profile = {
            'customer_type': 'regular'  # Default to regular customer
        }
        
        result = self.escalation_decision.should_escalate(
            customer_message=message,
            conversation_history=[],
            customer_profile=customer_profile,
            sentiment_result=sentiment_result,
            resolution_attempts=0
        )
        
        reason = result['reasons'][0] if result['reasons'] else None
        return result['should_escalate'], reason


# Example usage
if __name__ == "__main__":
    import os
    
    # Get Hugging Face token from environment variable
    hf_token = os.getenv("HF_TOKEN")
    
    # Initialize the agent
    agent = CustomerSuccessAgent(hf_token=hf_token)
    
    # Example query
    async def test_agent():
        result = await agent.handle_query(
            message="I need to reset my password but I'm not receiving the reset email",
            channel="email",
            customer_id="john.doe@example.com"
        )
        
        print("Response:", result['response'])
        print("Sentiment:", result['sentiment'])
        print("Should Escalate:", result['should_escalate'])
        print("Escalation Reason:", result['escalation_reason'])
    
    # Run the test
    if hf_token:
        asyncio.run(test_agent)
    else:
        print("HF_TOKEN not set. Running without Qwen API integration.")
        # Create a simple test without async to show basic functionality
        sentiment = agent.detect_sentiment("I need to reset my password but I'm not receiving the reset email")
        should_esc, reason = agent.should_escalate("I need to reset my password", sentiment)
        
        print(f"Sentiment: {sentiment}")
        print(f"Should Escalate: {should_esc}")
        print(f"Reason: {reason}")
        
        # Search knowledge base
        kb_results = agent.search_knowledge_base("password reset")
        print(f"KB Results: {len(kb_results)} found")
        for result in kb_results:
            print(f"  - {result['title'][:50]}...")