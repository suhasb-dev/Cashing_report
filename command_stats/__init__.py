"""
Command Stats Module - Command-Level Cache Statistics Analysis

This module provides comprehensive analysis of cache performance for specific commands.
It reuses existing classification logic while providing new insights into command-level
cache behavior.

Main Components:
- scanner: DynamoDB querying with exact command matching
- analyzer: Statistics calculation using existing classifier logic  
- reporter: JSON report generation and console output
- cli: Command-line interface for easy usage

Usage:
    # Command line usage
    python -m command_stats.cli --command "Tap on Submit Button" --package "in.swiggy.android.instamart"
    
    # Programmatic usage
    from command_stats import analyze_command_statistics, generate_command_stats_report
"""

# Import main functions for easy access
from .scanner import scan_command_steps_with_pagination, test_command_exists
from .analyzer import analyze_command_statistics
from .reporter import generate_command_stats_report, print_command_stats_summary
from .models import CommandStatsReport, StepInfo, CacheReadStatus

# Import CLI main function
from .cli import main as cli_main

# Module version
__version__ = "1.0.0"

# Module description
__description__ = "Command-level cache statistics analysis for DynamoDB TestSteps"

# Main exports
__all__ = [
    # Core functions
    'analyze_command_statistics',
    'generate_command_stats_report',
    'scan_command_steps_with_pagination',
    'test_command_exists',
    'print_command_stats_summary',
    
    
    # Data structures
    'CommandStatsReport',
    'StepInfo', 
    'CacheReadStatus',
    
    # CLI
    'cli_main',
    
    # Version info
    '__version__',
    '__description__'
]