"""
Bulk Command Analyzer - Single-Pass Analysis for All Commands

This module implements the dual strategy:
1. Individual command analysis (across all packages)
2. Command+Package analysis (existing approach)

All from a single DynamoDB scan with incremental count and stats updates.
"""

import json
import os
import re
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Any, Iterator
from pathlib import Path

from dynamodb_scanner import scan_test_steps_with_pagination
from utils import convert_dynamodb_item_to_dict, logger
from config import DEFAULT_OUTPUT_DIR

# Import classification logic from command_stats
from command_stats.analyzer import analyze_cache_miss_reason


class BulkCommandAggregator:
    """
    Aggregates command statistics during single-pass DynamoDB scan.
    
    Follows the correct plan:
    1. Single DB read with pagination (generator)
    2. For each row: Update count and ALL stats if command exists, or add new command
    3. No storing raw data - just incremental updates
    4. Generate files at the end with final aggregated stats
    """
    
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Individual command aggregation (NEW) - just counts and stats
        self.command_stats = {}  # command -> {count, cache_hits, cache_misses, app_packages, etc.}
        
        # Command+Package aggregation (EXISTING) - just counts and stats  
        self.command_package_stats = {}  # (command, package) -> {count, cache_hits, cache_misses, etc.}
        
        # Statistics
        self.total_steps_processed = 0
        self.start_time = datetime.now()
    
    def _init_breakdown_stats(self):
        """Initialize empty breakdown statistics"""
        return {
            'undoable': 0,
            'unblocker_call': 0,
            'ocr_steps': 0,
            'dynamic_step': 0,
            'null_llm_output': 0,
            'failed_step': 0,
            'cache_read_status_none': 0,
            'no_cache_documents_found': 0,
            'less_similarity_threshold': 0,
            'failed_at_cand_nos_after_must_match_filter': 0,
            'failed_after_similar_document_found_with_threshold_after_must_match_filter': 0,
            'unclassified': 0
        }
    
    def update_command_stats(self, step_data: Dict, step_dynamodb: Dict):
        """
        Update individual command statistics with incremental updates.
        
        If command exists: increment count and update all stats
        If command is new: initialize with count=1 and all stats
        
        Args:
            step_data: Converted dictionary format (for easier access)
            step_dynamodb: Original DynamoDB format (for classification)
        """
        command = step_data.get('command', 'UNKNOWN_COMMAND')
        app_package = step_data.get('app_package', 'UNKNOWN_PACKAGE')
        cache_status = step_data.get('cache_read_status')
        created_at = step_data.get('created_at', '')
        step_classification = step_data.get('step_classification', 'UNKNOWN')
        test_step_status = step_data.get('test_step_status', 'UNKNOWN')
        cache_latency = step_data.get('cache_read_latency')
        
        # Extract date
        date_key = created_at[:10] if created_at else 'unknown'
        
        # Classify cache miss if applicable
        miss_category = None
        if cache_status in [0, -1, None]:  # Cache miss or no cache attempt
            try:
                miss_category = analyze_cache_miss_reason(step_dynamodb)
            except Exception as e:
                logger.warning(f"Failed to classify cache miss: {e}")
                miss_category = "unclassified"
        
        if command not in self.command_stats:
            # First time seeing this command - initialize ALL stats
            self.command_stats[command] = {
                'count': 1,
                'app_packages': {app_package: 1},
                'cache_hits': 1 if cache_status == 1 else 0,
                'cache_misses': 1 if cache_status in [0, -1, None] else 0,
                'cache_hit_without_component': 1 if cache_status == 0 else 0,
                'date_distribution': {date_key: 1},
                'step_classifications': {step_classification: 1},
                'test_step_status': {test_step_status: 1},
                'cache_latencies': [cache_latency] if cache_latency else [],
                'cache_miss_breakdown': self._init_breakdown_stats()
            }
            # Update breakdown if this is a miss
            if miss_category:
                self.command_stats[command]['cache_miss_breakdown'][miss_category] += 1
        else:
            # Command exists - update ALL stats (incremental updates)
            stats = self.command_stats[command]
            stats['count'] += 1  # Increment count
            
            # Update app packages
            stats['app_packages'][app_package] = stats['app_packages'].get(app_package, 0) + 1
            
            # Update cache status
            if cache_status == 1:
                stats['cache_hits'] += 1
            elif cache_status in [0, -1, None]:
                stats['cache_misses'] += 1
                # Update breakdown for this miss
                if miss_category:
                    stats['cache_miss_breakdown'][miss_category] += 1
            
            if cache_status == 0:
                stats['cache_hit_without_component'] += 1
            
            # Update date distribution
            stats['date_distribution'][date_key] = stats['date_distribution'].get(date_key, 0) + 1
            
            # Update step classifications
            stats['step_classifications'][step_classification] = stats['step_classifications'].get(step_classification, 0) + 1
            
            # Update test step status
            stats['test_step_status'][test_step_status] = stats['test_step_status'].get(test_step_status, 0) + 1
            
            # Update cache latencies
            if cache_latency:
                stats['cache_latencies'].append(cache_latency)
    
    def update_command_package_stats(self, step_data: Dict, step_dynamodb: Dict):
        """
        Update command+package statistics with incremental updates.
        
        If (command, package) exists: increment count and update all stats
        If (command, package) is new: initialize with count=1 and all stats
        
        Args:
            step_data: Converted dictionary format (for easier access)
            step_dynamodb: Original DynamoDB format (for classification)
        """
        command = step_data.get('command', 'UNKNOWN_COMMAND')
        app_package = step_data.get('app_package', 'UNKNOWN_PACKAGE')
        cache_status = step_data.get('cache_read_status')
        created_at = step_data.get('created_at', '')
        step_classification = step_data.get('step_classification', 'UNKNOWN')
        test_step_status = step_data.get('test_step_status', 'UNKNOWN')
        cache_latency = step_data.get('cache_read_latency')
        
        # Extract date
        date_key = created_at[:10] if created_at else 'unknown'
        
        # Classify cache miss if applicable
        miss_category = None
        if cache_status in [0, -1, None]:  # Cache miss or no cache attempt
            try:
                miss_category = analyze_cache_miss_reason(step_dynamodb)
            except Exception as e:
                logger.warning(f"Failed to classify cache miss: {e}")
                miss_category = "unclassified"
        
        key = (command, app_package)
        
        if key not in self.command_package_stats:
            # First time seeing this command+package combination - initialize ALL stats
            self.command_package_stats[key] = {
                'count': 1,
                'cache_hits': 1 if cache_status == 1 else 0,
                'cache_misses': 1 if cache_status in [0, -1, None] else 0,
                'cache_hit_without_component': 1 if cache_status == 0 else 0,
                'date_distribution': {date_key: 1},
                'step_classifications': {step_classification: 1},
                'test_step_status': {test_step_status: 1},
                'cache_latencies': [cache_latency] if cache_latency else [],
                'cache_miss_breakdown': self._init_breakdown_stats()
            }
            # Update breakdown if this is a miss
            if miss_category:
                self.command_package_stats[key]['cache_miss_breakdown'][miss_category] += 1
        else:
            # Command+package exists - update ALL stats (incremental updates)
            stats = self.command_package_stats[key]
            stats['count'] += 1  # Increment count
            
            # Update cache status
            if cache_status == 1:
                stats['cache_hits'] += 1
            elif cache_status in [0, -1, None]:
                stats['cache_misses'] += 1
                # Update breakdown for this miss
                if miss_category:
                    stats['cache_miss_breakdown'][miss_category] += 1
            
            if cache_status == 0:
                stats['cache_hit_without_component'] += 1
            
            # Update date distribution
            stats['date_distribution'][date_key] = stats['date_distribution'].get(date_key, 0) + 1
            
            # Update step classifications
            stats['step_classifications'][step_classification] = stats['step_classifications'].get(step_classification, 0) + 1
            
            # Update test step status
            stats['test_step_status'][test_step_status] = stats['test_step_status'].get(test_step_status, 0) + 1
            
            # Update cache latencies
            if cache_latency:
                stats['cache_latencies'].append(cache_latency)
    
    def _format_breakdown_for_report(self, breakdown: Dict, total_misses: int) -> Dict:
        """Convert breakdown counts to formatted report structure"""
        formatted = {}
        for category, count in breakdown.items():
            percentage = (count / total_misses * 100) if total_misses > 0 else 0.0
            formatted[category] = {
                "count": count,
                "percentage": f"{percentage:.2f}%",
                "reason": "",
                "steps_list": []
            }
        return formatted
    
    def _sanitize_filename(self, text: str) -> str:
        """Convert text to safe filename"""
        safe_name = re.sub(r'[^\w\s-]', '', text)
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        safe_name = safe_name.strip('_')
        return safe_name[:50] if len(safe_name) > 50 else safe_name
    
    def generate_individual_command_file(self, command: str, stats: Dict):
        """Generate individual command file with aggregated stats"""
        try:
            # Calculate percentages
            total_count = stats['count']
            cache_hit_percentage = (stats['cache_hits'] / total_count) * 100 if total_count > 0 else 0
            cache_miss_percentage = (stats['cache_misses'] / total_count) * 100 if total_count > 0 else 0
            cache_hit_without_component_percentage = (stats['cache_hit_without_component'] / total_count) * 100 if total_count > 0 else 0
            
            # Calculate average latency
            avg_latency = sum(stats['cache_latencies']) / len(stats['cache_latencies']) if stats['cache_latencies'] else 0.0
            
            # Get the most common package for this command
            most_common_package = max(stats['app_packages'].items(), key=lambda x: x[1])[0] if stats['app_packages'] else "UNKNOWN_PACKAGE"
            
            # Structure with command first, app_package second
            command_report = {
                "command": command,  # Full command at the top
                "app_package": most_common_package,  # Most common package second
                "total_step_runs": total_count,
                "app_package_distribution": stats['app_packages'],
                "date_range": {
                    "start": min(stats['date_distribution'].keys()) if stats['date_distribution'] else None,
                    "end": max(stats['date_distribution'].keys()) if stats['date_distribution'] else None
                },
                "cache_hit": {
                    "count": stats['cache_hits'],
                    "percentage": f"{cache_hit_percentage:.2f}%",
                    "average_latency": avg_latency,
                    "steps_list": []
                },
                "cache_miss": {
                    "count": stats['cache_misses'],
                    "percentage": f"{cache_miss_percentage:.2f}%",
                    "breakdown": self._format_breakdown_for_report(
                        stats.get('cache_miss_breakdown', self._init_breakdown_stats()),
                        stats['cache_misses']
                    )
                },
                "cache_hit_without_component": {
                    "count": stats['cache_hit_without_component'],
                    "percentage": f"{cache_hit_without_component_percentage:.2f}%"
                },
                "step_classifications": stats['step_classifications'],
                "test_step_status": stats['test_step_status'],
                "date_distribution": stats['date_distribution']
            }
            
            # Generate filename (use sanitized command for filename, but keep full command in JSON)
            safe_command_name = self._sanitize_filename(command)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Truncate the filename if it's too long, but keep the full command in the JSON
            max_filename_length = 200  # Increased from 50 to 200 for better readability
            if len(safe_command_name) > max_filename_length:
                # Keep first 100 chars and last 50 chars with ... in between
                safe_command_name = f"{safe_command_name[:100]}...{safe_command_name[-50:]}"
            
            filename = f"command_stats_{safe_command_name}_{timestamp}.json"
            filepath = os.path.join(self.output_dir, filename)
            
            # Save file with full command in the JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(command_report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Generated individual command file: {filename}")
            
        except Exception as e:
            logger.error(f"Failed to generate file for command '{command}': {e}")
    
    def generate_command_package_file(self, command: str, app_package: str, stats: Dict):
        """Generate command+package file with aggregated stats"""
        try:
            # Calculate percentages
            total_count = stats['count']
            cache_hit_percentage = (stats['cache_hits'] / total_count) * 100 if total_count > 0 else 0
            cache_miss_percentage = (stats['cache_misses'] / total_count) * 100 if total_count > 0 else 0
            cache_hit_without_component_percentage = (stats['cache_hit_without_component'] / total_count) * 100 if total_count > 0 else 0
            
            # Calculate average latency
            avg_latency = sum(stats['cache_latencies']) / len(stats['cache_latencies']) if stats['cache_latencies'] else 0.0
            
            # Generate report structure with command and app_package at the top
            command_package_report = {
                "command": command,  # Full command at the top
                "app_package": app_package  # Full package name
            }
            
            # Add all other fields as they were
            command_package_report.update({
                "total_step_runs": total_count,
                "date_range": {
                    "start": min(stats['date_distribution'].keys()) if stats['date_distribution'] else None,
                    "end": max(stats['date_distribution'].keys()) if stats['date_distribution'] else None
                },
                "cache_hit": {
                    "count": stats['cache_hits'],
                    "percentage": f"{cache_hit_percentage:.2f}%",
                    "average_latency": avg_latency,
                    "steps_list": []
                },
                "cache_miss": {
                    "count": stats['cache_misses'],
                    "percentage": f"{cache_miss_percentage:.2f}%",
                    "breakdown": self._format_breakdown_for_report(
                        stats.get('cache_miss_breakdown', self._init_breakdown_stats()),
                        stats['cache_misses']
                    )
                },
                "cache_hit_without_component": {
                    "count": stats['cache_hit_without_component'],
                    "percentage": f"{cache_hit_without_component_percentage:.2f}%"
                },
                "step_classifications": stats['step_classifications'],
                "test_step_status": stats['test_step_status'],
                "date_distribution": stats['date_distribution']
            })
            
            # Generate filename (use sanitized command/package for filename, but keep full values in JSON)
            safe_command_name = self._sanitize_filename(command)
            safe_package_name = self._sanitize_filename(app_package)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Truncate the filename if it's too long, but keep full data in JSON
            max_filename_length = 200
            if len(safe_command_name) > max_filename_length:
                safe_command_name = f"{safe_command_name[:100]}...{safe_command_name[-50:]}"
            if len(safe_package_name) > max_filename_length:
                safe_package_name = f"{safe_package_name[:100]}...{safe_package_name[-50:]}"
                
            filename = f"command_package_stats_{safe_package_name}_{safe_command_name}_{timestamp}.json"
            filepath = os.path.join(self.output_dir, filename)
            
            # Save file with full command and package in the JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(command_package_report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Generated command+package file: {filename}")
            
        except Exception as e:
            logger.error(f"Failed to generate file for command '{command}' + package '{app_package}': {e}")
    
    def generate_all_files(self):
        """Generate files for all commands and command+package combinations"""
        logger.info("Generating individual command files...")
        for command, stats in self.command_stats.items():
            self.generate_individual_command_file(command, stats)
        
        logger.info("Generating command+package files...")
        for (command, package), stats in self.command_package_stats.items():
            self.generate_command_package_file(command, package, stats)
    
    def generate_summary_report(self):
        """Generate summary report of the bulk analysis"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        summary = {
            "bulk_analysis_summary": {
                "scan_timestamp": self.start_time.isoformat(),
                "completion_timestamp": end_time.isoformat(),
                "duration_seconds": duration,
                "total_steps_processed": self.total_steps_processed,
                "unique_commands_found": len(self.command_stats),
                "command_package_combinations": len(self.command_package_stats),
                "individual_command_files_generated": len(self.command_stats),
                "command_package_files_generated": len(self.command_package_stats)
            },
            "command_list": list(self.command_stats.keys()),
            "command_package_combinations": [
                f"{command}|{package}" 
                for (command, package) in self.command_package_stats.keys()
            ]
        }
        
        summary_file = os.path.join(self.output_dir, "bulk_analysis_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Bulk analysis summary saved to: {summary_file}")
        return summary


def run_bulk_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    output_dir: Optional[str] = None,
    generate_individual: bool = True,
    generate_command_package: bool = True,
    batch_size: int = 1000
) -> Dict[str, Any]:
    """
    Run bulk analysis with single-pass DynamoDB scan.
    
    CORRECT IMPLEMENTATION following the exact plan:
    1. Single DB read with pagination (generator)
    2. For each row: Update count and ALL stats if command exists, or add new command
    3. No storing raw data - just incremental updates
    4. Generate files at the end with final aggregated stats
    
    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter  
        output_dir: Output directory for reports
        generate_individual: Whether to generate individual command files
        generate_command_package: Whether to generate command+package files
        batch_size: Number of steps to process before logging progress
        
    Returns:
        Summary of the analysis
    """
    aggregator = BulkCommandAggregator(output_dir)
    
    logger.info("Starting bulk command analysis with single-pass DynamoDB scan")
    logger.info(f"Individual command files: {generate_individual}")
    logger.info(f"Command+Package files: {generate_command_package}")
    
    try:
        # Single pass through DynamoDB with pagination (generator)
        for item in scan_test_steps_with_pagination():
            aggregator.total_steps_processed += 1
            step_data = convert_dynamodb_item_to_dict(item)
            
            # Update both aggregators with incremental updates
            # Pass both converted dict (for easy access) and original DynamoDB format (for classification)
            if generate_individual:
                aggregator.update_command_stats(step_data, item)
            
            if generate_command_package:
                aggregator.update_command_package_stats(step_data, item)
            
            # Log progress periodically
            if aggregator.total_steps_processed % batch_size == 0:
                logger.info(f"Processed {aggregator.total_steps_processed} steps, "
                          f"{len(aggregator.command_stats)} unique commands, "
                          f"{len(aggregator.command_package_stats)} command+package combinations")
        
        # Generate all files at the end with final aggregated stats
        aggregator.generate_all_files()
        
        # Generate summary
        summary = aggregator.generate_summary_report()
        
        logger.info("Bulk analysis complete!")
        return summary
        
    except Exception as e:
        logger.error(f"Bulk analysis failed: {e}")
        raise