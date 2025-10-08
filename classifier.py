"""
Cache Failure Classification Logic with Deep Diagnostics

This module contains the business logic for classifying cache failures
with comprehensive diagnostic capabilities for unclassified steps.
"""

from typing import Dict, List, Optional, Tuple
from models import CacheFailureCategory
from config import SIMILARITY_THRESHOLD
from utils import parse_json_string, get_nested_value, logger


# ============================================================================
# MAIN CLASSIFICATION FUNCTION
# ============================================================================

def classify_step(step: Dict) -> Tuple[List[str], Optional[Dict]]:
    """
    Classify a step into one or more cache failure categories.
    
    Now returns diagnostic info for unclassified steps.
    
    Args:
        step: DynamoDB item (in DynamoDB JSON format)
        
    Returns:
        Tuple of (categories list, diagnostic dict or None)
    """
    categories = []
    
  # Check each category
    if check_unblocker_category(step):
        categories.append(CacheFailureCategory.UNBLOCKER_CALL.value)
  
    if check_no_documents_found_category(step):                  
        categories.append(CacheFailureCategory.NO_CACHE_DOCUMENTS_FOUND.value) #-1 


    if check_ocr_category(step):
        categories.append(CacheFailureCategory.OCR_STEPS.value)
    
    
    if check_failed_step_category(step):
        categories.append(CacheFailureCategory.FAILED_STEP.value)
    
    if check_dynamic_components_category(step):
        categories.append(CacheFailureCategory.CACHE_READ_STATUS_NONE.value)
    
    
    
    if check_less_similarity_category(step):
        categories.append(CacheFailureCategory.LESS_SIMILARITY_THRESHOLD.value)
    
    if check_must_match_filter_category(step):
        categories.append(CacheFailureCategory.FAILED_AT_MUST_MATCH_FILTER.value)
    
    if check_failed_after_similar_doc_category(step):
        categories.append(CacheFailureCategory.FAILED_AFTER_SIMILAR_DOC.value)
    
    # If unclassified, generate diagnostic report
    diagnosis = None
    if len(categories) == 0:
        categories.append(CacheFailureCategory.UNCLASSIFIED.value)
        diagnosis = diagnose_unclassified_step(step)
    
    return categories, diagnosis


# ============================================================================
# DIAGNOSTIC FUNCTION - WHY IS STEP UNCLASSIFIED?
# ============================================================================

