#!/usr/bin/env python3
"""
Unified Server Startup Script for Cache Failure Classification System UI

This script starts both the Flask API server and React development server simultaneously.
It provides process monitoring, error handling, and graceful shutdown.
"""

import os
import sys
import subprocess
import time
import signal
import threading
import json
from pathlib import Path
from datetime import datetime

class ServerManager:
    def __init__(self):
        self.project_root = Path(__file__).parent.absolute()
        self.ui_dir = self.project_root / "ui"
        self.processes = []
        self.running = True
        
    def log(self, message, level="INFO"):
        """Log messages with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def check_prerequisites(self):
        """Check if all prerequisites are met"""
        self.log("Checking prerequisites...")
        
        # Check and free up ports
        self.free_up_ports()
        
        # Check if UI directory exists
        if not self.ui_dir.exists():
            self.log("❌ UI directory not found. Please run the setup first.", "ERROR")
            return False
        
        # Check if node_modules exists
        node_modules = self.ui_dir / "node_modules"
        if not node_modules.exists():
            self.log("❌ Node modules not found. Installing dependencies...", "WARN")
            try:
                subprocess.run(["npm", "install"], cwd=self.ui_dir, check=True)
                self.log("✅ Node modules installed successfully", "SUCCESS")
            except subprocess.CalledProcessError:
                self.log("❌ Failed to install node modules", "ERROR")
                return False
        
        # Check if virtual environment is activated
        if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            self.log("⚠️  Virtual environment not detected. Make sure to activate it first.", "WARN")
        
        # Check if API dependencies are installed
        try:
            import flask
            import flask_cors
            self.log("✅ API dependencies found", "SUCCESS")
        except ImportError:
            self.log("❌ API dependencies not found. Installing...", "WARN")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "api_requirements.txt"], 
                             cwd=self.project_root, check=True)
                self.log("✅ API dependencies installed successfully", "SUCCESS")
            except subprocess.CalledProcessError:
                self.log("❌ Failed to install API dependencies", "ERROR")
                return False
        
        return True
    
    def free_up_ports(self):
        """Free up ports 5000 and 3000 if they're in use"""
        import subprocess
        
        self.log("🔍 Checking for port conflicts...")
        
        # Check port 5000
        try:
            result = subprocess.run(['lsof', '-ti:5000'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                self.log(f"⚠️  Port 5000 is in use by PIDs: {', '.join(pids)}. Freeing up...", "WARN")
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-9', pid], check=True)
                        self.log(f"✅ Killed process {pid} on port 5000", "SUCCESS")
                    except:
                        pass
        except:
            pass
        
        # Check port 3000
        try:
            result = subprocess.run(['lsof', '-ti:3000'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                self.log(f"⚠️  Port 3000 is in use by PIDs: {', '.join(pids)}. Freeing up...", "WARN")
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-9', pid], check=True)
                        self.log(f"✅ Killed process {pid} on port 3000", "SUCCESS")
                    except:
                        pass
        except:
            pass
        
        self.log("✅ Port check complete", "SUCCESS")
    
    def start_api_server(self):
        """Start the Flask API server"""
        self.log("🚀 Starting Flask API server...")
        
        try:
            # Set environment variables for the API server
            env = os.environ.copy()
            env['FLASK_ENV'] = 'development'
            env['FLASK_DEBUG'] = '1'
            
            process = subprocess.Popen(
                [sys.executable, "api_server.py"],
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                env=env
            )
            
            self.processes.append(("API Server", process))
            self.log("✅ API Server started (PID: {})".format(process.pid), "SUCCESS")
            return process
            
        except Exception as e:
            self.log(f"❌ Failed to start API server: {e}", "ERROR")
            return None
    
    def start_react_app(self):
        """Start the React development server"""
        self.log("⚛️  Starting React development server...")
        
        try:
            # Set environment variables for React
            env = os.environ.copy()
            env['BROWSER'] = 'none'  # Don't auto-open browser
            env['PORT'] = '3000'
            
            process = subprocess.Popen(
                ["npm", "start"],
                cwd=self.ui_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                env=env
            )
            
            self.processes.append(("React App", process))
            self.log("✅ React App started (PID: {})".format(process.pid), "SUCCESS")
            return process
            
        except Exception as e:
            self.log(f"❌ Failed to start React app: {e}", "ERROR")
            return None
    
    def monitor_process(self, process, name):
        """Monitor a process and log its output"""
        try:
            for line in iter(process.stdout.readline, ''):
                if line and self.running:
                    # Clean up the line and log it
                    clean_line = line.strip()
                    if clean_line:
                        self.log(f"[{name}] {clean_line}")
        except Exception as e:
            if self.running:
                self.log(f"Error monitoring {name}: {e}", "ERROR")
    
    def wait_for_api_server(self, timeout=30):
        """Wait for API server to be ready"""
        self.log("⏳ Waiting for API server to be ready...")
        
        import requests
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get("http://localhost:5000/", timeout=2)
                if response.status_code == 200:
                    self.log("✅ API server is ready!", "SUCCESS")
                    return True
            except:
                pass
            
            time.sleep(1)
        
        self.log("❌ API server failed to start within timeout", "ERROR")
        return False
    
    def wait_for_react_app(self, timeout=60):
        """Wait for React app to be ready"""
        self.log("⏳ Waiting for React app to be ready...")
        
        import requests
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get("http://localhost:3000/", timeout=2)
                if response.status_code == 200:
                    self.log("✅ React app is ready!", "SUCCESS")
                    return True
            except:
                pass
            
            time.sleep(2)
        
        self.log("❌ React app failed to start within timeout", "ERROR")
        return False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.log("🛑 Shutdown signal received...", "WARN")
        self.running = False
        self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown all processes"""
        self.log("🛑 Shutting down servers...", "WARN")
        
        for name, process in self.processes:
            if process.poll() is None:  # Process is still running
                self.log(f"🛑 Stopping {name} (PID: {process.pid})...", "WARN")
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    self.log(f"✅ {name} stopped gracefully", "SUCCESS")
                except subprocess.TimeoutExpired:
                    self.log(f"⚠️  Force killing {name}...", "WARN")
                    process.kill()
                    process.wait()
                    self.log(f"✅ {name} force killed", "SUCCESS")
                except Exception as e:
                    self.log(f"❌ Error stopping {name}: {e}", "ERROR")
        
        self.log("✅ All servers stopped", "SUCCESS")
    
    def run(self):
        """Main execution function"""
        self.log("🚀 Starting Cache Failure Classification System UI")
        self.log("=" * 60)
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Check prerequisites
            if not self.check_prerequisites():
                self.log("❌ Prerequisites check failed", "ERROR")
                return 1
            
            # Start API server
            api_process = self.start_api_server()
            if not api_process:
                self.log("❌ Failed to start API server", "ERROR")
                return 1
            
            # Start API monitoring thread
            api_thread = threading.Thread(
                target=self.monitor_process, 
                args=(api_process, "API"),
                daemon=True
            )
            api_thread.start()
            
            # Wait for API server to be ready
            if not self.wait_for_api_server():
                self.log("❌ API server failed to start", "ERROR")
                return 1
            
            # Start React app
            react_process = self.start_react_app()
            if not react_process:
                self.log("❌ Failed to start React app", "ERROR")
                return 1
            
            # Start React monitoring thread
            react_thread = threading.Thread(
                target=self.monitor_process, 
                args=(react_process, "React"),
                daemon=True
            )
            react_thread.start()
            
            # Wait for React app to be ready
            if not self.wait_for_react_app():
                self.log("❌ React app failed to start", "ERROR")
                return 1
            
            # Success message
            self.log("🎉 Both servers are running successfully!", "SUCCESS")
            self.log("=" * 60)
            self.log("📡 API Server: http://localhost:5000", "INFO")
            self.log("⚛️  React App: http://localhost:3000", "INFO")
            self.log("=" * 60)
            self.log("Press Ctrl+C to stop both servers", "INFO")
            self.log("=" * 60)
            
            # Keep the main thread alive and monitor processes
            while self.running:
                time.sleep(1)
                
                # Check if any process has died
                for name, process in self.processes:
                    if process.poll() is not None:
                        self.log(f"❌ {name} has stopped unexpectedly (exit code: {process.returncode})", "ERROR")
                        self.running = False
                        break
                
                if not self.running:
                    break
            
            return 0
            
        except KeyboardInterrupt:
            self.log("🛑 Interrupted by user", "WARN")
            return 0
            
        except Exception as e:
            self.log(f"❌ Unexpected error: {e}", "ERROR")
            return 1
            
        finally:
            self.shutdown()

def main():
    """Main entry point"""
    manager = ServerManager()
    exit_code = manager.run()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
