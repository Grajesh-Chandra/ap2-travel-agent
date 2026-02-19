#!/bin/bash
# AP2 Travel Agent - Stop Script
# This script stops all backend agents and frontend server
# Usage: ./stop.sh [--clean] [--full-clean]
#   --clean      Remove venv and node_modules
#   --full-clean Remove venv, node_modules, logs, and __pycache__

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

# Parse arguments
CLEAN=false
FULL_CLEAN=false
for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN=true
            ;;
        --full-clean)
            CLEAN=true
            FULL_CLEAN=true
            ;;
    esac
done

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║       AP2 Travel Agent - Stopping All Services            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Function to stop a service by PID file
stop_service() {
    local name=$1
    local pidfile=$2

    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Stopping $name (PID: $PID)...${NC}"
            kill $PID 2>/dev/null || true
            sleep 1

            # Force kill if still running
            if ps -p $PID > /dev/null 2>&1; then
                echo -e "${RED}Force killing $name...${NC}"
                kill -9 $PID 2>/dev/null || true
            fi

            echo -e "${GREEN}✓ $name stopped${NC}"
        else
            echo -e "${YELLOW}$name was not running${NC}"
        fi
        rm -f "$pidfile"
    else
        echo -e "${YELLOW}No PID file for $name${NC}"
    fi
}

# Stop services using PID files
echo -e "\n${BLUE}Stopping services...${NC}"
stop_service "Shopping Agent" "$LOG_DIR/shopping_agent.pid"
stop_service "Merchant Agent" "$LOG_DIR/merchant_agent.pid"
stop_service "Credentials Agent" "$LOG_DIR/credentials_agent.pid"
stop_service "Payment Agent" "$LOG_DIR/payment_agent.pid"
stop_service "Frontend" "$LOG_DIR/frontend.pid"

# Also check ports directly
echo -e "\n${BLUE}Checking ports...${NC}"
for PORT in 8000 8001 8002 8003 5173; do
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}Killing process on port $PORT (PID: $PID)${NC}"
        kill -9 $PID 2>/dev/null || true
    else
        echo -e "${GREEN}✓ Port $PORT is free${NC}"
    fi
done

# Archive logs
echo -e "\n${BLUE}Archiving logs...${NC}"
if [ -d "$LOG_DIR" ] && [ "$(ls -A $LOG_DIR 2>/dev/null)" ]; then
    ARCHIVE_DIR="$LOG_DIR/archive"
    mkdir -p "$ARCHIVE_DIR"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    ARCHIVE_NAME="logs_$TIMESTAMP.tar.gz"

    # Create archive of current logs
    cd "$LOG_DIR"
    tar -czf "$ARCHIVE_DIR/$ARCHIVE_NAME" *.log 2>/dev/null || true

    # Remove old log files
    rm -f "$LOG_DIR"/*.log

    echo -e "${GREEN}✓ Logs archived to $ARCHIVE_DIR/$ARCHIVE_NAME${NC}"

    # Clean up old archives (keep last 10)
    cd "$ARCHIVE_DIR"
    ls -t | tail -n +11 | xargs -I {} rm -f {} 2>/dev/null || true
else
    echo -e "${YELLOW}No logs to archive${NC}"
fi

# Clean up venv and node_modules if requested
if [ "$CLEAN" = true ]; then
    echo -e "\n${BLUE}Cleaning up development artifacts...${NC}"

    # Remove Python virtual environment
    if [ -d "$SCRIPT_DIR/backend/venv" ]; then
        echo -e "${YELLOW}Removing Python virtual environment...${NC}"
        rm -rf "$SCRIPT_DIR/backend/venv"
        echo -e "${GREEN}✓ venv removed${NC}"
    else
        echo -e "${YELLOW}No venv found${NC}"
    fi

    # Remove node_modules
    if [ -d "$SCRIPT_DIR/frontend/node_modules" ]; then
        echo -e "${YELLOW}Removing node_modules...${NC}"
        rm -rf "$SCRIPT_DIR/frontend/node_modules"
        echo -e "${GREEN}✓ node_modules removed${NC}"
    else
        echo -e "${YELLOW}No node_modules found${NC}"
    fi

    # Remove __pycache__ directories
    echo -e "${YELLOW}Removing __pycache__ directories...${NC}"
    find "$SCRIPT_DIR/backend" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}✓ __pycache__ cleaned${NC}"
fi

# Full clean - remove logs as well
if [ "$FULL_CLEAN" = true ]; then
    echo -e "\n${BLUE}Full cleanup...${NC}"

    # Remove logs directory entirely
    if [ -d "$LOG_DIR" ]; then
        echo -e "${YELLOW}Removing logs directory...${NC}"
        rm -rf "$LOG_DIR"
        echo -e "${GREEN}✓ logs removed${NC}"
    fi

    # Remove .pyc files
    find "$SCRIPT_DIR/backend" -type f -name "*.pyc" -delete 2>/dev/null || true

    # Remove frontend build artifacts
    if [ -d "$SCRIPT_DIR/frontend/dist" ]; then
        rm -rf "$SCRIPT_DIR/frontend/dist"
        echo -e "${GREEN}✓ frontend dist removed${NC}"
    fi
fi

echo -e "\n${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║              ✓ All Services Stopped                       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "To start again: ${CYAN}./start.sh${NC}" echo ""
echo -e "Cleanup options:"
echo -e "  ${CYAN}./stop.sh --clean${NC}       Remove venv and node_modules"
echo -e "  ${CYAN}./stop.sh --full-clean${NC}  Remove all artifacts including logs"