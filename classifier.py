"""
Cache Failure Classification Logic - Priority-Based Single Category

Each step is classified into EXACTLY ONE category based on priority order.
This ensures clean percentages that sum to 100%.

Priority Order (from highest to lowest):
1. Unblocker Call
2. OCR Steps  
3. Failed Step
4. Cache Read Status None (Dynamic Components)
5. No Cache Documents Found (cache_read_status = -1)
6. Less Similarity Threshold (has cache_query_results but all < 0.75)
7. Failed At Must Match Filter
8. Failed After Similar Document
9. Unclassified (catch-all)
"""

from typing import Dict, List, Optional, Tuple
from models import CacheFailureCategory
from config import SIMILARITY_THRESHOLD
from utils import parse_json_string, get_nested_value, logger


# ============================================================================
# MAIN CLASSIFICATION FUNCTION - PRIORITY BASED
# ============================================================================

def classify_step(step: Dict) -> Tuple[List[str], Optional[Dict]]:
    """
    Classify a step into EXACTLY ONE category using priority order.
    
    Returns the FIRST matching category, then stops checking.
    This ensures each step belongs to only one category.
    
    Args:
        step: DynamoDB item (in DynamoDB JSON format)
        
    Returns:
        Tuple of ([single category], diagnostic dict or None)
    """
    # Priority 1: Unblocker Call (HIGHEST)
    if check_undoable_category(step):
        return [CacheFailureCategory.UNDOABLE.value], None

    if check_unblocker_category(step):
        return [CacheFailureCategory.UNBLOCKER_CALL.value], None
    
    # Priority 2: OCR Steps
    if check_ocr_category(step):
        return [CacheFailureCategory.OCR_STEPS.value], None

    if check_dynamic_component(step):
        return [CacheFailureCategory.DYNAMIC_STEP.value], None
    
    # Priority 3: Failed Step
    if check_failed_step_category(step):
        return [CacheFailureCategory.FAILED_STEP.value], None

    if check_null_llm_output(step):
        return [CacheFailureCategory.NULL_LLM_OUTPUT.value], None
    
    # Priority 4: Cache Read Status None
    if check_cache_read_status_none(step):
        return [CacheFailureCategory.CACHE_READ_STATUS_NONE.value], None
    
    # Priority 5: No Cache Documents Found (cache_read_status = -1)
    if check_no_documents_found_category(step):
        return [CacheFailureCategory.NO_CACHE_DOCUMENTS_FOUND.value], None
    
    # Priority 6: Less Similarity Threshold
    if check_less_similarity_category(step):
        return [CacheFailureCategory.LESS_SIMILARITY_THRESHOLD.value], None
    
    # Priority 7: Failed At Must Match Filter
    if check_must_match_filter_category(step):
        return [CacheFailureCategory.FAILED_AT_MUST_MATCH_FILTER.value], None
    
    # Priority 8: Failed After Similar Document
    if check_failed_after_similar_doc_category(step):
        return [CacheFailureCategory.FAILED_AFTER_SIMILAR_DOC.value], None
    
    # Priority 9: Unclassified (LOWEST - should rarely happen)
    diagnosis = diagnose_unclassified_step(step)
    return [CacheFailureCategory.UNCLASSIFIED.value], diagnosis


# ============================================================================
# DIAGNOSTIC FUNCTION
# ============================================================================

def diagnose_unclassified_step(step: Dict) -> Dict[str, any]:
    """
    Deep diagnostic analysis for unclassified steps.
    """
    step_id = get_nested_value(step, 'step_id', 'S', default='unknown')
    
    diagnosis = {
        'step_id': step_id,
        'step_classification': get_nested_value(step, 'step_classification', 'S'),
        'cache_read_status': get_nested_value(step, 'cache_read_status', 'N'),
        'test_step_status': get_nested_value(step, 'test_step_status', 'S'),
        'has_cache_query_results': bool(get_nested_value(step, 'cache_query_results', 'S')),
        'has_ocr_output': bool(get_nested_value(step, 'ocr_output', 'S') not in [None, 'NA', '']),
        'is_blocker': get_nested_value(step, 'is_blocker', 'BOOL'),
        'category_checks': {}
    }
    
    # Check all categories
    ocr_output = get_nested_value(step, 'ocr_output', 'S', default='NA')
    diagnosis['category_checks']['ocr_steps'] = {
        'passed': check_ocr_category(step),
        'reason': f"ocr_output={'present' if ocr_output not in ['NA', '', None] else 'absent'}"
    }
    
    is_blocker = get_nested_value(step, 'is_blocker', 'BOOL')
    diagnosis['category_checks']['unblocker_call'] = {
        'passed': check_unblocker_category(step),
        'reason': f"is_blocker={is_blocker}"
    }
    
    test_step_status = get_nested_value(step, 'test_step_status', 'S')
    diagnosis['category_checks']['failed_step'] = {
        'passed': check_failed_step_category(step),
        'reason': f"test_step_status={test_step_status}"
    }
    
    has_cache_read_status = 'cache_read_status' in step
    diagnosis['category_checks']['cache_read_status_none'] = {
        'passed': check_cache_read_status_none(step),
        'reason': f"cache_read_status field {'missing' if not has_cache_read_status else 'present'}"
    }
    
    cache_read_status = get_nested_value(step, 'cache_read_status', 'N')
    diagnosis['category_checks']['no_cache_documents_found'] = {
        'passed': check_no_documents_found_category(step),
        'reason': f"cache_read_status={cache_read_status}"
    }
    
    return diagnosis


# ============================================================================
# CATEGORY CHECK FUNCTIONS (IN PRIORITY ORDER)
# ============================================================================

