#!/usr/bin/env python3
"""
Startup script for the Cache Failure Classification System UI

This script starts both the Flask API server and the React development server.
It provides a unified way to launch the entire UI system.
"""

import os
import sys
import subprocess
import time
import signal
import threading
from pathlib import Path

def run_command(command, cwd=None, shell=True):
    """Run a command and return the process"""
    print(f"Running: {command}")
    if cwd:
        print(f"Working directory: {cwd}")
    
    process = subprocess.Popen(
        command,
        cwd=cwd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    return process

def monitor_process(process, name):
    """Monitor a process and print its output"""
    print(f"\n=== {name} Output ===")
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[{name}] {line.strip()}")
    except Exception as e:
        print(f"Error monitoring {name}: {e}")

def main():
    """Main function to start both servers"""
    project_root = Path(__file__).parent.absolute()
    ui_dir = project_root / "ui"
    
    print("🚀 Starting Cache Failure Classification System UI")
    print("=" * 60)
    
    # Check if UI directory exists
    if not ui_dir.exists():
        print("❌ UI directory not found. Please run the setup first.")
        sys.exit(1)
    
    # Check if node_modules exists
    node_modules = ui_dir / "node_modules"
    if not node_modules.exists():
        print("❌ Node modules not found. Please run 'npm install' in the ui directory first.")
        sys.exit(1)
    
    processes = []
    
    try:
        # Start Flask API server
        print("\n📡 Starting Flask API server...")
        api_process = run_command("python api_server.py", cwd=project_root)
        processes.append(("API Server", api_process))
        
        # Start API server monitoring thread
        api_thread = threading.Thread(
            target=monitor_process, 
            args=(api_process, "API")
        )
        api_thread.daemon = True
        api_thread.start()
        
        # Wait a moment for API server to start
        time.sleep(3)
        
        # Start React development server
        print("\n⚛️  Starting React development server...")
        react_process = run_command("npm start", cwd=ui_dir)
        processes.append(("React App", react_process))
        
        # Start React monitoring thread
        react_thread = threading.Thread(
            target=monitor_process, 
            args=(react_process, "React")
        )
        react_thread.daemon = True
        react_thread.start()
        
        print("\n" + "=" * 60)
        print("🎉 Both servers are starting up!")
        print("=" * 60)
        print("📡 API Server: http://localhost:5000")
        print("⚛️  React App: http://localhost:3000")
        print("=" * 60)
        print("Press Ctrl+C to stop both servers")
        print("=" * 60)
        
        # Wait for processes
        while True:
            time.sleep(1)
            
            # Check if any process has died
            for name, process in processes:
                if process.poll() is not None:
                    print(f"\n❌ {name} has stopped unexpectedly")
                    return_code = process.returncode
                    print(f"Return code: {return_code}")
                    break
            else:
                continue
            break
    
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down servers...")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    finally:
        # Clean up processes
        for name, process in processes:
            if process.poll() is None:  # Process is still running
                print(f"🛑 Stopping {name}...")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"⚠️  Force killing {name}...")
                    process.kill()
                except Exception as e:
                    print(f"Error stopping {name}: {e}")
        
        print("✅ All servers stopped")

if __name__ == "__main__":
    main()
