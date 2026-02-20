#!/bin/bash
# AP2 Travel Agent - Startup Script
# This script starts all backend agents and the frontend development server
#
# Usage:
#   ./start.sh           - Interactive startup with env configuration
#   ./start.sh --quick   - Skip env configuration (use existing or defaults)
#   ./start.sh --help    - Show this help

set -e

# Parse command line arguments
SKIP_ENV_CONFIG=false
for arg in "$@"; do
    case $arg in
        --quick|-q)
            SKIP_ENV_CONFIG=true
            shift
            ;;
        --help|-h)
            echo "AP2 Travel Agent - Startup Script"
            echo ""
            echo "Usage:"
            echo "  ./start.sh           Interactive startup with env configuration"
            echo "  ./start.sh --quick   Skip env configuration prompts"
            echo "  ./start.sh --help    Show this help"
            exit 0
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Log directory
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     AP2 Travel Agent - Multi-Agent Checkout Demo          ║"
echo "║                                                           ║"
echo "║  🛫 Shopping Agent    →  Port 8000                        ║"
echo "║  🏪 Merchant Agent    →  Port 8001                        ║"
echo "║  💳 Credentials Agent →  Port 8002                        ║"
echo "║  💵 Payment Agent     →  Port 8003                        ║"
echo "║  🌐 Frontend          →  Port 5173                        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# Environment Configuration
# ============================================================================
configure_env() {
    local ENV_FILE="$SCRIPT_DIR/.env"
    local ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

    echo -e "\n${BLUE}[0/6] Environment Configuration...${NC}"

    if [ ! -f "$ENV_EXAMPLE" ]; then
        echo -e "${YELLOW}⚠ .env.example not found, skipping env configuration${NC}"
        return
    fi

    if [ -f "$ENV_FILE" ]; then
        # .env exists - ask user what to do
        echo -e "${GREEN}✓ Found existing .env file${NC}"
        echo ""
        echo -e "${CYAN}What would you like to do?${NC}"
        echo "  1) Skip - Use existing configuration"
        echo "  2) Verify - Show current values"
        echo "  3) Modify - Update configuration"
        echo "  4) Reset - Start fresh from .env.example"
        echo ""
        read -p "Enter choice [1-4, default: 1]: " env_choice
        env_choice=${env_choice:-1}

        case $env_choice in
            1)
                echo -e "${GREEN}✓ Using existing .env configuration${NC}"
                return
                ;;
            2)
                echo -e "\n${CYAN}Current .env configuration:${NC}"
                echo "────────────────────────────────────────"
                grep -v "^#" "$ENV_FILE" | grep -v "^$" | while read line; do
                    # Mask sensitive values
                    if echo "$line" | grep -qiE "(secret|key|password|token)"; then
                        key=$(echo "$line" | cut -d'=' -f1)
                        echo -e "${YELLOW}$key=${NC}********"
                    else
                        echo -e "${GREEN}$line${NC}"
                    fi
                done
                echo "────────────────────────────────────────"
                echo ""
                read -p "Press Enter to continue with these settings, or 'm' to modify: " verify_choice
                if [ "$verify_choice" = "m" ] || [ "$verify_choice" = "M" ]; then
                    prompt_env_values
                fi
                return
                ;;
            3)
                prompt_env_values
                return
                ;;
            4)
                echo -e "${YELLOW}Resetting .env from template...${NC}"
                cp "$ENV_EXAMPLE" "$ENV_FILE"
                prompt_env_values
                return
                ;;
            *)
                echo -e "${GREEN}✓ Using existing .env configuration${NC}"
                return
                ;;
        esac
    else
        # No .env file - create one
        echo -e "${YELLOW}No .env file found. Creating from template...${NC}"
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo ""
        echo -e "${CYAN}Would you like to configure the environment now?${NC}"
        echo "  1) Use defaults (recommended for quick start)"
        echo "  2) Configure values"
        echo ""
        read -p "Enter choice [1-2, default: 1]: " create_choice
        create_choice=${create_choice:-1}

        if [ "$create_choice" = "2" ]; then
            prompt_env_values
        else
            echo -e "${GREEN}✓ Created .env with default values${NC}"
        fi
    fi
}

