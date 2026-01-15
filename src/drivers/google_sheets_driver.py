"""
Google Sheets Driver for Mamnoon Mezze Weekly Order Sheet

Sheet structure (per tab):
- 5 daily order tables (Monday-Friday)
- 1 lot code summary table at bottom
- Each daily table: date header → day header → customer rows → TOTALS row

Products: HUMMUS, HARRA HUMMUS, BASAL LABNEH, LABNEH, MUHAMMARA, BABA, MAMA CHIPS, HARRA
"""

from googleapiclient.discovery import build
from google.oauth2 import service_account
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import re
import os


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OrderLine:
    """Single order line from Mezze sheet."""
    # Time context
    week_start: date
    week_end: date
    day_of_week: str
    
    # Customer
    customer: str           # Canonical name (e.g., "Crown")
    customer_raw: str       # Original cell value (e.g., "Crown - PO # 779322")
    po_hint: Optional[str]  # PO# if present in cell (not authoritative)
    
    # Product
    product: str
    unit_type: str          # CASE or EACH
    quantity: float
    
    # Traceability
    source_tab: str
    source_row: int
    raw_value: str          # Original cell value for debugging


@dataclass
class ChannelSummary:
    """Weekly totals by channel from lot code summary section."""
    week_start: date
    week_end: date
    source_tab: str
    
    # Totals by channel and product
    psfh: Dict[str, float] = field(default_factory=dict)
    restaurant: Dict[str, float] = field(default_factory=dict)
    met: Dict[str, float] = field(default_factory=dict)
    pcc: Dict[str, float] = field(default_factory=dict)


@dataclass
class ParseResult:
    """Complete parse result from driver."""
    order_lines: List[OrderLine]
    channel_summaries: List[ChannelSummary]
    warnings: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    stats: Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def extract_customer_and_po(raw_value: str) -> tuple[str, Optional[str]]:
    """
    Extract canonical customer name and PO hint from raw cell value.
    
    Examples:
        "Crown - PO # 779322"     → ("Crown", "779322")
        "Crown - PO# 785153"      → ("Crown", "785153")
        "PSFH - PO # MAMN-54127"  → ("PSFH", "MAMN-54127")
        "PSFH (FROZEN) - PO#"     → ("PSFH (FROZEN)", None)
        "Met #165 Crown Hill"     → ("Met #165 Crown Hill", None)
        "Leschi Market"           → ("Leschi Market", None)
    """
    raw = raw_value.strip()
    
    # Pattern: "Customer - PO # NUMBER" or "Customer - PO# NUMBER"
    po_pattern = re.compile(r'^(.+?)\s*-\s*PO\s*#?\s*(.*)$', re.I)
    match = po_pattern.match(raw)
    
    if match:
        customer = match.group(1).strip()
        po_part = match.group(2).strip()
        po_hint = po_part if po_part else None
        return customer, po_hint
    
    return raw, None


def parse_date_range(date_str: str) -> tuple[Optional[date], Optional[date]]:
    """
    Parse date range from header like "01/12/26 - 01/16/26" or "3/10/25 - 3/14/25".
    """
    # Pattern: MM/DD/YY - MM/DD/YY (with various separators)
    pattern = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{2,4})\s*[-–]\s*(\d{1,2})/(\d{1,2})/(\d{2,4})')
    match = pattern.match(date_str.strip())
    
    if not match:
        return None, None
    
    try:
        m1, d1, y1 = int(match.group(1)), int(match.group(2)), int(match.group(3))
        m2, d2, y2 = int(match.group(4)), int(match.group(5)), int(match.group(6))
        
        # Handle 2-digit years
        if y1 < 100:
            y1 += 2000
        if y2 < 100:
            y2 += 2000
        
        return date(y1, m1, d1), date(y2, m2, d2)
    except (ValueError, TypeError):
        return None, None


