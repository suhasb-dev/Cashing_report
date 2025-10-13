"""
Flask API Server for Cache Failure Classification System UI

This server provides REST API endpoints to connect the React UI with the existing Python backend.
It acts as a bridge between the frontend and the DynamoDB analysis modules.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import existing modules
from bulk_analyzer import run_bulk_analysis
from command_stats import analyze_command_statistics, generate_command_stats_report
from command_stats.scanner import scan_command_steps_with_pagination
from utils import logger

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Configuration
API_VERSION = "v1"
DEFAULT_OUTPUT_DIR = "./cache_reports"

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Cache Failure Classification API",
        "version": API_VERSION,
        "timestamp": datetime.now().isoformat()
    })

@app.route(f'/api/{API_VERSION}/analyze-command', methods=['POST'])
def analyze_command():
    """
    Analyze cache performance for a specific command and package combination.
    
    Expected JSON payload:
    {
        "command": "Tap on Submit Button",
        "packageName": "in.swiggy.android.instamart",
        "startDate": "2025-10-08",  # Optional
        "endDate": "2025-10-08"     # Optional
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        command = data.get('command', '').strip()
        package_name = data.get('packageName', '').strip()
        start_date = data.get('startDate', '').strip() or None
        end_date = data.get('endDate', '').strip() or None
        
        if not command:
            return jsonify({"error": "Command is required"}), 400
        
        if not package_name:
            return jsonify({"error": "Package name is required"}), 400
        
        logger.info(f"Analyzing command: '{command}' in package: '{package_name}'")
        logger.info(f"Date range: {start_date} to {end_date}")
        
        # Use the existing command_stats module
        try:
            # First, scan DynamoDB to get the steps data
            logger.info(f"Scanning DynamoDB for command: '{command}' in package: '{package_name}'")
            steps = list(scan_command_steps_with_pagination(
                command=command,
                app_package=package_name,
                start_date=start_date,
                end_date=end_date
            ))
            
            if not steps:
                return jsonify({
                    "error": f"No data found for command '{command}' in package '{package_name}'",
                    "command": command,
                    "app_package": package_name,
                    "total_step_runs": 0
                }), 404
            
            logger.info(f"Found {len(steps)} steps for command '{command}'")
            
            # Now analyze the steps using the existing function
            report = analyze_command_statistics(
                steps=steps,
                command=command,
                app_package=package_name,
                start_date=start_date,
                end_date=end_date
            )
            
            # The report is already a dictionary, so we can return it directly
            # Just add some additional formatting for the UI
            result = report.copy()
            
            # Format percentages for better display (only if they're numbers)
            if 'cache_hit' in result and 'percentage' in result['cache_hit']:
                if isinstance(result['cache_hit']['percentage'], (int, float)):
                    result['cache_hit']['percentage'] = f"{result['cache_hit']['percentage']:.2f}%"
            
            if 'cache_miss' in result and 'percentage' in result['cache_miss']:
                if isinstance(result['cache_miss']['percentage'], (int, float)):
                    result['cache_miss']['percentage'] = f"{result['cache_miss']['percentage']:.2f}%"
                
                # Format breakdown percentages
                if 'breakdown' in result['cache_miss']:
                    for category, breakdown in result['cache_miss']['breakdown'].items():
                        if 'percentage' in breakdown and isinstance(breakdown['percentage'], (int, float)):
                            breakdown['percentage'] = f"{breakdown['percentage']:.2f}%"
            
            logger.info(f"Successfully analyzed command '{command}': {report['total_step_runs']} total runs")
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error analyzing command '{command}': {str(e)}")
            return jsonify({
                "error": f"Failed to analyze command: {str(e)}",
                "command": command,
                "app_package": package_name
            }), 500
    
    except Exception as e:
        logger.error(f"API error in analyze_command: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route(f'/api/{API_VERSION}/bulk-analyze', methods=['POST'])
def bulk_analyze():
    """
    Run bulk analysis across all commands in the DynamoDB table.
    
    Expected JSON payload:
    {
        "startDate": "2025-10-08",  # Optional
        "endDate": "2025-10-08",    # Optional
        "generateIndividual": true,  # Optional, default true
        "generateCommandPackage": true  # Optional, default true
    }
    """
    try:
        data = request.get_json() or {}
        
        start_date = data.get('startDate', '').strip() or None
        end_date = data.get('endDate', '').strip() or None
        generate_individual = data.get('generateIndividual', True)
        generate_command_package = data.get('generateCommandPackage', True)
        
        logger.info("Starting bulk analysis")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Generate individual: {generate_individual}")
        logger.info(f"Generate command+package: {generate_command_package}")
        
        # Create timestamped directory for this analysis run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_dir = os.path.join(DEFAULT_OUTPUT_DIR, f"analysis_{timestamp}")
        os.makedirs(analysis_dir, exist_ok=True)
        
        # Store metadata about this analysis run
        metadata = {
            "start_time": datetime.now().isoformat(),
            "start_date": start_date,
            "end_date": end_date,
            "generate_individual": generate_individual,
            "generate_command_package": generate_command_package,
            "output_directory": analysis_dir
        }
        
        with open(os.path.join(analysis_dir, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Run the analysis in the timestamped directory
        try:
            summary = run_bulk_analysis(
                start_date=start_date,
                end_date=end_date,
                output_dir=analysis_dir,
                generate_individual=generate_individual,
                generate_command_package=generate_command_package,
                batch_size=1000
            )
            
            # Update metadata with completion info
            metadata.update({
                "end_time": datetime.now().isoformat(),
                "status": "completed",
                "summary": summary
            })
            
            with open(os.path.join(analysis_dir, "metadata.json"), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Bulk analysis completed successfully in {analysis_dir}")
            return jsonify({
                "status": "success",
                "analysis_id": timestamp,
                "directory": analysis_dir,
                "summary": summary
            })
            
        except Exception as e:
            logger.error(f"Error in bulk analysis: {str(e)}")
            return jsonify({
                "error": f"Bulk analysis failed: {str(e)}",
                "bulk_analysis_summary": {
                    "scan_timestamp": datetime.now().isoformat(),
                    "completion_timestamp": datetime.now().isoformat(),
                    "duration_seconds": 0,
                    "total_steps_processed": 0,
                    "unique_commands_found": 0,
                    "command_package_combinations": 0,
                    "individual_command_files_generated": 0,
                    "command_package_files_generated": 0
                }
            }), 500
    
    except Exception as e:
        logger.error(f"API error in bulk_analyze: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route(f'/api/{API_VERSION}/reports', methods=['GET'])
def list_reports():
    """
    List all analysis runs and their reports in the cache_reports directory.
    Returns a list of analysis runs with their metadata and reports.
    """
    try:
        if not os.path.exists(DEFAULT_OUTPUT_DIR):
            os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
            return jsonify({"analyses": [], "message": "No analyses found"})
            
        analyses = []
        
        # Get all analysis directories (those starting with 'analysis_')
        analysis_dirs = [
            d for d in os.listdir(DEFAULT_OUTPUT_DIR) 
            if os.path.isdir(os.path.join(DEFAULT_OUTPUT_DIR, d)) and d.startswith('analysis_')
        ]
        
        # Sort by creation time (newest first)
        analysis_dirs.sort(key=lambda x: os.path.getmtime(os.path.join(DEFAULT_OUTPUT_DIR, x)), reverse=True)
        
        for analysis_dir in analysis_dirs:
            analysis_path = os.path.join(DEFAULT_OUTPUT_DIR, analysis_dir)
            metadata_path = os.path.join(analysis_path, 'metadata.json')
            
            # Load metadata if it exists
            metadata = {
                "id": analysis_dir.replace('analysis_', ''),
                "directory": analysis_dir,
                "status": "unknown",
                "start_time": os.path.getmtime(analysis_path),
                "reports": []
            }
            
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata.update(json.load(f))
                except Exception as e:
                    logger.warning(f"Error reading metadata for {analysis_dir}: {str(e)}")
            
            # List all JSON reports in this analysis directory
            reports = []
            for filename in os.listdir(analysis_path):
                if filename.endswith('.json') and filename != 'metadata.json':
                    file_path = os.path.join(analysis_path, filename)
                    try:
                        with open(file_path, 'r') as f:
                            report_data = json.load(f)
                            reports.append({
                                "filename": filename,
                                "path": file_path.replace(DEFAULT_OUTPUT_DIR, '').lstrip('/'),
                                "size": os.path.getsize(file_path),
                                "modified": os.path.getmtime(file_path),
                                "command": report_data.get('command', ''),
                                "app_package": report_data.get('app_package', '')
                            })
                    except Exception as e:
                        logger.warning(f"Error reading report {filename}: {str(e)}")
                        continue
            
            metadata["reports"] = reports
            analyses.append(metadata)
                    
        return jsonify({"analyses": analyses})
        
    except Exception as e:
        logger.error(f"Error listing analyses: {str(e)}")
        return jsonify({"error": f"Failed to list analyses: {str(e)}"}), 500

@app.route(f'/api/{API_VERSION}/reports/<path:filepath>', methods=['GET'])
def get_report(filepath):
    """
    Get the content of a specific report file within an analysis directory.
    The filepath should be in the format: analysis_<timestamp>/filename.json
    """
    try:
        if not filepath.endswith('.json') or '..' in filepath:
            return jsonify({"error": "Invalid file path"}), 400
            
        file_path = os.path.join(DEFAULT_OUTPUT_DIR, filepath)
        if not os.path.exists(file_path):
            return jsonify({"error": "Report not found"}), 404
            
        with open(file_path, 'r') as f:
            report_data = json.load(f)
            
        # Get the analysis directory name from the path
        analysis_dir = os.path.dirname(file_path)
        analysis_id = os.path.basename(analysis_dir).replace('analysis_', '')
        
        return jsonify({
            "analysis_id": analysis_id,
            "filename": os.path.basename(filepath),
            "path": filepath,
            "size": os.path.getsize(file_path),
            "modified": os.path.getmtime(file_path),
            "data": report_data
        })
        
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file"}), 400
    except Exception as e:
        logger.error(f"Error reading report {filepath}: {str(e)}")
        return jsonify({"error": f"Failed to read report: {str(e)}"}), 500

@app.route(f'/api/{API_VERSION}/system-info', methods=['GET'])
def system_info():
    """
    Get system information and configuration.
    """
    try:
        from config import (
            DYNAMODB_TABLE_NAME,
            AWS_REGION,
            STEP_CLASSIFICATIONS_FILTER,
            CACHE_READ_STATUS_FILTER,
            SIMILARITY_THRESHOLD
        )
        
        return jsonify({
            "dynamodb_table": DYNAMODB_TABLE_NAME,
            "aws_region": AWS_REGION,
            "step_classifications_filter": STEP_CLASSIFICATIONS_FILTER,
            "cache_read_status_filter": CACHE_READ_STATUS_FILTER,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "output_directory": DEFAULT_OUTPUT_DIR,
            "api_version": API_VERSION,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error getting system info: {str(e)}")
        return jsonify({"error": f"Failed to get system info: {str(e)}"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Create output directory if it doesn't exist
    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
    
    logger.info("Starting Cache Failure Classification API Server")
    logger.info(f"API Version: {API_VERSION}")
    logger.info(f"Output Directory: {DEFAULT_OUTPUT_DIR}")
    
    # Run the Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