prompt_env_values() {
    local ENV_FILE="$SCRIPT_DIR/.env"
    local temp_env=$(mktemp)
    cp "$ENV_FILE" "$temp_env"

    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║           Environment Configuration                       ║${NC}"
    echo -e "${CYAN}║  Press Enter to keep default/current value                ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # OpenRouter Configuration
    echo -e "${BLUE}── OpenRouter Configuration ──${NC}"

    current_val=$(grep "^OPENROUTER_API_KEY=" "$temp_env" | cut -d'=' -f2-)
    read -p "OpenRouter API Key [${current_val:0:20}...]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$new_val|" "$temp_env"

    current_val=$(grep "^OPENROUTER_MODEL=" "$temp_env" | cut -d'=' -f2-)
    read -p "OpenRouter Model [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^OPENROUTER_MODEL=.*|OPENROUTER_MODEL=$new_val|" "$temp_env"

    current_val=$(grep "^OPENROUTER_TIMEOUT=" "$temp_env" | cut -d'=' -f2-)
    read -p "OpenRouter Timeout (seconds) [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^OPENROUTER_TIMEOUT=.*|OPENROUTER_TIMEOUT=$new_val|" "$temp_env"

    # Server Ports
    echo ""
    echo -e "${BLUE}── Server Ports ──${NC}"

    current_val=$(grep "^SHOPPING_AGENT_PORT=" "$temp_env" | cut -d'=' -f2-)
    read -p "Shopping Agent Port [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^SHOPPING_AGENT_PORT=.*|SHOPPING_AGENT_PORT=$new_val|" "$temp_env"

    current_val=$(grep "^MERCHANT_AGENT_PORT=" "$temp_env" | cut -d'=' -f2-)
    read -p "Merchant Agent Port [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^MERCHANT_AGENT_PORT=.*|MERCHANT_AGENT_PORT=$new_val|" "$temp_env"

    current_val=$(grep "^CREDENTIALS_AGENT_PORT=" "$temp_env" | cut -d'=' -f2-)
    read -p "Credentials Agent Port [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^CREDENTIALS_AGENT_PORT=.*|CREDENTIALS_AGENT_PORT=$new_val|" "$temp_env"

    current_val=$(grep "^PAYMENT_AGENT_PORT=" "$temp_env" | cut -d'=' -f2-)
    read -p "Payment Agent Port [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^PAYMENT_AGENT_PORT=.*|PAYMENT_AGENT_PORT=$new_val|" "$temp_env"

    current_val=$(grep "^FRONTEND_PORT=" "$temp_env" | cut -d'=' -f2-)
    read -p "Frontend Port [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^FRONTEND_PORT=.*|FRONTEND_PORT=$new_val|" "$temp_env"

    # Wallet Configuration
    echo ""
    echo -e "${BLUE}── Wallet Configuration (AP2 Payment Signing) ──${NC}"

    current_val=$(grep "^WALLET_ADDRESS=" "$temp_env" | cut -d'=' -f2-)
    read -p "Wallet Address [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^WALLET_ADDRESS=.*|WALLET_ADDRESS=$new_val|" "$temp_env"

    echo -e "${YELLOW}Note: Private key will be masked for security${NC}"
    current_val=$(grep "^WALLET_PRIVATE_KEY=" "$temp_env" | cut -d'=' -f2-)
    if [ "$current_val" = "your_private_key_here" ]; then
        read -s -p "Wallet Private Key [not set]: " new_val
    else
        read -s -p "Wallet Private Key [****hidden****]: " new_val
    fi
    echo ""
    [ -n "$new_val" ] && sed -i.bak "s|^WALLET_PRIVATE_KEY=.*|WALLET_PRIVATE_KEY=$new_val|" "$temp_env"

    # Advanced Settings
    echo ""
    echo -e "${BLUE}── Advanced Settings ──${NC}"

    current_val=$(grep "^LOG_LEVEL=" "$temp_env" | cut -d'=' -f2-)
    read -p "Log Level (DEBUG/INFO/WARNING/ERROR) [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^LOG_LEVEL=.*|LOG_LEVEL=$new_val|" "$temp_env"

    current_val=$(grep "^AP2_MANDATE_TTL_MINUTES=" "$temp_env" | cut -d'=' -f2-)
    read -p "AP2 Mandate TTL (minutes) [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^AP2_MANDATE_TTL_MINUTES=.*|AP2_MANDATE_TTL_MINUTES=$new_val|" "$temp_env"

    current_val=$(grep "^DEMO_MODE=" "$temp_env" | cut -d'=' -f2-)
    read -p "Demo Mode (true/false) [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^DEMO_MODE=.*|DEMO_MODE=$new_val|" "$temp_env"

    # LLM Package Generation
    current_val=$(grep "^USE_LLM_FOR_PACKAGES=" "$temp_env" | cut -d'=' -f2-)
    if [ -z "$current_val" ]; then
        echo "USE_LLM_FOR_PACKAGES=false" >> "$temp_env"
        current_val="false"
    fi
    echo -e "${YELLOW}Note: LLM package generation can be slow (2+ minutes)${NC}"
    read -p "Use LLM for package generation (true/false) [$current_val]: " new_val
    [ -n "$new_val" ] && sed -i.bak "s|^USE_LLM_FOR_PACKAGES=.*|USE_LLM_FOR_PACKAGES=$new_val|" "$temp_env"

    # Copy temp file back and cleanup
    mv "$temp_env" "$ENV_FILE"
    rm -f "$temp_env.bak" 2>/dev/null

    echo ""
    echo -e "${GREEN}✓ Environment configuration saved to .env${NC}"
}

