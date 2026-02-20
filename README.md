# AP2 Travel Agent Demo

A full-stack, production-grade Travel Agent Checkout Demo that combines **A2A (Agent-to-Agent)** protocol with **AP2 (Agent Payments Protocol)** for secure, transparent multi-agent commerce.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AP2 Travel Agent Architecture                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌─────────────┐                                                          │
│    │   User /    │                                                          │
│    │   Browser   │                                                          │
│    └──────┬──────┘                                                          │
│           │                                                                 │
│           ▼                                                                 │
│    ┌─────────────────────────────────────────────────────────────────┐     │
│    │                    React Frontend (:5173)                        │     │
│    │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │     │
│    │  │   Travel    │  │   Checkout   │  │    Protocol Debugger   │  │     │
│    │  │   Planner   │  │     Flow     │  │  (A2A Messages, Logs)  │  │     │
│    │  └─────────────┘  └──────────────┘  └────────────────────────┘  │     │
│    └─────────────────────────────┬───────────────────────────────────┘     │
│                                  │                                          │
│                                  ▼                                          │
│    ┌─────────────────────────────────────────────────────────────────┐     │
│    │                  Shopping Agent (:8000)                          │     │
│    │                 [User-Facing Orchestrator]                       │     │
│    │                                                                  │     │
│    │   • Chat Interface (OpenRouter LLM)                             │     │
│    │   • Session Management                                           │     │
│    │   • IntentMandate Creation                                       │     │
│    │   • Checkout Flow Coordination                                   │     │
│    └─────────────┬───────────────────────────────────────────────────┘     │
│                  │                                                          │
│     ┌────────────┼────────────────────────────────┐                        │
│     │            │                                │                        │
│     ▼            ▼                                ▼                        │
│ ┌─────────┐ ┌──────────────┐              ┌─────────────┐                  │
│ │Merchant │ │ Credentials  │              │   Payment   │                  │
│ │ Agent   │ │    Agent     │              │    Agent    │                  │
│ │ (:8001) │ │   (:8002)    │              │   (:8003)   │                  │
│ ├─────────┤ ├──────────────┤              ├─────────────┤                  │
│ │• Catalog│ │• List Cards  │              │• Validate   │                  │
│ │• Search │ │• Tokenize    │              │  Mandates   │                  │
│ │• Package│ │  Payment     │              │• Process    │                  │
│ │  Builder│ │  Methods     │              │  Payments   │                  │
│ │• Cart   │ │• Risk Tokens │              │• Settlement │                  │
│ │  Sign   │ │              │              │             │                  │
│ └─────────┘ └──────────────┘              └─────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

### Multi-Agent System
- **4 Specialized Agents** communicating via A2A protocol (JSON-RPC 2.0)
- **Agent Cards** for capability discovery at `/.well-known/agent.json`
- **Session-based** conversation management

### AP2 Payment Flow
- **IntentMandate**: User's spending intent with limits and preferences
- **CartMandate**: Finalized cart signed by user and merchant
- **PaymentMandate**: Payment authorization with full audit trail

### Real-Time Debugging
- **A2A Message Bus**: View all inter-agent communications
- **Mandate Timeline**: Visual checkout progress
- **LLM Calls**: Inspect AI reasoning
- **Server Logs**: Live log streaming with filters

### LLM Integration
- **OpenRouter LLM**: Cloud-hosted LLM for travel intent extraction
- **Graceful Fallback**: Mock responses when LLM unavailable
- **Structured Output**: JSON schema-constrained generation

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **OpenRouter API key** (for LLM features)
- **macOS** or **Linux**

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/ap2-travel-agent.git
cd ap2-travel-agent

# Copy environment file
cp .env.example .env

# Make scripts executable
chmod +x start.sh stop.sh
```

### 2. Configure OpenRouter

Get an API key from [openrouter.ai](https://openrouter.ai/) and add it to your `.env`:

```bash
# Edit .env and set your API key
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=arcee-ai/trinity-large-preview:free
OPENROUTER_TIMEOUT=60
```

### 3. Start All Services

```bash
./start.sh
```

This will:
- Create Python virtual environment and install dependencies
- Install npm packages for frontend
- Start all 4 backend agents (ports 8000-8003)
- Start React frontend (port 5173)
- Open browser to http://localhost:5173

### 4. Stop All Services

```bash
./stop.sh
```

### 5. Clean Up (Optional)

```bash
# Remove venv and node_modules
./stop.sh --clean

