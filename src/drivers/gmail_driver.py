"""
Gmail Driver - Fetch emails by label with OAuth 2.0 authentication.

Supports:
- Persistent refresh tokens (authenticate once, use for months)
- Label-based filtering
- Full message retrieval (headers, body, attachments)
- Incremental sync (only fetch new messages)

Usage:
    driver = GmailDriver(
        credentials_dir='config/.credentials',
        token_file='gmail_token.json'
    )
    
    # First run: opens browser for OAuth consent
    # Subsequent runs: uses stored refresh token
    
    messages = driver.fetch_by_label('mrayeh', max_results=100)
    for msg in messages:
        print(msg['subject'], msg['from'], msg['date'])
"""

import os
import json
import base64
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scopes
# readonly: Can read emails and labels
# modify: Can also mark as read, add labels, etc.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


@dataclass
class EmailMessage:
    """Parsed email message."""
    id: str
    thread_id: str
    subject: str
    sender: str
    to: str
    date: Optional[datetime]
    snippet: str
    body_text: str
    body_html: str
    labels: List[str]
    attachments: List[Dict[str, Any]]
    headers: Dict[str, str]
    raw_message: Dict[str, Any] = field(default_factory=dict, repr=False)


class GmailDriver:
    """
    Gmail API driver with persistent OAuth authentication.
    
    Tokens are stored in credentials_dir and automatically refreshed.
    First run requires browser-based OAuth consent.
    """
    
    def __init__(
        self,
        credentials_dir: str = 'config/.credentials',
        token_file: str = 'gmail_token.json',
        client_secrets_file: str = 'config/client_secrets.json',
        scopes: List[str] = None
    ):
        self.credentials_dir = credentials_dir
        self.token_path = os.path.join(credentials_dir, token_file)
        self.client_secrets_path = client_secrets_file
        self.scopes = scopes or SCOPES
        self._service = None
        self._credentials = None
        
        # Ensure credentials directory exists
        os.makedirs(credentials_dir, exist_ok=True)
    
    def authenticate(self, force_new: bool = False) -> Credentials:
        """
        Authenticate with Gmail API.
        
        Uses stored token if available, otherwise initiates OAuth flow.
        
        Args:
            force_new: If True, ignore stored token and re-authenticate
            
        Returns:
            Valid Credentials object
        """
        creds = None
        
        # Load existing token
        if not force_new and os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
                print(f"✓ Loaded credentials from {self.token_path}")
            except Exception as e:
                print(f"⚠ Could not load token: {e}")
                creds = None
        
        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("✓ Refreshed expired token")
                self._save_credentials(creds)
            except Exception as e:
                print(f"⚠ Could not refresh token: {e}")
                creds = None
        
        # New OAuth flow if needed
        if not creds or not creds.valid:
            if not os.path.exists(self.client_secrets_path):
                raise FileNotFoundError(
                    f"Client secrets file not found: {self.client_secrets_path}\n"
                    "Download from Google Cloud Console:\n"
                    "1. Go to APIs & Services > Credentials\n"
                    "2. Create OAuth 2.0 Client ID (Desktop app)\n"
                    "3. Download JSON and save as config/client_secrets.json"
                )
            
            print("\n" + "=" * 60)
            print("GMAIL OAUTH AUTHENTICATION")
            print("=" * 60)
            print("Opening browser for Google sign-in...")
            print("Sign in as: backup@mamnoonrestaurant.com")
            print("=" * 60 + "\n")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secrets_path,
                self.scopes
            )
            creds = flow.run_local_server(port=0)
            self._save_credentials(creds)
            print("✓ Authentication successful, token saved")
        
        self._credentials = creds
        return creds
    
    def _save_credentials(self, creds: Credentials):
        """Save credentials to token file."""
        with open(self.token_path, 'w') as f:
            f.write(creds.to_json())
        print(f"✓ Token saved to {self.token_path}")
    
    @property
    def service(self):
        """Get or create Gmail API service."""
        if not self._service:
            if not self._credentials:
                self.authenticate()
            self._service = build('gmail', 'v1', credentials=self._credentials)
        return self._service
    
    def list_labels(self) -> List[Dict[str, str]]:
        """List all labels in the mailbox."""
        results = self.service.users().labels().list(userId='me').execute()
        return results.get('labels', [])
    
    def get_label_id(self, label_name: str) -> Optional[str]:
        """Get label ID by name."""
        labels = self.list_labels()
        for label in labels:
            if label['name'].lower() == label_name.lower():
                return label['id']
        return None
    
    def fetch_by_label(
        self,
        label_name: str,
        max_results: int = 100,
        query: str = None,
        include_body: bool = True
    ) -> List[EmailMessage]:
        """
        Fetch emails by label name.
        
        Args:
            label_name: Gmail label name (e.g., 'mrayeh')
            max_results: Maximum messages to fetch
            query: Optional Gmail search query (e.g., 'after:2024/01/01')
            include_body: Whether to fetch full message body
            
        Returns:
            List of EmailMessage objects
        """
        label_id = self.get_label_id(label_name)
        if not label_id:
            raise ValueError(f"Label not found: {label_name}")
        
        return self.fetch_by_label_id(label_id, max_results, query, include_body)
    
    def fetch_by_label_id(
        self,
        label_id: str,
        max_results: int = 100,
        query: str = None,
        include_body: bool = True
    ) -> List[EmailMessage]:
        """
        Fetch emails by label ID.
        
        Args:
            label_id: Gmail label ID
            max_results: Maximum messages to fetch
            query: Optional Gmail search query
            include_body: Whether to fetch full message body
            
        Returns:
            List of EmailMessage objects
        """
        messages = []
        page_token = None
        
        while len(messages) < max_results:
            # List message IDs
            request_params = {
                'userId': 'me',
                'labelIds': [label_id],
                'maxResults': min(100, max_results - len(messages))
            }
            if query:
                request_params['q'] = query
            if page_token:
                request_params['pageToken'] = page_token
            
            response = self.service.users().messages().list(**request_params).execute()
            
            msg_refs = response.get('messages', [])
            if not msg_refs:
                break
            
            # Fetch full messages
            for msg_ref in msg_refs:
                msg = self._get_message(msg_ref['id'], include_body)
                messages.append(msg)
                
                if len(messages) >= max_results:
                    break
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        
        return messages
    
    def _get_message(self, msg_id: str, include_body: bool = True) -> EmailMessage:
        """Fetch and parse a single message."""
        format_type = 'full' if include_body else 'metadata'
        raw = self.service.users().messages().get(
            userId='me',
            id=msg_id,
            format=format_type
        ).execute()
        
        return self._parse_message(raw)
    
    def _parse_message(self, raw: Dict[str, Any]) -> EmailMessage:
        """Parse raw Gmail API message into EmailMessage."""
        headers = {}
        payload = raw.get('payload', {})
        
        # Extract headers
        for header in payload.get('headers', []):
            name = header['name'].lower()
            headers[name] = header['value']
        
        # Parse date
        date = None
        if 'date' in headers:
            try:
                date = parsedate_to_datetime(headers['date'])
            except:
                pass
        
        # Extract body
        body_text = ''
        body_html = ''
        attachments = []
        
        self._extract_parts(payload, body_text, body_html, attachments)
        
        # If body is in payload directly
        if not body_text and not body_html:
            body_data = payload.get('body', {}).get('data', '')
            if body_data:
                decoded = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                if payload.get('mimeType', '').startswith('text/html'):
                    body_html = decoded
                else:
                    body_text = decoded
        
        return EmailMessage(
            id=raw['id'],
            thread_id=raw['threadId'],
            subject=headers.get('subject', ''),
            sender=headers.get('from', ''),
            to=headers.get('to', ''),
            date=date,
            snippet=raw.get('snippet', ''),
            body_text=body_text,
            body_html=body_html,
            labels=raw.get('labelIds', []),
            attachments=attachments,
            headers=headers,
            raw_message=raw
        )
    
    def _extract_parts(
        self,
        payload: Dict,
        body_text: str,
        body_html: str,
        attachments: List[Dict]
    ) -> tuple:
        """Recursively extract body and attachments from message parts."""
        parts = payload.get('parts', [])
        
        for part in parts:
            mime_type = part.get('mimeType', '')
            filename = part.get('filename', '')
            body = part.get('body', {})
            
            if filename:
                # Attachment
                attachments.append({
                    'filename': filename,
                    'mime_type': mime_type,
                    'size': body.get('size', 0),
                    'attachment_id': body.get('attachmentId')
                })
            elif mime_type == 'text/plain':
                data = body.get('data', '')
                if data:
                    body_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            elif mime_type == 'text/html':
                data = body.get('data', '')
                if data:
                    body_html = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            elif 'parts' in part:
                # Nested multipart
                self._extract_parts(part, body_text, body_html, attachments)
        
        return body_text, body_html, attachments
    
    def fetch_unread_by_label(self, label_name: str, max_results: int = 100) -> List[EmailMessage]:
        """Fetch only unread messages with a specific label."""
        return self.fetch_by_label(label_name, max_results, query='is:unread')
    
    def fetch_since(
        self,
        label_name: str,
        since_date: str,
        max_results: int = 500
    ) -> List[EmailMessage]:
        """
        Fetch messages since a specific date.
        
        Args:
            label_name: Gmail label name
            since_date: Date string in YYYY/MM/DD format
            max_results: Maximum messages to fetch
            
        Returns:
            List of EmailMessage objects
        """
        query = f'after:{since_date}'
        return self.fetch_by_label(label_name, max_results, query=query)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience functions
# ─────────────────────────────────────────────────────────────────────────────

def create_gmail_driver(
    credentials_dir: str = 'config/.credentials',
    token_file: str = 'gmail_token.json'
) -> GmailDriver:
    """Create and authenticate a Gmail driver."""
    driver = GmailDriver(credentials_dir=credentials_dir, token_file=token_file)
    driver.authenticate()
    return driver
