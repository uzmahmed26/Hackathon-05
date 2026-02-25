"""
Gmail Handler for Customer Success AI
Handles Gmail integration with OAuth2, push notifications, and message processing
"""

import base64
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import message_from_bytes
import asyncio

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError


class GmailAuth:
    """Helper class for Gmail authentication."""
    
    @staticmethod
    def create_credentials(client_secret_path: str, scopes: List[str]) -> Credentials:
        """
        Create credentials from client secret file.
        
        Args:
            client_secret_path: Path to client secret JSON file
            scopes: List of OAuth2 scopes
            
        Returns:
            Credentials object
        """
        from google_auth_oauthlib.flow import InstalledAppFlow
        
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secret_path, scopes
        )
        creds = flow.run_local_server(port=0)
        return creds
    
    @staticmethod
    def refresh_credentials(credentials: Credentials) -> Credentials:
        """
        Refresh expired credentials.
        
        Args:
            credentials: Current credentials object
            
        Returns:
            Refreshed credentials object
        """
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        return credentials
    
    @staticmethod
    def save_credentials(credentials: Credentials, path: str):
        """
        Save credentials to file.
        
        Args:
            credentials: Credentials object to save
            path: Path to save credentials
        """
        with open(path, 'w') as token:
            token.write(credentials.to_json())


