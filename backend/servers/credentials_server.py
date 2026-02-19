"""
Credentials Agent FastAPI Server - Port 8002
Payment credential tokenizer with AP2 support
"""

from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    CORS_ORIGINS,
    CREDENTIALS_AGENT_CARD,
    CREDENTIALS_AGENT_PORT,
)
from agents.credentials_agent import credentials_agent
from utils import get_logger, build_a2a_response, extract_mandate_from_message

logger = get_logger("CredentialsServer")

app = FastAPI(
    title="Voyager Credentials Agent",
    description="Payment credential tokenizer with AP2 support",
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
# Request Models
# ═══════════════════════════════════════════════════════════════

class TokenizeRequest(BaseModel):
    user_id: str
    payment_token: str
    amount_usd: float


# ═══════════════════════════════════════════════════════════════
# Well-Known & Health Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """Return the agent's well-known card for A2A discovery."""
    return CREDENTIALS_AGENT_CARD


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "credentials_agent",
        "port": CREDENTIALS_AGENT_PORT,
        "timestamp": datetime.utcnow().isoformat()
    }


# ═══════════════════════════════════════════════════════════════
# A2A Protocol Endpoint
# ═══════════════════════════════════════════════════════════════

@app.post("/a2a/credentials_agent")
async def a2a_endpoint(request: Request):
    """
    A2A JSON-RPC 2.0 endpoint for inter-agent communication.
    Handles payment method listing and tokenization.
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

        instruction = " ".join(text_parts).lower()

        # Check for user_id in data parts
        user_id = "demo_user"
        for part in parts:
            if part.get("kind") == "data":
                data = part.get("data", {})
                if "user_id" in data:
                    user_id = data["user_id"]

        # Handle different requests
        if "list" in instruction or "payment method" in instruction:
            # List payment methods
            payment_methods = credentials_agent.get_payment_methods(user_id)
            return build_a2a_response(
                request_id,
                text=f"Found {len(payment_methods)} payment methods",
                data={"payment_methods": payment_methods}
            )

        # Check for CartMandate (tokenization request)
        cart_mandate = extract_mandate_from_message(body, "CartMandate")
        if cart_mandate:
            # Tokenize payment for cart
            payment_method = cart_mandate.get("payment_method", {})
            payer = cart_mandate.get("payer", {})
            amounts = cart_mandate.get("amounts", {})

            result = credentials_agent.tokenize_payment(
                user_id=payer.get("user_id", user_id),
                payment_token=payment_method.get("token", ""),
                amount_usd=amounts.get("total_usd", 0)
            )

            return build_a2a_response(
                request_id,
                text="Payment tokenized",
                data=result
            )

        # Default: list payment methods
        payment_methods = credentials_agent.get_payment_methods(user_id)
        return build_a2a_response(
            request_id,
            text=f"Found {len(payment_methods)} payment methods",
            data={"payment_methods": payment_methods}
        )

    except Exception as e:
        logger.error(f"A2A endpoint error: {e}", exc_info=True)
        return build_a2a_response(
            "error",
            error={"code": -32603, "message": str(e)}
        )


# ═══════════════════════════════════════════════════════════════
# Direct API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/api/payment-methods/{user_id}")
async def get_payment_methods(user_id: str):
    """
    Get available payment methods for a user.
    """
    methods = credentials_agent.get_payment_methods(user_id)
    return {"payment_methods": methods}


@app.post("/api/tokenize")
async def tokenize_payment(request: TokenizeRequest):
    """
    Create a transaction-specific token for payment.
    """
    result = credentials_agent.tokenize_payment(
        user_id=request.user_id,
        payment_token=request.payment_token,
        amount_usd=request.amount_usd
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.get("/tokens/{token}")
async def get_token_details(token: str):
    """
    Get details about a payment token.
    """
    details = credentials_agent.get_token_details(token)

    if not details:
        raise HTTPException(status_code=404, detail="Token not found")

    return details


@app.post("/api/validate-token")
async def validate_token(token: str):
    """
    Validate a payment token.
    """
    result = credentials_agent.validate_token(token)
    return result


# ═══════════════════════════════════════════════════════════════
# Startup/Shutdown
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    logger.info(f"Credentials Agent server starting on port {CREDENTIALS_AGENT_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Credentials Agent server shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=CREDENTIALS_AGENT_PORT)
