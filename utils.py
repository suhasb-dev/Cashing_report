"""
Utility Functions for Cache Failure Classifier

This module contains reusable helper functions with proper timezone handling.
All DynamoDB timestamps are in UTC and are properly converted to IST for filtering.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Union

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# ============================================================================
# TIMEZONE CONSTANTS
# ============================================================================

# IST is UTC + 5:30
IST_OFFSET = timedelta(hours=5, minutes=30)


# ============================================================================
# DYNAMODB DATA CONVERSION
# ============================================================================

def convert_dynamodb_item_to_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert DynamoDB JSON format to regular Python dictionary.
    
    DynamoDB stores data in a special format:
        {"field_name": {"S": "string_value"}}   # String
        {"field_name": {"N": "123"}}            # Number
        {"field_name": {"BOOL": true}}          # Boolean
    
    Args:
        item: DynamoDB item in native format
        
    Returns:
        Regular Python dictionary with actual values
    """
    result = {}
    
    for key, value in item.items():
        if isinstance(value, dict):
            if 'S' in value:
                result[key] = value['S']
            elif 'N' in value:
                number_str = value['N']
                if '.' in number_str:
                    result[key] = float(number_str)
                else:
                    result[key] = int(number_str)
            elif 'BOOL' in value:
                result[key] = value['BOOL']
            elif 'NULL' in value:
                result[key] = None
            elif 'M' in value:
                result[key] = convert_dynamodb_item_to_dict(value['M'])
            elif 'L' in value:
                result[key] = [
                    convert_dynamodb_item_to_dict({'item': v})['item'] 
                    for v in value['L']
                ]
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result


# ============================================================================
# JSON PARSING
# ============================================================================

def parse_json_string(json_str: Optional[str]) -> Optional[Any]:
    """
    Safely parse JSON string, return None if invalid.
    
    Args:
        json_str: String containing JSON data (or None, "NA", etc.)
        
    Returns:
        Parsed Python object (dict/list) or None if parsing fails
    """
    if not json_str or json_str == "NA":
        return None
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {str(e)[:100]}")
        return None


# ============================================================================
# SAFE NESTED ACCESS
# ============================================================================

def get_nested_value(data: Dict, *keys: str, default: Any = None) -> Any:
    """
    Safely access nested dictionary values without KeyError.
    
    Args:
        data: Dictionary to access
        *keys: Variable number of keys to traverse
        default: Value to return if key not found
        
    Returns:
        Value at nested location or default if not found
    """
    result = data
    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default
    return result


# ============================================================================
# DATE/TIME PARSING WITH PROPER TIMEZONE HANDLING
# ============================================================================

def parse_iso_datetime(date_str: str) -> datetime:
    """
    Parse ISO datetime string to timezone-aware UTC datetime.
    
    Properly handles timezone information without discarding it!
    
    Handles various ISO formats:
    - "2025-10-07T16:37:17.918342+0000"  (with UTC offset)
    - "2025-10-07T16:37:17Z"              (Zulu/UTC timezone)
    - "2025-10-07T16:37:17"              (no timezone - assumes UTC)
    - "2025-10-07"                        (date only - assumes UTC midnight)
    
    Args:
        date_str: ISO format datetime string
        
    Returns:
        timezone-aware datetime object in UTC
        
    Raises:
        ValueError: If string cannot be parsed
        
    Example:
        >>> # DynamoDB format with timezone
        >>> dt = parse_iso_datetime("2025-10-08T10:00:00+0000")
        >>> print(dt)
        2025-10-08 10:00:00+00:00  # Timezone preserved!
        
        >>> # Zulu notation
        >>> dt = parse_iso_datetime("2025-10-08T10:00:00Z")
        >>> print(dt)
        2025-10-08 10:00:00+00:00
    """
    try:
        # Case 1: Has timezone offset (+0000, +0530, etc.)
        if '+' in date_str or '-' in date_str.split('T')[-1]:
            # Python's fromisoformat handles this directly
            dt = datetime.fromisoformat(date_str)
            
            # Convert to UTC if not already
            if dt.tzinfo is not None:
                dt_utc = dt.astimezone(timezone.utc)
                return dt_utc
            else:
                # Shouldn't happen, but handle it
                return dt.replace(tzinfo=timezone.utc)
        
        # Case 2: Zulu notation (Z = UTC)
        elif date_str.endswith('Z'):
            # Replace Z with +00:00 for parsing
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.astimezone(timezone.utc)
        
        # Case 3: No timezone - assume UTC
        elif 'T' in date_str:
            dt = datetime.fromisoformat(date_str)
            return dt.replace(tzinfo=timezone.utc)
        
        # Case 4: Date only - assume UTC midnight
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)
    
    except ValueError as e:
        logger.error(f"Failed to parse date: {date_str}")
        raise ValueError(f"Invalid date format: {date_str}") from e


