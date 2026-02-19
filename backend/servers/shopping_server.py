"""
Shopping Agent FastAPI Server - Port 8000
User-facing orchestrator for travel planning and AP2 checkout
"""

import json
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    CORS_ORIGINS,
    SHOPPING_AGENT_CARD,
    SHOPPING_AGENT_PORT,
    LOG_DIR,
)
from agents.shopping_agent import shopping_agent
from utils import get_logger, build_a2a_response, extract_mandate_from_message

logger = get_logger("ShoppingServer")

app = FastAPI(
    title="Voyager Shopping Agent",
    description="User-facing travel shopping orchestrator with AP2 checkout capability",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    user_id: str = "demo_user"
    session_id: Optional[str] = None


class PackageSelectionRequest(BaseModel):
    session_id: str
    package_id: str
    user_email: str = "user@example.com"
    user_name: str = "John Smith"


class PaymentMethodRequest(BaseModel):
    session_id: str


class CartMandateRequest(BaseModel):
    session_id: str
    payment_token: str


class ProcessPaymentRequest(BaseModel):
    session_id: str


# ═══════════════════════════════════════════════════════════════
# Well-Known & Health Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """Return the agent's well-known card for A2A discovery."""
    return SHOPPING_AGENT_CARD


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "shopping_agent",
        "port": SHOPPING_AGENT_PORT,
        "timestamp": datetime.utcnow().isoformat()
    }


# ═══════════════════════════════════════════════════════════════
# A2A Protocol Endpoint
# ═══════════════════════════════════════════════════════════════

@app.post("/a2a/shopping_agent")
async def a2a_endpoint(request: Request):
    """
    A2A JSON-RPC 2.0 endpoint for inter-agent communication.
    """
    try:
        body = await request.json()
        logger.info(f"A2A request received: {body.get('method', 'unknown')}")

        method = body.get("method")
        request_id = body.get("id", "unknown")

        if method != "message/send":
            return build_a2a_response(
                request_id,
                error={"code": -32601, "message": "Method not found"}
            )

        # Extract message parts
        parts = body.get("params", {}).get("message", {}).get("parts", [])
        text_parts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
        data_parts = [p.get("data", {}) for p in parts if p.get("kind") == "data"]

        user_message = " ".join(text_parts)

        # Check if this is a travel planning request
        if user_message:
            result = await shopping_agent.process_user_message(
                message=user_message,
                user_id="a2a_user"
            )

            return build_a2a_response(
                request_id,
                text="Travel intent processed",
                data=result
            )

        return build_a2a_response(
            request_id,
            error={"code": -32600, "message": "Invalid request - no message content"}
        )

    except Exception as e:
        logger.error(f"A2A endpoint error: {e}", exc_info=True)
        return build_a2a_response(
            str(request.state.request_id) if hasattr(request.state, 'request_id') else "error",
            error={"code": -32603, "message": str(e)}
        )


