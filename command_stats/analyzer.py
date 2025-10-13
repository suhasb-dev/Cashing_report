"""
Command Stats Analyzer - Reusing Existing Classification Logic

This module analyzes cache statistics for specific commands by reusing
the proven classification functions from classifier.py. This ensures:
1. Same analysis logic across both systems
2. No code duplication
3. Proven, tested logic
4. Consistent results

Key Features:
- Reuses existing classifier functions for cache miss analysis
- Calculates hit/miss statistics and percentages
- Provides detailed breakdown of cache miss reasons
- Handles latency calculations for cache hits
- Maintains DynamoDB format compatibility
"""

from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# REUSE existing classifier functions - this is the key insight!
from classifier import (
    check_undoable_category,
    check_unblocker_category,
    check_ocr_category,
    check_dynamic_component,
    check_null_llm_output,
    check_failed_step_category,
    check_cache_read_status_none,
    check_no_documents_found_category,
    check_less_similarity_category, 
    check_must_match_filter_category,
    check_failed_after_similar_doc_category
)

# REUSE existing utilities
from utils import get_nested_value, parse_json_string, logger, convert_dynamodb_item_to_dict
from config import SIMILARITY_THRESHOLD

from .models import (
    StepInfo, CacheMissBreakdown, CacheMissBreakdownCategory,
    CacheHitStats, CacheMissStats, CommandStatsReport,
    create_empty_breakdown, calculate_percentage, create_step_info_from_dict
)


# ============================================================================
# MAIN ANALYSIS FUNCTION - Orchestrates the Entire Analysis
# ============================================================================

