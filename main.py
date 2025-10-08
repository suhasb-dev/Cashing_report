"""
Main Entry Point for Cache Failure Classifier

IMPORTANT: All date inputs are treated as IST (Indian Standard Time).
UTC+5:30 timezone is automatically handled.

Usage:
    # Filter by Oct 8, 2025 IST (full day)
    python main.py --start-date "2025-10-08" --end-date "2025-10-08"
    
    # This will match all steps created between:
    # - Oct 8, 12:00 AM IST (Oct 7, 6:30 PM UTC)
    # - Oct 8, 11:59 PM IST (Oct 8, 6:29 PM UTC)
"""

import argparse
import sys
from datetime import datetime
from typing import Dict, Optional

from report_generator import generate_cache_report, print_report_summary
from utils import logger


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description='Generate cache failure classification report (IST timezone)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full table scan (all records)
  python main.py
  
  # Filter by IST date (recommended)
  python main.py --start-date "2025-10-08" --end-date "2025-10-08"
  
  # With time component (IST)
  python main.py --start-date "2025-10-08T10:00:00" --end-date "2025-10-08T11:00:00"
  
  # Custom output path
  python main.py --start-date "2025-10-08" --end-date "2025-10-08" --output "./my_report.json"

IMPORTANT: All dates are interpreted as IST (UTC+5:30).
DynamoDB stores timestamps in UTC, conversion is handled automatically.
        """
    )
    
    # Optional date arguments
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help='Start date in IST (format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)',
        metavar='DATE'
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='End date in IST (format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)',
        metavar='DATE'
    )
    
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
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )
    
    return parser.parse_args()


def validate_date_format(date_str: str) -> bool:
    """
    Validate that date string is in correct ISO format.
    """
    try:
        datetime.strptime(date_str.split('T')[0], "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_date_arguments(
    start_date: Optional[str], 
    end_date: Optional[str]
) -> bool:
    """
    Validate date arguments logic.
    """
    if start_date is None and end_date is None:
        return True
    
    if (start_date is None) != (end_date is None):
        logger.error("Error: Both --start-date and --end-date must be provided together")
        logger.error("For full table scan, omit both date arguments")
        return False
    
    if not validate_date_format(start_date):
        logger.error(f"Invalid start date format: {start_date}")
        logger.error("Expected format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
        return False
    
    if not validate_date_format(end_date):
        logger.error(f"Invalid end date format: {end_date}")
        logger.error("Expected format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
        return False
    
    return True


def main() -> int:
    """
    Main function - orchestrates the entire process.
    """
    args: argparse.Namespace = parse_arguments()
    
    if args.verbose:
        logger.setLevel('DEBUG')
    
    if not validate_date_arguments(args.start_date, args.end_date):
        return 1
    
    try:
        logger.info("="*70)
        logger.info("Cache Failure Classification Report Generator")
        logger.info("="*70)
        logger.info("Timezone: IST (UTC+5:30) - dates are interpreted as IST")
        
        if args.start_date and args.end_date:
            logger.info(f"Mode: Date Range Filter (IST)")
            logger.info(f"Date Range: {args.start_date} to {args.end_date} IST")
        else:
            logger.info(f"Mode: Full Table Scan (no date filter)")
        
        if args.output:
            logger.info(f"Output Path: {args.output}")
        
        if args.no_save:
            logger.info("File Save: Disabled (console output only)")
        
        start_time: datetime = datetime.now()
        
        report: Dict = generate_cache_report(
            start_date=args.start_date,
            end_date=args.end_date,
            save_to_file=not args.no_save,
            output_path=args.output
        )
        
        end_time: datetime = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print_report_summary(report)
        
        logger.info(f"Report generation completed in {duration:.2f} seconds")
        logger.info("="*70)
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\nOperation cancelled by user")
        return 1
    
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
