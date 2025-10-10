"""
Data Models and Enums for Cache Failure Classification

This module defines:
- Enums for cache failure categories (type-safe classification)
- Type definitions for data structures (TypedDict for better IDE support)

Priority-based single-category classification:
Each step is classified into EXACTLY ONE category.
"""

from enum import Enum
from typing import TypedDict, Optional, Dict, Any


# ============================================================================
# ENUMS - Type-Safe Constants (Priority Order)
# ============================================================================

class CacheFailureCategory(Enum):
    """
    All possible cache failure categories in PRIORITY ORDER.
    
    Each step is classified into the FIRST matching category.
    Using Enum ensures type-safe classification.
    """
    UNDOABLE = "undoable"                                # Priority 0
    UNBLOCKER_CALL = "unblocker_call"                    # Priority 1
    OCR_STEPS = "ocr_steps"                              # Priority 2
    DYNAMIC_STEP = "dynamic_step"
    NULL_LLM_OUTPUT = "null_llm_output"
    FAILED_STEP = "failed_step"                          # Priority 3
    CACHE_READ_STATUS_NONE = "cache_read_status_none"    # Priority 4
    NO_CACHE_DOCUMENTS_FOUND = "no_cache_documents_found"  # Priority 5
    LESS_SIMILARITY_THRESHOLD = "less_similarity_threshold"  # Priority 6
    FAILED_AT_MUST_MATCH_FILTER = "failed_at_cand_nos_after_must_match_filter"  # Priority 7
    FAILED_AFTER_SIMILAR_DOC = "failed_after_similar_document_found_with_threshold_after_must_match_filter"  # Priority 8
    UNCLASSIFIED = "unclassified"  # Priority 9 (catch-all)


# ============================================================================
# TYPE DEFINITIONS - Structure Documentation
# ============================================================================

class CacheQueryResult(TypedDict):
    """
    Type definition for cache query result structure.
    """
    document_id: str
    similarity_score: float
    component_metadata: Optional[Dict]
    is_used: bool
    component_selection_report: Optional[Dict]


class ComponentSelectionReport(TypedDict):
    """
    Type definition for component_selection_report structure.
    """
    match_config: Dict[str, Any]
    old_scrn_dimn: list
    new_scrn_dimn: list
    cand_nos_after_must_match_filter: Optional[int]
    cand_nos_after_hint_filter: Optional[int]
    is_parent_filter_applicable: Optional[bool]
    cand_nos_after_parent_filter: Optional[int]
    are_candidates_sibling: Optional[bool]
    cand_nos_after_own_deep_text_filter: Optional[int]
    cand_nos_after_parent_deep_text_filter: Optional[int]


class ReportCategory(TypedDict):
    """
    Type definition for each category in the report.
    """
    percentage: str
    document_count: int
    steps_list: list
