"""
Command-Specific DynamoDB Scanner

This module follows the exact same pattern as dynamodb_scanner.py
but adds command and package filtering. We reuse the same:
- Generator pattern for memory efficiency
- Pagination logic with LastEvaluatedKey
- Error handling and logging patterns
- DynamoDB client setup

Key Features:
- Exact command matching (case-sensitive string equality)
- App package filtering
- Optional date range filtering
- Memory-efficient generator pattern
- Comprehensive error handling
"""

import boto3
from typing import Iterator, Dict, Optional, List
from botocore.exceptions import ClientError

# Reuse existing configuration and utilities
from config import (
    AWS_ACCESS_KEY_ID, 
    AWS_SECRET_ACCESS_KEY, 
    AWS_REGION,
    DYNAMODB_TABLE_NAME,
    DYNAMODB_HOST,
    STEP_CLASSIFICATIONS_FILTER
)
from utils import logger, convert_dynamodb_item_to_dict


# ============================================================================
# DYNAMODB CLIENT SETUP - Reusing Existing Pattern
# ============================================================================

def get_dynamodb_client():
    """
    Create and return boto3 DynamoDB client.
    
    This is identical to the existing dynamodb_scanner.py implementation.
    We reuse the same client setup to maintain consistency.
    
    Uses AWS credentials from config.
    Supports both AWS DynamoDB and local DynamoDB.
    
    Returns:
        boto3 DynamoDB client
    """
    client_config = {
        'aws_access_key_id': AWS_ACCESS_KEY_ID,
        'aws_secret_access_key': AWS_SECRET_ACCESS_KEY,
        'region_name': AWS_REGION
    }
    
    # Add host URL if using local DynamoDB
    if DYNAMODB_HOST:
        client_config['endpoint_url'] = DYNAMODB_HOST
    
    return boto3.client('dynamodb', **client_config)


# ============================================================================
# COMMAND-SPECIFIC SCANNING WITH PAGINATION
# ============================================================================

