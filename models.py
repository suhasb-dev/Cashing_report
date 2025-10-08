"""
Data Models and Enums for Cache Failure Classification

This module defines:
- Enums for cache failure categories (type-safe classification)
- Type definitions for data structures (TypedDict for better IDE support)
"""

from enum import Enum
from typing import TypedDict, Optional, Dict, Any

# ============================================================================
# ENUMS - Type-Safe Constants
# ============================================================================

class CacheFailureCategory(Enum):
    """
    All possible cache failure categories.
    
    Using Enum ensures we can only use these specific values,
    preventing typos like "ocr_step" vs "ocr_steps"
    """
    OCR_STEPS = "ocr_steps"
    UNBLOCKER_CALL = "unblocker_call"
    FAILED_STEP = "failed_step"
    NO_CACHE_DOCUMENTS_FOUND = "no_cache_documents_found"  # ✅ ADD THIS
    LESS_SIMILARITY_THRESHOLD = "less_similarity_threshold"
    CACHE_READ_STATUS_NONE = "cache_read_status_none"
    FAILED_AT_MUST_MATCH_FILTER = "failed_at_cand_nos_after_must_match_filter"
    FAILED_AFTER_SIMILAR_DOC = "failed_after_similar_document_found_with_threshold_after_must_match_filter"
    UNCLASSIFIED = "unclassified" 

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