# Run environment configuration
if [ "$SKIP_ENV_CONFIG" = true ]; then
    echo -e "\n${BLUE}[0/6] Environment Configuration...${NC}"
    if [ ! -f "$SCRIPT_DIR/.env" ] && [ -f "$SCRIPT_DIR/.env.example" ]; then
        echo -e "${YELLOW}Creating .env from template with defaults...${NC}"
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    fi
    echo -e "${GREEN}✓ Using existing .env configuration (--quick mode)${NC}"
else
    configure_env
fi

# Check for required commands
echo -e "\n${BLUE}[1/6] Checking dependencies...${NC}"

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}✗ $1 is not installed${NC}"
        return 1
    else
        echo -e "${GREEN}✓ $1 found${NC}"
        return 0
    fi
}

MISSING_DEPS=0
check_command python3 || MISSING_DEPS=1
check_command node || MISSING_DEPS=1
check_command npm || MISSING_DEPS=1

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "${RED}Please install missing dependencies and try again.${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Check Node version
NODE_VERSION=$(node --version)
echo -e "${GREEN}✓ Node $NODE_VERSION${NC}"

# Check OpenRouter API key
echo -e "\n${BLUE}[2/6] Checking OpenRouter configuration...${NC}"
if grep -q "^OPENROUTER_API_KEY=" "$SCRIPT_DIR/.env" 2>/dev/null; then
    API_KEY=$(grep "^OPENROUTER_API_KEY=" "$SCRIPT_DIR/.env" | cut -d'=' -f2-)
    if [ -n "$API_KEY" ] && [ "$API_KEY" != "your_openrouter_api_key_here" ]; then
        echo -e "${GREEN}✓ OpenRouter API key configured${NC}"
        MODEL=$(grep "^OPENROUTER_MODEL=" "$SCRIPT_DIR/.env" | cut -d'=' -f2-)
        echo -e "${GREEN}✓ Model: ${MODEL:-arcee-ai/trinity-large-preview:free}${NC}"
    else
        echo -e "${YELLOW}⚠ OpenRouter API key not set - will use mock responses${NC}"
        echo -e "${YELLOW}  Set OPENROUTER_API_KEY in .env to enable LLM features${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No .env file found - will use mock responses${NC}"
fi

# Install Python dependencies
echo -e "\n${BLUE}[3/6] Installing Python dependencies...${NC}"
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Install frontend dependencies
echo -e "\n${BLUE}[4/6] Installing frontend dependencies...${NC}"
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    npm install
else
    echo -e "${GREEN}✓ node_modules already exists${NC}"