def diagnose_unclassified_step(step: Dict) -> Dict[str, any]:
    """
    Deep diagnostic analysis for unclassified steps.
    
    Returns detailed information about WHY each category check failed.
    This helps us understand what's missing in our classification logic.
    
    Args:
        step: DynamoDB item
        
    Returns:
        Dict with diagnostic information for each category
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
    
    # Check OCR category
    ocr_output = get_nested_value(step, 'ocr_output', 'S', default='NA')
    diagnosis['category_checks']['ocr_steps'] = {
        'passed': check_ocr_category(step),
        'reason': f"ocr_output={'present' if ocr_output not in ['NA', '', None] else 'absent'} (value: {str(ocr_output)[:50] if ocr_output else 'None'}...)"
    }
    
    # Check Unblocker category
    is_blocker = get_nested_value(step, 'is_blocker', 'BOOL')
    diagnosis['category_checks']['unblocker_call'] = {
        'passed': check_unblocker_category(step),
        'reason': f"is_blocker={is_blocker}"
    }
    
    # Check Failed Step category
    test_step_status = get_nested_value(step, 'test_step_status', 'S')
    diagnosis['category_checks']['failed_step'] = {
        'passed': check_failed_step_category(step),
        'reason': f"test_step_status={test_step_status} (needs FAILED)"
    }
    
    # Check Dynamic Components category
    has_cache_read_status = 'cache_read_status' in step
    diagnosis['category_checks']['cache_read_status_none'] = {
        'passed': check_dynamic_components_category(step),
        'reason': f"cache_read_status field {'missing' if not has_cache_read_status else 'present'}"
    }
    
    # Check No Documents Found category
    cache_read_status = get_nested_value(step, 'cache_read_status', 'N')
    cache_results_str = get_nested_value(step, 'cache_query_results', 'S')
    diagnosis['category_checks']['no_cache_documents_found'] = {
        'passed': check_no_documents_found_category(step),
        'reason': f"cache_read_status={cache_read_status}, has_cache_query_results={bool(cache_results_str)}"
    }
    
    # Check Less Similarity category
    if cache_results_str:
        cache_results = parse_json_string(cache_results_str)
        if cache_results:
            scores = [doc.get('similarity_score', 0) for doc in cache_results]
            all_below = all(score < SIMILARITY_THRESHOLD for score in scores)
            diagnosis['category_checks']['less_similarity_threshold'] = {
                'passed': check_less_similarity_category(step),
                'reason': f"scores={scores}, all_below_0.75={all_below}, threshold={SIMILARITY_THRESHOLD}"
            }
        else:
            diagnosis['category_checks']['less_similarity_threshold'] = {
                'passed': False,
                'reason': "Failed to parse cache_query_results JSON"
            }
    else:
        diagnosis['category_checks']['less_similarity_threshold'] = {
            'passed': False,
            'reason': "No cache_query_results"
        }
    
    # Check Must Match Filter category
    diagnosis['category_checks']['failed_at_must_match_filter'] = {
        'passed': check_must_match_filter_category(step),
        'reason': analyze_must_match_filter(step)
    }
    
    # Check Failed After Similar Doc category
    diagnosis['category_checks']['failed_after_similar_doc'] = {
        'passed': check_failed_after_similar_doc_category(step),
        'reason': analyze_failed_after_similar_doc(step)
    }
    
    return diagnosis


def analyze_must_match_filter(step: Dict) -> str:
    """Analyze why must_match_filter check passed/failed."""
    cache_results_str = get_nested_value(step, 'cache_query_results', 'S')
    if not cache_results_str:
        return "No cache_query_results"
    
    cache_results = parse_json_string(cache_results_str)
    if not cache_results:
        return "Invalid cache_query_results JSON"
    
    high_similarity_docs = [
        doc for doc in cache_results 
        if doc.get('similarity_score', 0) >= SIMILARITY_THRESHOLD
    ]
    
    if not high_similarity_docs:
        return f"No docs with similarity >= {SIMILARITY_THRESHOLD}"
    
    docs_with_zero_cands = []
    for doc in high_similarity_docs:
        report = doc.get('component_selection_report')
        if report:
            cand_nos = report.get('cand_nos_after_must_match_filter')
            if cand_nos == 0:
                docs_with_zero_cands.append(doc.get('document_id', 'unknown'))
    
    if docs_with_zero_cands:
        return f"Found {len(docs_with_zero_cands)} docs with cand_nos=0: {docs_with_zero_cands}"
    else:
        return f"{len(high_similarity_docs)} high-similarity docs, but none have cand_nos=0"


def analyze_failed_after_similar_doc(step: Dict) -> str:
    """Analyze why failed_after_similar_doc check passed/failed."""
    cache_read_status = get_nested_value(step, 'cache_read_status', 'N')
    cache_results_str = get_nested_value(step, 'cache_query_results', 'S')
    
    if not cache_results_str:
        return f"No cache_query_results (cache_read_status={cache_read_status})"
    
    cache_results = parse_json_string(cache_results_str)
    if not cache_results:
        return "Invalid cache_query_results JSON"
    
    high_similarity_unused = []
    for doc in cache_results:
        similarity = doc.get('similarity_score', 0)
        is_used = doc.get('is_used', False)
        
        if similarity >= SIMILARITY_THRESHOLD and not is_used:
            report = doc.get('component_selection_report')
            if report:
                cand_nos = report.get('cand_nos_after_must_match_filter')
                high_similarity_unused.append({
                    'doc_id': doc.get('document_id', 'unknown'),
                    'similarity': round(similarity, 3),
                    'cand_nos': cand_nos
                })
    
    if not high_similarity_unused:
        return "No high-similarity unused docs found"
    
    with_nonzero_cands = [d for d in high_similarity_unused if d['cand_nos'] and d['cand_nos'] != 0]
    
    if with_nonzero_cands:
        return f"Found {len(with_nonzero_cands)} docs: {with_nonzero_cands}"
    else:
        return f"Found {len(high_similarity_unused)} high-sim unused docs, but all have cand_nos=0 or None"


# ============================================================================
# CATEGORY CHECK FUNCTIONS
# ============================================================================

def check_ocr_category(step: Dict) -> bool:
    """Check if OCR was used."""
    ocr_output = get_nested_value(step, 'ocr_output', 'S', default='NA')
    return (
        ocr_output is not None and 
        ocr_output != '' and 
        ocr_output != 'NA'
    )


def check_unblocker_category(step: Dict) -> bool:
    """Check if step is a blocker/unblocker call."""
    is_blocker_bool = get_nested_value(step, 'is_blocker', 'BOOL')
    is_blocker_str = get_nested_value(step, 'is_blocker', 'S')
    return (
        is_blocker_bool is True or 
        is_blocker_str == 'TRUE' or 
        is_blocker_str == 'true'
    )


def check_failed_step_category(step: Dict) -> bool:
    """Check if the step execution failed."""
    test_step_status = get_nested_value(step, 'test_step_status', 'S')
    is_failed = test_step_status == 'FAILED'
    
    if is_failed:
        logger.debug(
            f"Step {get_nested_value(step, 'step_id', 'S')}: "
            f"test_step_status = FAILED"
        )
    
    return is_failed


def check_dynamic_components_category(step: Dict) -> bool:
    """Check if cache_read_status is missing."""
    return 'cache_read_status' not in step


def check_no_documents_found_category(step: Dict) -> bool:
    """Check if cache lookup returned NO documents."""
    cache_read_status = get_nested_value(step, 'cache_read_status', 'N')
    
    if cache_read_status != '-1':
        return False
    
#    cache_results_str = get_nested_value(step, 'cache_query_results', 'S')
    
#     if not cache_results_str:
#         logger.debug(
#             f"Step {get_nested_value(step, 'step_id', 'S')}: "
#             f"cache_read_status=-1 with no cache_query_results"
#         )
#         return True
    
#     cache_results = parse_json_string(cache_results_str)
#     if not cache_results or len(cache_results) == 0:
#         logger.debug(
#             f"Step {get_nested_value(step, 'step_id', 'S')}: "
#             f"cache_query_results is empty array"
#         )
#         return True
    
#     return False 


def check_less_similarity_category(step: Dict) -> bool:
    """Check if ALL similarity scores are below threshold."""
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
    """Check if step failed at must_match_filter stage."""
    cache_results_str = get_nested_value(step, 'cache_query_results', 'S')
    if not cache_results_str:
        return False
    
    cache_results = parse_json_string(cache_results_str)
    if not cache_results or not isinstance(cache_results, list):
        return False
    
    for doc in cache_results:
        similarity = doc.get('similarity_score', 0)
        
        if similarity >= SIMILARITY_THRESHOLD:
            report = doc.get('component_selection_report')
            
            if report and isinstance(report, dict):
                cand_nos = report.get('cand_nos_after_must_match_filter')
                
                if cand_nos == 0:
                    return True
    
    return False


def check_failed_after_similar_doc_category(step: Dict) -> bool:
    """Check if step failed after finding similar document."""
    cache_results_str = get_nested_value(step, 'cache_query_results', 'S')
    if not cache_results_str:
        return False
    
    cache_results = parse_json_string(cache_results_str)
    if not cache_results or not isinstance(cache_results, list):
        return False
    
    for doc in cache_results:
        similarity = doc.get('similarity_score', 0)
        is_used = doc.get('is_used', False)
        
        if similarity >= SIMILARITY_THRESHOLD and not is_used:
            report = doc.get('component_selection_report')
            
            if report and isinstance(report, dict):
                cand_nos = report.get('cand_nos_after_must_match_filter')
                
                if cand_nos is not None and cand_nos != 0:
                    return True
    
    return False
