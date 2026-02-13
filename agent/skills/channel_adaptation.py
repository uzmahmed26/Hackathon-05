"""
Channel Adaptation Skill
Adapts response tone, length, and format based on communication channel.
"""

from typing import Dict, Any, Optional


class ChannelAdaptation:
    def __init__(self):
        """
        Initialize the channel adaptation system.
        """
        # Define character limits for different channels
        self.char_limits = {
            'whatsapp': 300,
            'sms': 160,
            'live_chat': 500,
            'voice': 200,  # Words instead of characters for voice
            'email': 1000,
            'web_form': 500
        }
        
        # Define greeting styles for different channels
        self.greetings = {
            'email': 'Dear Customer,',
            'whatsapp': 'Hey there!',
            'live_chat': 'Hi there!',
            'web_form': 'Hello,',
            'voice': ''  # No greeting needed for voice as it's usually verbal
        }
        
        # Define closing styles for different channels
        self.closings = {
            'email': 'Best regards,\nTechCorp Support',
            'whatsapp': 'Have a great day!',
            'live_chat': 'Take care!',
            'web_form': 'Thank you for contacting us.',
            'voice': ''  # No closing needed for voice as it's usually verbal
        }

    def format_for_channel(self, response: str, channel: str) -> str:
        """
        Format the response appropriately for the given channel.
        
        Args:
            response: Original response text
            channel: Communication channel ('email', 'whatsapp', 'live_chat', 'voice', 'web_form')
            
        Returns:
            Formatted response for the specific channel
        """
        # Normalize channel name
        channel = channel.lower()
        
        # Apply channel-specific formatting
        if channel == 'email':
            # Formal email format
            formatted_response = f"{self.greetings.get(channel, '')}\n\n{response}\n\n{self.closings.get(channel, '')}"
        elif channel == 'whatsapp':
            # Casual WhatsApp format, shorter
            formatted_response = f"{self.greetings.get(channel, '')} {response} {self.closings.get(channel, '')}"
            # Ensure it stays under the character limit
            if len(formatted_response) > self.char_limits.get(channel, 300):
                # Truncate and add indicator
                formatted_response = formatted_response[:self.char_limits[channel]-10] + "... (continued)"
        elif channel == 'web_form':
            # Semi-formal format for web form responses
            formatted_response = f"{self.greetings.get(channel, '')}\n\n{response}\n\n{self.closings.get(channel, '')}"
            # Ensure it's within reasonable length
            if len(formatted_response) > self.char_limits.get(channel, 500):
                # Truncate to fit
                formatted_response = formatted_response[:self.char_limits[channel]-10] + "..."
        elif channel in ['live_chat', 'voice']:
            # Casual format for live chat or voice
            if channel == 'live_chat':
                formatted_response = f"{self.greetings.get(channel, '')} {response} {self.closings.get(channel, '')}"
            else:
                # For voice, just return the response as-is (no formatting needed)
                formatted_response = response
        else:
            # Default: return as-is if channel not recognized
            formatted_response = response
        
        return formatted_response

    def adapt_response(
        self,
        original_response: str,
        channel: str,
        customer_profile: Optional[Dict[str, Any]] = None,
        sentiment_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main method to adapt a response to the appropriate channel format.
        
        Args:
            original_response: AI-generated response before adaptation
            channel: Communication channel
            customer_profile: Customer information (age, preferences, history)
            sentiment_context: Current sentiment of the conversation
            
        Returns:
            Dictionary containing the adapted response and metadata
        """
        # Format the response for the channel
        adapted_response = self.format_for_channel(original_response, channel)
        
        # Adjust tone based on sentiment if provided
        if sentiment_context:
            sentiment_score = sentiment_context.get('sentiment_score', 0)
            
            # If sentiment is negative, add more empathetic language
            if sentiment_score < -0.2:
                if channel == 'email':
                    # Add empathetic opening for negative sentiment in emails
                    adapted_response = f"{self.greetings.get(channel, '')}\n\nI understand this situation might be frustrating. {adapted_response[len(self.greetings.get(channel, '')):].lstrip()}"
                elif channel in ['whatsapp', 'live_chat']:
                    # Add empathetic note for chat channels
                    adapted_response = f"Hey there! 😕 I understand this might be frustrating. {adapted_response[len(self.greetings.get(channel, '')):].lstrip()}"
        
        # Determine tone level based on channel
        tone_mapping = {
            'email': 'formal',
            'whatsapp': 'casual',
            'live_chat': 'friendly',
            'voice': 'conversational',
            'web_form': 'semi-formal'
        }
        
        tone_level = tone_mapping.get(channel, 'neutral')
        
        # Prepare accessibility features (if applicable)
        accessibility_features = []
        if channel == 'voice':
            # For voice, ensure simple, clear language
            accessibility_features.append('simple_language')
        elif channel in ['email', 'web_form']:
            # For email/web, consider adding alt-text for any images (not applicable here)
            pass
        
        return {
            'adapted_response': adapted_response,
            'formatting_applied': [f'channel_specific_formatting_{channel}'],
            'tone_level': tone_level,
            'accessibility_features': accessibility_features
        }


# Example usage
if __name__ == "__main__":
    # Initialize the channel adaptation system
    channel_adapter = ChannelAdaptation()
    
    # Test response
    original_response = "I understand your concern about the delayed shipment. We can look into this for you."
    
    # Test different channels
    channels = ['email', 'whatsapp', 'web_form', 'live_chat']
    
    for channel in channels:
        result = channel_adapter.adapt_response(
            original_response=original_response,
            channel=channel,
            sentiment_context={'sentiment_score': -0.5}  # Negative sentiment
        )
        
        print(f"Channel: {channel}")
        print(f"Tone: {result['tone_level']}")
        print(f"Response: {result['adapted_response']}")
        print("-" * 60)