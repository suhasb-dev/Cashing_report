"""
Report Generator with Unclassified Step Analysis

This module orchestrates the entire report generation process with
comprehensive diagnostic capabilities for debugging classification issues.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
from pathlib import Path

from dynamodb_scanner import scan_test_steps_with_pagination
from classifier import classify_step
from utils import convert_dynamodb_item_to_dict, is_within_date_range, logger
from config import DEFAULT_OUTPUT_DIR, CACHE_READ_STATUS_FILTER


# ============================================================================
# MAIN REPORT GENERATION
# ============================================================================

def generate_cache_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_to_file: bool = True,
    output_path: Optional[str] = None
) -> Dict:
    """
    Generate comprehensive cache failure classification report with diagnostics.
    
    Process:
    1. Scan all steps from DynamoDB (with pagination)
    2. Filter by date range and criteria
    3. Classify each step into categories
    4. Track unclassified steps with diagnostics
    5. Calculate statistics (counts, percentages)
    6. Build report structure
    7. Save report and diagnostic files
    
    Args:
        start_date: Start date in IST (optional)
        end_date: End date in IST (optional)
        save_to_file: Whether to save report to JSON file
        output_path: Custom output file path (optional)
        
    Returns:
        Dict containing the complete report
    """
    if start_date and end_date:
        logger.info(f"Starting filtered report: {start_date} to {end_date}")
    else:
        logger.info("Starting full table scan (no date filter)")
    
    categorized_steps: Dict[str, List[Dict]] = defaultdict(list)
    unclassified_diagnostics: List[Dict] = []
    total_rows_analysed: int = 0
    
    # Scan and process steps
    for item in scan_test_steps_with_pagination():
        step_dict: Dict = convert_dynamodb_item_to_dict(item)
        
        if not should_analyze_step(step_dict, start_date, end_date):
            continue
        
        total_rows_analysed += 1
        
        # Classify step and get diagnostics for unclassified
        categories, diagnosis = classify_step(item)
        
        # If unclassified, log detailed diagnosis
        if diagnosis:
            unclassified_diagnostics.append(diagnosis)
            
            # Log to console
            logger.warning("="*70)
            logger.warning(f"UNCLASSIFIED STEP: {diagnosis['step_id']}")
            logger.warning(f"Step Classification: {diagnosis['step_classification']}")
            logger.warning(f"Cache Read Status: {diagnosis['cache_read_status']}")
            logger.warning(f"Test Step Status: {diagnosis['test_step_status']}")
            logger.warning(f"Has Cache Query Results: {diagnosis['has_cache_query_results']}")
            logger.warning(f"Has OCR Output: {diagnosis['has_ocr_output']}")
            logger.warning(f"Is Blocker: {diagnosis['is_blocker']}")
            logger.warning("")
            logger.warning("Category Check Results:")
            for category_name, check_result in diagnosis['category_checks'].items():
                status = "✅ PASSED" if check_result['passed'] else "❌ FAILED"
                logger.warning(f"  {category_name}: {status}")
                logger.warning(f"    Reason: {check_result['reason']}")
            logger.warning("="*70)
        
        # Add step to categories
        for category in categories:
            categorized_steps[category].append(step_dict)
        
        # Log progress
        if total_rows_analysed % 100 == 0:
            logger.info(f"Processed {total_rows_analysed} steps...")
    
    # Summary of unclassified steps
    unclassified_count = len(unclassified_diagnostics)
    if unclassified_count > 0:
        logger.warning("")
        logger.warning("="*70)
        logger.warning(f"UNCLASSIFIED SUMMARY: {unclassified_count} steps ({unclassified_count/total_rows_analysed*100:.2f}%)")
        logger.warning("="*70)
        
        # Analyze common patterns
        analyze_unclassified_patterns(unclassified_diagnostics)
    
    logger.info(f"Analysis complete. Total steps: {total_rows_analysed}")
    
    # Build report
    report: Dict = build_report_structure(
        total_rows=total_rows_analysed,
        categorized_steps=categorized_steps,
        unclassified_diagnostics=unclassified_diagnostics
    )
    
    # Save to file
    if save_to_file:
        file_path: str = save_report_to_file(report, output_path, start_date or "all", end_date or "all")
        logger.info(f"Report saved to: {file_path}")
        
        # Save separate diagnostic file for unclassified
        if unclassified_count > 0:
            diagnostic_path = file_path.replace('.json', '_unclassified_diagnostics.json')
            with open(diagnostic_path, 'w') as f:
                json.dump(unclassified_diagnostics, f, indent=2)
            logger.info(f"Unclassified diagnostics saved to: {diagnostic_path}")
    
    return report


# ============================================================================
# PATTERN ANALYSIS
# ============================================================================

def analyze_unclassified_patterns(diagnostics: List[Dict]) -> None:
    """
    Analyze patterns in unclassified steps to find common characteristics.
    
    This helps identify missing classification categories or logic bugs.
    """
    logger.warning("\nPattern Analysis:")
    logger.warning("-" * 70)
    
    # Group by various attributes
    by_cache_status = defaultdict(int)
    by_test_status = defaultdict(int)
    has_query_results_count = 0
    has_ocr_count = 0
    is_blocker_count = 0
    
    for diag in diagnostics:
        by_cache_status[diag['cache_read_status']] += 1
        by_test_status[diag['test_step_status']] += 1
        if diag['has_cache_query_results']:
            has_query_results_count += 1
        if diag['has_ocr_output']:
            has_ocr_count += 1
        if diag['is_blocker']:
            is_blocker_count += 1
    
    logger.warning(f"By cache_read_status:")
    for status, count in sorted(by_cache_status.items()):
        logger.warning(f"  {status}: {count} steps")
    
    logger.warning(f"\nBy test_step_status:")
    for status, count in sorted(by_test_status.items()):
        logger.warning(f"  {status}: {count} steps")
    
    logger.warning(f"\nOther characteristics:")
    logger.warning(f"  Has cache_query_results: {has_query_results_count}")
    logger.warning(f"  Has OCR output: {has_ocr_count}")
    logger.warning(f"  Is blocker: {is_blocker_count}")


# ============================================================================
# FILTERING LOGIC
# ============================================================================

def should_analyze_step(
    step: Dict, 
    start_date: Optional[str],
    end_date: Optional[str]
) -> bool:
    """
    Determine if step should be included in analysis.
    
    Filters:
    1. step_classification must be 'TAP' or 'TEXT'
    2. cache_read_status must be -1, 0, or missing
    3. created_at must be within date range (if dates provided)
    """
    # Filter 1: Step classification
    step_classification: Optional[str] = step.get('step_classification')
    if step_classification not in ['TAP', 'TEXT']:
        return False
    
    # Filter 2: Cache read status
    cache_read_status: Optional[int] = step.get('cache_read_status')
    if cache_read_status is not None and cache_read_status not in CACHE_READ_STATUS_FILTER:
        return False
    
    # Filter 3: Date range
    if start_date and end_date:
        created_at: Optional[str] = step.get('created_at')
        if created_at:
            if not is_within_date_range(created_at, start_date, end_date):
                return False
    
    return True


# ============================================================================
# REPORT STRUCTURE BUILDING
# ============================================================================

def build_report_structure(
    total_rows: int,
    categorized_steps: Dict[str, List[Dict]],
    unclassified_diagnostics: List[Dict]
) -> Dict:
    """
    Build the final report structure with statistics.
    """
    report_data: Dict = {}
    
    # Define all categories
    category_names: List[str] = [
        "ocr_steps",
        "unblocker_call",
        "failed_step",
        "no_cache_documents_found",
        "less_similarity_threshold",
        "cache_read_status_none",
        "failed_at_cand_nos_after_must_match_filter",
        "failed_after_similar_document_found_with_threshold_after_must_match_filter",
        "unclassified"
    ]
    
    # Build report for each category
    for category in category_names:
        steps: List[Dict] = categorized_steps.get(category, [])
        count: int = len(steps)
        percentage: float = (count / total_rows * 100) if total_rows > 0 else 0.0
        
        report_data[category] = {
            "percentage": f"{percentage:.2f}%",
            "document_count": count,
            "steps_list": steps
        }
    
    return {
        "total_rows_analysed": total_rows,
        "unclassified_count": len(unclassified_diagnostics),
        "unclassified_percentage": f"{(len(unclassified_diagnostics)/total_rows*100):.2f}%" if total_rows > 0 else "0.00%",
        "report": report_data
    }


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def save_report_to_file(
    report: Dict,
    output_path: Optional[str],
    start_date: str,
    end_date: str
) -> str:
    """Save report to JSON file."""
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not output_path:
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if start_date == "all" or end_date == "all":
            filename: str = f"cache_report_full_scan_{timestamp}.json"
        else:
            start_simple: str = start_date.split('T')[0]
            end_simple: str = end_date.split('T')[0]
            filename: str = f"cache_report_{start_simple}_to_{end_simple}_{timestamp}.json"
        
        output_path = str(output_dir / filename)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Report written to: {output_path}")
    
    return output_path


def print_report_summary(report: Dict) -> None:
    """Print human-readable summary of report to console."""
    print("\n" + "="*70)
    print("CACHE FAILURE CLASSIFICATION REPORT - SUMMARY")
    print("="*70)
    print(f"Total Rows Analysed: {report['total_rows_analysed']}")
    print("\nCategory Breakdown:")
    print("-"*70)
    
    for category_name, category_data in report['report'].items():
        count: int = category_data['document_count']
        percentage: str = category_data['percentage']
        
        display_name: str = category_name.replace('_', ' ').title()
        
        print(f"{display_name}:")
        print(f"  Count: {count:>5}")
        print(f"  Percentage: {percentage:>8}")
        print()
    
    print("="*70)
