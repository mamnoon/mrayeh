"""
Generic CSV Import Driver

Uses YAML mapping files to define how different CSV formats should be parsed
and normalized into the common data model.

Usage:
    driver = CSVDriver(mapping_path='config/mappings/psfh_sales.yml')
    result = driver.parse(csv_path='data/psfh_export.csv')
"""

import csv
import re
import yaml
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────────
# Data Types
# ─────────────────────────────────────────────────────────────────────────────

class FieldType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    CURRENCY = "currency"  # Strips $, commas, parses as float


@dataclass
class ColumnMapping:
    """Defines how a source column maps to a target field."""
    source: str                          # Source column name or index
    target: str                          # Target field name
    type: FieldType = FieldType.STRING   # Data type
    format: Optional[str] = None         # Format string (for dates)
    default: Any = None                  # Default if missing/empty
    required: bool = False               # Fail if missing
    transform: Optional[str] = None      # Transform function name
    regex: Optional[str] = None          # Regex to extract value
    strip_chars: Optional[str] = None    # Characters to strip


@dataclass
class MappingConfig:
    """Complete mapping configuration from YAML."""
    name: str                            # Mapping name/identifier
    description: str = ""                # Human description
    source_type: str = "csv"             # Source format
    
    # CSV options
    delimiter: str = ","
    encoding: str = "utf-8"
    skip_rows: int = 0                   # Rows to skip at start
    header_row: Optional[int] = None     # Row index for headers (0-based after skip)
    
    # Column mappings
    columns: List[ColumnMapping] = field(default_factory=list)
    
    # Row filtering
    skip_patterns: List[str] = field(default_factory=list)  # Regex patterns to skip rows
    stop_pattern: Optional[str] = None   # Stop parsing when this pattern matches
    
    # Validation
    required_columns: List[str] = field(default_factory=list)
    
    # Output
    output_type: str = "dict"            # dict, order_line, custom


@dataclass
class ParseResult:
    """Result of parsing a CSV file."""
    records: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    stats: Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Transform Functions
# ─────────────────────────────────────────────────────────────────────────────

def transform_uppercase(value: str) -> str:
    return value.upper() if value else value

def transform_lowercase(value: str) -> str:
    return value.lower() if value else value

def transform_titlecase(value: str) -> str:
    return value.title() if value else value

def transform_strip(value: str) -> str:
    return value.strip() if value else value

def transform_extract_po(value: str) -> Optional[str]:
    """Extract PO number from strings like 'Crown - PO # 779322'."""
    if not value:
        return None
    # Require "PO" followed by optional # and the actual number/code
    match = re.search(r'\bPO\s*#?\s*(\S+)', value, re.I)
    if match:
        po = match.group(1).strip()
        # Don't return empty or just punctuation
        if po and not re.match(r'^[\s\-#]+$', po):
            return po
    return None

def transform_extract_customer(value: str) -> str:
    """Extract customer name, stripping PO suffix."""
    if not value:
        return value
    match = re.match(r'^(.+?)\s*-\s*PO', value, re.I)
    return match.group(1).strip() if match else value.strip()

def transform_clean_currency(value: str) -> Optional[float]:
    """Clean currency string to float: '$1,234.56' -> 1234.56."""
    if not value:
        return None
    cleaned = re.sub(r'[$,\s]', '', str(value))
    try:
        return float(cleaned)
    except ValueError:
        return None

def transform_yes_no_bool(value: str) -> Optional[bool]:
    """Convert yes/no/y/n to boolean."""
    if not value:
        return None
    v = value.strip().lower()
    if v in ('yes', 'y', 'true', '1'):
        return True
    if v in ('no', 'n', 'false', '0'):
        return False
    return None


TRANSFORMS: Dict[str, Callable] = {
    'uppercase': transform_uppercase,
    'lowercase': transform_lowercase,
    'titlecase': transform_titlecase,
    'strip': transform_strip,
    'extract_po': transform_extract_po,
    'extract_customer': transform_extract_customer,
    'clean_currency': transform_clean_currency,
    'yes_no_bool': transform_yes_no_bool,
}


# ─────────────────────────────────────────────────────────────────────────────
# Type Converters
# ─────────────────────────────────────────────────────────────────────────────

