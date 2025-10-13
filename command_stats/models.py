"""
Data Models for Command-Level Cache Statistics

This module extends the existing models.py patterns while adding
command-specific data structures. We reuse existing enums and
add new ones specific to command analysis.

Key Design Principles:
- Follow existing codebase patterns and naming conventions
- Reuse existing type definitions where possible
- Maintain consistency with existing models.py structure
- Provide clear documentation for each data structure
"""

from enum import Enum
from typing import TypedDict, List, Optional, Dict, Any
from dataclasses import dataclass

# Import existing models to reuse patterns and maintain consistency
from models import CacheQueryResult, ComponentSelectionReport


# ============================================================================
# ENUMS - Type-Safe Constants (Following Existing Pattern)
# ============================================================================

class CacheReadStatus(Enum):
    """
    Cache read status values from DynamoDB.
    
    These match the exact values we find in the cache_read_status field:
    - HIT_WITH_COMPONENT = 1: Cache worked perfectly, component found and used
    - HIT_WITHOUT_COMPONENT = 0: Cache found something but couldn't extract component
    - MISS = -1: No similar documents found in vector database
    - None/Missing: Cache was never attempted (dynamic component resolution)
    
    This enum provides type safety and clear documentation of what each value means.
    """
    HIT_WITH_COMPONENT = 1      # ✅ Cache success - component found and used
    HIT_WITHOUT_COMPONENT = 0   # ❌ Cache partial - found but couldn't use
    MISS = -1                   # ❌ Cache miss - no similar documents found


# ============================================================================
# DATA STRUCTURES - Following Existing Patterns
# ============================================================================

@dataclass
class StepInfo:
    """
    Complete information about a single test step.
    
    This contains ALL the fields from DynamoDB for a step that matches
    our command and package criteria. We use a dataclass for clean
    data organization and type safety.
    
    Following the existing codebase pattern of including all available
    fields from DynamoDB, with Optional types for fields that might be missing.
    """
    # Core identification fields
    step_id: str
    command: str
    app_package: str
    thread_code: str
    
    # Timing information
    created_at: str  # ISO timestamp from DynamoDB
    
    # Cache performance data
    cache_read_status: Optional[int]  # 1, 0, -1, or None
    cache_read_latency: Optional[float]  # Time taken for cache lookup in seconds
    
    # Step execution data
    step_classification: str  # TAP, TEXT, etc.
    test_step_status: str  # SUCCESS, FAILED, etc.
    
    # Additional fields from DynamoDB (might be None if not present)
    cache_query_results: Optional[str]  # JSON string with cache results
    ocr_output: Optional[str]  # OCR output if available
    llm_output: Optional[str]  # LLM output if available
    is_blocker: Optional[bool]  # Whether this step is a blocker
    ensemble_used: Optional[bool]  # Whether ensemble was used


# ============================================================================
# STATISTICS STRUCTURES - Command-Specific Analysis
# ============================================================================

class CacheHitStats(TypedDict):
    """
    Statistics for cache hits (when cache_read_status = 1).
    
    This tells us how well cache performed when it worked successfully.
    Includes count, percentage, average latency, and list of all steps that hit cache.
    """
    count: int                    # Number of successful cache hits
    percentage: str               # Percentage as string (e.g., "80.00%")
    average_latency: float        # Average time for cache lookups in seconds
    steps_list: List[StepInfo]    # List of all the steps that hit cache


class CacheMissBreakdownCategory(TypedDict):
    """
    Detailed breakdown for one type of cache miss.
    
    This helps us understand WHY cache failed in each specific case.
    Each category represents a different failure reason with its own
    count, percentage, explanation, and list of affected steps.
    """
    count: int                    # Number of steps with this type of miss
    percentage: str               # Percentage as string (e.g., "6.67%")
    reason: str                   # Human-readable explanation of why cache failed
    steps_list: List[StepInfo]    # List of steps with this miss type