# Full cleanup (venv, node_modules, logs, __pycache__)
./stop.sh --full-clean
```

## Project Structure

```
ap2-travel-agent/
├── backend/
│   ├── agents/                 # Agent implementations
│   │   ├── shopping_agent.py   # User-facing orchestrator
│   │   ├── merchant_agent.py   # Catalog & packages
│   │   ├── credentials_agent.py # Payment tokenization
│   │   └── payment_agent.py    # Payment processing
│   │
│   ├── servers/                # FastAPI servers
│   │   ├── shopping_server.py  # Port 8000
│   │   ├── merchant_server.py  # Port 8001
│   │   ├── credentials_server.py # Port 8002
│   │   └── payment_server.py   # Port 8003
│   │
│   ├── utils/                  # Shared utilities
│   │   ├── crypto.py           # HMAC signing, hashing
│   │   ├── logger.py           # JSON logging
│   │   └── a2a_client.py       # A2A HTTP client
│   │
│   ├── ap2_types.py            # Pydantic models
│   ├── config.py               # Shared configuration
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── TravelPlanner.jsx   # Chat interface
│   │   │   ├── CheckoutFlow.jsx    # 5-step wizard
│   │   │   ├── MandateViewer.jsx   # VDC display
│   │   │   ├── AP2Debugger.jsx     # Protocol debugger
│   │   │   └── AgentNetwork.jsx    # Agent topology
│   │   ├── App.jsx
│   │   └── main.jsx
│   │
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── logs/                       # Runtime logs
├── start.sh                    # Startup script
├── stop.sh                     # Cleanup script
├── .env.example                # Environment template
└── README.md
```

## Demo Script

### Step 1: Plan Your Trip

1. Open http://localhost:5173
2. Use the chat interface or quick prompts:
   - "Plan a 5-day trip to Tokyo for 2 people"
   - "Find business class flights to Paris"
   - "I want a romantic getaway in Bali"

### Step 2: Review Package

1. The Shopping Agent orchestrates with Merchant Agent
2. Review generated travel packages with flights, hotels, activities
3. Select "Proceed to Checkout"

### Step 3: AP2 Checkout Flow

1. **Intent Signing**: Review and sign your IntentMandate
   - View spending limits, preferences, refundability requirements

2. **Cart Review**: See finalized package with line items
   - Subtotal, taxes, fees breakdown

3. **Payment Method**: Select from tokenized payment options
   - Cards are tokenized via Credentials Agent

4. **Cart Mandate**: Review and approve CartMandate
   - Contains cart hash, signatures from both parties

5. **Confirmation**: Payment processed via Payment Agent
   - Receive booking references, PNR codes

### Step 4: Explore Debugger

Switch to "Debugger" tab to see:
- **A2A Messages**: All JSON-RPC calls between agents
- **Mandate Timeline**: Visual flow of VDCs
- **LLM Calls**: OpenRouter prompts and responses
- **Agent Cards**: Discovery metadata
- **Server Logs**: Real-time log streaming

## API Reference

### Shopping Agent (Port 8000)

```http
POST /api/chat
Content-Type: application/json

{
  "session_id": "uuid",
  "message": "Plan a trip to Paris"
}
```

```http
POST /api/checkout/intent
Content-Type: application/json

{
  "session_id": "uuid",
  "shopping_intent": {
    "destination": "Paris",
    "origin": "NYC",
    "travelers": 2,
    "budget_usd": 5000
  }
}
```

### Agent Cards

All agents expose their capabilities at:
- `GET /.well-known/agent.json`

Example:
```json
{
  "name": "shopping-agent",
  "version": "1.0.0",
  "description": "User-facing travel shopping assistant",
  "capabilities": ["chat", "intent-capture", "checkout-orchestration"],
  "endpoints": {
    "chat": "/api/chat",
    "checkout": "/api/checkout/*"
  }
}
```

## Configuration

### Environment Variables

```bash
# OpenRouter Configuration
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=arcee-ai/trinity-large-preview:free
OPENROUTER_TIMEOUT=60

# Agent Ports
SHOPPING_AGENT_PORT=8000
MERCHANT_AGENT_PORT=8001
CREDENTIALS_AGENT_PORT=8002
PAYMENT_AGENT_PORT=8003

# Security
AP2_SIGNING_SECRET=your-secret-key
LOG_LEVEL=INFO
```

## AP2 Protocol Overview

### Verifiable Delegation Credentials (VDCs)

AP2 uses three types of mandates to ensure transparent, auditable payments:

#### 1. IntentMandate
Created by user, defines shopping constraints:
```json
{
  "mandate_id": "intent_...",
  "version": "1.0",
  "issued_at": "2024-01-15T10:00:00Z",
  "shopping_intent": {
    "destination": "Tokyo",
    "travelers": 2,
    "budget_usd": 5000
  },
  "spending_limits": {
    "max_total_usd": 5000,
    "max_per_transaction_usd": 2500
  },
  "refundability_required": true,
  "signature": "hmac_sha256_..."
}
```

#### 2. CartMandate
Created by merchant, signed by both parties:
```json
{
  "mandate_id": "cart_...",
  "intent_mandate_id": "intent_...",
  "amounts": {
    "subtotal_usd": 3500.00,
    "taxes_usd": 315.00,
    "fees_usd": 50.00,
    "total_usd": 3865.00
  },
  "cart_hash": "sha256_...",
  "user_signature": "...",
  "merchant_signature": "..."
}
```

#### 3. PaymentMandate
Used for actual payment execution:
```json
{
  "mandate_id": "payment_...",
  "cart_mandate_id": "cart_...",
  "intent_mandate_id": "intent_...",
  "agent_presence": "human_present",
  "payment_details": {
    "payment_id": "pay_...",
    "status": "authorized"
  },
  "user_authorization": "hmac_..."
}
```

## Troubleshooting

### LLM Not Available

The system uses mock responses when OpenRouter is unavailable. To enable LLM:

```bash
# Ensure your .env has a valid API key
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Get a free key at https://openrouter.ai/
```

### Port Already in Use

```bash
# Kill process on specific port
lsof -ti:8000 | xargs kill -9

# Or use the stop script
./stop.sh
```

### View Logs

```bash
# Tail all logs
tail -f logs/*.log

# View specific agent
tail -f logs/shopping_agent.log
```

## Development

### Backend Development

```bash
cd backend
source venv/bin/activate

# Run single agent with reload
uvicorn servers.shopping_server:app --reload --port 8000

# Run tests
pytest
```

### Frontend Development

```bash
cd frontend

# Development server
npm run dev

# Build for production
npm run build
```

## License

MIT License - See [LICENSE](LICENSE) for details

## Acknowledgments

- [A2A Protocol](https://github.com/anthropics/a2a-protocol) - Agent-to-Agent communication
- [OpenRouter](https://openrouter.ai) - LLM inference API
- [FastAPI](https://fastapi.tiangolo.com) - Python web framework
- [Vite](https://vitejs.dev) - Frontend build tool