def convert_value(value: str, field_type: FieldType, format_str: Optional[str] = None) -> Any:
    """Convert string value to target type."""
    if value is None or value == '':
        return None
    
    value = str(value).strip()
    
    if field_type == FieldType.STRING:
        return value
    
    elif field_type == FieldType.INTEGER:
        try:
            # Handle comma-separated numbers
            cleaned = value.replace(',', '')
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None
    
    elif field_type == FieldType.FLOAT:
        try:
            cleaned = value.replace(',', '')
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    elif field_type == FieldType.CURRENCY:
        return transform_clean_currency(value)
    
    elif field_type == FieldType.DATE:
        formats = [format_str] if format_str else [
            '%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', 
            '%d/%m/%Y', '%Y/%m/%d', '%m-%d-%Y'
        ]
        for fmt in formats:
            if fmt:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        return None
    
    elif field_type == FieldType.DATETIME:
        formats = [format_str] if format_str else [
            '%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S', '%m/%d/%y %H:%M'
        ]
        for fmt in formats:
            if fmt:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        return None
    
    elif field_type == FieldType.BOOLEAN:
        v = value.lower()
        if v in ('true', 'yes', 'y', '1'):
            return True
        if v in ('false', 'no', 'n', '0'):
            return False
        return None
    
    return value


# ─────────────────────────────────────────────────────────────────────────────
# YAML Loader
# ─────────────────────────────────────────────────────────────────────────────

