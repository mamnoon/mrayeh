"""
MBOX Driver - Parse historical emails from Google Takeout/Vault exports.

Supports:
- Standard MBOX format (Google Takeout, Vault exports)
- Extracts headers, body (text/html), and attachment metadata
- Memory-efficient streaming for large files
- Compatible with EmailMessage format from gmail_driver

Usage:
    driver = MboxDriver('data/finefoods-archive.mbox')
    
    # Stream messages (memory efficient)
    for message in driver.iter_messages():
        print(message.subject, message.sender, message.date)
    
    # Or load all at once
    messages = driver.parse_all()
    print(f"Loaded {len(messages)} messages")
"""

import mailbox
import email
import base64
import os
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Generator, List, Optional
from dataclasses import dataclass, field


@dataclass
class EmailMessage:
    """
    Parsed email message.
    Compatible with gmail_driver.EmailMessage for unified processing.
    """
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
    raw_message: Any = field(default=None, repr=False)


@dataclass
class ParseResult:
    """Result of parsing MBOX file."""
    messages: List[EmailMessage]
    total_count: int
    parsed_count: int
    error_count: int
    errors: List[Dict[str, Any]]
    date_range: Optional[tuple] = None


class MboxDriver:
    """
    MBOX file parser for historical email archives.
    
    Designed for Google Takeout and Vault exports of Google Groups.
    """
    
    def __init__(self, mbox_path: str):
        """
        Initialize MBOX driver.
        
        Args:
            mbox_path: Path to .mbox file
        """
        if not os.path.exists(mbox_path):
            raise FileNotFoundError(f"MBOX file not found: {mbox_path}")
        
        self.mbox_path = mbox_path
        self.file_size = os.path.getsize(mbox_path)
        self._mbox = None
    
    @property
    def mbox(self) -> mailbox.mbox:
        """Get or open the mbox file."""
        if self._mbox is None:
            self._mbox = mailbox.mbox(self.mbox_path)
        return self._mbox
    
    def close(self):
        """Close the mbox file."""
        if self._mbox is not None:
            self._mbox.close()
            self._mbox = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def count_messages(self) -> int:
        """Count total messages in the mbox file."""
        return len(self.mbox)
    
    def iter_messages(
        self,
        limit: Optional[int] = None,
        skip_errors: bool = True
    ) -> Generator[EmailMessage, None, None]:
        """
        Iterate over messages in the mbox file.
        
        Memory efficient - yields one message at a time.
        
        Args:
            limit: Maximum number of messages to yield
            skip_errors: If True, skip messages that fail to parse
            
        Yields:
            EmailMessage objects
        """
        count = 0
        for i, raw_message in enumerate(self.mbox):
            try:
                parsed = self._parse_message(raw_message, index=i)
                yield parsed
                count += 1
                
                if limit and count >= limit:
                    break
            except Exception as e:
                if not skip_errors:
                    raise
                # Silently skip on error when skip_errors=True
    
    def parse_all(
        self,
        limit: Optional[int] = None,
        skip_errors: bool = True
    ) -> ParseResult:
        """
        Parse all messages in the mbox file.
        
        Args:
            limit: Maximum number of messages to parse
            skip_errors: If True, continue on parse errors
            
        Returns:
            ParseResult with messages and statistics
        """
        messages = []
        errors = []
        dates = []
        
        for i, raw_message in enumerate(self.mbox):
            if limit and len(messages) >= limit:
                break
            
            try:
                parsed = self._parse_message(raw_message, index=i)
                messages.append(parsed)
                
                if parsed.date:
                    dates.append(parsed.date)
                    
            except Exception as e:
                errors.append({
                    'index': i,
                    'error': str(e),
                    'subject': self._safe_get_header(raw_message, 'subject')
                })
                if not skip_errors:
                    raise
        
        date_range = None
        if dates:
            date_range = (min(dates), max(dates))
        
        return ParseResult(
            messages=messages,
            total_count=len(self.mbox),
            parsed_count=len(messages),
            error_count=len(errors),
            errors=errors,
            date_range=date_range
        )
    
    def _parse_message(
        self,
        raw: mailbox.mboxMessage,
        index: int = 0
    ) -> EmailMessage:
        """Parse a single mbox message into EmailMessage."""
        
        # Extract headers
        headers = {}
        for key in raw.keys():
            headers[key.lower()] = raw[key]
        
        # Parse date
        date = None
        date_str = raw.get('Date', '')
        if date_str:
            try:
                date = parsedate_to_datetime(date_str)
            except:
                pass
        
        # Generate ID (mbox doesn't have native IDs)
        message_id = headers.get('message-id', f'mbox-{index}')
        # Clean up message ID
        message_id = message_id.strip('<>').replace('@', '_at_')
        
        # Extract thread ID from references or in-reply-to
        thread_id = headers.get('in-reply-to', message_id)
        thread_id = thread_id.strip('<>').replace('@', '_at_') if thread_id else message_id
        
        # Extract body
        body_text = ''
        body_html = ''
        attachments = []
        
        if raw.is_multipart():
            for part in raw.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition', ''))
                
                # Skip container types
                if content_type.startswith('multipart/'):
                    continue
                
                # Check for attachment
                if 'attachment' in content_disposition:
                    filename = part.get_filename() or 'unnamed'
                    attachments.append({
                        'filename': filename,
                        'mime_type': content_type,
                        'size': len(part.get_payload(decode=True) or b'')
                    })
                elif content_type == 'text/plain' and not body_text:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        body_text = payload.decode(charset, errors='replace')
                elif content_type == 'text/html' and not body_html:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        body_html = payload.decode(charset, errors='replace')
        else:
            # Single part message
            payload = raw.get_payload(decode=True)
            if payload:
                charset = raw.get_content_charset() or 'utf-8'
                content = payload.decode(charset, errors='replace')
                
                if raw.get_content_type() == 'text/html':
                    body_html = content
                else:
                    body_text = content
        
        # Generate snippet
        snippet = body_text[:200].replace('\n', ' ').strip() if body_text else ''
        
        # Extract labels from X-Gmail-Labels header (if present in Takeout)
        labels = []
        gmail_labels = headers.get('x-gmail-labels', '')
        if gmail_labels:
            labels = [l.strip() for l in gmail_labels.split(',')]
        
        return EmailMessage(
            id=message_id,
            thread_id=thread_id,
            subject=headers.get('subject', ''),
            sender=headers.get('from', ''),
            to=headers.get('to', ''),
            date=date,
            snippet=snippet,
            body_text=body_text,
            body_html=body_html,
            labels=labels,
            attachments=attachments,
            headers=headers,
            raw_message=raw
        )
    
    def _safe_get_header(self, msg: mailbox.mboxMessage, header: str) -> str:
        """Safely get a header value."""
        try:
            return msg.get(header, '') or ''
        except:
            return ''
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the mbox file without parsing all messages."""
        return {
            'path': self.mbox_path,
            'file_size_mb': round(self.file_size / (1024 * 1024), 2),
            'message_count': self.count_messages()
        }


# ─────────────────────────────────────────────────────────────────────────────
# Convenience functions
# ─────────────────────────────────────────────────────────────────────────────

def parse_mbox_file(
    mbox_path: str,
    limit: Optional[int] = None
) -> ParseResult:
    """
    Parse an mbox file and return all messages.
    
    Args:
        mbox_path: Path to .mbox file
        limit: Maximum messages to parse
        
    Returns:
        ParseResult with messages and statistics
    """
    with MboxDriver(mbox_path) as driver:
        return driver.parse_all(limit=limit)


def iter_mbox_messages(
    mbox_path: str,
    limit: Optional[int] = None
) -> Generator[EmailMessage, None, None]:
    """
    Iterate over messages in an mbox file.
    
    Memory efficient for large files.
    
    Args:
        mbox_path: Path to .mbox file
        limit: Maximum messages to yield
        
    Yields:
        EmailMessage objects
    """
    with MboxDriver(mbox_path) as driver:
        yield from driver.iter_messages(limit=limit)
