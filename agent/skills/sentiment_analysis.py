"""
Sentiment Analysis Skill
Analyzes user message and classifies sentiment (positive, neutral, negative, angry).
"""

import re
from typing import Dict, List, Optional


class SentimentAnalysis:
    def __init__(self):
        """
        Initialize the sentiment analysis system with predefined word lists.
        """
        # Define word lists for sentiment analysis
        self.positive_words = {
            'thank', 'thanks', 'great', 'love', 'perfect', 'amazing', 'awesome', 
            'excellent', 'good', 'nice', 'fantastic', 'wonderful', 'brilliant',
            'superb', 'outstanding', 'pleased', 'satisfied', 'happy', 'delighted'
        }
        
        self.negative_words = {
            'angry', 'frustrated', 'terrible', 'awful', 'hate', 'disappointed',
            'annoyed', 'upset', 'mad', 'furious', 'horrible', 'disgusting',
            'worst', 'pathetic', 'ridiculous', 'stupid', 'useless', 'broken',
            'problem', 'issue', 'bug', 'error', 'crash', 'fail'
        }
        
        self.anger_words = {
            'angry', 'furious', 'mad', 'rage', 'livid', 'infuriated', 
            'outraged', 'seething', 'enraged', 'irate', 'incensed'
        }
        
        # Compile regex patterns for efficiency
        self.exclamation_pattern = re.compile(r'[!]{2,}')
        self.caps_pattern = re.compile(r'\b[A-Z]{3,}\b')
        
    def detect_sentiment(self, message: str, previous_messages: Optional[List[str]] = None, 
                        language: str = "en") -> Dict[str, float]:
        """
        Analyze the sentiment of a message.
        
        Args:
            message: The customer message to analyze
            previous_messages: Recent conversation history for context
            language: Language of the message (default: "en")
            
        Returns:
            Dictionary containing sentiment analysis results
        """
        # Normalize the message
        normalized_msg = message.lower().strip()
        
        # Initialize scores
        positive_score = 0
        negative_score = 0
        anger_score = 0
        
        # Split message into words
        words = normalized_msg.split()
        
        # Count sentiment-bearing words
        for word in words:
            # Clean the word of punctuation
            clean_word = re.sub(r'[^\w]', '', word)
            
            if clean_word in self.positive_words:
                positive_score += 1
            elif clean_word in self.negative_words:
                negative_score += 1
            elif clean_word in self.anger_words:
                anger_score += 1
                negative_score += 1  # Anger is also negative
        
        # Factor in emotional indicators
        exclamation_count = len(self.exclamation_pattern.findall(message))
        caps_count = len(self.caps_pattern.findall(message))
        
        # Calculate base sentiment score
        total_sentiment_words = positive_score + negative_score
        if total_sentiment_words == 0:
            sentiment_score = 0.0
        else:
            sentiment_score = (positive_score - negative_score) / total_sentiment_words
        
        # Adjust for intensity indicators
        # Exclamations and caps increase emotional intensity
        intensity_factor = 1 + (exclamation_count * 0.1) + (caps_count * 0.05)
        
        # Apply intensity adjustment but cap the score between -1 and 1
        adjusted_score = sentiment_score * intensity_factor
        final_score = max(-1.0, min(1.0, adjusted_score))
        
        # Determine sentiment label
        if final_score > 0.1:
            sentiment_label = "positive"
        elif final_score >= -0.1:
            sentiment_label = "neutral"
        elif final_score >= -0.6:
            sentiment_label = "negative"
        else:
            sentiment_label = "angry"
        
        # Calculate intensity (0-1 scale)
        intensity = abs(final_score)
        
        # Identify emotional indicators
        emotional_indicators = []
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word in self.positive_words:
                if clean_word not in emotional_indicators:
                    emotional_indicators.append(clean_word)
            elif clean_word in self.negative_words:
                if clean_word not in emotional_indicators:
                    emotional_indicators.append(clean_word)
        
        # Add intensity indicators
        if exclamation_count > 0:
            emotional_indicators.extend(['!' * min(exclamation_count, 3)])  # Limit to 3 for display
        if caps_count > 0:
            emotional_indicators.append('CAPS')
        
        # Calculate confidence in classification
        # Higher confidence with more sentiment-bearing words
        confidence = min(1.0, (positive_score + negative_score) / 5.0)
        
        return {
            'sentiment_label': sentiment_label,
            'sentiment_score': round(final_score, 3),
            'intensity': round(intensity, 3),
            'emotional_indicators': emotional_indicators,
            'confidence': round(confidence, 3)
        }


# Example usage
if __name__ == "__main__":
    # Initialize the sentiment analysis system
    sentiment_analyzer = SentimentAnalysis()
    
    # Test messages
    test_messages = [
        "Thank you for your help, it was great!",
        "This is okay, nothing special.",
        "I'm frustrated with this issue.",
        "This is absolutely ridiculous! I've been waiting for hours and nobody is helping me!!!"
    ]
    
    for msg in test_messages:
        result = sentiment_analyzer.detect_sentiment(msg)
        print(f"Message: {msg}")
        print(f"Sentiment: {result['sentiment_label']}")
        print(f"Score: {result['sentiment_score']}")
        print(f"Intensity: {result['intensity']}")
        print(f"Indicators: {result['emotional_indicators']}")
        print("-" * 50)