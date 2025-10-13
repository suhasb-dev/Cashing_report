"""
Command Stats CLI - Production-Ready Command-Line Interface

This module provides the main entry point for command-level cache statistics analysis.
It follows the same patterns as the existing main.py but focuses on command-specific analysis.

Key Features:
- Comprehensive argument parsing with validation
- Error handling and user feedback
- Progress reporting and logging
- Integration with all command_stats modules
- Production-ready error handling and edge cases
"""

import argparse
import sys
from datetime import datetime, date
from typing import Optional, Dict, Any

# Import our command_stats modules
from .scanner import scan_command_steps_with_pagination, test_command_exists, validate_command_inputs
from .analyzer import analyze_command_statistics, validate_analysis_inputs
from .reporter import generate_command_stats_report, validate_report_consistency
from .models import CommandStatsReport

# Import existing utilities
from utils import logger


# ============================================================================
# ARGUMENT PARSING - Production-Ready with Comprehensive Validation
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments with comprehensive validation.
    
    This follows the same pattern as the existing main.py but adds
    command-specific arguments and validation.
    
    Returns:
        Parsed arguments namespace with validated values
    """
    parser = argparse.ArgumentParser(
        description='Generate command-level cache statistics report (IST timezone)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic command analysis
  python -m command_stats.cli --command "Tap on Submit Button" --package "in.swiggy.android.instamart"
  
  # With date range (IST)
  python -m command_stats.cli --command "Tap on Submit Button" --package "in.swiggy.android.instamart" --start-date "2025-10-07" --end-date "2025-10-08"
  
  # Custom output path
  python -m command_stats.cli --command "Tap on Submit Button" --package "in.swiggy.android.instamart" --output "./my_command_report.json"
  
  # Console output only (no file save)
  python -m command_stats.cli --command "Tap on Submit Button" --package "in.swiggy.android.instamart" --no-save

IMPORTANT: 
- All dates are interpreted as IST (UTC+5:30)
- Command matching is EXACT (case-sensitive)
- Default start date: 2025-09-28 (data quality cutoff)
- Default end date: Current date
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--command',
        type=str,
        required=True,
        help='Exact command string to analyze (e.g., "Tap on Submit Button")',
        metavar='COMMAND'
    )
    
    parser.add_argument(
        '--package',
        type=str,
        required=True,
        help='App package name to filter by (e.g., "in.swiggy.android.instamart")',
        metavar='PACKAGE'
    )
    
    # Optional date arguments
    parser.add_argument(
        '--start-date',
        type=str,
        default='2025-09-28',  # Default as per requirements
        help='Start date in IST (format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS). Default: 2025-09-28',
        metavar='DATE'
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,  # Will be set to current date if not provided
        help='End date in IST (format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS). Default: Current date',
        metavar='DATE'
    )
    
    # Output options
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output file path (optional, auto-generated if not provided)',
        metavar='PATH'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save report to file, only print summary to console'
    )
    
    # Debugging and development options
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )
    
    parser.add_argument(
        '--test-command',
        action='store_true',
        help='Test if command exists in database before running full analysis'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate inputs and test command existence, do not run full analysis'
    )
    
    return parser.parse_args()


# ============================================================================
# INPUT VALIDATION - Production-Ready Validation
# ============================================================================

def validate_date_format(date_str: str) -> bool:
    """
    Validate that date string is in correct ISO format.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        True if valid format, False otherwise
    """
    try:
        # Try parsing the date part (before any time component)
        date_part = date_str.split('T')[0]
        datetime.strptime(date_part, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_date_arguments(start_date: str, end_date: str) -> bool:
    """
    Validate date arguments logic and format.
    
    Args:
        start_date: Start date string
        end_date: End date string
        
    Returns:
        True if valid, False otherwise
    """
    # Validate format
    if not validate_date_format(start_date):
        logger.error(f"Invalid start date format: {start_date}")
        logger.error("Expected format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
        return False
    
    if not validate_date_format(end_date):
        logger.error(f"Invalid end date format: {end_date}")
        logger.error("Expected format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
        return False
    
    # Validate logical relationship
    try:
        start_dt = datetime.fromisoformat(start_date.split('T')[0])
        end_dt = datetime.fromisoformat(end_date.split('T')[0])
        
        if start_dt > end_dt:
            logger.error(f"Start date ({start_date}) cannot be after end date ({end_date})")
            return False
        
        # Check if date range is reasonable (not more than 1 year)
        if (end_dt - start_dt).days > 365:
            logger.warning(f"Date range is very large: {(end_dt - start_dt).days} days")
            logger.warning("This may result in a very large dataset and slow processing")
    
    except ValueError as e:
        logger.error(f"Date parsing error: {e}")
        return False
    
    return True


def validate_all_inputs(args: argparse.Namespace) -> bool:
    """
    Validate all command line inputs.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        True if all inputs are valid, False otherwise
    """
    # Validate command and package
    try:
        validate_command_inputs(args.command, args.package)
    except ValueError as e:
        logger.error(f"Input validation error: {e}")
        return False
    
    # Set default end date if not provided
    if not args.end_date:
        args.end_date = date.today().strftime("%Y-%m-%d")
        logger.info(f"End date not provided, using current date: {args.end_date}")
    
    # Validate date arguments
    if not validate_date_arguments(args.start_date, args.end_date):
        return False
    
    return True


# ============================================================================
# MAIN ORCHESTRATION - Production-Ready Main Function
# ============================================================================

def main() -> int:
    """
    Main function - orchestrates the entire command stats analysis process.
    
    This follows the same pattern as the existing main.py but focuses on
    command-specific analysis with comprehensive error handling.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Parse and validate arguments
        args = parse_arguments()
        
        # Set logging level
        if args.verbose:
            logger.setLevel('DEBUG')
        
        # Validate all inputs
        if not validate_all_inputs(args):
            return 1
        
        # Log startup information
        logger.info("="*80)
        logger.info("Command-Level Cache Statistics Analysis")
        logger.info("="*80)
        logger.info(f"Command: '{args.command}'")
        logger.info(f"App Package: '{args.package}'")
        logger.info(f"Date Range: {args.start_date} to {args.end_date} IST")
        logger.info("Timezone: IST (UTC+5:30) - dates are interpreted as IST")
        
        if args.output:
            logger.info(f"Output Path: {args.output}")
        
        if args.no_save:
            logger.info("File Save: Disabled (console output only)")
        
        # Test command existence if requested
        if args.test_command or args.validate_only:
            logger.info("Testing command existence in database...")
            
            if not test_command_exists(args.command, args.package, args.start_date, args.end_date):
                logger.error(f"Command '{args.command}' not found for package '{args.package}' in the specified date range")
                logger.error("Please check:")
                logger.error("1. Command spelling (exact match required)")
                logger.error("2. App package name")
                logger.error("3. Date range (data available from 2025-09-28 onwards)")
                return 1
            
            logger.info("✅ Command found in database")
            
            if args.validate_only:
                logger.info("Validation complete - command exists and inputs are valid")
                return 0
        
        # Run the analysis
        start_time = datetime.now()
        
        try:
            # Step 1: Scan DynamoDB for matching steps
            logger.info("Step 1: Scanning DynamoDB for matching steps...")
            steps = list(scan_command_steps_with_pagination(
                command=args.command,
                app_package=args.package,
                start_date=args.start_date,
                end_date=args.end_date
            ))
            
            if not steps:
                logger.error(f"No steps found for command '{args.command}' and package '{args.package}'")
                logger.error("Please verify:")
                logger.error("1. Command exists in database (use --test-command)")
                logger.error("2. Date range contains data")
                logger.error("3. App package name is correct")
                return 1
            
            logger.info(f"Found {len(steps)} matching steps")
            
            # Step 2: Analyze cache statistics
            logger.info("Step 2: Analyzing cache statistics...")
            report = analyze_command_statistics(
                steps=steps,
                command=args.command,
                app_package=args.package,
                start_date=args.start_date,
                end_date=args.end_date
            )
            
            # Step 3: Validate report consistency
            logger.info("Step 3: Validating report consistency...")
            if not validate_report_consistency(report):
                logger.warning("Report validation failed, but continuing with generation")
            
            # Step 4: Generate and save report
            logger.info("Step 4: Generating report...")
            file_path = generate_command_stats_report(
                report=report,
                save_to_file=not args.no_save,
                output_path=args.output,
                print_to_console=True
            )
            
            # Calculate execution time
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Final summary
            logger.info("="*80)
            logger.info("ANALYSIS COMPLETE")
            logger.info("="*80)
            logger.info(f"Total Steps Analyzed: {report['total_step_runs']}")
            logger.info(f"Cache Hit Rate: {report['cache_hit']['percentage']}")
            logger.info(f"Cache Miss Rate: {report['cache_miss']['percentage']}")
            logger.info(f"Average Cache Latency: {report['cache_hit']['average_latency']:.6f}s")
            logger.info(f"Execution Time: {duration:.2f} seconds")
            
            if not args.no_save:
                logger.info(f"Report saved to: {file_path}")
            
            logger.info("="*80)
            
            return 0
        
        except KeyboardInterrupt:
            logger.warning("\nOperation cancelled by user")
            return 1
        
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}", exc_info=True)
            return 1
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return 1


# ============================================================================
# DEVELOPMENT AND TESTING HELPERS
# ============================================================================

def run_quick_test(command: str, package: str) -> bool:
    """
    Run a quick test to verify the system works.
    
    This is useful for development and testing.
    
    Args:
        command: Command to test
        package: Package to test
        
    Returns:
        True if test passes, False otherwise
    """
    try:
        logger.info(f"Running quick test for command: '{command}', package: '{package}'")
        
        # Test command existence
        if not test_command_exists(command, package):
            logger.error("Command not found in database")
            return False
        
        # Run minimal analysis
        steps = list(scan_command_steps_with_pagination(command, package))
        
        if not steps:
            logger.error("No steps found")
            return False
        
        # Analyze first 10 steps only
        limited_steps = steps[:10]
        report = analyze_command_statistics(limited_steps, command, package)
        
        # Validate report
        if not validate_report_consistency(report):
            logger.error("Report validation failed")
            return False
        
        logger.info("✅ Quick test passed")
        return True
        
    except Exception as e:
        logger.error(f"Quick test failed: {e}")
        return False


if __name__ == "__main__":
    sys.exit(main())