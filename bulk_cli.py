"""
Bulk Analysis CLI - Single-Pass Analysis for All Commands

New entry point for bulk analysis that generates both:
1. Individual command files
2. Command+Package files

All from a single DynamoDB scan.
"""

import argparse
import sys
from datetime import datetime
from typing import Optional

from bulk_analyzer import run_bulk_analysis
from utils import logger


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for bulk analysis"""
    parser = argparse.ArgumentParser(
        description='Bulk command analysis - Single-pass DynamoDB scan for all commands',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate both individual and command+package files
  python bulk_cli.py
  
  # Generate only individual command files
  python bulk_cli.py --individual-only
  
  # Generate only command+package files  
  python bulk_cli.py --command-package-only
  
  # Custom output directory
  python bulk_cli.py --output-dir "./bulk_reports"
  
  # With date filtering
  python bulk_cli.py --start-date "2025-10-01" --end-date "2025-10-10"

This will generate:
- Individual command files: command_stats_Type_Snacks_in_search_bar_20251010_184045.json
- Command+Package files: command_stats_in_swiggy_android_instamart_Type_"Snacks"_in_search_bar_20251010_184045.json
- Summary file: bulk_analysis_summary.json
        """
    )
    
    # Analysis type options
    parser.add_argument(
        '--individual-only',
        action='store_true',
        help='Generate only individual command files (across all packages)'
    )
    
    parser.add_argument(
        '--command-package-only',
        action='store_true',
        help='Generate only command+package files (existing approach)'
    )
    
    # Date filtering
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date filter (YYYY-MM-DD format)'
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date filter (YYYY-MM-DD format)'
    )
    
    # Output options
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory for reports (default: ./cache_reports)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of steps to process before generating files (default: 1000)'
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point for bulk analysis"""
    try:
        args = parse_arguments()
        
        # Validate arguments
        if args.individual_only and args.command_package_only:
            logger.error("Cannot specify both --individual-only and --command-package-only")
            return 1
        
        # Determine what to generate
        generate_individual = not args.command_package_only
        generate_command_package = not args.individual_only
        
        logger.info("Starting bulk command analysis...")
        logger.info(f"Individual command files: {generate_individual}")
        logger.info(f"Command+Package files: {generate_command_package}")
        
        if args.start_date and args.end_date:
            logger.info(f"Date range: {args.start_date} to {args.end_date}")
        
        # Run bulk analysis
        summary = run_bulk_analysis(
            start_date=args.start_date,
            end_date=args.end_date,
            output_dir=args.output_dir,
            generate_individual=generate_individual,
            generate_command_package=generate_command_package,
            batch_size=args.batch_size
        )
        
        # Print summary
        print("\n" + "="*60)
        print("BULK ANALYSIS COMPLETE")
        print("="*60)
        print(f"Total steps processed: {summary['bulk_analysis_summary']['total_steps_processed']}")
        print(f"Unique commands found: {summary['bulk_analysis_summary']['unique_commands_found']}")
        print(f"Command+Package combinations: {summary['bulk_analysis_summary']['command_package_combinations']}")
        print(f"Individual command files: {summary['bulk_analysis_summary']['individual_command_files_generated']}")
        print(f"Command+Package files: {summary['bulk_analysis_summary']['command_package_files_generated']}")
        print(f"Duration: {summary['bulk_analysis_summary']['duration_seconds']:.2f} seconds")
        print("="*60)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Analysis interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Bulk analysis failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