def scan_command_steps_with_pagination(
    command: str,
    app_package: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Iterator[Dict]:
    """
    Scan TestSteps table for specific command and package with pagination.
    
    This follows the exact same pattern as scan_test_steps_with_pagination()
    but adds additional filters for command and package matching.
    
    Key Features:
    - Exact command matching (case-sensitive string equality)
    - App package filtering
    - Optional date range filtering
    - Generator pattern for memory efficiency
    - Pagination support for large datasets
    
    Args:
        command: Exact command string to match (e.g., "Tap on Submit Button")
        app_package: App package to filter by (e.g., "in.swiggy.android.instamart")
        start_date: Optional start date in IST format (e.g., "2025-09-28")
        end_date: Optional end date in IST format (e.g., "2025-10-08")
    
    Yields:
        Dict: DynamoDB items (in DynamoDB JSON format)
        
    Example usage:
        >>> for item in scan_command_steps_with_pagination(
        ...     "Tap on Submit Button",
        ...     "in.swiggy.android.instamart"
        ... ):
        ...     step_id = item['step_id']['S']
        ...     print(step_id)
    
    Raises:
        ClientError: If DynamoDB operation fails
        ValueError: If command or app_package is empty
    """
    # Input validation
    if not command or not command.strip():
        raise ValueError("Command cannot be empty")
    
    if not app_package or not app_package.strip():
        raise ValueError("App package cannot be empty")
    
    client = get_dynamodb_client()
    
    # Build scan parameters with multiple filters
    # We use AND conditions to combine all our filters
    filter_conditions = [
        'step_classification IN (:tap, :text)',  # Existing filter
        'command = :command',                    # Exact command match
        'app_package = :app_package'             # App package match
    ]
    
    # Add date range filter if provided
    if start_date and end_date:
        filter_conditions.append('created_at BETWEEN :start_date AND :end_date')
    
    # Combine all conditions with AND
    filter_expression = ' AND '.join(filter_conditions)
    
    # Build expression attribute values
    expression_values = {
        ':tap': {'S': 'TAP'},
        ':text': {'S': 'TEXT'},
        ':command': {'S': command.strip()},  # Exact match, trimmed
        ':app_package': {'S': app_package.strip()}  # Exact match, trimmed
    }
    
    # Add date range values if provided
    if start_date and end_date:
        expression_values[':start_date'] = {'S': start_date}
        expression_values[':end_date'] = {'S': end_date}
    
    # Build scan parameters
    scan_kwargs = {
        'TableName': DYNAMODB_TABLE_NAME,
        'FilterExpression': filter_expression,
        'ExpressionAttributeValues': expression_values
    }
    
    # Track statistics for logging
    scanned_count = 0  # Total items scanned by DynamoDB
    yielded_count = 0  # Total items yielded to caller
    page_count = 0     # Number of pages processed
    
    logger.info(f"Starting command-specific scan of table: {DYNAMODB_TABLE_NAME}")
    logger.info(f"Command: '{command}'")
    logger.info(f"App Package: '{app_package}'")
    logger.info(f"Step Classifications: {STEP_CLASSIFICATIONS_FILTER}")
    
    if start_date and end_date:
        logger.info(f"Date Range: {start_date} to {end_date}")
    else:
        logger.info("Date Range: All time")
    
    try:
        # Pagination loop - same pattern as existing scanner
        while True:
            page_count += 1
            
            # Perform scan operation
            response = client.scan(**scan_kwargs)
            
            # Get items from this page
            items = response.get('Items', [])
            scanned_count += len(items)
            
            # Yield items one by one (Generator pattern)
            for item in items:
                yielded_count += 1
                # Convert DynamoDB item to regular dict before yielding
                converted_item = convert_dynamodb_item_to_dict(item)
                yield converted_item  # This is what makes it a generator
            
            # Log progress every 5 pages
            if page_count % 5 == 0:
                logger.info(
                    f"Progress: Page {page_count}, "
                    f"Scanned: {scanned_count}, "
                    f"Yielded: {yielded_count}"
                )
            
            # Check if there are more pages
            if 'LastEvaluatedKey' not in response:
                break  # No more pages, exit loop
            
            # Set starting point for next page
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    
    except ClientError as e:
        # Handle DynamoDB-specific errors
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"DynamoDB error ({error_code}): {error_message}")
        logger.error(f"Command: '{command}', Package: '{app_package}'")
        raise
    
    except Exception as e:
        # Handle other errors
        logger.error(f"Error scanning DynamoDB: {str(e)}")
        logger.error(f"Command: '{command}', Package: '{app_package}'")
        raise
    
    # Final statistics
    logger.info(
        f"Command scan complete. Pages: {page_count}, "
        f"Total items: {yielded_count}"
    )
    
    if yielded_count == 0:
        logger.warning(
            f"No steps found for command '{command}' and package '{app_package}'"
        )


# ============================================================================
# UTILITY FUNCTIONS - Helper Functions for Command Scanning
# ============================================================================

def validate_command_inputs(command: str, app_package: str) -> None:
    """
    Validate command and app_package inputs.
    
    This ensures we have valid inputs before making DynamoDB calls.
    
    Args:
        command: Command string to validate
        app_package: App package string to validate
        
    Raises:
        ValueError: If inputs are invalid
    """
    if not command or not command.strip():
        raise ValueError("Command cannot be empty or whitespace only")
    
    if not app_package or not app_package.strip():
        raise ValueError("App package cannot be empty or whitespace only")
    
    # Check for reasonable length limits
    if len(command.strip()) > 500:
        raise ValueError("Command is too long (max 500 characters)")
    
    if len(app_package.strip()) > 200:
        raise ValueError("App package is too long (max 200 characters)")