class CacheMissBreakdown(TypedDict):
    """
    Detailed breakdown of all cache miss types using existing classifier categories.
    
    This provides comprehensive categorization of WHY cache failed, using the same
    categories as the existing classifier system for consistency and detailed analysis:
    
    Priority-based categories (matching existing classifier):
    - undoable: Step was undoable, no cache needed
    - unblocker_call: Unblocker call, no cache needed  
    - ocr_steps: OCR was used, no cache needed
    - dynamic_step: Dynamic component resolution, no cache needed
    - null_llm_output: No LLM output, no cache needed
    - failed_step: Step execution failed, no cache needed
    - cache_read_status_none: Cache was never attempted (dynamic resolution)
    - no_cache_documents_found: No similar documents found in vector DB
    - less_similarity_threshold: Documents found but similarity < 0.75
    - failed_at_cand_nos_after_must_match_filter: Component selection failed at must_match_filter
    - failed_after_similar_document_found_with_threshold_after_must_match_filter: Failed after finding similar doc
    - unclassified: Catch-all for unclassified cases
    """
    undoable: CacheMissBreakdownCategory
    unblocker_call: CacheMissBreakdownCategory
    ocr_steps: CacheMissBreakdownCategory
    dynamic_step: CacheMissBreakdownCategory
    null_llm_output: CacheMissBreakdownCategory
    failed_step: CacheMissBreakdownCategory
    cache_read_status_none: CacheMissBreakdownCategory
    no_cache_documents_found: CacheMissBreakdownCategory
    less_similarity_threshold: CacheMissBreakdownCategory
    failed_at_cand_nos_after_must_match_filter: CacheMissBreakdownCategory
    failed_after_similar_document_found_with_threshold_after_must_match_filter: CacheMissBreakdownCategory
    unclassified: CacheMissBreakdownCategory


class CacheMissStats(TypedDict):
    """
    Overall statistics for cache misses.
    
    This gives us the big picture of cache failures, including
    total count, percentage, and detailed breakdown by failure reason.
    """
    count: int                    # Total number of cache misses
    percentage: str               # Total percentage of misses
    breakdown: CacheMissBreakdown # Detailed breakdown by failure reason


class CommandStatsReport(TypedDict):
    """
    The final report structure that we'll output as JSON.
    
    This is the complete analysis of cache performance for a specific command.
    It matches exactly what your senior requested in the requirements and
    provides comprehensive insights into cache behavior for that command.
    
    Structure matches the expected output format:
    - Input parameters (what the user asked for)
    - Overall statistics (total step runs)
    - Cache performance breakdown (hits vs misses with detailed analysis)
    """
    # Input parameters (what the user asked for)
    command: str                  # The command we analyzed
    app_package: str              # The app package we analyzed
    date_range: Dict[str, str]    # Start and end dates of analysis
    
    # Overall statistics
    total_step_runs: int          # Total number of steps analyzed
    
    # Cache performance breakdown
    cache_hit: CacheHitStats      # Statistics for successful cache usage
    cache_miss: CacheMissStats    # Statistics for cache failures with breakdown


# ============================================================================
# HELPER FUNCTIONS - Following Existing Utility Pattern
# ============================================================================

def create_empty_breakdown_category() -> CacheMissBreakdownCategory:
    """
    Create an empty breakdown category with zero counts.
    
    This is useful when initializing our statistics - we start with
    zero counts and increment as we process each step.
    
    Following the existing codebase pattern of providing helper functions
    for creating default/empty data structures.
    
    Returns:
        CacheMissBreakdownCategory with all fields initialized to empty/zero values
    """
    return CacheMissBreakdownCategory(
        count=0,
        percentage="0.00%",
        reason="",
        steps_list=[]
    )


def create_empty_breakdown() -> CacheMissBreakdown:
    """
    Create an empty breakdown with all categories initialized to zero.
    
    This gives us a clean starting point for our analysis where we can
    increment counts as we process each step. Uses all existing classifier
    categories for comprehensive breakdown.
    
    Returns:
        CacheMissBreakdown with all categories initialized to empty state
    """
    return CacheMissBreakdown(
        undoable=create_empty_breakdown_category(),
        unblocker_call=create_empty_breakdown_category(),
        ocr_steps=create_empty_breakdown_category(),
        dynamic_step=create_empty_breakdown_category(),
        null_llm_output=create_empty_breakdown_category(),
        failed_step=create_empty_breakdown_category(),
        cache_read_status_none=create_empty_breakdown_category(),
        no_cache_documents_found=create_empty_breakdown_category(),
        less_similarity_threshold=create_empty_breakdown_category(),
        failed_at_cand_nos_after_must_match_filter=create_empty_breakdown_category(),
        failed_after_similar_document_found_with_threshold_after_must_match_filter=create_empty_breakdown_category(),
        unclassified=create_empty_breakdown_category()
    )


