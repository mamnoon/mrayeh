#!/usr/bin/env python3
"""
Test MBOX import - parse historical email archive.

Usage:
    python test_mbox_import.py [path_to_mbox]
    
    # Default: looks for .mbox files in data/
"""

import os
import sys
from collections import defaultdict
from glob import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from drivers.mbox_driver import MboxDriver, parse_mbox_file


def find_mbox_files(data_dir: str = 'data') -> list:
    """Find all .mbox files in data directory."""
    patterns = [
        os.path.join(data_dir, '*.mbox'),
        os.path.join(data_dir, '**/*.mbox'),
    ]
    files = []
    for pattern in patterns:
        files.extend(glob(pattern, recursive=True))
    return list(set(files))


def main():
    print("=" * 70)
    print("MBOX IMPORT TEST")
    print("=" * 70)
    
    # Find mbox file
    if len(sys.argv) > 1:
        mbox_path = sys.argv[1]
    else:
        mbox_files = find_mbox_files()
        if not mbox_files:
            print("\n⚠ No .mbox files found in data/")
            print("  Place your Google Takeout/Vault export in the data/ folder")
            print("  Or specify path: python test_mbox_import.py path/to/file.mbox")
            return 1
        mbox_path = mbox_files[0]
        if len(mbox_files) > 1:
            print(f"\nFound {len(mbox_files)} mbox files, using: {mbox_path}")
    
    if not os.path.exists(mbox_path):
        print(f"\n❌ File not found: {mbox_path}")
        return 1
    
    print(f"\nFile: {mbox_path}")
    print(f"Size: {os.path.getsize(mbox_path) / (1024*1024):.1f} MB")
    
    # Quick stats
    print("\n## Quick Stats")
    print("-" * 50)
    driver = MboxDriver(mbox_path)
    stats = driver.get_stats()
    print(f"  Messages: {stats['message_count']}")
    
    # Parse with limit for testing
    print("\n## Parsing (first 100 messages for preview)")
    print("-" * 50)
    result = driver.parse_all(limit=100)
    
    print(f"  Parsed:    {result.parsed_count}")
    print(f"  Errors:    {result.error_count}")
    if result.date_range:
        print(f"  Date range: {result.date_range[0].date()} to {result.date_range[1].date()}")
    
    # Sender analysis
    print("\n## Top Senders (from sample)")
    print("-" * 50)
    sender_counts = defaultdict(int)
    for msg in result.messages:
        sender = msg.sender
        # Simplify sender
        if '<' in sender:
            sender = sender.split('<')[0].strip().strip('"')
        sender_counts[sender] += 1
    
    for sender, count in sorted(sender_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {sender[:50]:<50} {count:>4}")
    
    # Subject patterns
    print("\n## Subject Patterns (from sample)")
    print("-" * 50)
    subject_words = defaultdict(int)
    for msg in result.messages:
        words = msg.subject.lower().split()
        for word in words:
            if len(word) > 3:
                subject_words[word] += 1
    
    for word, count in sorted(subject_words.items(), key=lambda x: -x[1])[:15]:
        print(f"  {word:<30} {count:>4}")
    
    # Sample messages
    print("\n## Sample Messages (first 5)")
    print("-" * 50)
    for i, msg in enumerate(result.messages[:5]):
        print(f"\n  Message {i+1}:")
        print(f"    Date:    {msg.date}")
        print(f"    From:    {msg.sender[:60]}")
        print(f"    Subject: {msg.subject[:60]}")
        print(f"    Snippet: {msg.snippet[:80]}...")
        if msg.attachments:
            print(f"    Attachments: {len(msg.attachments)}")
    
    # Errors
    if result.errors:
        print("\n## Parse Errors (first 5)")
        print("-" * 50)
        for err in result.errors[:5]:
            print(f"  Index {err['index']}: {err['error']}")
            if err.get('subject'):
                print(f"    Subject: {err['subject'][:50]}")
    
    # Full parse option
    if stats['message_count'] > 100:
        print("\n" + "=" * 70)
        print(f"Preview complete. Full file has {stats['message_count']} messages.")
        print("To parse all messages, run:")
        print(f"  python -c \"from src.drivers.mbox_driver import parse_mbox_file; r = parse_mbox_file('{mbox_path}'); print(f'Parsed {{r.parsed_count}} messages')\"")
        print("=" * 70)
    
    driver.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
