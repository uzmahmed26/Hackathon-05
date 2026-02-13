"""
Hugging Face Client for Qwen API integration
Handles communication with Hugging Face Inference API for Qwen 2.5 model.
"""

import asyncio
import time
from typing import Dict, Any, Optional
from huggingface_hub import InferenceClient


class QwenClient:
    def __init__(self, token: str):
        """
        Initialize the Qwen client with Hugging Face token.
        
        Args:
            token: Hugging Face API token for authentication
        """
        self.client = InferenceClient(token=token)
        self.rate_limit_delay = 1  # Delay in seconds between requests to handle rate limits
        self.last_request_time = 0

    async def generate(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Generate text using the Qwen model via Hugging Face Inference API.
        
        Args:
            prompt: Input prompt for text generation
            max_tokens: Maximum number of tokens to generate (default: 500)
            temperature: Sampling temperature for generation (default: 0.7)
            
        Returns:
            Generated text response
        """
        # Handle rate limiting by ensuring minimum delay between requests
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            # Wait before making the next request
            await asyncio.sleep(self.rate_limit_delay - time_since_last_request)
        
        try:
            # Update the last request time
            self.last_request_time = time.time()
            
            # Call the Hugging Face Inference API
            # Using text generation task for the Qwen model
            response = self.client.text_generation(
                prompt=prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                return_full_text=False  # Only return the generated part
            )
            
            return response
        
        except Exception as e:
            # Handle rate limit errors specifically
            if "rate limit" in str(e).lower():
                print("Rate limit reached. Waiting before retrying...")
                await asyncio.sleep(5)  # Wait 5 seconds before retrying
                # Retry the request once
                try:
                    response = self.client.text_generation(
                        prompt=prompt,
                        max_new_tokens=max_tokens,
                        temperature=temperature,
                        return_full_text=False
                    )
                    return response
                except Exception as retry_error:
                    print(f"Retry failed: {retry_error}")
                    return "I'm sorry, I'm currently experiencing high demand. Please try again later."
            
            # Handle other errors
            print(f"Error generating response: {e}")
            return "I'm sorry, I encountered an error while processing your request. Please try again later."
    
    async def generate_with_retry(self, prompt: str, max_tokens: int = 500, 
                                 temperature: float = 0.7, max_retries: int = 3) -> str:
        """
        Generate text with automatic retry logic for handling temporary failures.
        
        Args:
            prompt: Input prompt for text generation
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature for generation
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            Generated text response
        """
        for attempt in range(max_retries):
            try:
                response = await self.generate(prompt, max_tokens, temperature)
                
                # If the response is valid (not an error message), return it
                if not response.startswith("I'm sorry"):
                    return response
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    # Exponential backoff: wait longer between retries
                    wait_time = (2 ** attempt) + 1
                    await asyncio.sleep(wait_time)
                else:
                    # All retries exhausted
                    return "I'm sorry, I'm unable to process your request at this time. Please try again later."
        
        return "I'm sorry, I'm unable to process your request after multiple attempts. Please try again later."


# Example usage
if __name__ == "__main__":
    import os
    
    # Get token from environment variable (recommended for security)
    hf_token = os.getenv("HF_TOKEN")
    
    if not hf_token:
        print("Please set the HF_TOKEN environment variable with your Hugging Face token")
    else:
        # Initialize the client
        qwen_client = QwenClient(token=hf_token)
        
        # Example prompt
        prompt = """You are a helpful customer support agent for TechCorp. 
        Context from documentation: Password reset is done through the account settings page.
        Customer question: How do I reset my password?
        Provide a helpful, accurate answer based on the documentation."""
        
        # Generate response (this would need to be called within an async context)
        # response = asyncio.run(qwen_client.generate_with_retry(prompt))
        # print(response)