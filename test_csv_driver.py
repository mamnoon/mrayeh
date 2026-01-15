#!/usr/bin/env python3
"""
Test script for CSV Driver

Tests the generic CSV import driver with sample data.
"""

import os
import sys
from textwrap import dedent

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from drivers.csv_driver import CSVDriver, load_mapping

# ─────────────────────────────────────────────────────────────────────────────
# Test Data
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_CSV = dedent("""
    Customer,Product,Qty,Unit,Price,Total,Date,Order #
    Crown - PO # 12345,HUMMUS,24,CASE,$45.00,"$1,080.00",01/15/2026,ORD-001
    Met #165 Crown Hill,HUMMUS,12,EACH,$5.00,$60.00,01/15/2026,ORD-002
    Leschi Market,BABA,6,CASE,$42.00,$252.00,01/15/2026,ORD-003
    PSFH - PO # MAMN-123,MUHAMMARA,36,EACH,$6.50,$234.00,01/16/2026,ORD-004
    Total,,,,,,"$1,626.00",,
    Bright Spot,HARRA,3,CASE,$38.00,$114.00,01/16/2026,ORD-005
""").strip()

SAMPLE_MAPPING = dedent("""
    name: test_orders
    description: "Test order mapping"
    
    delimiter: ","
    skip_rows: 0
    header_row: 0
    
    skip_patterns:
      - "^Total"
    
    required_columns:
      - Customer
      - Product
    
    columns:
      - source: Customer
        target: customer_raw
        type: string
        required: true
      
      - source: Customer
        target: customer
        type: string
        transform: extract_customer
      
      - source: Customer
        target: po_hint
        type: string
        transform: extract_po
      
      - source: Product
        target: product
        type: string
        transform: uppercase
        required: true
      
      - source: Qty
        target: quantity
        type: float
        default: 0
      
      - source: Unit
        target: unit_type
        type: string
        transform: uppercase
      
      - source: Price
        target: unit_price
        type: currency
      
      - source: Total
        target: line_total
        type: currency
      
      - source: Date
        target: order_date
        type: date
        format: "%m/%d/%Y"
      
      - source: "Order #"
        target: order_number
        type: string
    
    output_type: dict
""").strip()


def test_csv_driver():
    """Test CSV driver with sample data."""
    print("=" * 60)
    print("CSV DRIVER TEST")
    print("=" * 60)
    
    # Write temp mapping file
    mapping_path = '/tmp/test_mapping.yml'
    with open(mapping_path, 'w') as f:
        f.write(SAMPLE_MAPPING)
    
    # Initialize driver
    driver = CSVDriver(mapping_path=mapping_path)
    
    # Validate mapping
    print("\n## Mapping Validation")
    print("-" * 40)
    issues = driver.validate_mapping()
    if issues:
        for issue in issues:
            print(f"  ⚠ {issue}")
    else:
        print("  ✓ Mapping is valid")
    
    # Parse CSV
    print("\n## Parsing CSV")
    print("-" * 40)
    result = driver.parse(csv_path="test.csv", csv_content=SAMPLE_CSV)
    
    print(f"  Rows processed: {result.stats['rows_processed']}")
    print(f"  Rows skipped:   {result.stats['rows_skipped']}")
    print(f"  Records:        {result.stats['records_created']}")
    print(f"  Warnings:       {result.stats['warnings_count']}")
    print(f"  Errors:         {result.stats['errors_count']}")
    
    # Show records
    print("\n## Parsed Records")
    print("-" * 40)
    for i, rec in enumerate(result.records):
        print(f"\n  Record {i+1}:")
        print(f"    customer_raw:  {rec.get('customer_raw')}")
        print(f"    customer:      {rec.get('customer')}")
        print(f"    po_hint:       {rec.get('po_hint')}")
        print(f"    product:       {rec.get('product')}")
        print(f"    quantity:      {rec.get('quantity')}")
        print(f"    unit_type:     {rec.get('unit_type')}")
        print(f"    unit_price:    ${rec.get('unit_price', 0):.2f}" if rec.get('unit_price') else "    unit_price:    None")
        print(f"    line_total:    ${rec.get('line_total', 0):.2f}" if rec.get('line_total') else "    line_total:    None")
        print(f"    order_date:    {rec.get('order_date')}")
        print(f"    order_number:  {rec.get('order_number')}")
    
    # Show warnings/errors
    if result.warnings:
        print("\n## Warnings")
        print("-" * 40)
        for w in result.warnings:
            print(f"  {w}")
    
    if result.errors:
        print("\n## Errors")
        print("-" * 40)
        for e in result.errors:
            print(f"  {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    # Verify expected results
    expected_records = 5  # 6 rows - 1 Total row
    expected_po_hints = 2  # Crown and PSFH have PO#s
    
    actual_records = len(result.records)
    actual_po_hints = sum(1 for r in result.records if r.get('po_hint'))
    
    print(f"  Records: {actual_records}/{expected_records} {'✓' if actual_records == expected_records else '✗'}")
    print(f"  PO hints extracted: {actual_po_hints}/{expected_po_hints} {'✓' if actual_po_hints == expected_po_hints else '✗'}")
    print(f"  Total row skipped: {'✓' if result.stats['rows_skipped'] == 1 else '✗'}")
    
    return result.stats['errors_count'] == 0


def test_with_mapping_files():
    """Test with actual mapping files in config/mappings/."""
    print("\n\n" + "=" * 60)
    print("MAPPING FILES TEST")
    print("=" * 60)
    
    mapping_dir = os.path.join(os.path.dirname(__file__), 'config', 'mappings')
    
    for filename in os.listdir(mapping_dir):
        if filename.endswith('.yml'):
            path = os.path.join(mapping_dir, filename)
            print(f"\n## {filename}")
            print("-" * 40)
            
            try:
                mapping = load_mapping(path)
                print(f"  Name: {mapping.name}")
                print(f"  Description: {mapping.description}")
                print(f"  Columns: {len(mapping.columns)}")
                print(f"  Skip patterns: {len(mapping.skip_patterns)}")
                
                driver = CSVDriver(mapping_path=path)
                issues = driver.validate_mapping()
                if issues:
                    for issue in issues:
                        print(f"  ⚠ {issue}")
                else:
                    print(f"  ✓ Valid")
            except Exception as e:
                print(f"  ✗ Error: {e}")


if __name__ == '__main__':
    success = test_csv_driver()
    test_with_mapping_files()
    exit(0 if success else 1)
