#!/usr/bin/env python3
"""
Test PSFH CSV import with real data.
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from drivers.csv_driver import CSVDriver

CSV_PATH = "data/psfh test report 1_6_2026 3_05_01 PM.csv"
MAPPING_PATH = "config/mappings/psfh_sales.yml"

def main():
    print("=" * 70)
    print("PSFH IMPORT TEST")
    print("=" * 70)
    
    # Initialize driver
    driver = CSVDriver(mapping_path=MAPPING_PATH)
    
    # Validate mapping
    issues = driver.validate_mapping()
    if issues:
        print("\n⚠ Mapping issues:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    
    # Parse CSV
    print(f"\nParsing: {CSV_PATH}")
    result = driver.parse(csv_path=CSV_PATH)
    
    # Stats
    print("\n## Stats")
    print("-" * 50)
    print(f"  Rows processed:    {result.stats['rows_processed']}")
    print(f"  Rows skipped:      {result.stats['rows_skipped']}")
    print(f"  Records created:   {result.stats['records_created']}")
    print(f"  Warnings:          {result.stats['warnings_count']}")
    print(f"  Errors:            {result.stats['errors_count']}")
    
    # Product breakdown
    print("\n## Products")
    print("-" * 50)
    product_stats = defaultdict(lambda: {'qty': 0, 'sales': 0, 'count': 0})
    for rec in result.records:
        prod = rec.get('product', 'UNKNOWN')
        qty = rec.get('quantity', 0) or 0
        sales = rec.get('total_sales', 0) or 0
        product_stats[prod]['qty'] += qty
        product_stats[prod]['sales'] += sales
        product_stats[prod]['count'] += 1
    
    for prod in sorted(product_stats.keys()):
        stats = product_stats[prod]
        print(f"  {prod:<30} Qty: {stats['qty']:>6}  Sales: ${stats['sales']:>10,.2f}  Lines: {stats['count']}")
    
    # Customer breakdown (top 15)
    print("\n## Top 15 Customers by Sales")
    print("-" * 50)
    customer_stats = defaultdict(lambda: {'qty': 0, 'sales': 0, 'orders': set()})
    for rec in result.records:
        cust = rec.get('customer', 'UNKNOWN')
        qty = rec.get('quantity', 0) or 0
        sales = rec.get('total_sales', 0) or 0
        order = rec.get('order_number', '')
        customer_stats[cust]['qty'] += qty
        customer_stats[cust]['sales'] += sales
        if order:
            customer_stats[cust]['orders'].add(order)
    
    top_customers = sorted(customer_stats.items(), key=lambda x: -x[1]['sales'])[:15]
    for cust, stats in top_customers:
        print(f"  {cust:<40} ${stats['sales']:>10,.2f}  ({len(stats['orders'])} orders)")
    
    # Date range
    print("\n## Date Range")
    print("-" * 50)
    dates = [rec.get('period_start') for rec in result.records if rec.get('period_start')]
    if dates:
        print(f"  Earliest: {min(dates)}")
        print(f"  Latest:   {max(dates)}")
    
    # Sample records
    print("\n## Sample Records (first 3)")
    print("-" * 50)
    for i, rec in enumerate(result.records[:3]):
        print(f"\n  Record {i+1}:")
        for key, val in rec.items():
            if not key.startswith('_'):
                print(f"    {key}: {val}")
    
    # Show errors if any
    if result.errors:
        print("\n## Errors")
        print("-" * 50)
        for err in result.errors[:10]:
            print(f"  {err}")
    
    # Show warnings if any
    if result.warnings:
        print("\n## Warnings (first 10)")
        print("-" * 50)
        for warn in result.warnings[:10]:
            print(f"  {warn}")
    
    print("\n" + "=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    
    return 0 if result.stats['errors_count'] == 0 else 1


if __name__ == '__main__':
    exit(main())
