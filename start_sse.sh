#!/bin/bash

# Start SSE Server Script for MCP Jira Confluence
# This script starts the SSE server with proper environment configuration

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PORT=${PORT:-8000}
HOST=${HOST:-127.0.0.1}
LOG_LEVEL=${LOG_LEVEL:-info}
RELOAD=${RELOAD:-false}

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if environment variables are set
check_env_vars() {
    local missing_vars=()
    
    # Check Jira configuration
    if [[ -z "$JIRA_URL" ]]; then
        missing_vars+=("JIRA_URL")
    fi
    
    # Note: Authentication can be provided via client headers or server environment
    if [[ -z "$JIRA_PERSONAL_TOKEN" ]] && ([[ -z "$JIRA_USERNAME" ]] || [[ -z "$JIRA_API_TOKEN" ]]); then
        print_warning "No Jira authentication found in environment"
        print_info "You can either:"
        print_info "  1. Set JIRA_PERSONAL_TOKEN (or JIRA_USERNAME + JIRA_API_TOKEN)"
        print_info "  2. Pass authentication via HTTP headers from MCP client"
    fi
    
    # Check Confluence configuration
    if [[ -z "$CONFLUENCE_URL" ]]; then
        missing_vars+=("CONFLUENCE_URL")
    fi
    
    if [[ -z "$CONFLUENCE_PERSONAL_TOKEN" ]] && ([[ -z "$CONFLUENCE_USERNAME" ]] || [[ -z "$CONFLUENCE_API_TOKEN" ]]); then
        print_warning "No Confluence authentication found in environment"
        print_info "You can either:"
        print_info "  1. Set CONFLUENCE_PERSONAL_TOKEN (or CONFLUENCE_USERNAME + CONFLUENCE_API_TOKEN)"
        print_info "  2. Pass authentication via HTTP headers from MCP client"
    fi
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        print_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        print_info "Please set the environment variables or create a .env file"
        print_info "See .env.example for reference"
        print_info "Note: Authentication tokens can also be passed from MCP clients via HTTP headers"
        return 1
    fi
    
    return 0
}

# Function to load .env file if it exists
load_env_file() {
    if [[ -f ".env" ]]; then
        print_info "Loading environment variables from .env file"
        set -a  # automatically export all variables
        source .env
        set +a
    elif [[ -f ".env.example" ]]; then
        print_warning ".env file not found, but .env.example exists"
        print_info "Consider copying .env.example to .env and filling in your credentials"
    fi
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Start the MCP Jira Confluence SSE Server"
    echo ""
    echo "Options:"
    echo "  -h, --help         Show this help message"
    echo "  -p, --port PORT    Port to run server on (default: 8000)"
    echo "  -H, --host HOST    Host to bind to (default: 127.0.0.1)"
    echo "  -l, --log LOG      Log level (debug, info, warning, error) (default: info)"
    echo "  -r, --reload       Enable auto-reload for development (default: false)"
    echo "  --dev             Development mode (enables reload and debug logging)"
    echo ""
    echo "Environment Variables:"
    echo "  JIRA_URL                    Your Jira instance URL"
    echo "  JIRA_USERNAME               Your Jira username/email"
    echo "  JIRA_API_TOKEN              Your Jira API token"
    echo "  JIRA_PERSONAL_TOKEN         Alternative to username/token"
    echo "  CONFLUENCE_URL              Your Confluence instance URL"
    echo "  CONFLUENCE_USERNAME         Your Confluence username/email"
    echo "  CONFLUENCE_API_TOKEN        Your Confluence API token"
    echo "  CONFLUENCE_PERSONAL_TOKEN   Alternative to username/token"
    echo ""
    echo "Examples:"
    echo "  $0                          # Start with default settings"
    echo "  $0 --port 3000              # Start on port 3000"
    echo "  $0 --dev                    # Start in development mode"
    echo "  $0 --host 0.0.0.0 --port 8080  # Bind to all interfaces on port 8080"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -H|--host)
            HOST="$2"
            shift 2
            ;;
        -l|--log)
            LOG_LEVEL="$2"
            shift 2
            ;;
        -r|--reload)
            RELOAD=true
            shift
            ;;
        --dev)
            RELOAD=true
            LOG_LEVEL=debug
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_info "Starting MCP Jira Confluence SSE Server..."
    echo ""
    
    # Load environment variables
    load_env_file
    
    # Check if we're in the right directory
    if [[ ! -f "src/mcp_jira_confluence/sse_server.py" ]]; then
        print_error "SSE server file not found. Please run this script from the project root directory."
        exit 1
    fi
    
    # Check environment variables
    if ! check_env_vars; then
        exit 1
    fi
    
    print_success "Environment variables configured"
    
    # Install package in development mode if needed
    if [[ ! -d "venv" ]] && ! python -c "import mcp_jira_confluence" 2>/dev/null; then
        print_info "Installing package in development mode..."
        pip install -e . || {
            print_error "Failed to install package"
            exit 1
        }
    fi
    
    # Build uvicorn command
    local uvicorn_cmd="uvicorn"
    local uvicorn_args=(
        "mcp_jira_confluence.sse_server:app"
        "--host" "$HOST"
        "--port" "$PORT"
        "--log-level" "$LOG_LEVEL"
    )
    
    if [[ "$RELOAD" == "true" ]]; then
        uvicorn_args+=("--reload")
        print_info "Development mode enabled (auto-reload)"
    fi
    
    # Show configuration
    echo ""
    print_info "Server Configuration:"
    echo "  Host: $HOST"
    echo "  Port: $PORT"
    echo "  Log Level: $LOG_LEVEL"
    echo "  Reload: $RELOAD"
    echo "  Jira URL: ${JIRA_URL}"
    echo "  Confluence URL: ${CONFLUENCE_URL}"
    echo ""
    
    print_info "Server will be available at:"
    echo "  • Health Check: http://$HOST:$PORT/health"
    echo "  • SSE Endpoint: http://$HOST:$PORT/sse"
    echo "  • MCP Endpoint: http://$HOST:$PORT/mcp"
    echo "  • Metrics: http://$HOST:$PORT/metrics"
    echo ""
    
    print_success "Starting server..."
    echo ""
    
    # Start the server
    exec "$uvicorn_cmd" "${uvicorn_args[@]}"
}

# Handle Ctrl+C gracefully
trap 'print_info "Shutting down server..."; exit 0' INT TERM

# Run main function
main "$@"
