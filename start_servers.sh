#!/bin/bash

# Cache Failure Classification System - Server Startup Script
# This script starts both the Flask API server and React development server

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✅ $1${NC}"
}

print_error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}[$(date +'%H:%M:%S')] ℹ️  $1${NC}"
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
UI_DIR="$PROJECT_ROOT/ui"

print_status "🚀 Starting Cache Failure Classification System UI"
echo "============================================================"

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/api_server.py" ]; then
    print_error "api_server.py not found. Please run this script from the project root directory."
    exit 1
fi

# Check if UI directory exists
if [ ! -d "$UI_DIR" ]; then
    print_error "UI directory not found. Please run the setup first."
    exit 1
fi

# Check if node_modules exists
if [ ! -d "$UI_DIR/node_modules" ]; then
    print_warning "Node modules not found. Installing dependencies..."
    cd "$UI_DIR"
    npm install
    if [ $? -eq 0 ]; then
        print_success "Node modules installed successfully"
    else
        print_error "Failed to install node modules"
        exit 1
    fi
    cd "$PROJECT_ROOT"
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "Virtual environment not detected. Make sure to activate it first."
    print_info "Run: source report/bin/activate"
fi

# Check if API dependencies are installed
print_status "Checking API dependencies..."
python3 -c "import flask, flask_cors" 2>/dev/null
if [ $? -ne 0 ]; then
    print_warning "API dependencies not found. Installing..."
    pip install -r api_requirements.txt
    if [ $? -eq 0 ]; then
        print_success "API dependencies installed successfully"
    else
        print_error "Failed to install API dependencies"
        exit 1
    fi
fi

# Function to cleanup processes on exit
cleanup() {
    print_warning "Shutting down servers..."
    
    if [ ! -z "$API_PID" ]; then
        print_status "Stopping API server (PID: $API_PID)..."
        kill $API_PID 2>/dev/null || true
        wait $API_PID 2>/dev/null || true
        print_success "API server stopped"
    fi
    
    if [ ! -z "$REACT_PID" ]; then
        print_status "Stopping React app (PID: $REACT_PID)..."
        kill $REACT_PID 2>/dev/null || true
        wait $REACT_PID 2>/dev/null || true
        print_success "React app stopped"
    fi
    
    print_success "All servers stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start API server
print_status "🚀 Starting Flask API server..."
cd "$PROJECT_ROOT"
python3 api_server.py &
API_PID=$!

# Wait a moment for API server to start
sleep 3

# Check if API server is running
if ! kill -0 $API_PID 2>/dev/null; then
    print_error "API server failed to start"
    exit 1
fi

print_success "API server started (PID: $API_PID)"

# Start React app
print_status "⚛️  Starting React development server..."
cd "$UI_DIR"
BROWSER=none npm start &
REACT_PID=$!

# Wait a moment for React app to start
sleep 5

# Check if React app is running
if ! kill -0 $REACT_PID 2>/dev/null; then
    print_error "React app failed to start"
    cleanup
    exit 1
fi

print_success "React app started (PID: $REACT_PID)"

# Success message
echo "============================================================"
print_success "🎉 Both servers are running successfully!"
echo "============================================================"
print_info "📡 API Server: http://localhost:5000"
print_info "⚛️  React App: http://localhost:3000"
echo "============================================================"
print_info "Press Ctrl+C to stop both servers"
echo "============================================================"

# Wait for processes
wait $API_PID $REACT_PID
