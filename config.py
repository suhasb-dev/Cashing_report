"""
Configuration Module for Cache Failure Classifier

This module centralizes all configuration values:
- AWS credentials and settings
- DynamoDB table information  
- Business logic constants (thresholds, filters)

Why separate config?
- Easy to modify constants without touching business logic
- Environment-specific settings
- Single source of truth for configuration
"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
# This reads the .env file and sets them in os.environ
load_dotenv()

# ============================================================================
# AWS CONFIGURATION
# ============================================================================

# AWS Credentials
# os.getenv() reads from environment variables with a fallback default
AWS_ACCESS_KEY_ID: str = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY: str = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_REGION: str = os.getenv('AWS_REGION', 'ap-south-1')

# DynamoDB Settings
DYNAMODB_TABLE_NAME: str = os.getenv('DYNAMODB_TABLE_NAME', 'TestSteps')
DYNAMODB_HOST: str = os.getenv('DYNAMODB_HOST', None)  # None = use AWS, URL = local

# ============================================================================
# BUSINESS LOGIC CONSTANTS
# ============================================================================

# Similarity threshold for cache matching (75%)
# Why 0.75? Based on your requirement - vectors with similarity >= 75% are considered matches
SIMILARITY_THRESHOLD: float = 0.75

# Step classifications to analyze
# Why list? We only care about TAP and TEXT steps for cache analysis
STEP_CLASSIFICATIONS_FILTER: List[str] = ['TAP', 'TEXT']

# Cache read status values to analyze
# -1 = MISS (no match found)
# 0 = HIT_WITHOUT_COMPONENT (found but couldn't use component)
CACHE_READ_STATUS_FILTER: List[int] = [-1, 0]

# ============================================================================
# REPORT CONFIGURATION
# ============================================================================

# Default directory for saving reports
DEFAULT_OUTPUT_DIR: str = './cache_reports'

# Validation: Ensure required variables are set
if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError(
        "AWS credentials not found! Please set AWS_ACCESS_KEY_ID and "
        "AWS_SECRET_ACCESS_KEY in .env file"
    )