def convert_ist_to_utc(ist_datetime: datetime) -> datetime:
    """
    Convert IST datetime to UTC datetime.
    
    IST = UTC + 5:30
    To convert IST to UTC: subtract 5:30
    
    Args:
        ist_datetime: datetime in IST (can be naive or aware)
        
    Returns:
        timezone-aware datetime in UTC
        
    Example:
        >>> from datetime import datetime
        >>> ist = datetime(2025, 10, 8, 10, 0, 0)  # Oct 8, 10:00 AM IST
        >>> utc = convert_ist_to_utc(ist)
        >>> print(utc)
        2025-10-08 04:30:00+00:00  # Oct 8, 4:30 AM UTC
    """
    # If naive, treat as IST
    if ist_datetime.tzinfo is None:
        utc_dt = ist_datetime - IST_OFFSET
        return utc_dt.replace(tzinfo=timezone.utc)
    
    # If already aware, convert to UTC
    return ist_datetime.astimezone(timezone.utc) - IST_OFFSET


def parse_date_as_ist_to_utc(date_str: str, end_of_day: bool = False) -> datetime:
    """
    Parse date string as IST and convert to UTC.
    
    This is the KEY function for IST filtering!
    User input is interpreted as IST, then converted to UTC for DynamoDB comparison.
    
    Args:
        date_str: Date string in format "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SS"
        end_of_day: If True and date has no time, set to 23:59:59
        
    Returns:
        timezone-aware datetime in UTC
        
    Example:
        >>> # User inputs: "2025-10-08" (meaning Oct 8 in IST)
        >>> start_utc = parse_date_as_ist_to_utc("2025-10-08", end_of_day=False)
        >>> print(start_utc)
        2025-10-07 18:30:00+00:00  # Oct 7, 6:30 PM UTC (Oct 8, 12:00 AM IST)
        
        >>> end_utc = parse_date_as_ist_to_utc("2025-10-08", end_of_day=True)
        >>> print(end_utc)
        2025-10-08 18:29:59+00:00  # Oct 8, 6:29 PM UTC (Oct 8, 11:59 PM IST)
    """
    # Parse the input date (treat as IST)
    parsed_dt = datetime.fromisoformat(date_str.split('+')[0].replace('Z', ''))
    
    # If date only (no time component) and end_of_day requested
    if 'T' not in date_str and end_of_day:
        # Set to 23:59:59 IST
        parsed_dt = parsed_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Convert IST to UTC
    utc_dt = convert_ist_to_utc(parsed_dt)
    
    logger.debug(f"Parsed '{date_str}' as IST → UTC: {utc_dt}")
    
    return utc_dt


def is_within_date_range(
    created_at: str, 
    start_date: str, 
    end_date: str
) -> bool:
    """
    Check if created_at (UTC) falls within IST date range.
    
    IMPORTANT: 
    - created_at from DynamoDB is in UTC with timezone
    - start_date and end_date are interpreted as IST
    - Proper timezone conversion is applied
    
    Args:
        created_at: ISO datetime string in UTC (from DynamoDB)
                   e.g., "2025-10-08T10:00:00+0000"
        start_date: Start date in IST (user input)
                   e.g., "2025-10-08" or "2025-10-08T00:00:00"
        end_date: End date in IST (user input)
                 e.g., "2025-10-08" or "2025-10-08T23:59:59"
        
    Returns:
        True if created_at is within range, False otherwise
        
    Example:
        >>> # DynamoDB: "2025-10-08T10:00:00+0000" (10 AM UTC = 3:30 PM IST)
        >>> # User filters: Oct 8, 2025 IST (12:00 AM to 11:59 PM IST)
        >>> is_within_date_range(
        ...     "2025-10-08T10:00:00+0000",  # 3:30 PM IST
        ...     "2025-10-08",                 # Oct 8 IST start
        ...     "2025-10-08"                  # Oct 8 IST end
        ... )
        True  # 3:30 PM IST is within Oct 8 IST
    """
    try:
        # Parse created_at from DynamoDB (UTC with timezone)
        # This now properly handles timezone!
        created_dt_utc = parse_iso_datetime(created_at)
        
        # Parse start_date as IST and convert to UTC
        start_dt_utc = parse_date_as_ist_to_utc(start_date, end_of_day=False)
        
        # Parse end_date as IST and convert to UTC
        end_dt_utc = parse_date_as_ist_to_utc(end_date, end_of_day=True)
        
        # Compare in UTC (all timezone-aware)
        result = start_dt_utc <= created_dt_utc <= end_dt_utc
        
        # Debug logging
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Date comparison:\n"
                f"  Created (UTC):  {created_dt_utc}\n"
                f"  Start (UTC):    {start_dt_utc}\n"
                f"  End (UTC):      {end_dt_utc}\n"
                f"  Within range:   {result}"
            )
        
        return result
    
    except Exception as e:
        logger.error(f"Date comparison error for '{created_at}': {e}")
        return False