fi

# Kill any existing processes on our ports
echo -e "\n${BLUE}[5/6] Cleaning up existing processes...${NC}"
for PORT in 8000 8001 8002 8003 5173; do
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}Killing process on port $PORT (PID: $PID)${NC}"
        kill -9 $PID 2>/dev/null || true
    fi
done
sleep 1

# Start backend agents
echo -e "\n${BLUE}[6/6] Starting services...${NC}"
cd "$SCRIPT_DIR/backend"
source venv/bin/activate

# Start Shopping Agent (Port 8000)
echo -e "${CYAN}Starting Shopping Agent on port 8000...${NC}"
python -m uvicorn servers.shopping_server:app --host 0.0.0.0 --port 8000 --reload &> "$LOG_DIR/shopping_agent.log" &
SHOPPING_PID=$!
echo $SHOPPING_PID > "$LOG_DIR/shopping_agent.pid"

# Start Merchant Agent (Port 8001)
echo -e "${CYAN}Starting Merchant Agent on port 8001...${NC}"
python -m uvicorn servers.merchant_server:app --host 0.0.0.0 --port 8001 --reload &> "$LOG_DIR/merchant_agent.log" &
MERCHANT_PID=$!
echo $MERCHANT_PID > "$LOG_DIR/merchant_agent.pid"

# Start Credentials Agent (Port 8002)
echo -e "${CYAN}Starting Credentials Agent on port 8002...${NC}"
python -m uvicorn servers.credentials_server:app --host 0.0.0.0 --port 8002 --reload &> "$LOG_DIR/credentials_agent.log" &
CREDENTIALS_PID=$!
echo $CREDENTIALS_PID > "$LOG_DIR/credentials_agent.pid"

# Start Payment Agent (Port 8003)
echo -e "${CYAN}Starting Payment Agent on port 8003...${NC}"
python -m uvicorn servers.payment_server:app --host 0.0.0.0 --port 8003 --reload &> "$LOG_DIR/payment_agent.log" &
PAYMENT_PID=$!
echo $PAYMENT_PID > "$LOG_DIR/payment_agent.pid"

# Wait for backend agents to start
echo -e "\n${YELLOW}Waiting for agents to initialize...${NC}"
sleep 3

# Check agent health
check_agent() {
    local name=$1
    local port=$2

    if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ $name is healthy (port $port)${NC}"
        return 0
    else
        echo -e "${RED}✗ $name failed to start (port $port)${NC}"
        return 1
    fi
}

echo -e "\n${BLUE}Checking agent health...${NC}"
check_agent "Shopping Agent" 8000
check_agent "Merchant Agent" 8001
check_agent "Credentials Agent" 8002
check_agent "Payment Agent" 8003

# Start frontend
echo -e "\n${CYAN}Starting frontend development server on port 5173...${NC}"
cd "$SCRIPT_DIR/frontend"
npm run dev &> "$LOG_DIR/frontend.log" &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"

sleep 3

# Final status
echo -e "\n${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                  ✓ All Services Started                   ║"
echo "╠═══════════════════════════════════════════════════════════╣"
echo "║                                                           ║"
echo "║  🌐 Frontend:     http://localhost:5173                   ║"
echo "║                                                           ║"
echo "║  📡 Agent Cards:                                          ║"
echo "║     • http://localhost:8000/.well-known/agent.json        ║"
echo "║     • http://localhost:8001/.well-known/agent.json        ║"
echo "║     • http://localhost:8002/.well-known/agent.json        ║"
echo "║     • http://localhost:8003/.well-known/agent.json        ║"
echo "║                                                           ║"
echo "║  📋 Logs: $LOG_DIR                                        ║"
echo "║                                                           ║"
echo "║  To stop all services: ./stop.sh                          ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Open browser (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${BLUE}Opening browser...${NC}"
    sleep 2
    open http://localhost:5173
fi

echo -e "${YELLOW}Press Ctrl+C to stop watching logs (services will continue running)${NC}"
echo ""

# Tail logs
tail -f "$LOG_DIR"/*.log 2>/dev/null || true