def check_undoable_category(step: Dict) -> bool:
    """
    Priority 0: Check if step is undoable.
    """
    llm_result = get_nested_value(step, 'llm_output', 'S')
    
    return "undoable" in llm_result.lower() if llm_result else False


def check_unblocker_category(step: Dict) -> bool:
    """
    Priority 1: Check if step is a blocker/unblocker call.
    """
    # is_blocker_bool = get_nested_value(step, 'is_blocker', 'BOOL')
    # is_blocker_str = get_nested_value(step, 'is_blocker', 'S')
    
    # return (
    #     is_blocker_bool is True or 
    #     is_blocker_str == 'TRUE' or 
    #     is_blocker_str == 'true'
    # )
    llm_result = get_nested_value(step, 'llm_output', 'S')
    return "unblock: " in llm_result.lower() if llm_result else False


def check_ocr_category(step: Dict) -> bool:
    """
    Priority 2: Check if OCR was used.
    """
    ocr_output = get_nested_value(step, 'ocr_output', 'S', default='NA')
    
    return (
        ocr_output is not None and 
        ocr_output != '' and 
        ocr_output != 'NA'
    )

def check_dynamic_component(step: Dict) -> bool:
    """
    Priority 2.5: Check if the step used dynamic component resolution.
    """
    is_ensemble = get_nested_value(step, 'ensemble_used', 'BOOL')
    
    return is_ensemble is True


def check_failed_step_category(step: Dict) -> bool:
    """
    Priority 3: Check if the step execution failed.
    """
    test_step_status = get_nested_value(step, 'test_step_status', 'S')
    is_failed = test_step_status == 'FAILED'
    
    if is_failed:
        logger.debug(
            f"Step {get_nested_value(step, 'step_id', 'S')}: "
            f"test_step_status = FAILED"
        )
    
    return is_failed


def check_cache_read_status_none(step: Dict) -> bool:
    """
    Priority 4: Check if cache_read_status is missing.
    
    When this field is missing, cache was never attempted
    because the step used dynamic component resolution.
    """
    return 'cache_read_status' not in step


def check_null_llm_output(step: Dict) -> bool:
    """
    Priority 3.5: Check if the step execution failed.
    """
    llm_output = get_nested_value(step, 'llm_output', 'S')
    is_null_llm_output = llm_output == ''
    return is_null_llm_output


def check_no_documents_found_category(step: Dict) -> bool:
    """
    Priority 5: Check if cache lookup failed (cache miss).
    
    Simplified logic: cache_read_status = -1 means cache was
    attempted but found no usable documents (for any reason).
    
    We don't check cache_query_results because:
    - If cache_read_status = -1, the outcome is already clear
    - Whether no docs found OR low similarity, result is the same: cache didn't help
    """
    cache_read_status = get_nested_value(step, 'cache_read_status', 'N')
    
    return cache_read_status == '-1'


def check_less_similarity_category(step: Dict) -> bool:
    """
    Priority 6: Check if ALL similarity scores are below threshold.
    
    This is now a specialized check for steps that:
    - Have cache_read_status = 0 (or other non-miss values)
    - Have cache_query_results with documents
    - All documents have similarity < 0.75
    
    Note: Steps with cache_read_status = -1 are already caught
    by check_no_documents_found_category() at priority 5.
    """
    cache_read_status = get_nested_value(step, 'cache_read_status', 'N')
    
    # Skip steps with cache_read_status = -1 (already handled)
    if cache_read_status == '-1':
        return False
    
    cache_results_str = get_nested_value(step, 'cache_query_results', 'S')
    
    if not cache_results_str:
        return False
    
    cache_results = parse_json_string(cache_results_str)
    
    if not cache_results or not isinstance(cache_results, list) or len(cache_results) == 0:
        return False
    
    all_below_threshold = all(
        doc.get('similarity_score', 0) < SIMILARITY_THRESHOLD 
        for doc in cache_results
    )
    
    if all_below_threshold:
        logger.debug(
            f"Step {get_nested_value(step, 'step_id', 'S')}: "
            f"All {len(cache_results)} documents have similarity < {SIMILARITY_THRESHOLD}"
        )
    
    return all_below_threshold


def check_must_match_filter_category(step: Dict) -> bool:
    """
    Priority 7: Check if step failed at must_match_filter stage.
    """
    cache_results_str = get_nested_value(step, 'cache_query_results', 'S')
    if not cache_results_str:
        return False
    
    cache_results = parse_json_string(cache_results_str)
    if not cache_results or not isinstance(cache_results, list):
        return False
    
    for doc in cache_results:
        similarity = doc.get('similarity_score', 0)
        
        if similarity > SIMILARITY_THRESHOLD:
            report = doc.get('component_selection_report')
            
            if report and isinstance(report, dict):
                cand_nos = report.get('cand_nos_after_must_match_filter')
                
                if cand_nos == 0:
                    return True
    
    return False


def check_failed_after_similar_doc_category(step: Dict) -> bool:
    """
    Priority 8: Check if step failed after finding similar document.
    """
    cache_results_str = get_nested_value(step, 'cache_query_results', 'S')
    if not cache_results_str:
        return False
    
    cache_results = parse_json_string(cache_results_str)
    if not cache_results or not isinstance(cache_results, list):
        return False
    
    for doc in cache_results:
        similarity = doc.get('similarity_score', 0)
        is_used = doc.get('is_used', False)
        
        if similarity > SIMILARITY_THRESHOLD and not is_used:
            report = doc.get('component_selection_report')
            
            if report and isinstance(report, dict):
                cand_nos = report.get('cand_nos_after_must_match_filter')
                
                if cand_nos is not None and cand_nos != 0:
                    return True
    
    return False