def load_mapping(mapping_path: Union[str, Path]) -> MappingConfig:
    """Load mapping configuration from YAML file."""
    path = Path(mapping_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Mapping file not found: {path}")
    
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Parse column mappings
    columns = []
    for col_data in data.get('columns', []):
        col = ColumnMapping(
            source=col_data['source'],
            target=col_data['target'],
            type=FieldType(col_data.get('type', 'string')),
            format=col_data.get('format'),
            default=col_data.get('default'),
            required=col_data.get('required', False),
            transform=col_data.get('transform'),
            regex=col_data.get('regex'),
            strip_chars=col_data.get('strip_chars'),
        )
        columns.append(col)
    
    return MappingConfig(
        name=data.get('name', path.stem),
        description=data.get('description', ''),
        source_type=data.get('source_type', 'csv'),
        delimiter=data.get('delimiter', ','),
        encoding=data.get('encoding', 'utf-8'),
        skip_rows=data.get('skip_rows', 0),
        header_row=data.get('header_row'),
        columns=columns,
        skip_patterns=data.get('skip_patterns', []),
        stop_pattern=data.get('stop_pattern'),
        required_columns=data.get('required_columns', []),
        output_type=data.get('output_type', 'dict'),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CSV Driver
# ─────────────────────────────────────────────────────────────────────────────

class CSVDriver:
    """
    Generic CSV import driver using YAML mapping configuration.
    """
    
    source_name = "csv"
    
    def __init__(self, mapping_path: Union[str, Path]):
        """
        Initialize driver with mapping configuration.
        
        Args:
            mapping_path: Path to YAML mapping file
        """
        self.mapping = load_mapping(mapping_path)
        self._skip_patterns = [re.compile(p, re.I) for p in self.mapping.skip_patterns]
        self._stop_pattern = re.compile(self.mapping.stop_pattern, re.I) if self.mapping.stop_pattern else None
    
    def parse(self, csv_path: Union[str, Path], csv_content: Optional[str] = None) -> ParseResult:
        """
        Parse a CSV file using the mapping configuration.
        
        Args:
            csv_path: Path to CSV file (or identifier if using csv_content)
            csv_content: Optional CSV content as string (instead of file)
            
        Returns:
            ParseResult with records, warnings, errors, stats
        """
        records = []
        warnings = []
        errors = []
        
        # Read CSV
        if csv_content:
            lines = csv_content.strip().split('\n')
            reader_input = lines
        else:
            path = Path(csv_path)
            if not path.exists():
                return ParseResult(
                    records=[],
                    warnings=[],
                    errors=[{'type': 'file_not_found', 'path': str(path)}],
                    stats={'rows_processed': 0}
                )
            with open(path, 'r', encoding=self.mapping.encoding) as f:
                reader_input = f.readlines()
        
        # Skip initial rows
        reader_input = reader_input[self.mapping.skip_rows:]
        
        # Parse CSV
        reader = csv.reader(reader_input, delimiter=self.mapping.delimiter)
        rows = list(reader)
        
        if not rows:
            return ParseResult(records=[], warnings=[], errors=[], stats={'rows_processed': 0})
        
        # Determine headers
        if self.mapping.header_row is not None:
            headers = rows[self.mapping.header_row]
            data_rows = rows[self.mapping.header_row + 1:]
        else:
            # Assume first row is headers
            headers = rows[0]
            data_rows = rows[1:]
        
        # Build column index map
        col_index_map = {h.strip(): i for i, h in enumerate(headers)}
        
        # Validate required columns
        for req_col in self.mapping.required_columns:
            if req_col not in col_index_map:
                errors.append({
                    'type': 'missing_required_column',
                    'column': req_col,
                    'available': list(col_index_map.keys())
                })
        
        if errors:
            return ParseResult(records=[], warnings=warnings, errors=errors, stats={'rows_processed': 0})
        
        # Process rows
        rows_processed = 0
        rows_skipped = 0
        
        for row_idx, row in enumerate(data_rows):
            row_num = row_idx + self.mapping.skip_rows + (self.mapping.header_row or 0) + 2
            
            # Join row for pattern matching
            row_str = self.mapping.delimiter.join(row)
            
            # Check stop pattern
            if self._stop_pattern and self._stop_pattern.search(row_str):
                break
            
            # Check skip patterns
            if any(p.search(row_str) for p in self._skip_patterns):
                rows_skipped += 1
                continue
            
            # Skip empty rows
            if not any(cell.strip() for cell in row):
                rows_skipped += 1
                continue
            
            # Process columns
            record = {'_source_row': row_num}
            row_has_error = False
            
            for col_map in self.mapping.columns:
                # Get source value
                source_val = None
                
                if col_map.source.isdigit():
                    # Source is column index
                    idx = int(col_map.source)
                    if idx < len(row):
                        source_val = row[idx]
                elif col_map.source in col_index_map:
                    # Source is column name
                    idx = col_index_map[col_map.source]
                    if idx < len(row):
                        source_val = row[idx]
                else:
                    # Try fuzzy match on column name
                    for header, idx in col_index_map.items():
                        if col_map.source.lower() in header.lower():
                            if idx < len(row):
                                source_val = row[idx]
                            break
                
                # Strip specified characters
                if source_val and col_map.strip_chars:
                    for char in col_map.strip_chars:
                        source_val = source_val.replace(char, '')
                
                # Apply regex extraction
                if source_val and col_map.regex:
                    match = re.search(col_map.regex, source_val)
                    source_val = match.group(1) if match else None
                
                # Apply transform
                if source_val and col_map.transform:
                    if col_map.transform in TRANSFORMS:
                        source_val = TRANSFORMS[col_map.transform](source_val)
                    else:
                        warnings.append({
                            'type': 'unknown_transform',
                            'transform': col_map.transform,
                            'row': row_num
                        })
                
                # Convert type
                converted = convert_value(source_val, col_map.type, col_map.format)
                
                # Apply default
                if converted is None and col_map.default is not None:
                    converted = col_map.default
                
                # Check required
                if converted is None and col_map.required:
                    errors.append({
                        'type': 'missing_required_value',
                        'column': col_map.source,
                        'target': col_map.target,
                        'row': row_num
                    })
                    row_has_error = True
                
                record[col_map.target] = converted
            
            if not row_has_error:
                records.append(record)
            
            rows_processed += 1
        
        stats = {
            'rows_processed': rows_processed,
            'rows_skipped': rows_skipped,
            'records_created': len(records),
            'warnings_count': len(warnings),
            'errors_count': len(errors),
        }
        
        return ParseResult(
            records=records,
            warnings=warnings,
            errors=errors,
            stats=stats
        )
    
    def validate_mapping(self) -> List[str]:
        """Validate the mapping configuration."""
        issues = []
        
        if not self.mapping.columns:
            issues.append("No column mappings defined")
        
        targets = [c.target for c in self.mapping.columns]
        if len(targets) != len(set(targets)):
            issues.append("Duplicate target field names")
        
        for col in self.mapping.columns:
            if col.transform and col.transform not in TRANSFORMS:
                issues.append(f"Unknown transform '{col.transform}' for column '{col.source}'")
        
        return issues