# ═══════════════════════════════════════════════════════════════
# Frontend API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Process a user's travel request and return intent analysis + packages.
    """
    logger.info(f"Chat request: {request.message[:100]}...")

    try:
        result = await shopping_agent.process_user_message(
            message=request.message,
            user_id=request.user_id,
            session_id=request.session_id
        )
        return result
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/select-package")
async def select_package(request: PackageSelectionRequest):
    """
    User selects a travel package, generates partial cart mandate.
    """
    logger.info(f"Package selection: {request.package_id}")

    try:
        result = await shopping_agent.select_package(
            session_id=request.session_id,
            package_id=request.package_id,
            user_email=request.user_email,
            user_name=request.user_name
        )
        return result
    except Exception as e:
        logger.error(f"Package selection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/payment-methods")
async def get_payment_methods(request: PaymentMethodRequest):
    """
    Get available payment methods from credentials agent.
    """
    logger.info(f"Get payment methods for session: {request.session_id}")

    try:
        result = await shopping_agent.get_payment_methods(request.session_id)
        return result
    except Exception as e:
        logger.error(f"Payment methods error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/create-cart-mandate")
async def create_cart_mandate(request: CartMandateRequest):
    """
    Create and sign full cart mandate with selected payment method.
    """
    logger.info(f"Create cart mandate: {request.session_id}")

    try:
        result = await shopping_agent.create_cart_mandate(
            session_id=request.session_id,
            payment_token=request.payment_token
        )
        return result
    except Exception as e:
        logger.error(f"Cart mandate error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process-payment")
async def process_payment(request: ProcessPaymentRequest):
    """
    Process payment through PaymentAgent.
    """
    logger.info(f"Process payment: {request.session_id}")

    try:
        result = await shopping_agent.process_payment(request.session_id)
        return result
    except Exception as e:
        logger.error(f"Payment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """
    Get current session state.
    """
    session = shopping_agent.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ═══════════════════════════════════════════════════════════════
# Log Streaming Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/api/logs")
@app.get("/logs")
async def get_logs(
    agent: str = Query("all", description="Agent name filter"),
    lines: int = Query(100, description="Number of lines to return")
):
    """
    Get recent log entries from all agents.
    """
    log_entries = []
    log_files = list(LOG_DIR.glob("*.log"))

    for log_file in log_files:
        if agent != "all" and agent.lower() not in log_file.stem.lower():
            continue

        try:
            with open(log_file, 'r') as f:
                # Read last N lines
                file_lines = f.readlines()
                recent_lines = file_lines[-lines:] if len(file_lines) > lines else file_lines

                for line in recent_lines:
                    try:
                        entry = json.loads(line.strip())
                        log_entries.append(entry)
                    except json.JSONDecodeError:
                        # Skip non-JSON lines
                        pass
        except Exception as e:
            logger.warning(f"Could not read log file {log_file}: {e}")

    # Sort by timestamp
    log_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return log_entries[:lines]


@app.get("/api/logs/stream")
@app.get("/logs/stream")
async def stream_logs(
    agent: str = Query("all", description="Agent name filter")
):
    """
    Server-Sent Events stream for real-time logs.
    """
    async def generate():
        last_positions = {}

        while True:
            log_files = list(LOG_DIR.glob("*.log"))

            for log_file in log_files:
                if agent != "all" and agent.lower() not in log_file.stem.lower():
                    continue

                try:
                    current_pos = last_positions.get(str(log_file), 0)

                    with open(log_file, 'r') as f:
                        f.seek(current_pos)
                        new_lines = f.readlines()
                        last_positions[str(log_file)] = f.tell()

                    for line in new_lines:
                        try:
                            entry = json.loads(line.strip())
                            yield f"data: {json.dumps(entry)}\n\n"
                        except json.JSONDecodeError:
                            pass
                except Exception:
                    pass

            await asyncio.sleep(2)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# ═══════════════════════════════════════════════════════════════
# Agent Network Info
# ═══════════════════════════════════════════════════════════════

@app.get("/api/agents")
async def get_agents():
    """
    Get information about all agents in the network.
    """
    import httpx

    agents = []
    agent_ports = {
        "shopping_agent": 8000,
        "merchant_agent": 8001,
        "credentials_agent": 8002,
        "payment_agent": 8003
    }

    async with httpx.AsyncClient(timeout=2.0) as client:
        for agent_name, port in agent_ports.items():
            try:
                response = await client.get(f"http://localhost:{port}/.well-known/agent.json")
                if response.status_code == 200:
                    card = response.json()
                    card["status"] = "online"
                    card["port"] = port
                    agents.append(card)
            except Exception:
                agents.append({
                    "name": agent_name,
                    "port": port,
                    "status": "offline"
                })

    return {"agents": agents}


# ═══════════════════════════════════════════════════════════════
# Startup/Shutdown
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    logger.info(f"Shopping Agent server starting on port {SHOPPING_AGENT_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shopping Agent server shutting down")
    await shopping_agent.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SHOPPING_AGENT_PORT)