def parse_quantity(value: str) -> Optional[float]:
    """
    Parse quantity from cell value. Returns None if not a valid number.
    """
    if not value:
        return None
    
    val = str(value).strip()
    
    # Skip known non-numeric patterns
    skip_patterns = [
        'TOTAL', 'CASE', 'EACH', 'HUMMUS', 'HARRA', 'LABNEH', 'BABA', 'MUHAMMARA',
        'PSFH', 'MET', 'PCC', 'RESTAURANT', 'PRODUCTION', 'LOT', 'EXPIRATION',
        '#REF!', '#N/A', '#VALUE!', '#DIV/0!',
    ]
    val_upper = val.upper()
    if any(p in val_upper for p in skip_patterns):
        return None
    
    # Handle special notations
    val = val.replace('#', '').strip()  # "12#" → "12"
    
    # Try to parse as number
    try:
        return float(val)
    except ValueError:
        return None


def col_letter(col_idx: int) -> str:
    """Convert 0-based column index to letter (A, B, ... Z, AA, AB, ...)."""
    result = ""
    idx = col_idx
    while idx >= 0:
        result = chr(idx % 26 + ord('A')) + result
        idx = idx // 26 - 1
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Row Classification
# ─────────────────────────────────────────────────────────────────────────────

PATTERNS = {
    'day_header': re.compile(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*$', re.I),
    'date_range': re.compile(r'^\d{1,2}/\d{1,2}/\d{2,4}\s*[-–]\s*\d{1,2}/\d{1,2}/\d{2,4}'),
    'totals': re.compile(r'^TOTALS?$', re.I),
    'production_date': re.compile(r'^Production Date', re.I),
    'lot_number': re.compile(r'^Lot Number', re.I),
    'expiration': re.compile(r'^Expiration', re.I),
    'lot_code_section': re.compile(r'^Production Lot Code', re.I),
}


def classify_row(row: list) -> str:
    """Classify a row based on its first cell and content."""
    if not row:
        return 'empty'
    
    first_cell = str(row[0]).strip() if row[0] else ''
    
    if not first_cell:
        has_content = any(str(c).strip() for c in row[1:] if c)
        return 'empty' if not has_content else 'data_no_label'
    
    if PATTERNS['day_header'].match(first_cell):
        return 'day_header'
    if PATTERNS['date_range'].match(first_cell):
        return 'date_range'
    if PATTERNS['totals'].match(first_cell):
        return 'totals'
    if PATTERNS['production_date'].match(first_cell):
        return 'production_date'
    if PATTERNS['lot_number'].match(first_cell):
        return 'lot_number'
    if PATTERNS['expiration'].match(first_cell):
        return 'expiration'
    if PATTERNS['lot_code_section'].match(first_cell):
        return 'lot_code_section'
    
    return 'data_row'


# ─────────────────────────────────────────────────────────────────────────────
# Product Column Mapping
# ─────────────────────────────────────────────────────────────────────────────

# Order matters: check longer/more specific names FIRST to avoid premature matching
# e.g., "HARRA HUMMUS" must be checked before "HARRA"
KNOWN_PRODUCTS = [
    'HARRA HUMMUS',   # Check before HARRA
    'BASAL LABNEH',   # Check before LABNEH
    'MAMA CHIPS',
    'MUHAMMARA',
    'HUMMUS',
    'LABNEH',         # Legacy, usually = BASAL LABNEH post-2023
    'HARRA',          # Sauce product (distinct from HARRA HUMMUS)
    'BABA',
]


def extract_product_columns(header_row: list, unit_row: list) -> List[Dict]:
    """
    Extract product column mappings from header rows.
    
    Returns list of: {'product': str, 'case_col': int, 'each_col': int}
    """
    products = []
    matched_cols = set()  # Track which columns we've already matched
    
    # Find product names in header row
    for col_idx, cell in enumerate(header_row):
        if col_idx in matched_cols:
            continue
            
        cell_val = str(cell).strip().upper()
        if not cell_val:
            continue
        
        # Check if this is a known product (exact match preferred)
        matched_product = None
        
        # First try exact match
        for prod in KNOWN_PRODUCTS:
            if cell_val == prod:
                matched_product = prod
                break
        
        # Then try contains (but respect the order in KNOWN_PRODUCTS)
        if not matched_product:
            for prod in KNOWN_PRODUCTS:
                if prod in cell_val or cell_val in prod:
                    matched_product = prod
                    break
        
        if matched_product:
            # Found a product - look for CASE/EACH columns
            case_col = None
            each_col = None
            
            # Check this column and next few for CASE/EACH in unit row
            for offset in range(3):
                check_col = col_idx + offset
                if check_col < len(unit_row) and check_col not in matched_cols:
                    unit_val = str(unit_row[check_col]).strip().upper() if check_col < len(unit_row) else ''
                    if 'CASE' in unit_val and case_col is None:
                        case_col = check_col
                    elif 'EACH' in unit_val and each_col is None:
                        each_col = check_col
            
            if case_col is not None or each_col is not None:
                products.append({
                    'product': matched_product,
                    'case_col': case_col,
                    'each_col': each_col,
                })
                matched_cols.add(col_idx)
                if case_col:
                    matched_cols.add(case_col)
                if each_col:
                    matched_cols.add(each_col)
    
    return products


# ─────────────────────────────────────────────────────────────────────────────
# Main Driver Class
# ─────────────────────────────────────────────────────────────────────────────

class GoogleSheetsDriver:
    """
    Driver for extracting order data from Mamnoon Mezze weekly order sheets.
    """
    
    source_name = "mezze_sheet"
    
    def __init__(self, sheet_id: str, credentials_path: str = None, api_key: str = None):
        """
        Initialize the driver.
        
        Args:
            sheet_id: Google Sheet ID from the URL
            credentials_path: Path to service account JSON key file (Option A)
            api_key: Google API key for public sheets (Option B)
        """
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self.api_key = api_key or os.environ.get('GOOGLE_API_KEY')
        self._service = None
        
    def _get_service(self):
        """Lazy-load Google Sheets API service."""
        if self._service is None:
            if self.api_key:
                # Option B: API key for public sheets
                self._service = build('sheets', 'v4', developerKey=self.api_key)
            elif self.credentials_path:
                # Option A: Service account
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}\n"
                        "Please create a service account and download the JSON key."
                    )
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                )
                self._service = build('sheets', 'v4', credentials=credentials)
            else:
                raise ValueError(
                    "Either api_key or credentials_path must be provided.\n"
                    "Set GOOGLE_API_KEY environment variable or pass credentials_path."
                )
        return self._service
    
    def get_weekly_tabs(self) -> List[str]:
        """Get list of weekly order tab names."""
        service = self._get_service()
        sheet_metadata = service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
        all_tabs = [s['properties']['title'] for s in sheet_metadata['sheets']]
        
        # Filter to weekly order tabs (exclude master template)
        weekly_tabs = [
            t for t in all_tabs 
            if 'Weekly Order' in t and t != 'Weekly Order Master'
        ]
        return sorted(weekly_tabs)
    
    def fetch_all(self) -> ParseResult:
        """
        Fetch and parse all weekly order tabs.
        
        Returns:
            ParseResult with order_lines, channel_summaries, warnings, errors, stats
        """
        all_order_lines = []
        all_channel_summaries = []
        all_warnings = []
        all_errors = []
        
        tabs = self.get_weekly_tabs()
        
        for tab in tabs:
            try:
                result = self._parse_tab(tab)
                all_order_lines.extend(result['order_lines'])
                if result.get('channel_summary'):
                    all_channel_summaries.append(result['channel_summary'])
                all_warnings.extend(result['warnings'])
            except Exception as e:
                all_errors.append({
                    'tab': tab,
                    'error': str(e),
                    'type': 'tab_parse_error'
                })
        
        # Aggregate stats
        stats = {
            'tabs_processed': len(tabs),
            'total_order_lines': len(all_order_lines),
            'total_channel_summaries': len(all_channel_summaries),
            'unique_customers': len(set(ol.customer for ol in all_order_lines)),
            'unique_products': len(set(ol.product for ol in all_order_lines)),
            'warnings_count': len(all_warnings),
            'errors_count': len(all_errors),
        }
        
        return ParseResult(
            order_lines=all_order_lines,
            channel_summaries=all_channel_summaries,
            warnings=all_warnings,
            errors=all_errors,
            stats=stats,
        )
    
    def _parse_tab(self, tab_name: str) -> Dict:
        """Parse a single tab."""
        service = self._get_service()
        
        # Fetch all data from tab
        result = service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=f"'{tab_name}'!A1:Z200"
        ).execute()
        rows = result.get('values', [])
        
        order_lines = []
        warnings = []
        
        # State machine for parsing
        current_week_start = None
        current_week_end = None
        current_day = None
        current_products = []  # Product column mappings
        in_day_block = False
        in_lot_code_section = False
        
        row_idx = 0
        while row_idx < len(rows):
            row = rows[row_idx]
            row_num = row_idx + 1
            row_type = classify_row(row)
            first_cell = str(row[0]).strip() if row else ''
            
            # Stop parsing orders when we hit lot code section
            if row_type == 'lot_code_section':
                in_lot_code_section = True
                # TODO: Parse channel summary from lot code section
                break
            
            # Date range header - sets week context
            if row_type == 'date_range':
                week_start, week_end = parse_date_range(first_cell)
                if week_start and week_end:
                    current_week_start = week_start
                    current_week_end = week_end
                    
                    # Next row after date range should have product columns
                    # Extract product column mappings
                    if row_idx + 1 < len(rows):
                        unit_row = rows[row_idx + 1]
                        current_products = extract_product_columns(row, unit_row)
            
            # Day header - starts a new day block
            elif row_type == 'day_header':
                current_day = first_cell.strip().title()
                in_day_block = True
            
            # Totals row - ends day block
            elif row_type == 'totals':
                in_day_block = False
            
            # Data row - parse order lines
            elif row_type == 'data_row' and in_day_block:
                customer_raw = first_cell
                customer, po_hint = extract_customer_and_po(customer_raw)
                
                # Extract quantities for each product
                for prod_map in current_products:
                    product = prod_map['product']
                    
                    # CASE quantity
                    if prod_map['case_col'] is not None:
                        col_idx = prod_map['case_col']
                        if col_idx < len(row):
                            raw_val = str(row[col_idx]).strip()
                            qty = parse_quantity(raw_val)
                            if qty is not None and qty > 0:
                                order_lines.append(OrderLine(
                                    week_start=current_week_start,
                                    week_end=current_week_end,
                                    day_of_week=current_day,
                                    customer=customer,
                                    customer_raw=customer_raw,
                                    po_hint=po_hint,
                                    product=product,
                                    unit_type='CASE',
                                    quantity=qty,
                                    source_tab=tab_name,
                                    source_row=row_num,
                                    raw_value=raw_val,
                                ))
                            elif raw_val and qty is None:
                                warnings.append({
                                    'type': 'unparseable_quantity',
                                    'tab': tab_name,
                                    'cell': f"{col_letter(col_idx)}{row_num}",
                                    'value': raw_val,
                                    'customer': customer,
                                    'product': product,
                                })
                    
                    # EACH quantity
                    if prod_map['each_col'] is not None:
                        col_idx = prod_map['each_col']
                        if col_idx < len(row):
                            raw_val = str(row[col_idx]).strip()
                            qty = parse_quantity(raw_val)
                            if qty is not None and qty > 0:
                                order_lines.append(OrderLine(
                                    week_start=current_week_start,
                                    week_end=current_week_end,
                                    day_of_week=current_day,
                                    customer=customer,
                                    customer_raw=customer_raw,
                                    po_hint=po_hint,
                                    product=product,
                                    unit_type='EACH',
                                    quantity=qty,
                                    source_tab=tab_name,
                                    source_row=row_num,
                                    raw_value=raw_val,
                                ))
                            elif raw_val and qty is None:
                                warnings.append({
                                    'type': 'unparseable_quantity',
                                    'tab': tab_name,
                                    'cell': f"{col_letter(col_idx)}{row_num}",
                                    'value': raw_val,
                                    'customer': customer,
                                    'product': product,
                                })
            
            row_idx += 1
        
        return {
            'order_lines': order_lines,
            'channel_summary': None,  # TODO: implement
            'warnings': warnings,
        }
