"""
Voyager AI - AP2 Travel Agent Demo
Shared Configuration Module
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))

# Server Ports
SHOPPING_AGENT_PORT = int(os.getenv("SHOPPING_AGENT_PORT", "8000"))
MERCHANT_AGENT_PORT = int(os.getenv("MERCHANT_AGENT_PORT", "8001"))
CREDENTIALS_AGENT_PORT = int(os.getenv("CREDENTIALS_AGENT_PORT", "8002"))
PAYMENT_AGENT_PORT = int(os.getenv("PAYMENT_AGENT_PORT", "8003"))

# Agent URLs
SHOPPING_AGENT_URL = f"http://localhost:{SHOPPING_AGENT_PORT}"
MERCHANT_AGENT_URL = f"http://localhost:{MERCHANT_AGENT_PORT}"
CREDENTIALS_AGENT_URL = f"http://localhost:{CREDENTIALS_AGENT_PORT}"
PAYMENT_AGENT_URL = f"http://localhost:{PAYMENT_AGENT_PORT}"

# AP2 Protocol Configuration
AP2_VERSION = os.getenv("AP2_VERSION", "v1")
AP2_EXTENSION_URI = "https://github.com/google-agentic-commerce/ap2/v1"
AP2_MANDATE_TTL_MINUTES = int(os.getenv("AP2_MANDATE_TTL_MINUTES", "30"))

# A2A Protocol Configuration
A2A_PROTOCOL_VERSION = "0.3.0"
A2A_JSONRPC_VERSION = "2.0"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")

# Crypto (Demo only)
AP2_SIGNING_SECRET = os.getenv("AP2_SIGNING_SECRET", "voyager-ap2-demo-secret-2025")

# Wallet Configuration (for AP2 payment signing)
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "0x1467DcbB9208aEe398F41D0F1d768434a5d2dbA5")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "4f0aaa5ad4d500f82c6945e4c28027228b5cc8a54fc7383f0bb632ebb64505ac")

# Demo Mode
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

# Merchant Configuration
MERCHANT_ID = "voyager_travel_merchants"
MERCHANT_NAME = "Voyager Travel Merchants"

# Agent IDs
SHOPPING_AGENT_ID = "voyager_shopping_agent"
MERCHANT_AGENT_ID = "voyager_merchant_agent"
CREDENTIALS_AGENT_ID = "voyager_credentials_agent"
PAYMENT_AGENT_ID = "voyager_payment_agent"

# CORS Configuration
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# Well-Known Agent Cards
def get_agent_card(agent_name: str, agent_id: str, port: int, skills: list, description: str) -> dict:
    """Generate a well-known agent card for A2A discovery"""
    return {
        "name": agent_name,
        "description": description,
        "version": "1.0.0",
        "url": f"http://localhost:{port}/a2a/{agent_id}",
        "protocolVersion": A2A_PROTOCOL_VERSION,
        "preferredTransport": "JSONRPC",
        "defaultInputModes": ["json"],
        "defaultOutputModes": ["json"],
        "capabilities": {
            "extensions": [
                {
                    "description": "Supports the Agent Payments Protocol",
                    "required": True,
                    "uri": AP2_EXTENSION_URI
                }
            ]
        },
        "skills": skills
    }

# Shopping Agent Card
SHOPPING_AGENT_CARD = get_agent_card(
    agent_name="VoyagerShoppingAgent",
    agent_id="shopping_agent",
    port=SHOPPING_AGENT_PORT,
    description="User-facing travel shopping orchestrator with AP2 checkout capability",
    skills=[
        {
            "id": "plan_travel",
            "name": "Plan Travel",
            "description": "Interprets user travel requests and creates Intent Mandates",
            "tags": ["travel", "planning", "intent"]
        },
        {
            "id": "checkout",
            "name": "AP2 Checkout",
            "description": "Orchestrates the full AP2 checkout flow with VDC mandates",
            "tags": ["checkout", "payment", "ap2"]
        }
    ]
)

# Merchant Agent Card
MERCHANT_AGENT_CARD = get_agent_card(
    agent_name="VoyagerMerchantAgent",
    agent_id="merchant_agent",
    port=MERCHANT_AGENT_PORT,
    description="Travel merchant agent for Voyager AI with catalog and cart management",
    skills=[
        {
            "id": "search_travel_catalog",
            "name": "Search Travel Catalog",
            "description": "Searches flights, hotels, and activities matching an IntentMandate",
            "tags": ["travel", "search", "catalog"]
        },
        {
            "id": "generate_cart",
            "name": "Generate Cart",
            "description": "Creates a cart from search results and user selections",
            "tags": ["cart", "booking"]
        }
    ]
)

# Credentials Agent Card
CREDENTIALS_AGENT_CARD = get_agent_card(
    agent_name="VoyagerCredentialsAgent",
    agent_id="credentials_agent",
    port=CREDENTIALS_AGENT_PORT,
    description="Payment credential tokenizer for secure payment processing",
    skills=[
        {
            "id": "list_payment_methods",
            "name": "List Payment Methods",
            "description": "Returns available tokenized payment methods for a user",
            "tags": ["payment", "credentials", "tokenization"]
        },
        {
            "id": "tokenize_payment",
            "name": "Tokenize Payment",
            "description": "Creates a secure payment token for checkout",
            "tags": ["payment", "token", "security"]
        }
    ]
)

# Payment Agent Card
PAYMENT_AGENT_CARD = get_agent_card(
    agent_name="VoyagerPaymentAgent",
    agent_id="payment_agent",
    port=PAYMENT_AGENT_PORT,
    description="Payment processor and settlement agent for AP2 transactions",
    skills=[
        {
            "id": "process_payment",
            "name": "Process Payment",
            "description": "Processes PaymentMandate and authorizes transaction",
            "tags": ["payment", "authorization", "settlement"]
        },
        {
            "id": "validate_mandate",
            "name": "Validate Mandate",
            "description": "Validates VDC signatures and cart integrity",
            "tags": ["validation", "security", "mandate"]
        }
    ]
)
