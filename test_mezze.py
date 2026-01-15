#!/usr/bin/env python3
"""
Test script for Mezze Sheet Driver v2

Tests:
1. Sheet connectivity
2. Multi-table parsing (stops at lot code section)
3. Customer/PO extraction
4. Product column detection
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from drivers.google_sheets_driver import GoogleSheetsDriver, extract_customer_and_po

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SHEET_ID = '1gsDSGjrE7bvOhITgU-S2Q_kTHw6OCrNPAfKHg6AF3XE'

# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_customer_po_extraction():
    """Test customer/PO parsing logic."""
    print("\n## Testing Customer/PO Extraction")
    print("-" * 50)
    
    test_cases = [
        ("Crown - PO # 779322", "Crown", "779322"),
        ("Crown - PO# 785153", "Crown", "785153"),
        ("Crown - PO #", "Crown", None),
        ("PSFH - PO # MAMN-54127", "PSFH", "MAMN-54127"),
        ("PSFH (FROZEN) - PO#", "PSFH (FROZEN)", None),
        ("Met #165 Crown Hill", "Met #165 Crown Hill", None),
        ("Leschi Market", "Leschi Market", None),
        ("Cone & Steiner RD", "Cone & Steiner RD", None),
    ]
    
    all_passed = True
    for raw, expected_customer, expected_po in test_cases:
        customer, po = extract_customer_and_po(raw)
        passed = customer == expected_customer and po == expected_po
        status = "✓" if passed else "✗"
        print(f"  {status} '{raw[:35]:<35}' → customer='{customer}', po={po}")
        if not passed:
            print(f"      Expected: customer='{expected_customer}', po={expected_po}")
            all_passed = False
    
    return all_passed


def test_sheet_fetch():
    """Test full sheet fetch and parse."""
    print("\n## Testing Sheet Fetch")
    print("-" * 50)
    
    driver = GoogleSheetsDriver(sheet_id=SHEET_ID)
    
    # Get tabs
    tabs = driver.get_weekly_tabs()
    print(f"  ✓ Found {len(tabs)} weekly order tabs")
    
    # Parse all
    print(f"  ... Parsing all tabs (this may take a moment)")
    result = driver.fetch_all()
    
    print(f"\n## Results")
    print("-" * 50)
    print(f"  Tabs processed:      {result.stats['tabs_processed']}")
    print(f"  Order lines:         {result.stats['total_order_lines']}")
    print(f"  Unique customers:    {result.stats['unique_customers']}")
    print(f"  Unique products:     {result.stats['unique_products']}")
    print(f"  Warnings:            {result.stats['warnings_count']}")
    print(f"  Errors:              {result.stats['errors_count']}")
    
    # Products breakdown
    print(f"\n## Products")
    print("-" * 50)
    products = defaultdict(lambda: {'case': 0, 'each': 0})
    for ol in result.order_lines:
        products[ol.product][ol.unit_type.lower()] += ol.quantity
    
    for prod in sorted(products.keys()):
        case_qty = products[prod]['case']
        each_qty = products[prod]['each']
        print(f"  {prod:<20} CASE: {case_qty:>8,.0f}  EACH: {each_qty:>10,.0f}")
    
    # Customer breakdown (top 15)
    print(f"\n## Top 15 Customers by Order Lines")
    print("-" * 50)
    customer_counts = defaultdict(int)
    customer_po_samples = defaultdict(set)
    for ol in result.order_lines:
        customer_counts[ol.customer] += 1
        if ol.po_hint:
            customer_po_samples[ol.customer].add(ol.po_hint)
    
    for customer, count in sorted(customer_counts.items(), key=lambda x: -x[1])[:15]:
        po_sample = list(customer_po_samples[customer])[:2]
        po_str = f" (POs: {', '.join(po_sample)})" if po_sample else ""
        print(f"  {customer[:40]:<40} {count:>5} lines{po_str}")
    
    # Warnings breakdown
    if result.warnings:
        print(f"\n## Warning Types")
        print("-" * 50)
        warning_types = defaultdict(int)
        for w in result.warnings:
            warning_types[w['type']] += 1
        for wtype, count in sorted(warning_types.items(), key=lambda x: -x[1]):
            print(f"  {wtype}: {count}")
        
        print(f"\n## Sample Warnings (first 5)")
        print("-" * 50)
        for w in result.warnings[:5]:
            print(f"  Tab: {w.get('tab', 'N/A')}")
            print(f"  Cell: {w.get('cell', 'N/A')}")
            print(f"  Value: '{w.get('value', 'N/A')}'")
            print(f"  Customer: {w.get('customer', 'N/A')}")
            print()
    
    # Errors
    if result.errors:
        print(f"\n## Errors")
        print("-" * 50)
        for e in result.errors[:5]:
            print(f"  {e}")
    
    return result.stats['errors_count'] == 0


def main():
    print("=" * 60)
    print("MEZZE SHEET DRIVER TEST v2")
    print("=" * 60)
    
    # Test 1: Customer/PO extraction
    test1_passed = test_customer_po_extraction()
    
    # Test 2: Full sheet fetch
    test2_passed = test_sheet_fetch()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"  Customer/PO extraction: {'PASS' if test1_passed else 'FAIL'}")
    print(f"  Sheet fetch & parse:    {'PASS' if test2_passed else 'FAIL'}")
    
    return 0 if (test1_passed and test2_passed) else 1


if __name__ == '__main__':
    exit(main())