def analyze_command_statistics(
    steps: List[Dict],
    command: str,
    app_package: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> CommandStatsReport:
    """
    Analyze cache statistics for a specific command.
    
    This is the main function that orchestrates the entire analysis process:
    1. Converts DynamoDB items to StepInfo objects
    2. Separates hits from misses
    3. Analyzes cache miss reasons using existing classifier logic
    4. Calculates statistics and percentages
    5. Builds the final report structure
    
    Args:
        steps: List of DynamoDB items (in DynamoDB JSON format)
        command: The command being analyzed
        app_package: The app package being analyzed
        start_date: Optional start date for the analysis
        end_date: Optional end date for the analysis
        
    Returns:
        CommandStatsReport with complete analysis
    """
    if not steps:
        logger.warning(f"No steps found for command '{command}' and package '{app_package}'")
        return create_empty_report(command, app_package, start_date, end_date)
    
    logger.info(f"Analyzing {len(steps)} steps for command '{command}'")
    
    # Convert DynamoDB items to StepInfo objects
    step_infos = []
    for step_dynamodb in steps:
        try:
            # Convert DynamoDB format to regular dict
            step_dict = convert_dynamodb_item_to_dict(step_dynamodb)
            step_info = create_step_info_from_dict(step_dict)
            step_infos.append(step_info)
        except Exception as e:
            logger.warning(f"Failed to convert step: {e}")
            continue
    
    logger.info(f"Successfully converted {len(step_infos)} steps")
    
    # Separate hits from misses
    hit_steps, miss_steps = separate_hits_and_misses(step_infos)
    
    # Analyze cache hits
    hit_stats = analyze_cache_hits(hit_steps)
    
    # Analyze cache misses with detailed breakdown
    miss_stats = analyze_cache_misses(miss_steps, steps)  # Pass original DynamoDB format for classifier
    
    # Build final report
    report = build_command_stats_report(
        command=command,
        app_package=app_package,
        start_date=start_date,
        end_date=end_date,
        total_steps=len(step_infos),
        hit_stats=hit_stats,
        miss_stats=miss_stats
    )
    
    logger.info(f"Analysis complete: {hit_stats['count']} hits, {miss_stats['count']} misses")
    
    return report


# ============================================================================
# CACHE HIT/MISS SEPARATION
# ============================================================================

def separate_hits_and_misses(step_infos: List[StepInfo]) -> Tuple[List[StepInfo], List[StepInfo]]:
    """
    Separate steps into cache hits and cache misses.
    
    Cache hits: cache_read_status = 1 (HIT_WITH_COMPONENT)
    Cache misses: cache_read_status = 0, -1, or None
    
    Args:
        step_infos: List of StepInfo objects
        
    Returns:
        Tuple of (hit_steps, miss_steps)
    """
    hit_steps = []
    miss_steps = []
    
    for step_info in step_infos:
        if step_info.cache_read_status == 1:
            hit_steps.append(step_info)
        else:
            miss_steps.append(step_info)
    
    logger.debug(f"Separated steps: {len(hit_steps)} hits, {len(miss_steps)} misses")
    
    return hit_steps, miss_steps


# ============================================================================
# CACHE HIT ANALYSIS
# ============================================================================

def analyze_cache_hits(hit_steps: List[StepInfo]) -> CacheHitStats:
    """
    Analyze cache hit statistics.
    
    Calculates count, percentage, average latency, and provides list of hit steps.
    
    Args:
        hit_steps: List of steps that had cache hits
        
    Returns:
        CacheHitStats with hit analysis
    """
    count = len(hit_steps)
    
    # Calculate average latency for hits
    latencies = [step.cache_read_latency for step in hit_steps if step.cache_read_latency is not None]
    average_latency = sum(latencies) / len(latencies) if latencies else 0.0
    
    return CacheHitStats(
        count=count,
        percentage=calculate_percentage(count, count + len(hit_steps)),  # Will be updated with total
        average_latency=round(average_latency, 6),  # Round to 6 decimal places
        steps_list=hit_steps
    )


# ============================================================================
# CACHE MISS ANALYSIS - REUSING EXISTING CLASSIFIER LOGIC
# ============================================================================

def analyze_cache_misses(miss_steps: List[StepInfo], original_dynamodb_steps: List[Dict]) -> CacheMissStats:
    """
    Analyze cache miss statistics with detailed breakdown.
    
    This function reuses the existing classifier logic to determine
    the specific reasons for cache misses. We need to work with the
    original DynamoDB format because the classifier functions expect that format.
    
    Args:
        miss_steps: List of StepInfo objects that had cache misses
        original_dynamodb_steps: Original DynamoDB items (for classifier functions)
        
    Returns:
        CacheMissStats with detailed miss breakdown
    """
    # Create mapping from step_id to DynamoDB format for classifier functions
    dynamodb_by_step_id = {get_nested_value(step, 'step_id', 'S'): step for step in original_dynamodb_steps}
    
    # Initialize breakdown categories
    breakdown = create_empty_breakdown()
    
    # Categorize each miss step
    for step_info in miss_steps:
        # Get the original DynamoDB format for this step
        dynamodb_step = dynamodb_by_step_id.get(step_info.step_id)
        
        if not dynamodb_step:
            logger.warning(f"Could not find DynamoDB format for step {step_info.step_id}")
            continue
        
        # Determine miss reason using existing classifier logic
        miss_reason = analyze_cache_miss_reason(dynamodb_step)
        
        # Add to appropriate category
        add_step_to_breakdown_category(breakdown, miss_reason, step_info)
    
    # Calculate final statistics
    total_misses = len(miss_steps)
    
    # Update percentages for each category
    for category_name, category_data in breakdown.items():
        category_data['percentage'] = calculate_percentage(category_data['count'], total_misses)
    
    return CacheMissStats(
        count=total_misses,
        percentage=calculate_percentage(total_misses, total_misses),  # Will be updated with total
        breakdown=breakdown
    )


def analyze_cache_miss_reason(step_dynamodb_format: Dict) -> str:
    """
    Determine specific cache miss reason using EXISTING classifier logic.
    
    This reuses your proven analysis functions in the SAME PRIORITY ORDER
    as the existing classifier. The step must be in DynamoDB format because
    the existing functions expect that format.
    
    Args:
        step_dynamodb_format: DynamoDB item in original format
        
    Returns:
        String indicating the miss reason category (matches existing classifier categories)
    """
    # Use existing classification logic in PRIORITY ORDER - no need to rewrite!
    # Priority 0: Undoable
    if check_undoable_category(step_dynamodb_format):
        return "undoable"
    
    # Priority 1: Unblocker Call
    if check_unblocker_category(step_dynamodb_format):
        return "unblocker_call"
    
    # Priority 2: OCR Steps
    if check_ocr_category(step_dynamodb_format):
        return "ocr_steps"
    
    # Priority 2.5: Dynamic Component
    if check_dynamic_component(step_dynamodb_format):
        return "dynamic_step"
    
    # Priority 3: Failed Step
    if check_failed_step_category(step_dynamodb_format):
        return "failed_step"
    
    # Priority 3.5: Null LLM Output
    if check_null_llm_output(step_dynamodb_format):
        return "null_llm_output"
    
    # Priority 4: Cache Read Status None
    if check_cache_read_status_none(step_dynamodb_format):
        return "cache_read_status_none"
    
    # Priority 5: No Cache Documents Found
    if check_no_documents_found_category(step_dynamodb_format):
        return "no_cache_documents_found"
    
    # Priority 6: Less Similarity Threshold
    if check_less_similarity_category(step_dynamodb_format):
        return "less_similarity_threshold"
    
    # Priority 7: Failed At Must Match Filter
    if check_must_match_filter_category(step_dynamodb_format):
        return "failed_at_cand_nos_after_must_match_filter"
    
    # Priority 8: Failed After Similar Document
    if check_failed_after_similar_doc_category(step_dynamodb_format):
        return "failed_after_similar_document_found_with_threshold_after_must_match_filter"
    
    # Priority 9: Unclassified (catch-all)
    return "unclassified"


def add_step_to_breakdown_category(
    breakdown: CacheMissBreakdown,
    miss_reason: str,
    step_info: StepInfo
) -> None:
    """
    Add a step to the appropriate breakdown category.
    
    Args:
        breakdown: The breakdown structure to update
        miss_reason: The reason for the cache miss (matches existing classifier categories)
        step_info: The step information to add
    """
    # Direct mapping - miss_reason already matches breakdown category names
    # This ensures consistency with existing classifier categories
    if miss_reason not in breakdown:
        logger.warning(f"Unknown miss reason: {miss_reason}, using 'unclassified'")
        miss_reason = "unclassified"
    
    category = breakdown[miss_reason]
    
    # Update category
    category['count'] += 1
    category['steps_list'].append(step_info)
    
    # Set reason description if not already set
    if not category['reason']:
        category['reason'] = get_miss_reason_description(miss_reason)


def get_miss_reason_description(miss_reason: str) -> str:
    """
    Get human-readable description for miss reason.
    
    Args:
        miss_reason: The miss reason code (matches existing classifier categories)
        
    Returns:
        Human-readable description
    """
    descriptions = {
        "undoable": "Step was undoable, no cache needed",
        "unblocker_call": "Unblocker call made, no cache needed",
        "ocr_steps": "OCR was used for step execution, no cache needed",
        "dynamic_step": "Dynamic component resolution used, no cache needed",
        "null_llm_output": "No LLM output generated, no cache needed",
        "failed_step": "Step execution failed, no cache needed",
        "cache_read_status_none": "Cache was never attempted (dynamic resolution)",
        "no_cache_documents_found": "Vector DB found no similar screenshots (cache_read_status=-1)",
        "less_similarity_threshold": "Found similar documents but similarity < 0.75",
        "failed_at_cand_nos_after_must_match_filter": "Component selection failed at must_match_filter stage",
        "failed_after_similar_document_found_with_threshold_after_must_match_filter": "Failed after finding similar document with good similarity",
        "unclassified": "Unclassified cache miss reason"
    }
    
    return descriptions.get(miss_reason, "Unknown cache miss reason")


# ============================================================================
# REPORT BUILDING
# ============================================================================

def build_command_stats_report(
    command: str,
    app_package: str,
    start_date: Optional[str],
    end_date: Optional[str],
    total_steps: int,
    hit_stats: CacheHitStats,
    miss_stats: CacheMissStats
) -> CommandStatsReport:
    """
    Build the final command statistics report.
    
    Args:
        command: The command being analyzed
        app_package: The app package being analyzed
        start_date: Optional start date
        end_date: Optional end date
        total_steps: Total number of steps analyzed
        hit_stats: Cache hit statistics
        miss_stats: Cache miss statistics
        
    Returns:
        Complete CommandStatsReport
    """
    # Update percentages with correct totals
    hit_stats['percentage'] = calculate_percentage(hit_stats['count'], total_steps)
    miss_stats['percentage'] = calculate_percentage(miss_stats['count'], total_steps)
    
    # Build date range info
    date_range = {
        "start": start_date or "2025-09-28",  # Default start date
        "end": end_date or "all_time"
    }
    
    return CommandStatsReport(
        command=command,
        app_package=app_package,
        date_range=date_range,
        total_step_runs=total_steps,
        cache_hit=hit_stats,
        cache_miss=miss_stats
    )


def create_empty_report(
    command: str,
    app_package: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> CommandStatsReport:
    """
    Create an empty report when no steps are found.
    
    Args:
        command: The command being analyzed
        app_package: The app package being analyzed
        start_date: Optional start date
        end_date: Optional end date
        
    Returns:
        Empty CommandStatsReport
    """
    empty_hit_stats = CacheHitStats(
        count=0,
        percentage="0.00%",
        average_latency=0.0,
        steps_list=[]
    )
    
    empty_miss_stats = CacheMissStats(
        count=0,
        percentage="0.00%",
        breakdown=create_empty_breakdown()
    )
    
    return build_command_stats_report(
        command=command,
        app_package=app_package,
        start_date=start_date,
        end_date=end_date,
        total_steps=0,
        hit_stats=empty_hit_stats,
        miss_stats=empty_miss_stats
    )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_analysis_inputs(steps: List[Dict], command: str, app_package: str) -> None:
    """
    Validate inputs for analysis.
    
    Args:
        steps: List of DynamoDB items
        command: Command string
        app_package: App package string
        
    Raises:
        ValueError: If inputs are invalid
    """
    if not isinstance(steps, list):
        raise ValueError("Steps must be a list")
    
    if not command or not command.strip():
        raise ValueError("Command cannot be empty")
    
    if not app_package or not app_package.strip():
        raise ValueError("App package cannot be empty")


def get_analysis_summary(report: CommandStatsReport) -> Dict[str, str]:
    """
    Get a summary of the analysis results.
    
    Args:
        report: The complete analysis report
        
    Returns:
        Dict with summary information
    """
    return {
        "command": report['command'],
        "app_package": report['app_package'],
        "total_steps": str(report['total_step_runs']),
        "cache_hit_percentage": report['cache_hit']['percentage'],
        "cache_miss_percentage": report['cache_miss']['percentage'],
        "average_latency": f"{report['cache_hit']['average_latency']:.6f}s"
    }