def calculate_percentage(count: int, total: int) -> str:
    """
    Calculate percentage as a formatted string.
    
    This follows the existing codebase pattern of formatting percentages
    as strings with exactly 2 decimal places (e.g., "80.00%").
    
    Args:
        count: Number of items in this category
        total: Total number of items
        
    Returns:
        Formatted percentage string (e.g., "80.00%")
        
    Example:
        >>> calculate_percentage(120, 150)
        "80.00%"
        >>> calculate_percentage(0, 100)
        "0.00%"
    """
    if total == 0:
        return "0.00%"
    
    percentage = (count / total) * 100
    return f"{percentage:.2f}%"


def create_step_info_from_dict(step_dict: Dict[str, Any]) -> StepInfo:
    """
    Create StepInfo from a converted DynamoDB dictionary.
    
    This helper function converts a regular Python dictionary (from
    convert_dynamodb_item_to_dict) into our typed StepInfo dataclass.
    
    Args:
        step_dict: Dictionary with step data (from DynamoDB conversion)
        
    Returns:
        StepInfo dataclass with all fields properly typed
        
    Example:
        >>> step_dict = {
        ...     'step_id': 'abc123',
        ...     'command': 'Tap on Submit Button',
        ...     'cache_read_status': 1,
        ...     'cache_read_latency': 0.234
        ... }
        >>> step_info = create_step_info_from_dict(step_dict)
        >>> print(step_info.step_id)
        'abc123'
    """
    return StepInfo(
        # Core identification
        step_id=step_dict.get('step_id', ''),
        command=step_dict.get('command', ''),
        app_package=step_dict.get('app_package', ''),
        thread_code=step_dict.get('thread_code', ''),
        
        # Timing
        created_at=step_dict.get('created_at', ''),
        
        # Cache performance
        cache_read_status=step_dict.get('cache_read_status'),
        cache_read_latency=step_dict.get('cache_read_latency'),
        
        # Step execution
        step_classification=step_dict.get('step_classification', ''),
        test_step_status=step_dict.get('test_step_status', ''),
        
        # Additional fields
        cache_query_results=step_dict.get('cache_query_results'),
        ocr_output=step_dict.get('ocr_output'),
        llm_output=step_dict.get('llm_output'),
        is_blocker=step_dict.get('is_blocker'),
        ensemble_used=step_dict.get('ensemble_used')
    )


# ============================================================================
# VALIDATION FUNCTIONS - Data Integrity Checks
# ============================================================================

def validate_step_info(step_info: StepInfo) -> bool:
    """
    Validate that a StepInfo object has required fields.
    
    This ensures data integrity before processing steps.
    
    Args:
        step_info: StepInfo object to validate
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['step_id', 'command', 'app_package', 'created_at']
    
    for field in required_fields:
        if not getattr(step_info, field):
            return False
    
    return True


def validate_report_data(report: CommandStatsReport) -> bool:
    """
    Validate that a CommandStatsReport has consistent data.
    
    This ensures that percentages add up correctly and counts are consistent.
    
    Args:
        report: CommandStatsReport to validate
        
    Returns:
        True if valid, False otherwise
    """
    total = report['total_step_runs']
    hit_count = report['cache_hit']['count']
    miss_count = report['cache_miss']['count']
    
    # Check that hit + miss = total
    if hit_count + miss_count != total:
        return False
    
    # Check that breakdown counts add up to miss count
    breakdown = report['cache_miss']['breakdown']
    breakdown_total = sum(
        category['count'] 
        for category in breakdown.values()
    )
    
    if breakdown_total != miss_count:
        return False
    
    return True