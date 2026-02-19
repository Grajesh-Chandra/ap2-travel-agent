"""
Merchant Agent FastAPI Server - Port 8001
Travel catalog and cart builder with AP2 support
"""

from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    CORS_ORIGINS,
    MERCHANT_AGENT_CARD,
    MERCHANT_AGENT_PORT,
)
from agents.merchant_agent import merchant_agent
from utils import get_logger, build_a2a_response, extract_mandate_from_message

logger = get_logger("MerchantServer")

app = FastAPI(
    title="Voyager Merchant Agent",
    description="Travel catalog and cart builder with AP2 support",
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
    return MERCHANT_AGENT_CARD


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "merchant_agent",
        "port": MERCHANT_AGENT_PORT,
        "timestamp": datetime.utcnow().isoformat()
    }


# ═══════════════════════════════════════════════════════════════
# A2A Protocol Endpoint
# ═══════════════════════════════════════════════════════════════

@app.post("/a2a/merchant_agent")
async def a2a_endpoint(request: Request):
    """
    A2A JSON-RPC 2.0 endpoint for inter-agent communication.
    Receives IntentMandate and returns travel packages.
    """
    try:
        body = await request.json()
        from_agent = request.headers.get("X-A2A-Agent", "shopping_agent")
        logger.info(
            f"A2A RECEIVED: {from_agent} → merchant_agent [message/send]",
            extra={
                "type": "a2a_message",
                "direction": "RECEIVED",
                "from_agent": from_agent,
                "to_agent": "merchant_agent",
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

        # Extract IntentMandate from message
        intent_mandate = extract_mandate_from_message(body, "IntentMandate")

        if not intent_mandate:
            return build_a2a_response(
                request_id,
                error={"code": -32600, "message": "No IntentMandate found in message"}
            )

        # Extract shopping_agent_id and risk_data
        parts = body.get("params", {}).get("message", {}).get("parts", [])
        shopping_agent_id = None
        risk_data = None

        for part in parts:
            if part.get("kind") == "data":
                data = part.get("data", {})
                if "shopping_agent_id" in data:
                    shopping_agent_id = data["shopping_agent_id"]
                if "risk_data" in data:
                    risk_data = data["risk_data"]

        # Process the intent mandate
        result = await merchant_agent.process_intent_mandate(
            intent_mandate=intent_mandate,
            shopping_agent_id=shopping_agent_id or "unknown",
            risk_data=risk_data
        )

        if "error" in result:
            return build_a2a_response(
                request_id,
                error={"code": -32600, "message": result["error"]}
            )

        logger.info(
            f"A2A SENT: merchant_agent → {from_agent} [intent_mandate_response]",
            extra={
                "type": "a2a_message",
                "direction": "SENT",
                "from_agent": "merchant_agent",
                "to_agent": from_agent,
                "method": "intent_mandate_response",
                "packages_count": len(result.get('packages', []))
            }
        )

        return build_a2a_response(
            request_id,
            text=f"Generated {len(result.get('packages', []))} travel packages",
            data=result
        )

    except Exception as e:
        logger.error(f"A2A endpoint error: {e}", exc_info=True)
        return build_a2a_response(
            "error",
            error={"code": -32603, "message": str(e)}
        )


# ═══════════════════════════════════════════════════════════════
# Direct API Endpoints (for testing)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/catalog/search")
async def search_catalog(
    destination: str,
    origin: str = "New York",
    travelers: int = 2,
    budget: float = 5000
):
    """
    Direct catalog search endpoint (for testing).
    """
    from ap2_types import ShoppingIntent, SpendingLimits
    from datetime import timedelta

    # Create a mock intent mandate
    intent = {
        "mandate_id": "test_mandate",
        "shopping_intent": {
            "destination": destination,
            "origin": origin,
            "travel_dates": {
                "start": (datetime.now() + timedelta(days=21)).strftime("%Y-%m-%d"),
                "end": (datetime.now() + timedelta(days=26)).strftime("%Y-%m-%d")
            },
            "travelers": travelers,
            "budget_usd": budget,
            "cabin_class": "economy",
            "preferences": []
        },
        "spending_limits": {
            "max_total_usd": budget * 1.2,
            "max_per_transaction_usd": budget
        },
        "natural_language_description": f"Trip to {destination} for {travelers}",
        "expires_at": (datetime.now() + timedelta(minutes=30)).isoformat()
    }

    result = await merchant_agent.process_intent_mandate(
        intent_mandate=intent,
        shopping_agent_id="test_agent"
    )

    return result


# ═══════════════════════════════════════════════════════════════
# Startup/Shutdown
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    logger.info(f"Merchant Agent server starting on port {MERCHANT_AGENT_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Merchant Agent server shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=MERCHANT_AGENT_PORT)