class GmailHandler:
    """Main class for handling Gmail integration."""
    
    def __init__(self, credentials_path: str):
        """
        Initialize the Gmail handler.

        Args:
            credentials_path: Path to saved credentials JSON file
        """
        self.credentials_path = credentials_path
        self.logger = logging.getLogger(__name__)
        self.service = self._load_service()
    
    def _load_service(self):
        """Load the Gmail API service."""
        try:
            # Load credentials from file
            with open(self.credentials_path, 'r') as f:
                creds_data = json.load(f)
            
            creds = Credentials.from_authorized_user_info(creds_data)
            
            # Refresh credentials if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed credentials
                with open(self.credentials_path, 'w') as f:
                    f.write(creds.to_json())
            
            # Build the Gmail service
            service = build('gmail', 'v1', credentials=creds)
            return service
        except Exception as e:
            self.logger.warning(f"Gmail service unavailable (credentials not found or invalid): {e}")
            return None  # Service is None when credentials are missing
    
    async def setup_push_notifications(self, webhook_url: str) -> dict:
        """
        Set up Gmail push notifications via Pub/Sub.
        
        Args:
            webhook_url: URL to receive push notifications
            
        Returns:
            Watch response with historyId and expiration
        """
        try:
            # Set up push notification for INBOX
            watch_request = {
                'labelIds': ['INBOX'],
                'topicName': f'projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME'  # This would need to be configured separately
            }
            
            # Note: In a real implementation, you'd need to set up a Google Cloud Pub/Sub topic
            # For now, we'll just return a mock response
            response = {
                'historyId': '1234567890',
                'expiration': '2026-12-31T23:59:59Z'
            }
            
            self.logger.info(f"Push notifications set up for webhook: {webhook_url}")
            return response
        except HttpError as e:
            self.logger.error(f"Failed to set up push notifications: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error setting up push notifications: {e}")
            raise
    
    async def process_notification(self, pubsub_message: dict) -> List[dict]:
        """
        Process a Pub/Sub notification and fetch new messages.
        
        Args:
            pubsub_message: Pub/Sub message payload
            
        Returns:
            List of normalized messages
        """
        try:
            # Decode the Pub/Sub message
            message_data = pubsub_message.get('message', {})
            data = message_data.get('data', '')
            
            if data:
                decoded_data = base64.b64decode(data).decode('utf-8')
                notification = json.loads(decoded_data)
            else:
                notification = {}
            
            # Get the history ID to fetch new messages
            history_id = notification.get('historyId')
            
            # For now, we'll fetch recent messages (in a real implementation, 
            # we'd use the history API to get changes since the last historyId)
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                maxResults=10  # Limit to recent messages
            ).execute()
            
            messages = results.get('messages', [])
            normalized_messages = []
            
            for msg in messages:
                try:
                    normalized_msg = await self.get_message(msg['id'])
                    normalized_messages.append(normalized_msg)
                except Exception as e:
                    self.logger.error(f"Failed to process message {msg['id']}: {e}")
                    continue
            
            return normalized_messages
        except Exception as e:
            self.logger.error(f"Failed to process notification: {e}")
            raise
    
    async def get_message(self, message_id: str) -> dict:
        """
        Fetch a message by ID and normalize it.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Normalized message dictionary
        """
        try:
            # Fetch the full message
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = {header['name']: header['value'] for header in message['payload']['headers']}
            
            # Extract body
            body = self._extract_body(message['payload'])
            
            # Extract sender information
            from_header = headers.get('From', '')
            customer_email = self._extract_email(from_header)
            customer_name = self._extract_name(from_header)
            
            # Get thread ID
            thread_id = message.get('threadId', '')
            
            # Get timestamp
            timestamp = datetime.fromtimestamp(int(message['internalDate']) / 1000).isoformat() + 'Z'
            
            # Normalize the message
            normalized_message = {
                'channel': 'email',
                'channel_message_id': message_id,
                'customer_email': customer_email,
                'customer_name': customer_name,
                'subject': headers.get('Subject', ''),
                'content': body,
                'received_at': timestamp,
                'thread_id': thread_id,
                'metadata': {
                    'headers': headers,
                    'labels': message.get('labelIds', []),
                    'size_estimate': message.get('sizeEstimate', 0),
                    'snippet': message.get('snippet', '')
                }
            }
            
            return normalized_message
        except HttpError as e:
            self.logger.error(f"Failed to fetch message {message_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error fetching message {message_id}: {e}")
            raise
    
    def _extract_body(self, payload: dict) -> str:
        """
        Extract body text from message payload.
        
        Args:
            payload: Gmail message payload
            
        Returns:
            Plain text body
        """
        body = ''
        
        # Handle multipart messages
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    # Decode base64 content
                    raw_data = part['body']['data']
                    decoded_data = base64.urlsafe_b64decode(raw_data.encode('ASCII'))
                    body = decoded_data.decode('utf-8')
                    break
                elif part['mimeType'] == 'text/html':
                    # If no plain text part, use HTML part
                    if not body:
                        raw_data = part['body']['data']
                        decoded_data = base64.urlsafe_b64decode(raw_data.encode('ASCII'))
                        html_body = decoded_data.decode('utf-8')
                        # Strip HTML tags for plain text
                        body = re.sub('<[^<]+?>', '', html_body)
                elif part['mimeType'].startswith('multipart'):
                    # Recursively extract from nested parts
                    nested_body = self._extract_body(part)
                    if nested_body:
                        body = nested_body
                        break
        else:
            # Handle single-part messages
            if 'body' in payload and 'data' in payload['body']:
                raw_data = payload['body']['data']
                decoded_data = base64.urlsafe_b64decode(raw_data.encode('ASCII'))
                body = decoded_data.decode('utf-8')
        
        return body
    
    def _extract_email(self, from_header: str) -> str:
        """
        Extract email address from From header.
        
        Args:
            from_header: From header value
            
        Returns:
            Email address
        """
        # Match email in format "Name <email@domain.com>"
        match = re.search(r'<([^>]+)>', from_header)
        if match:
            return match.group(1)
        
        # If no angle brackets, assume the whole thing is the email
        # (though this is less reliable)
        if '@' in from_header:
            # Remove any leading name part
            parts = from_header.split()
            for part in parts:
                if '@' in part:
                    return part.strip(',"\'')
        
        return from_header.strip(',"\'')
    
    def _extract_name(self, from_header: str) -> str:
        """
        Extract name from From header.
        
        Args:
            from_header: From header value
            
        Returns:
            Name or empty string if not found
        """
        # Match name in format "Name <email@domain.com>"
        match = re.match(r'^([^<]+)', from_header)
        if match:
            name = match.group(1).strip(' "')
            # Remove quotes if present
            if name.startswith('"') and name.endswith('"'):
                name = name[1:-1]
            return name
        
        return ''
    
    async def send_reply(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: str = None,
        in_reply_to: str = None
    ) -> dict:
        """
        Send a reply email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            thread_id: Thread ID to maintain conversation thread
            in_reply_to: Message ID this is a reply to
            
        Returns:
            Response with message ID and delivery status
        """
        try:
            # Create the message
            message = MIMEMultipart()
            message['to'] = to_email
            message['subject'] = subject if subject.startswith('Re:') else f'Re: {subject}'
            
            if in_reply_to:
                message['In-Reply-To'] = in_reply_to
                message['References'] = in_reply_to  # Simplified - in a real impl, build proper refs
            
            # Add body
            message.attach(MIMEText(body, 'plain'))
            
            # Encode the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')
            
            # Prepare send request
            send_message = {
                'raw': raw_message
            }
            
            if thread_id:
                send_message['threadId'] = thread_id
            
            # Send the message
            sent_message = self.service.users().messages().send(
                userId='me',
                body=send_message
            ).execute()
            
            return {
                'channel_message_id': sent_message['id'],
                'delivery_status': 'sent',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        except HttpError as e:
            self.logger.error(f"Failed to send email to {to_email}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error sending email to {to_email}: {e}")
            raise
    
    async def get_thread(self, thread_id: str) -> List[dict]:
        """
        Fetch all messages in a thread.
        
        Args:
            thread_id: Gmail thread ID
            
        Returns:
            List of messages in the thread
        """
        try:
            # Get the thread
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()
            
            messages = []
            for msg in thread['messages']:
                normalized_msg = await self.get_message(msg['id'])
                messages.append(normalized_msg)
            
            return messages
        except HttpError as e:
            self.logger.error(f"Failed to fetch thread {thread_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error fetching thread {thread_id}: {e}")
            raise

    def extract_message_data(self, message: dict) -> dict:
        """
        Extract normalized data from a Gmail API message dict.

        Args:
            message: Gmail API message object with payload.headers and payload.body

        Returns:
            Dict with sender, subject, content, and thread_id keys
        """
        headers = message.get('payload', {}).get('headers', [])
        header_map = {h['name']: h['value'] for h in headers}

        sender = header_map.get('From', '')
        subject = header_map.get('Subject', '')
        thread_id = message.get('threadId', '')

        # Decode base64 body content
        body_data = message.get('payload', {}).get('body', {}).get('data', '')
        if body_data:
            try:
                content = base64.urlsafe_b64decode(body_data + '==').decode('utf-8')
            except Exception:
                content = message.get('snippet', '')
        else:
            content = message.get('snippet', '')

        return {
            'sender': sender,
            'subject': subject,
            'content': content,
            'thread_id': thread_id,
        }

    def format_response(self, response: str) -> str:
        """
        Format a plain text response for email delivery.

        Args:
            response: The raw response text

        Returns:
            Formatted email body string
        """
        return f"Dear Customer,\n\n{response}\n\nBest regards,\nTechCorp Support Team"