"""
Command Stats Reporter - JSON Report Generation

This module handles generating and saving the final JSON reports for
command-level cache statistics. It follows the same patterns as the
existing report_generator.py but focuses on command-specific analysis.

Key Features:
- JSON report generation with proper formatting
- File saving with timestamped filenames
- Console output for quick viewing
- Report validation and error handling
- Follows existing report generation patterns
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from utils import logger
from config import DEFAULT_OUTPUT_DIR

from .models import CommandStatsReport, validate_report_data


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_command_stats_report(
    report: CommandStatsReport,
    save_to_file: bool = True,
    output_path: Optional[str] = None,
    print_to_console: bool = True
) -> str:
    """
    Generate and save command statistics report.
    
    This function handles both file saving and console output,
    following the same patterns as the existing report_generator.py.
    
    Args:
        report: Complete CommandStatsReport to save
        save_to_file: Whether to save report to JSON file
        output_path: Custom output file path (optional)
        print_to_console: Whether to print summary to console
        
    Returns:
        Path to saved file (if saved) or "console_only"
        
    Example:
        >>> report = analyze_command_statistics(steps, "Tap on Submit Button", "com.example.app")
        >>> file_path = generate_command_stats_report(report)
        >>> print(f"Report saved to: {file_path}")
    """
    # Validate report data
    if not validate_report_data(report):
        logger.warning("Report data validation failed, but continuing with generation")
    
    # Print to console if requested
    if print_to_console:
        print_command_stats_summary(report)
    
    # Save to file if requested
    if save_to_file:
        file_path = save_report_to_file(report, output_path)
        logger.info(f"Command stats report saved to: {file_path}")
        return file_path
    
    return "console_only"


def save_report_to_file(
    report: CommandStatsReport,
    output_path: Optional[str] = None
) -> str:
    """
    Save command statistics report to JSON file.
    
    This follows the same file naming and directory patterns as
    the existing report_generator.py.
    
    Args:
        report: CommandStatsReport to save
        output_path: Custom output file path (optional)
        
    Returns:
        Path to the saved file
    """
    # Create output directory
    output_dir = Path(DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename if not provided
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create descriptive filename
        command_safe = report['command'].replace(' ', '_').replace('/', '_')[:50]
        package_safe = report['app_package'].replace('.', '_').replace('/', '_')[:30]
        
        filename = f"command_stats_{package_safe}_{command_safe}_{timestamp}.json"
        output_path = str(output_dir / filename)
    
    # Convert report to JSON-serializable format
    json_report = convert_report_to_json_serializable(report)
    
    # Save to file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Report written to: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to save report to {output_path}: {e}")
        raise


def convert_report_to_json_serializable(report: CommandStatsReport) -> Dict:
    """
    Convert CommandStatsReport to JSON-serializable format.
    
    This handles any non-JSON-serializable objects in the report,
    such as StepInfo dataclass objects.
    
    Args:
        report: CommandStatsReport to convert
        
    Returns:
        JSON-serializable dictionary
    """
    # Convert StepInfo objects to dictionaries
    json_report = dict(report)
    
    # Convert hit steps
    if 'cache_hit' in json_report and 'steps_list' in json_report['cache_hit']:
        json_report['cache_hit']['steps_list'] = [
            step_info.__dict__ for step_info in json_report['cache_hit']['steps_list']
        ]
    
    # Convert miss breakdown steps
    if 'cache_miss' in json_report and 'breakdown' in json_report['cache_miss']:
        breakdown = json_report['cache_miss']['breakdown']
        for category_name, category_data in breakdown.items():
            if 'steps_list' in category_data:
                category_data['steps_list'] = [
                    step_info.__dict__ for step_info in category_data['steps_list']
                ]
    
    return json_report


# ============================================================================
# CONSOLE OUTPUT
# ============================================================================

def print_command_stats_summary(report: CommandStatsReport) -> None:
    """
    Print human-readable summary of command statistics to console.
    
    This provides a quick overview of the analysis results,
    following the same format as the existing report_generator.py.
    
    Args:
        report: CommandStatsReport to summarize
    """
    print("\n" + "="*80)
    print("COMMAND-LEVEL CACHE STATISTICS REPORT")
    print("="*80)
    
    # Basic information
    print(f"Command: {report['command']}")
    print(f"App Package: {report['app_package']}")
    print(f"Date Range: {report['date_range']['start']} to {report['date_range']['end']}")
    print(f"Total Step Runs: {report['total_step_runs']}")
    
    if report['total_step_runs'] == 0:
        print("\n⚠️  No steps found for this command and package combination.")
        print("="*80)
        return
    
    print("\nCache Performance Summary:")
    print("-"*80)
    
    # Cache hits
    hit_stats = report['cache_hit']
    print(f"Cache Hits:")
    print(f"  Count: {hit_stats['count']:>6}")
    print(f"  Percentage: {hit_stats['percentage']:>8}")
    print(f"  Average Latency: {hit_stats['average_latency']:.6f}s")
    
    # Cache misses
    miss_stats = report['cache_miss']
    print(f"\nCache Misses:")
    print(f"  Count: {miss_stats['count']:>6}")
    print(f"  Percentage: {miss_stats['percentage']:>8}")
    
    # Detailed miss breakdown
    if miss_stats['count'] > 0:
        print(f"\nCache Miss Breakdown (Detailed):")
        print("-"*80)
        
        breakdown = miss_stats['breakdown']
        
        # Print categories in priority order (matching existing classifier)
        priority_order = [
            "undoable",
            "unblocker_call", 
            "ocr_steps",
            "dynamic_step",
            "null_llm_output",
            "failed_step",
            "cache_read_status_none",
            "no_cache_documents_found",
            "less_similarity_threshold",
            "failed_at_cand_nos_after_must_match_filter",
            "failed_after_similar_document_found_with_threshold_after_must_match_filter",
            "unclassified"
        ]
        
        for category_name in priority_order:
            if category_name in breakdown:
                category_data = breakdown[category_name]
                if category_data['count'] > 0:
                    display_name = category_name.replace('_', ' ').title()
                    print(f"{display_name}:")
                    print(f"  Count: {category_data['count']:>6}")
                    print(f"  Percentage: {category_data['percentage']:>8}")
                    print(f"  Reason: {category_data['reason']}")
                    print()
    
    print("="*80)
    print("Note: Percentages are calculated from total step runs")
    print("="*80)


# ============================================================================
# REPORT VALIDATION AND UTILITIES
# ============================================================================

def validate_report_consistency(report: CommandStatsReport) -> bool:
    """
    Validate that the report data is consistent and makes sense.
    
    This performs additional validation beyond the basic data structure
    validation to ensure the report is logically consistent.
    
    Args:
        report: CommandStatsReport to validate
        
    Returns:
        True if report is consistent, False otherwise
    """
    try:
        total = report['total_step_runs']
        hit_count = report['cache_hit']['count']
        miss_count = report['cache_miss']['count']
        
        # Check that hit + miss = total
        if hit_count + miss_count != total:
            logger.error(f"Hit count ({hit_count}) + Miss count ({miss_count}) != Total ({total})")
            return False
        
        # Check that breakdown counts add up to miss count
        breakdown = report['cache_miss']['breakdown']
        breakdown_total = sum(
            category['count'] 
            for category in breakdown.values()
        )
        
        if breakdown_total != miss_count:
            logger.error(f"Breakdown total ({breakdown_total}) != Miss count ({miss_count})")
            return False
        
        # Check that percentages are reasonable
        hit_percentage = float(report['cache_hit']['percentage'].rstrip('%'))
        miss_percentage = float(report['cache_miss']['percentage'].rstrip('%'))
        
        if abs(hit_percentage + miss_percentage - 100.0) > 0.01:  # Allow small floating point errors
            logger.error(f"Hit percentage ({hit_percentage}%) + Miss percentage ({miss_percentage}%) != 100%")
            return False
        
        logger.debug("Report validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Report validation failed: {e}")
        return False


def get_report_statistics(report: CommandStatsReport) -> Dict[str, any]:
    """
    Get key statistics from the report for quick analysis.
    
    Args:
        report: CommandStatsReport to analyze
        
    Returns:
        Dict with key statistics
    """
    return {
        "total_steps": report['total_step_runs'],
        "hit_count": report['cache_hit']['count'],
        "miss_count": report['cache_miss']['count'],
        "hit_percentage": report['cache_hit']['percentage'],
        "miss_percentage": report['cache_miss']['percentage'],
        "average_latency": report['cache_hit']['average_latency'],
        "command": report['command'],
        "app_package": report['app_package']
    }


# ============================================================================
# BATCH REPORTING
# ============================================================================

def generate_multiple_command_reports(
    reports: list[CommandStatsReport],
    output_dir: Optional[str] = None
) -> list[str]:
    """
    Generate multiple command reports in batch.
    
    This is useful for analyzing multiple commands at once.
    
    Args:
        reports: List of CommandStatsReport objects
        output_dir: Custom output directory (optional)
        
    Returns:
        List of file paths for generated reports
    """
    if output_dir:
        global DEFAULT_OUTPUT_DIR
        original_dir = DEFAULT_OUTPUT_DIR
        DEFAULT_OUTPUT_DIR = output_dir
    
    file_paths = []
    
    try:
        for i, report in enumerate(reports):
            logger.info(f"Generating report {i+1}/{len(reports)}: {report['command']}")
            
            file_path = generate_command_stats_report(
                report=report,
                save_to_file=True,
                print_to_console=False  # Don't spam console with multiple reports
            )
            
            file_paths.append(file_path)
    
    finally:
        # Restore original output directory
        if output_dir:
            DEFAULT_OUTPUT_DIR = original_dir
    
    logger.info(f"Generated {len(file_paths)} command statistics reports")
    return file_paths


# ============================================================================
# DEVELOPMENT AND DEBUGGING HELPERS
# ============================================================================

def print_report_debug_info(report: CommandStatsReport) -> None:
    """
    Print detailed debug information about the report.
    
    This is useful for development and debugging to understand
    the structure and content of the report.
    
    Args:
        report: CommandStatsReport to debug
    """
    print("\n" + "="*80)
    print("COMMAND STATS REPORT DEBUG INFO")
    print("="*80)
    
    print(f"Report Type: {type(report)}")
    print(f"Report Keys: {list(report.keys())}")
    
    # Hit stats debug
    hit_stats = report['cache_hit']
    print(f"\nHit Stats:")
    print(f"  Type: {type(hit_stats)}")
    print(f"  Keys: {list(hit_stats.keys())}")
    print(f"  Steps List Length: {len(hit_stats['steps_list'])}")
    
    # Miss stats debug
    miss_stats = report['cache_miss']
    print(f"\nMiss Stats:")
    print(f"  Type: {type(miss_stats)}")
    print(f"  Keys: {list(miss_stats.keys())}")
    
    breakdown = miss_stats['breakdown']
    print(f"  Breakdown Categories: {list(breakdown.keys())}")
    
    for category_name, category_data in breakdown.items():
        print(f"    {category_name}: {category_data['count']} steps")
    
    print("="*80)