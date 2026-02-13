"""
Escalation Decision Skill
Decides whether the issue should be handled by AI or escalated to a human agent.
"""

from typing import Dict, List, Any, Optional


class EscalationDecision:
    def __init__(self):
        """
        Initialize the escalation decision system with predefined criteria.
        """
        # Keywords that trigger escalation
        self.escalation_keywords = {
            'pricing', 'price', 'cost', 'charge', 'refund', 'cancel', 
            'billing', 'payment', 'invoice', 'quote', 'quote', 'enterprise',
            'plan', 'subscription', 'lawyer', 'legal', 'complaint',
            'manager', 'supervisor', 'ceo', 'executive', 'lawsuit', 'sue',
            'contract', 'agreement', 'violation', 'breach', 'dispute'
        }
        
        # Negative sentiment threshold for escalation
        self.negative_sentiment_threshold = -0.3
        
        # Maximum resolution attempts before escalation
        self.max_resolution_attempts = 3

    def should_escalate(
        self,
        customer_message: str,
        conversation_history: List[str],
        customer_profile: Dict[str, Any],
        sentiment_result: Dict[str, Any],
        resolution_attempts: int = 0
    ) -> Dict[str, Any]:
        """
        Determine whether to escalate the issue to a human agent.
        
        Args:
            customer_message: Current customer message
            conversation_history: Previous messages in the conversation
            customer_profile: Customer information (VIP status, history, etc.)
            sentiment_result: Result from sentiment analysis
            resolution_attempts: Number of AI attempts to resolve the issue
            
        Returns:
            Dictionary containing escalation decision and metadata
        """
        reasons = []
        urgency_level = "low"
        
        # Check for escalation keywords in the current message
        message_lower = customer_message.lower()
        found_keywords = [keyword for keyword in self.escalation_keywords 
                         if keyword in message_lower]
        
        if found_keywords:
            reasons.extend(found_keywords)
            # Set urgency based on keyword type
            high_urgency_keywords = {'lawyer', 'legal', 'lawsuit', 'sue', 'violation', 'breach'}
            if any(keyword in high_urgency_keywords for keyword in found_keywords):
                urgency_level = "critical"
            elif urgency_level != "critical":
                urgency_level = "high"
        
        # Check sentiment score
        sentiment_score = sentiment_result.get('sentiment_score', 0)
        if sentiment_score <= self.negative_sentiment_threshold:
            reasons.append(f"negative_sentiment ({sentiment_score})")
            # Increase urgency based on negativity
            if sentiment_score <= -0.6:
                urgency_level = "critical" if urgency_level != "critical" else urgency_level
            elif urgency_level == "low":
                urgency_level = "medium"
        
        # Check if customer explicitly requested human assistance
        human_request_phrases = [
            'speak to a human', 'human agent', 'talk to someone', 
            'real person', 'customer service rep', 'agent', 
            'can i talk', 'i want to speak', 'put me through to'
        ]
        
        for phrase in human_request_phrases:
            if phrase in message_lower:
                reasons.append("customer_requested_human")
                if urgency_level != "critical":
                    urgency_level = "high"
                break
        
        # Check resolution attempts
        if resolution_attempts >= self.max_resolution_attempts:
            reasons.append(f"max_resolution_attempts ({resolution_attempts})")
            if urgency_level == "low":
                urgency_level = "medium"
        
        # Check customer profile (VIP customers may have lower escalation thresholds)
        customer_type = customer_profile.get('customer_type', 'regular')
        if customer_type in ['vip', 'premium']:
            # VIP customers get priority escalation
            if sentiment_score <= -0.2:  # Less negative threshold for VIPs
                if 'negative_sentiment' not in [r.split()[0] for r in reasons]:
                    reasons.append(f"negative_sentiment_vip ({sentiment_score})")
                    if urgency_level == "low":
                        urgency_level = "medium"
        
        # Determine if escalation is needed
        should_escalate = len(reasons) > 0
        
        # Adjust urgency based on customer type
        if customer_type in ['vip', 'premium'] and urgency_level == "low":
            # Even low-urgency issues for VIPs get medium priority
            urgency_level = "medium"
        
        # Prepare preservation data for human agent
        preservation_data = {
            'customer_message': customer_message,
            'conversation_history': conversation_history,
            'customer_profile': customer_profile,
            'sentiment_result': sentiment_result,
            'resolution_attempts': resolution_attempts,
            'reasons': reasons
        }
        
        # Calculate recommended wait time based on urgency
        wait_times = {
            'low': 30,      # 30 minutes
            'medium': 15,   # 15 minutes
            'high': 5,      # 5 minutes
            'critical': 2    # 2 minutes
        }
        
        return {
            'should_escalate': should_escalate,
            'reasons': reasons,
            'urgency_level': urgency_level,
            'recommended_wait_time': wait_times[urgency_level],
            'preservation_data': preservation_data
        }


# Example usage
if __name__ == "__main__":
    # Initialize the escalation decision system
    escalation_system = EscalationDecision()
    
    # Test scenarios
    test_cases = [
        {
            'customer_message': 'I want to cancel my subscription and get a refund',
            'conversation_history': ['Customer asked about features', 'Provided information'],
            'customer_profile': {'customer_type': 'regular'},
            'sentiment_result': {'sentiment_score': -0.1},
            'resolution_attempts': 0
        },
        {
            'customer_message': 'This is terrible service, I want to speak to your manager now!',
            'conversation_history': [],
            'customer_profile': {'customer_type': 'vip'},
            'sentiment_result': {'sentiment_score': -0.7},
            'resolution_attempts': 1
        },
        {
            'customer_message': 'How do I reset my password?',
            'conversation_history': [],
            'customer_profile': {'customer_type': 'regular'},
            'sentiment_result': {'sentiment_score': 0.2},
            'resolution_attempts': 0
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        result = escalation_system.should_escalate(**case)
        print(f"Test Case {i}:")
        print(f"Message: {case['customer_message']}")
        print(f"Should Escalate: {result['should_escalate']}")
        print(f"Reasons: {result['reasons']}")
        print(f"Urgency Level: {result['urgency_level']}")
        print(f"Recommended Wait Time: {result['recommended_wait_time']} minutes")
        print("-" * 60)