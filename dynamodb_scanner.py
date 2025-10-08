"""
DynamoDB Scanner Module

This module handles scanning the TestSteps DynamoDB table with:
- Pagination (for large datasets)
- Filtering (step_classification IN ['TAP', 'TEXT'])
- Generator pattern (memory efficient)

Why Generator?
- Doesn't load all data into memory at once
- Yields items one by one
- Perfect for large tables (1000s of rows)
"""

import boto3
from typing import Iterator, Dict, Optional
from botocore.exceptions import ClientError

from config import (
    AWS_ACCESS_KEY_ID, 
    AWS_SECRET_ACCESS_KEY, 
    AWS_REGION,
    DYNAMODB_TABLE_NAME,
    DYNAMODB_HOST,
    STEP_CLASSIFICATIONS_FILTER
)
from utils import logger


# ============================================================================
# DYNAMODB CLIENT SETUP
# ============================================================================

def get_dynamodb_client():
    """
    Create and return boto3 DynamoDB client.
    
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
# DYNAMODB SCANNING WITH PAGINATION
# ============================================================================

def scan_test_steps_with_pagination() -> Iterator[Dict]:
    """
    Scan TestSteps table with pagination using generator pattern.
    
    Why Generator?
    - Memory efficient: Doesn't load entire table into memory
    - Yields items one-by-one as they're scanned
    - Caller can process items incrementally
    
    Filtering:
    - Only returns steps where step_classification IN ('TAP', 'TEXT')
    - DynamoDB FilterExpression applied server-side
    
    Pagination:
    - DynamoDB returns max 1MB per scan
    - We use LastEvaluatedKey to continue scanning
    - Loop until no more pages
    
    Yields:
        Dict: DynamoDB items (in DynamoDB JSON format)
        
    Example usage:
        >>> for item in scan_test_steps_with_pagination():
        ...     step_id = item['step_id']['S']
        ...     print(step_id)
    """
    client = get_dynamodb_client()
    
    # Build scan parameters
    # FilterExpression: Server-side filtering (reduces data transfer)
    # ExpressionAttributeValues: Values to substitute in filter expression
    scan_kwargs = {
        'TableName': DYNAMODB_TABLE_NAME,
        'FilterExpression': 'step_classification IN (:tap, :text)',
        'ExpressionAttributeValues': {
            ':tap': {'S': 'TAP'},
            ':text': {'S': 'TEXT'}
        }
    }
    # add the time stramp filter here 
    # Track statistics
    scanned_count = 0  # Total items scanned
    yielded_count = 0  # Total items yielded
    page_count = 0     # Number of pages processed
    
    logger.info(f"Starting scan of table: {DYNAMODB_TABLE_NAME}")
    logger.info(f"Filter: step_classification IN {STEP_CLASSIFICATIONS_FILTER}")
    
    try:
        # Pagination loop
        # Continue until DynamoDB has no more pages
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
                yield item  # This is what makes it a generator
            
            # Log progress
            if page_count % 5 == 0:  # Log every 5 pages
                logger.info(
                    f"Progress: Page {page_count}, "
                    f"Scanned: {scanned_count}, "
                    f"Yielded: {yielded_count}"
                )
            
            # Check if there are more pages
            # LastEvaluatedKey exists = more data available
            if 'LastEvaluatedKey' not in response:
                break  # No more pages, exit loop
            
            # Set starting point for next page
            # ExclusiveStartKey tells DynamoDB where to continue
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    
    except ClientError as e:
        # Handle DynamoDB-specific errors
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"DynamoDB error ({error_code}): {error_message}")
        raise
    
    except Exception as e:
        # Handle other errors
        logger.error(f"Error scanning DynamoDB: {str(e)}")
        raise
    
    # Final statistics
    logger.info(
        f"Scan complete. Pages: {page_count}, "
        f"Total items: {yielded_count}"
    )
