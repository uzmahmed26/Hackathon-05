"""
WhatsApp Handler for Customer Success AI
Handles WhatsApp integration with Twilio API
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from twilio.base.exceptions import TwilioRestException
import asyncio
import time
from fastapi import Request, Response, HTTPException


class WhatsAppHandler:
    """Main class for handling WhatsApp integration with Twilio."""
    
    def __init__(self):
        """Initialize the WhatsApp handler with Twilio credentials."""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        if not self.account_sid or not self.auth_token:
            # Don't raise an error, just set a flag for later use
            self.is_configured = False
            self.client = None
            self.validator = None
        else:
            self.client = Client(self.account_sid, self.auth_token)
            self.validator = RequestValidator(self.auth_token)
            self.is_configured = True

        self.logger = logging.getLogger(__name__)
    
    async def validate_webhook(self, request: Request) -> bool:
        """
        Validate Twilio webhook signature for security.

        Args:
            request: FastAPI request object

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.is_configured:
            # In test/dev mode, always return True
            return True
            
        try:
            # Get the signature from the header
            signature = request.headers.get('X-Twilio-Signature')
            if not signature:
                self.logger.warning("No Twilio signature in request headers")
                return False

            # Get the URL of the request
            url = str(request.url).split('?')[0]  # Remove query params

            # Get form data
            form_data = await request.form()
            form_dict = {}
            for key, value in form_data.items():
                form_dict[key] = value

            # Validate the signature
            is_valid = self.validator.validate(url, form_dict, signature)

            if not is_valid:
                self.logger.warning("Invalid Twilio webhook signature")

            return is_valid
        except Exception as e:
            self.logger.error(f"Error validating webhook signature: {e}")
            return False
    
    async def process_webhook(self, form_data: dict) -> dict:
        """
        Process incoming Twilio webhook payload.
        
        Args:
            form_data: Form data from Twilio webhook
            
        Returns:
            Normalized message dictionary
        """
        try:
            # Extract required fields from the webhook payload
            message_sid = form_data.get('MessageSid', '')
            from_phone = form_data.get('From', '')
            body = form_data.get('Body', '')
            profile_name = form_data.get('ProfileName', '')
            num_media = int(form_data.get('NumMedia', 0))
            
            # Extract media URLs if present
            media_urls = []
            for i in range(num_media):
                media_url_key = f'MediaUrl{i}'
                if media_url_key in form_data:
                    media_urls.append(form_data[media_url_key])
            
            # Get additional metadata
            wa_id = form_data.get('WaId', '')
            sms_status = form_data.get('SmsStatus', '')
            
            # Clean the phone number
            clean_phone = self._clean_phone_number(from_phone)
            
            # Create normalized message
            normalized_message = {
                'channel': 'whatsapp',
                'channel_message_id': message_sid,
                'customer_phone': clean_phone,
                'customer_name': profile_name,
                'content': body,
                'received_at': datetime.utcnow().isoformat() + 'Z',
                'metadata': {
                    'num_media': num_media,
                    'media_urls': media_urls,
                    'wa_id': wa_id,
                    'status': sms_status
                }
            }
            
            self.logger.info(f"Processed WhatsApp message from {clean_phone}: {body[:50]}...")
            return normalized_message
        except Exception as e:
            self.logger.error(f"Error processing webhook: {e}")
            raise
    
    async def send_message(self, to_phone: str, body: str) -> dict:
        """
        Send a WhatsApp message via Twilio API.

        Args:
            to_phone: Recipient's phone number (will be formatted to WhatsApp format)
            body: Message body

        Returns:
            Response with message ID and delivery status
        """
        if not self.is_configured:
            # In test/dev mode, return mock response
            return {
                'channel_message_id': 'mock_msg_' + str(time.time()),
                'delivery_status': 'sent',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'to': to_phone
            }
            
        try:
            # Format the recipient phone number to WhatsApp format
            formatted_to = self._format_phone_for_whatsapp(to_phone)

            # Check message length (Twilio's limit is 1600 characters for WhatsApp)
            if len(body) > 1600:
                self.logger.warning(f"Message exceeds 1600 character limit ({len(body)} chars), truncating")
                body = body[:1600]

            # Send the message with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    message = self.client.messages.create(
                        body=body,
                        from_=self.whatsapp_number,
                        to=formatted_to
                    )

                    response = {
                        'channel_message_id': message.sid,
                        'delivery_status': message.status,
                        'timestamp': message.date_created.isoformat() if message.date_created else datetime.utcnow().isoformat() + 'Z',
                        'to': formatted_to
                    }

                    self.logger.info(f"WhatsApp message sent successfully to {formatted_to}")
                    return response

                except TwilioRestException as e:
                    self.logger.warning(f"Twilio API error (attempt {attempt + 1}): {e.code} - {e.msg}")
                    if e.code == 20429:  # Rate limit exceeded
                        # Wait with exponential backoff
                        wait_time = (2 ** attempt) + 1  # 1, 3, 7 seconds
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # For other errors, don't retry
                        raise

                except Exception as e:
                    self.logger.warning(f"General error sending message (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + 1  # 1, 3, 7 seconds
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise

            # If we get here, all retries failed
            raise Exception(f"Failed to send message after {max_retries} attempts")

        except Exception as e:
            self.logger.error(f"Error sending WhatsApp message to {to_phone}: {e}")
            raise
    
    def format_response(self, response: str, max_length: int = 1600) -> str:
        """
        Format response to fit within WhatsApp's character limit.

        Args:
            response: Original response text
            max_length: Maximum length per message chunk (default 1600)

        Returns:
            Formatted response string (truncated to max_length if needed)
        """
        if len(response) <= max_length:
            return response
        
        # Split the response into chunks
        chunks = []
        current_chunk = ""
        
        # Split by sentences first
        sentences = response.split('. ')
        
        for sentence in sentences:
            # Add back the period if it's not the last sentence
            if sentence != sentences[-1]:
                sentence += '.'
            
            # Check if adding this sentence would exceed the limit
            if len(current_chunk) + len(sentence) + 1 <= max_length:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                # If the current chunk has content, save it and start a new one
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = sentence
                else:
                    # If the sentence itself is longer than max_length, split it
                    if len(sentence) > max_length:
                        # Split the long sentence into smaller parts
                        parts = [sentence[i:i+max_length] for i in range(0, len(sentence), max_length)]
                        chunks.extend(parts[:-1])  # Add all but the last part
                        current_chunk = parts[-1]  # Start new chunk with last part
                    else:
                        current_chunk = sentence
        
        # Add the last chunk if it exists
        if current_chunk:
            chunks.append(current_chunk)

        return " ".join(chunks)
    
    async def send_media(self, to_phone: str, body: str, media_url: str) -> dict:
        """
        Send a WhatsApp message with media attachment.
        
        Args:
            to_phone: Recipient's phone number
            body: Message body
            media_url: URL to media file (image, PDF, etc.)
            
        Returns:
            Response with message ID and delivery status
        """
        try:
            # Format the recipient phone number to WhatsApp format
            formatted_to = self._format_phone_for_whatsapp(to_phone)
            
            # Send the message with media
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    message = self.client.messages.create(
                        body=body,
                        from_=self.whatsapp_number,
                        to=formatted_to,
                        media_url=[media_url]
                    )
                    
                    response = {
                        'channel_message_id': message.sid,
                        'delivery_status': message.status,
                        'timestamp': message.date_created.isoformat() if message.date_created else datetime.utcnow().isoformat() + 'Z',
                        'to': formatted_to
                    }
                    
                    self.logger.info(f"WhatsApp message with media sent successfully to {formatted_to}")
                    return response
                
                except TwilioRestException as e:
                    self.logger.warning(f"Twilio API error (attempt {attempt + 1}): {e.code} - {e.msg}")
                    if e.code == 20429:  # Rate limit exceeded
                        # Wait with exponential backoff
                        wait_time = (2 ** attempt) + 1  # 1, 3, 7 seconds
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # For other errors, don't retry
                        raise
                
                except Exception as e:
                    self.logger.warning(f"General error sending media message (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + 1  # 1, 3, 7 seconds
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise
            
            # If we get here, all retries failed
            raise Exception(f"Failed to send media message after {max_retries} attempts")
        
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp media message to {to_phone}: {e}")
            raise
    
    async def get_message_status(self, message_sid: str) -> str:
        """
        Get the delivery status of a sent message.
        
        Args:
            message_sid: Twilio message SID
            
        Returns:
            Status string ('queued', 'sent', 'delivered', 'failed', 'undelivered')
        """
        try:
            message = self.client.messages(message_sid).fetch()
            return message.status
        except TwilioRestException as e:
            self.logger.error(f"Error fetching message status for {message_sid}: {e.code} - {e.msg}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error fetching message status for {message_sid}: {e}")
            raise
    
    def _clean_phone_number(self, phone: str) -> str:
        """
        Remove 'whatsapp:' prefix if present and return clean phone number.
        
        Args:
            phone: Phone number string (may include 'whatsapp:' prefix)
            
        Returns:
            Clean phone number
        """
        if phone.startswith('whatsapp:'):
            return phone[9:]  # Remove 'whatsapp:' prefix (9 characters)
        return phone
    
    def _format_phone_for_whatsapp(self, phone: str) -> str:
        """
        Format phone number to Twilio's WhatsApp format.
        
        Args:
            phone: Phone number string
            
        Returns:
            Formatted phone number in 'whatsapp:...' format
        """
        # Remove any existing 'whatsapp:' prefix
        clean_phone = self._clean_phone_number(phone)
        
        # Ensure the phone number starts with '+' and country code
        if not clean_phone.startswith('+'):
            # If it doesn't start with '+', assume it's missing the country code
            # In a real implementation, you might want to add the default country code
            # For now, we'll just add '+1' as a default (US)
            clean_phone = '+1' + clean_phone if not clean_phone.startswith('1') else '+' + clean_phone
        
        return f"whatsapp:{clean_phone}"


# Global instance for use in webhook - will handle missing env vars gracefully
whatsapp_handler = WhatsAppHandler()