def get_scan_statistics(
    command: str,
    app_package: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, int]:
    """
    Get quick statistics about a command without loading all data.
    
    This performs a count-only scan to get statistics without
    loading all the step data into memory.
    
    Args:
        command: Command to analyze
        app_package: App package to filter by
        start_date: Optional start date
        end_date: Optional end date
        
    Returns:
        Dict with scan statistics
    """
    validate_command_inputs(command, app_package)
    
    client = get_dynamodb_client()
    
    # Build the same filter expression as the main scan
    filter_conditions = [
        'step_classification IN (:tap, :text)',
        'command = :command',
        'app_package = :app_package'
    ]
    
    if start_date and end_date:
        filter_conditions.append('created_at BETWEEN :start_date AND :end_date')
    
    filter_expression = ' AND '.join(filter_conditions)
    
    expression_values = {
        ':tap': {'S': 'TAP'},
        ':text': {'S': 'TEXT'},
        ':command': {'S': command.strip()},
        ':app_package': {'S': app_package.strip()}
    }
    
    if start_date and end_date:
        expression_values[':start_date'] = {'S': start_date}
        expression_values[':end_date'] = {'S': end_date}
    
    # Use Select='COUNT' to get only the count, not the data
    scan_kwargs = {
        'TableName': DYNAMODB_TABLE_NAME,
        'FilterExpression': filter_expression,
        'ExpressionAttributeValues': expression_values,
        'Select': 'COUNT'  # Only return count, not items
    }
    
    total_count = 0
    page_count = 0
    
    try:
        while True:
            page_count += 1
            response = client.scan(**scan_kwargs)
            
            total_count += response.get('Count', 0)
            
            if 'LastEvaluatedKey' not in response:
                break
            
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    
    except ClientError as e:
        logger.error(f"Error getting scan statistics: {e}")
        raise
    
    return {
        'total_steps': total_count,
        'pages_scanned': page_count,
        'command': command,
        'app_package': app_package
    }


def test_command_exists(
    command: str,
    app_package: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> bool:
    """
    Test if a command exists in the database without loading all data.
    
    This is useful for validation before running the full analysis.
    
    Args:
        command: Command to test
        app_package: App package to filter by
        start_date: Optional start date
        end_date: Optional end date
        
    Returns:
        True if command exists, False otherwise
    """
    try:
        stats = get_scan_statistics(command, app_package, start_date, end_date)
        return stats['total_steps'] > 0
    except Exception as e:
        logger.error(f"Error testing command existence: {e}")
        return False


# ============================================================================
# DEBUGGING AND DEVELOPMENT HELPERS
# ============================================================================

def list_available_commands(
    app_package: str,
    limit: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[str]:
    """
    List available commands for a given app package.
    
    This is useful for development and debugging to see what commands
    are available in the database.
    
    Args:
        app_package: App package to search in
        limit: Maximum number of commands to return
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        List of unique commands found
    """
    if not app_package or not app_package.strip():
        raise ValueError("App package cannot be empty")
    
    client = get_dynamodb_client()
    
    # Build filter for app package and step classification
    filter_conditions = [
        'step_classification IN (:tap, :text)',
        'app_package = :app_package'
    ]
    
    if start_date and end_date:
        filter_conditions.append('created_at BETWEEN :start_date AND :end_date')
    
    filter_expression = ' AND '.join(filter_conditions)
    
    expression_values = {
        ':tap': {'S': 'TAP'},
        ':text': {'S': 'TEXT'},
        ':app_package': {'S': app_package.strip()}
    }
    
    if start_date and end_date:
        expression_values[':start_date'] = {'S': start_date}
        expression_values[':end_date'] = {'S': end_date}
    
    scan_kwargs = {
        'TableName': DYNAMODB_TABLE_NAME,
        'FilterExpression': filter_expression,
        'ExpressionAttributeValues': expression_values,
        'ProjectionExpression': 'command'  # Only return command field
    }
    
    commands = set()
    
    try:
        while len(commands) < limit:
            response = client.scan(**scan_kwargs)
            
            for item in response.get('Items', []):
                if 'command' in item and 'S' in item['command']:
                    commands.add(item['command']['S'])
            
            if 'LastEvaluatedKey' not in response:
                break
            
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    
    except ClientError as e:
        logger.error(f"Error listing commands: {e}")
        raise
    
    return list(commands)[:limit]