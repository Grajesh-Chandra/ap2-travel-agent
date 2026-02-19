"""
Payment Agent FastAPI Server - Port 8003
Payment processor and settlement with AP2 support
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
    PAYMENT_AGENT_CARD,
    PAYMENT_AGENT_PORT,
)
from agents.payment_agent import payment_agent
from utils import get_logger, build_a2a_response, extract_mandate_from_message

logger = get_logger("PaymentServer")

app = FastAPI(
    title="Voyager Payment Agent",
    description="Payment processor and settlement with AP2 support",
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
# Well-Known & Health Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """Return the agent's well-known card for A2A discovery."""
    return PAYMENT_AGENT_CARD


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "payment_agent",
        "port": PAYMENT_AGENT_PORT,
        "timestamp": datetime.utcnow().isoformat()
    }


# ═══════════════════════════════════════════════════════════════
# A2A Protocol Endpoint
# ═══════════════════════════════════════════════════════════════

@app.post("/a2a/payment_agent")
async def a2a_endpoint(request: Request):
    """
    A2A JSON-RPC 2.0 endpoint for inter-agent communication.
    Receives PaymentMandate and processes the transaction.
    """
    try:
        body = await request.json()
        from_agent = request.headers.get("X-A2A-Agent", "shopping_agent")
        logger.info(
            f"A2A RECEIVED: {from_agent} → payment_agent [message/send]",
            extra={
                "type": "a2a_message",
                "direction": "RECEIVED",
                "from_agent": from_agent,
                "to_agent": "payment_agent",
                "method": body.get("method", "unknown")
            }
        )

        method = body.get("method")
        request_id = body.get("id", "unknown")

        if method != "message/send":
            return build_a2a_response(
                request_id,
                error={"code": -32601, "message": "Method not found"}
            )

        # Check for AP2 extension header
        ap2_header = request.headers.get("X-A2A-Extensions", "")
        has_ap2 = "ap2" in ap2_header.lower()
        logger.info(f"AP2 Extension: {has_ap2}")

        # Extract all mandates from message
        payment_mandate = extract_mandate_from_message(body, "PaymentMandate")
        cart_mandate = extract_mandate_from_message(body, "CartMandate")
        intent_mandate = extract_mandate_from_message(body, "IntentMandate")

        if not payment_mandate:
            return build_a2a_response(
                request_id,
                error={"code": -32600, "message": "No PaymentMandate found in message"}
            )

        if not cart_mandate:
            return build_a2a_response(
                request_id,
                error={"code": -32600, "message": "No CartMandate found in message"}
            )

        if not intent_mandate:
            return build_a2a_response(
                request_id,
                error={"code": -32600, "message": "No IntentMandate found in message"}
            )

        # Process the payment
        result = await payment_agent.process_payment_mandate(
            payment_mandate=payment_mandate,
            cart_mandate=cart_mandate,
            intent_mandate=intent_mandate
        )

        if not result.get("success"):
            return build_a2a_response(
                request_id,
                text=f"Payment failed: {result.get('error', 'Unknown error')}",
                data=result
            )

        logger.info(
            f"A2A SENT: payment_agent → {from_agent} [payment_processed]",
            extra={
                "type": "a2a_message",
                "direction": "SENT",
                "from_agent": "payment_agent",
                "to_agent": from_agent,
                "method": "payment_mandate_response",
                "transaction_id": result.get("transaction_id")
            }
        )

        return build_a2a_response(
            request_id,
            text="Payment processed successfully",
            data=result
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

@app.get("/api/transactions")
async def list_transactions():
    """
    List all processed transactions.
    """
    transactions = payment_agent.get_all_transactions()
    return {"transactions": transactions}


@app.get("/api/transactions/{transaction_id}")
async def get_transaction(transaction_id: str):
    """
    Get details of a specific transaction.
    """
    transaction = payment_agent.get_transaction(transaction_id)

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return transaction


# ═══════════════════════════════════════════════════════════════
# Startup/Shutdown
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    logger.info(f"Payment Agent server starting on port {PAYMENT_AGENT_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Payment Agent server shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PAYMENT_AGENT_PORT)
