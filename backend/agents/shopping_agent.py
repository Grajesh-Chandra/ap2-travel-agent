"""
Shopping Agent - User-facing travel shopping orchestrator with conversational flow
Handles multi-turn conversations, creates Intent Mandates, and orchestrates the AP2 checkout flow
"""

import json
import uuid
import time
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
import ollama

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    MERCHANT_AGENT_URL,
    CREDENTIALS_AGENT_URL,
    PAYMENT_AGENT_URL,
    SHOPPING_AGENT_ID,
    MERCHANT_ID,
    MERCHANT_NAME,
)
from ap2_types import (
    IntentMandate,
    ShoppingIntent,
    SpendingLimits,
    CartMandate,
    PaymentMandate,
    PaymentDetails,
    Amounts,
    IssuerSignals,
    TravelPackage,
    LineItem,
    Payer,
    Payee,
    PaymentMethod,
    ShippingDetails,
    RefundPolicy,
)
from utils import (
    get_logger,
    log_mandate_event,
    log_llm_call,
    sign_mandate,
    hash_cart,
    generate_risk_token,
    generate_user_authorization,
    generate_device_signature,
    A2AClient,
    extract_mandate_from_message,
)

logger = get_logger("ShoppingAgent")


class ConversationStage(str, Enum):
    """Conversation stages for multi-turn flow"""
    GREETING = "greeting"
    GATHERING_INFO = "gathering_info"
    CONFIRMING_SEARCH = "confirming_search"
    SHOWING_PACKAGES = "showing_packages"
    CHECKOUT_DETAILS = "checkout_details"
    PAYMENT_SELECTION = "payment_selection"
    PROCESSING = "processing"
    COMPLETED = "completed"


class ShoppingAgent:
    """
    User-facing orchestrator for travel planning and AP2 checkout.
    Implements multi-turn conversational flow.

    Conversation Flow:
    1. GREETING - User says hi, agent greets and asks about trip
    2. GATHERING_INFO - Progressive collection of trip details
    3. CONFIRMING_SEARCH - Confirm details before searching
    4. SHOWING_PACKAGES - Display travel packages
    5. CHECKOUT_DETAILS - Collect name, email, address
    6. PAYMENT_SELECTION - Choose payment method
    7. PROCESSING - Process payment
    8. COMPLETED - Transaction complete
    """

    # Required fields for a complete travel request
    REQUIRED_FIELDS = ['destination', 'travel_dates', 'travelers']
    OPTIONAL_FIELDS = ['origin', 'budget_usd', 'cabin_class', 'preferences']

    def __init__(self):
        self.agent_id = SHOPPING_AGENT_ID
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.a2a_client = A2AClient(
            agent_name=self.agent_id,
            agent_url="http://localhost:8000",
            timeout=300.0,  # 5 min timeout for LLM-heavy operations
            logger=logger
        )

        # Intent types the LLM can classify
        self.INTENT_TYPES = [
            "greeting",           # Pure greeting (hi, hello)
            "provide_info",       # User providing travel details
            "confirm_yes",        # User confirming (yes, proceed, looks good)
            "confirm_no",         # User declining/changing (no, change, modify)
            "select_package",     # Selecting a package (value, premium, recommended)
            "provide_checkout",   # Providing checkout details (name, email, address)
            "select_payment",     # Selecting payment method
            "cancel",             # Cancel/start over
            "question",           # User asking a question
            "other"               # Unclear intent
        ]

    async def _classify_intent_with_llm(self, message: str, session: Dict) -> Dict[str, Any]:
        """
        LLM-based intent classification and entity extraction.
        Acts as the orchestrator to decide what action to take.
        """
        stage = session.get("stage", ConversationStage.GREETING)
        collected = session.get("collected_info", {})
        packages = session.get("packages", [])

        # Build context for LLM
        context_parts = []
        if collected:
            context_parts.append(f"Already collected: {json.dumps(collected)}")
        if packages:
            pkg_names = [p.tier if hasattr(p, 'tier') else p.get('tier', 'unknown') for p in packages]
            context_parts.append(f"Available packages: {pkg_names}")
        context_parts.append(f"Current stage: {stage}")

        context = "\n".join(context_parts) if context_parts else "No context yet"

        prompt = f"""You are an AI travel assistant orchestrator. Analyze the user message and decide the intent and action.

CONTEXT:
{context}

USER MESSAGE: "{message}"

Classify the intent and extract any relevant data. Output ONLY a JSON object:

{{
  "intent": "<one of: greeting, provide_info, confirm_yes, confirm_no, select_package, provide_checkout, select_payment, cancel, question, other>",
  "confidence": <0.0 to 1.0>,
  "extracted_data": {{
    "destination": "<city/country or null>",
    "origin": "<departure city or null>",
    "travel_dates": {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}} or null,
    "travelers": <number or null>,
    "budget_usd": <number or null>,
    "cabin_class": "<economy/business/first or null>",
    "preferences": ["<list>"] or null,
    "selected_package": "<value/recommended/premium or null>",
    "name": "<full name or null>",
    "email": "<email or null>",
    "phone": "<phone or null>",
    "payment_method": "<card/wallet or null>"
  }},
  "reasoning": "<brief explanation of why this intent>"
}}

INTENT GUIDE:
- "greeting": Pure greeting like "hi", "hello", "hey" with no travel content
- "provide_info": User sharing destination, dates, travelers, budget, preferences
- "confirm_yes": Agreeing/confirming like "yes", "proceed", "looks good", "that's right"
- "confirm_no": Declining like "no", "change", "modify", "not quite"
- "select_package": Choosing a package like "value", "premium", "recommended", "the first one", "cheapest"
- "provide_checkout": Giving name, email, phone, or address
- "select_payment": Choosing "card", "wallet", "visa", "mastercard"
- "cancel": "cancel", "start over", "forget it"
- "question": Asking about something (what, why, how, can you)
- "other": Unclear or unrelated

OUTPUT ONLY THE JSON, no explanation."""

        try:
            start_time = time.time()
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1, "num_predict": 500}
            )
            elapsed = time.time() - start_time

            content = response.get("message", {}).get("content", "")
            log_llm_call(logger, "intent_classification", prompt[:200], content, elapsed)

            # Remove <think> tags if present (qwen3)
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                logger.info(f"[LLM Orchestrator] Intent: {result.get('intent')}, Confidence: {result.get('confidence')}")
                return result

        except Exception as e:
            logger.warning(f"[LLM Orchestrator] Failed: {e}")

        # Fallback: use simple pattern matching
        return self._classify_intent_simple(message, session)

    def _classify_intent_simple(self, message: str, session: Dict) -> Dict[str, Any]:
        """Fast pattern-based intent classification as fallback."""
        msg_lower = message.lower().strip()
        stage = session.get("stage", ConversationStage.GREETING)

        # Pure greetings
        if msg_lower in ['hi', 'hello', 'hey', 'howdy', 'hola', 'greetings', 'good morning', 'good afternoon', 'good evening']:
            return {"intent": "greeting", "confidence": 1.0, "extracted_data": {}, "reasoning": "Pure greeting"}

        # Cancel
        if any(w in msg_lower for w in ['cancel', 'start over', 'forget it', 'never mind', 'nevermind']):
            return {"intent": "cancel", "confidence": 0.9, "extracted_data": {}, "reasoning": "Cancel keywords"}

        # Confirmations - match exact suggestions and common phrases
        confirm_phrases = [
            'yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'proceed', 'continue',
            'looks good', 'perfect', 'great', "let's go", 'confirm', 'correct',
            "that's right", 'yes, search', 'search for packages', 'find packages',
            "yes, let's start", 'start fresh'
        ]
        if msg_lower in confirm_phrases or any(phrase in msg_lower for phrase in confirm_phrases):
            return {"intent": "confirm_yes", "confidence": 0.9, "extracted_data": {}, "reasoning": "Confirmation"}

        # Decline/modify - match exact suggestions
        decline_phrases = [
            'no', 'nope', 'change', 'modify', 'edit', 'not quite', 'wrong',
            'change destination', 'change dates', 'change travelers', 'change budget',
            'add preferences', 'no thanks'
        ]
        if msg_lower in decline_phrases or any(phrase in msg_lower for phrase in decline_phrases):
            return {"intent": "confirm_no", "confidence": 0.9, "extracted_data": {}, "reasoning": "Decline/modify"}

        # Package selection - match exact suggestions
        if stage == ConversationStage.SHOWING_PACKAGES:
            # Exact suggestion matches
            if 'value package' in msg_lower or msg_lower == 'value':
                return {"intent": "select_package", "confidence": 0.95, "extracted_data": {"selected_package": "value"}, "reasoning": "Value package selected"}
            if 'recommended package' in msg_lower or msg_lower == 'recommended':
                return {"intent": "select_package", "confidence": 0.95, "extracted_data": {"selected_package": "recommended"}, "reasoning": "Recommended package selected"}
            if 'premium package' in msg_lower or msg_lower == 'premium':
                return {"intent": "select_package", "confidence": 0.95, "extracted_data": {"selected_package": "premium"}, "reasoning": "Premium package selected"}
            if 'show packages' in msg_lower or 'packages again' in msg_lower:
                return {"intent": "question", "confidence": 0.8, "extracted_data": {}, "reasoning": "Show packages again"}
            # Generic keywords
            for pkg in ['value', 'recommended', 'premium', 'cheapest', 'budget', 'best', 'expensive', 'luxury']:
                if pkg in msg_lower:
                    selected = 'value' if pkg in ['value', 'cheapest', 'budget'] else 'premium' if pkg in ['premium', 'expensive', 'luxury'] else 'recommended'
                    return {"intent": "select_package", "confidence": 0.8, "extracted_data": {"selected_package": selected}, "reasoning": f"Package keyword: {pkg}"}

        # Payment selection - match exact suggestions
        if stage == ConversationStage.PAYMENT_SELECTION:
            if any(w in msg_lower for w in ['card', 'credit', 'debit', 'visa', 'mastercard', 'credit card', 'debit card']):
                return {"intent": "select_payment", "confidence": 0.8, "extracted_data": {"payment_method": "card"}, "reasoning": "Card payment"}
            if any(w in msg_lower for w in ['wallet', 'paypal', 'apple pay', 'google pay', 'digital wallet']):
                return {"intent": "select_payment", "confidence": 0.8, "extracted_data": {"payment_method": "wallet"}, "reasoning": "Wallet payment"}

        # Questions
        if msg_lower.startswith(('what', 'why', 'how', 'when', 'where', 'can you', 'could you', 'is there', 'are there')):
            return {"intent": "question", "confidence": 0.7, "extracted_data": {}, "reasoning": "Question pattern"}

        # Default: assume providing info (will be extracted separately)
        return {"intent": "provide_info", "confidence": 0.5, "extracted_data": {}, "reasoning": "Default to info gathering"}

    def _get_or_create_session(self, session_id: Optional[str], user_id: str) -> tuple[str, Dict[str, Any]]:
        """Get existing session or create a new one."""
        if session_id and session_id in self.sessions:
            return session_id, self.sessions[session_id]

        session_id = session_id or str(uuid.uuid4())
        self.sessions[session_id] = {
            "user_id": user_id,
            "stage": ConversationStage.GREETING,
            "collected_info": {},
            "conversation_history": [],
            "packages": [],
            "selected_package": None,
            "checkout_details": {},
            "cart_mandate": None,
            "payment_mandate": None,
            "created_at": datetime.utcnow().isoformat()
        }
        return session_id, self.sessions[session_id]

    async def process_user_message(
        self,
        message: str,
        user_id: str = "demo_user",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user message using LLM-first orchestration.

        Flow:
        1. LLM classifies intent and extracts entities
        2. Route to action handler based on intent (not just stage)
        3. Stage tracks conversation state for context
        """
        session_id, session = self._get_or_create_session(session_id, user_id)
        session["conversation_history"].append({"role": "user", "content": message})
        stage = session["stage"]

        logger.info(f"[Orchestrator] Message: '{message[:80]}...' | Stage: {stage}")

        # Step 1: Classify intent using LLM (or fast fallback)
        # Try simple classification first for speed, use LLM for complex messages
        msg_lower = message.lower().strip()
        use_llm = len(message) > 30 or any(c in message for c in ['$', '@', ',', '.'])

        if use_llm:
            intent_result = await self._classify_intent_with_llm(message, session)
        else:
            intent_result = self._classify_intent_simple(message, session)

        intent = intent_result.get("intent", "other")
        extracted = intent_result.get("extracted_data", {})
        confidence = intent_result.get("confidence", 0.5)

        logger.info(f"[Orchestrator] Intent: {intent} (confidence: {confidence})")

        # Step 2: Route to action handler based on intent
        response = await self._route_by_intent(intent, message, extracted, session)

        response["session_id"] = session_id
        response["stage"] = session["stage"]
        response["agent_id"] = self.agent_id
        response["intent"] = intent  # Include for debugging
        session["conversation_history"].append({"role": "assistant", "content": response})

        return response

    async def _route_by_intent(self, intent: str, message: str, extracted: Dict, session: Dict) -> Dict[str, Any]:
        """Route to appropriate handler based on classified intent."""
        stage = session["stage"]

        # Handle cancel at any stage
        if intent == "cancel":
            return self._handle_cancel(session)

        # Handle question at any stage
        if intent == "question":
            return await self._handle_question(message, session)

        # Route based on intent
        if intent == "greeting":
            session["stage"] = ConversationStage.GATHERING_INFO
            return {
                "success": True,
                "type": "conversation",
                "message": "Hello! 👋 Welcome to AP2 Travel - where your dream trips meet secure, transparent checkout!\n\nI'm here to help you plan an amazing journey. Where would you like to go?",
                "suggestions": [
                    "I want to visit Dubai",
                    "Planning a trip to Tokyo",
                    "Looking for a Paris getaway",
                    "Beach vacation in Bali"
                ],
                "input_hint": "destination"
            }

        elif intent == "provide_info":
            # User is providing travel info - extract and update
            return await self._handle_provide_info(message, extracted, session)

        elif intent == "confirm_yes":
            # User confirming - action depends on stage
            if stage == ConversationStage.CONFIRMING_SEARCH:
                return await self._execute_search(session)
            elif stage == ConversationStage.CHECKOUT_DETAILS:
                session["stage"] = ConversationStage.PAYMENT_SELECTION
                return self._build_payment_selection_response(session)
            elif stage == ConversationStage.PAYMENT_SELECTION:
                return await self._process_payment(session)
            else:
                # Generic confirmation - continue to next step
                return await self._continue_flow(session)

        elif intent == "confirm_no":
            # User wants to modify - go back to gathering
            session["stage"] = ConversationStage.GATHERING_INFO
            return {
                "success": True,
                "type": "conversation",
                "message": "No problem! What would you like to change?",
                "suggestions": ["Change destination", "Change dates", "Change travelers", "Change budget"],
                "input_hint": "modification"
            }

        elif intent == "select_package":
            pkg_name = extracted.get("selected_package", "recommended")
            return await self._handle_package_selection(pkg_name, session)

        elif intent == "provide_checkout":
            return await self._handle_checkout_info(message, extracted, session)

        elif intent == "select_payment":
            method = extracted.get("payment_method", "card")
            return await self._handle_payment_method(method, session)

        else:
            # "other" or unknown - try to handle based on current stage
            return await self._handle_by_stage(message, session)

    async def _handle_provide_info(self, message: str, extracted: Dict, session: Dict) -> Dict[str, Any]:
        """Handle user providing travel information."""
        collected = session.get("collected_info", {})

        # First, merge any extracted data from LLM intent classification
        for key, value in extracted.items():
            if value and value != "null" and str(value) != "None":
                collected[key] = value

        # For short messages, use simple extraction directly (faster, more reliable)
        if len(message.strip()) < 40 or len(message.split()) <= 5:
            simple_result = self._simple_extract(message)
            if simple_result:
                logger.info(f"[ProvideInfo] Using simple extraction: {simple_result}")
                for key, value in simple_result.items():
                    if value and value != "null" and str(value) != "None":
                        collected[key] = value
        else:
            # For longer messages, use LLM extraction
            detailed_extracted = await self._extract_travel_info(message, collected)
            if detailed_extracted:
                for key, value in detailed_extracted.items():
                    if value and value != "null" and str(value) != "None":
                        collected[key] = value

        session["collected_info"] = collected

        # Check what we have vs what we need
        missing = self._get_missing_fields(collected)

        if not missing:
            # We have all required info - move to confirmation
            session["stage"] = ConversationStage.CONFIRMING_SEARCH
            return self._build_confirmation_response(collected, session)

        # Still gathering info
        session["stage"] = ConversationStage.GATHERING_INFO
        return self._build_gathering_response(collected, missing)

    async def _handle_question(self, message: str, session: Dict) -> Dict[str, Any]:
        """Handle user questions using LLM."""
        # Use LLM to answer the question in context
        context = json.dumps(session.get("collected_info", {}), indent=2)
        packages = session.get("packages", [])

        prompt = f"""You are a helpful travel assistant. Answer the user's question briefly and helpfully.

Context:
- Collected travel info: {context}
- Available packages: {len(packages)} packages
- Stage: {session.get('stage')}

User question: "{message}"

Answer in 1-3 sentences, then guide them back to the booking flow if appropriate."""

        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.7, "num_predict": 200}
            )
            answer = response.get("message", {}).get("content", "")
            answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()
        except Exception as e:
            logger.warning(f"LLM question answering failed: {e}")
            answer = "I'd be happy to help! Could you rephrase your question?"

        return {
            "success": True,
            "type": "conversation",
            "message": answer
        }

    def _handle_cancel(self, session: Dict) -> Dict[str, Any]:
        """Handle cancellation - reset session."""
        session["stage"] = ConversationStage.GREETING
        session["collected_info"] = {}
        session["packages"] = []
        session["selected_package"] = None
        session["checkout_details"] = {}

        return {
            "success": True,
            "type": "conversation",
            "message": "No problem! I've cleared everything. Would you like to start planning a new trip?",
            "suggestions": ["Yes, let's start fresh", "No thanks"]
        }

    async def _continue_flow(self, session: Dict) -> Dict[str, Any]:
        """Continue to the next logical step based on current state."""
        stage = session["stage"]
        collected = session.get("collected_info", {})

        if stage == ConversationStage.GATHERING_INFO:
            missing = self._get_missing_fields(collected)
            if not missing:
                session["stage"] = ConversationStage.CONFIRMING_SEARCH
                return self._build_confirmation_response(collected, session)
            return self._build_gathering_response(collected, missing)

        elif stage == ConversationStage.CONFIRMING_SEARCH:
            return await self._execute_search(session)

        elif stage == ConversationStage.SHOWING_PACKAGES:
            return {
                "success": True,
                "type": "conversation",
                "message": "Which package would you like? You can say 'value', 'recommended', or 'premium'.",
                "input_hint": "package"
            }

        elif stage == ConversationStage.CHECKOUT_DETAILS:
            session["stage"] = ConversationStage.PAYMENT_SELECTION
            return self._build_payment_selection_response(session)

        elif stage == ConversationStage.PAYMENT_SELECTION:
            return await self._process_payment(session)

        else:
            return await self._handle_greeting_stage("", session)

    async def _execute_search(self, session: Dict) -> Dict[str, Any]:
        """Execute search for packages - alias for _search_packages."""
        return await self._search_packages(session)

    async def _handle_package_selection(self, tier: str, session: Dict) -> Dict[str, Any]:
        """Handle package selection by tier name."""
        # Normalize tier name
        tier_map = {
            'value': 'value', 'budget': 'value', 'cheap': 'value', 'cheapest': 'value',
            'recommended': 'recommended', 'best': 'recommended', 'suggested': 'recommended',
            'premium': 'premium', 'luxury': 'premium', 'expensive': 'premium', 'top': 'premium'
        }
        normalized_tier = tier_map.get(tier.lower(), 'recommended')
        return self._select_package_by_tier(session, normalized_tier)

    async def _handle_checkout_info(self, message: str, extracted: Dict, session: Dict) -> Dict[str, Any]:
        """Handle checkout information (name, email, phone)."""
        checkout = session.get("checkout_details", {})

        # Merge extracted data
        for key in ['name', 'email', 'phone']:
            if extracted.get(key):
                checkout[key] = extracted[key]

        # Also try to extract from message using patterns
        # Email pattern
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email_match:
            checkout['email'] = email_match.group()

        # Name pattern (if message looks like a name)
        if not checkout.get('name') and len(message.split()) <= 4 and not '@' in message:
            # Might be a name
            words = message.strip().split()
            if all(w[0].isupper() for w in words if w):
                checkout['name'] = message.strip()

        session["checkout_details"] = checkout

        # Check what we still need
        missing_checkout = []
        if not checkout.get('name'):
            missing_checkout.append('name')
        if not checkout.get('email'):
            missing_checkout.append('email')

        if missing_checkout:
            session["stage"] = ConversationStage.CHECKOUT_DETAILS
            prompts = {
                'name': "What name should the booking be under?",
                'email': "What email should we send the confirmation to?"
            }
            return {
                "success": True,
                "type": "conversation",
                "message": prompts.get(missing_checkout[0], "Please provide your details."),
                "checkout_details": checkout,
                "input_hint": missing_checkout[0]
            }

        # We have all checkout details, move to payment
        session["stage"] = ConversationStage.PAYMENT_SELECTION
        return self._build_payment_selection_response(session)

    async def _handle_payment_method(self, method: str, session: Dict) -> Dict[str, Any]:
        """Handle payment method selection and process payment."""
        session["payment_method"] = method.lower()
        return await self._finalize_booking(session)

    def _build_payment_selection_response(self, session: Dict) -> Dict[str, Any]:
        """Build response for payment method selection."""
        selected_pkg = session.get("selected_package", {})
        total = selected_pkg.get("total_price_usd", 0) if isinstance(selected_pkg, dict) else 0

        return {
            "success": True,
            "type": "payment_selection",
            "message": f"Great! Your total is **${total:,.2f}**.\n\nHow would you like to pay?",
            "suggestions": ["Credit Card", "Debit Card", "Digital Wallet"],
            "payment_methods": [
                {"id": "card", "name": "Credit/Debit Card", "icon": "💳"},
                {"id": "wallet", "name": "Digital Wallet", "icon": "📱"}
            ],
            "total": total,
            "input_hint": "payment_method"
        }

    async def _process_payment(self, session: Dict) -> Dict[str, Any]:
        """Process payment - gets payment method and processes checkout."""
        # Get stored payment method or use default
        method = session.get("payment_method", "card")

        # Get available payment methods
        payment_methods = await self._get_payment_methods_list(session)

        # Find matching method
        selected = None
        for pm in payment_methods:
            if method == "card" and pm.get("type") == "CARD":
                selected = pm
                break
            elif method == "wallet" and pm.get("type") == "WALLET":
                selected = pm
                break

        if not selected and payment_methods:
            selected = payment_methods[0]

        if selected:
            session["stage"] = ConversationStage.PROCESSING
            return await self._process_full_checkout(session, selected)

        return {
            "success": False,
            "type": "error",
            "message": "No payment methods available. Please try again."
        }

    async def _finalize_booking(self, session: Dict) -> Dict[str, Any]:
        """Finalize booking with selected payment method."""
        return await self._process_payment(session)

    async def _handle_by_stage(self, message: str, session: Dict) -> Dict[str, Any]:
        """Fallback: handle message based on current stage."""
        stage = session["stage"]

        if stage == ConversationStage.GREETING:
            return await self._handle_greeting_stage(message, session)
        elif stage == ConversationStage.GATHERING_INFO:
            return await self._handle_gathering_stage(message, session)
        elif stage == ConversationStage.CONFIRMING_SEARCH:
            return await self._handle_confirm_stage(message, session)
        elif stage == ConversationStage.SHOWING_PACKAGES:
            return await self._handle_packages_stage(message, session)
        elif stage == ConversationStage.CHECKOUT_DETAILS:
            return await self._handle_checkout_details_stage(message, session)
        elif stage == ConversationStage.PAYMENT_SELECTION:
            return await self._handle_payment_selection_stage(message, session)
        else:
            return await self._handle_greeting_stage(message, session)

    async def _handle_greeting_stage(self, message: str, session: Dict) -> Dict[str, Any]:
        """Handle initial greeting and detect if user provides trip details."""
        msg_lower = message.lower().strip()

        # Pure greeting patterns
        pure_greetings = ['hi', 'hello', 'hey', 'howdy', 'hola', 'greetings',
                         'good morning', 'good afternoon', 'good evening']

        if msg_lower in pure_greetings:
            session["stage"] = ConversationStage.GATHERING_INFO
            return {
                "success": True,
                "type": "conversation",
                "message": "Hello! 👋 Welcome to AP2 Travel Assistant!\n\nI'm here to help you plan your perfect trip. Where would you like to go?",
                "suggestions": [
                    "I want to visit Dubai",
                    "Planning a trip to Tokyo",
                    "Looking for a Paris getaway",
                    "Beach vacation in Bali"
                ],
                "input_hint": "destination"
            }

        # Check if user provided travel details right away
        has_destination = any(dest in msg_lower for dest in ['dubai', 'tokyo', 'paris', 'london', 'bali', 'rome', 'new york', 'singapore', 'barcelona', 'amsterdam'])
        if has_destination or any(kw in msg_lower for kw in ['trip', 'travel', 'vacation', 'visit', 'flight', 'book']):
            # Parse whatever info is provided and move to gathering
            return await self._process_travel_info(message, session)

        # Generic greeting with some context
        session["stage"] = ConversationStage.GATHERING_INFO
        return {
            "success": True,
            "type": "conversation",
            "message": "Hello! 👋 I'm your AI travel assistant powered by AP2 secure checkout.\n\nTell me about your dream vacation - where would you like to go?",
            "suggestions": [
                "Dubai for a luxury getaway",
                "Tokyo for adventure",
                "Paris for romance",
                "Bali for relaxation"
            ],
            "input_hint": "destination"
        }

    async def _handle_gathering_stage(self, message: str, session: Dict) -> Dict[str, Any]:
        """Progressively gather travel information."""
        return await self._process_travel_info(message, session)

    async def _process_travel_info(self, message: str, session: Dict) -> Dict[str, Any]:
        """Use LLM to extract travel info and determine what's missing."""

        # Get current collected info
        collected = session.get("collected_info", {})

        # Use LLM to extract info from the message
        extracted = await self._extract_travel_info(message, collected)

        if extracted:
            # Merge extracted info with collected
            for key, value in extracted.items():
                if value and value != "null" and value != "unknown":
                    collected[key] = value
            session["collected_info"] = collected

        # Check what we have vs what we need
        missing = self._get_missing_fields(collected)

        if not missing:
            # We have enough info - move to confirmation
            session["stage"] = ConversationStage.CONFIRMING_SEARCH
            return self._build_confirmation_response(collected, session)

        # We're still gathering info
        session["stage"] = ConversationStage.GATHERING_INFO
        return self._build_gathering_response(collected, missing)

    async def _extract_travel_info(self, message: str, current_info: Dict) -> Optional[Dict]:
        """Use LLM to extract travel information from message."""

        # For short/simple messages, try simple extraction first (faster, more reliable)
        if len(message.strip()) < 30 or len(message.split()) <= 4:
            simple_result = self._simple_extract(message)
            if simple_result:
                logger.info(f"Using simple extraction for short message: {simple_result}")
                return simple_result

        current_date = datetime.now().strftime('%Y-%m-%d')

        prompt = f"""Extract travel info from the user message. Output ONLY a JSON object, nothing else.

User message: "{message}"
Current info: {json.dumps(current_info) if current_info else "{}"}
Today: {current_date}

Output this exact JSON format with extracted values (use null if not mentioned):
{{"destination": null, "origin": null, "travel_dates": null, "travelers": null, "budget_usd": null, "cabin_class": null, "preferences": null}}

Examples:
- "Paris" -> {{"destination": "Paris", "origin": null, "travel_dates": null, "travelers": null, "budget_usd": null, "cabin_class": null, "preferences": null}}
- "next month" -> {{"destination": null, "origin": null, "travel_dates": {{"start": "2026-03-21", "end": "2026-03-26"}}, "travelers": null, "budget_usd": null, "cabin_class": null, "preferences": null}}
- "2 people" -> {{"destination": null, "origin": null, "travel_dates": null, "travelers": 2, "budget_usd": null, "cabin_class": null, "preferences": null}}

Output JSON only:"""

        try:
            start_time = time.time()
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": 400}
            )

            duration = time.time() - start_time
            response_text = response["message"]["content"]

            log_llm_call(logger, OLLAMA_MODEL, prompt[:200], response_text[:200], duration)

            # Extract JSON - handle various LLM output formats
            json_text = response_text

            # Remove qwen3 thinking tags if present
            if "<think>" in json_text:
                json_text = re.sub(r'<think>.*?</think>', '', json_text, flags=re.DOTALL)

            # Try to extract JSON from code blocks
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0]
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0]

            # Try to find JSON object directly
            json_text = json_text.strip()
            if not json_text.startswith('{'):
                # Look for JSON object in the text
                match = re.search(r'\{[^{}]*\}', json_text, re.DOTALL)
                if match:
                    json_text = match.group(0)

            # Clean up common issues
            json_text = json_text.strip()

            if not json_text or not json_text.startswith('{'):
                logger.warning(f"No JSON found in response: {response_text[:100]}")
                return self._simple_extract(message)

            return json.loads(json_text)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e} - Response: {response_text[:100] if 'response_text' in locals() else 'N/A'}")
            return self._simple_extract(message)
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            # Fallback: simple pattern matching
            return self._simple_extract(message)

    def _simple_extract(self, message: str) -> Dict:
        """Simple pattern-based extraction as fallback."""
        msg_lower = message.lower().strip()
        result = {}

        # Destinations - comprehensive list
        destinations = {
            # Major international
            'dubai': 'Dubai', 'tokyo': 'Tokyo', 'paris': 'Paris',
            'london': 'London', 'bali': 'Bali', 'rome': 'Rome',
            'new york': 'New York', 'nyc': 'New York', 'singapore': 'Singapore',
            'barcelona': 'Barcelona', 'amsterdam': 'Amsterdam',
            'sydney': 'Sydney', 'bangkok': 'Bangkok', 'maldives': 'Maldives',
            'hawaii': 'Hawaii', 'hong kong': 'Hong Kong', 'los angeles': 'Los Angeles',
            'miami': 'Miami', 'las vegas': 'Las Vegas', 'cancun': 'Cancun',
            'greece': 'Greece', 'santorini': 'Santorini', 'italy': 'Italy',
            'spain': 'Spain', 'japan': 'Japan', 'thailand': 'Thailand',
            'france': 'France', 'uk': 'London', 'usa': 'New York',
            'australia': 'Sydney', 'brazil': 'Brazil',
            'mexico': 'Mexico', 'canada': 'Canada', 'iceland': 'Iceland',
            'switzerland': 'Switzerland', 'austria': 'Austria', 'portugal': 'Portugal',
            'morocco': 'Morocco', 'egypt': 'Egypt', 'south africa': 'South Africa',
            # Indian cities
            'bangalore': 'Bangalore', 'bengaluru': 'Bangalore',
            'mumbai': 'Mumbai', 'bombay': 'Mumbai',
            'delhi': 'Delhi', 'new delhi': 'New Delhi',
            'chennai': 'Chennai', 'madras': 'Chennai',
            'kolkata': 'Kolkata', 'calcutta': 'Kolkata',
            'hyderabad': 'Hyderabad', 'pune': 'Pune',
            'goa': 'Goa', 'jaipur': 'Jaipur', 'agra': 'Agra',
            'kerala': 'Kerala', 'kochi': 'Kochi', 'cochin': 'Kochi',
            'udaipur': 'Udaipur', 'varanasi': 'Varanasi',
            'india': 'India',
            # More Asian
            'seoul': 'Seoul', 'kuala lumpur': 'Kuala Lumpur', 'kl': 'Kuala Lumpur',
            'taipei': 'Taipei', 'osaka': 'Osaka', 'kyoto': 'Kyoto',
            'hanoi': 'Hanoi', 'ho chi minh': 'Ho Chi Minh City', 'saigon': 'Ho Chi Minh City',
            'phuket': 'Phuket', 'bora bora': 'Bora Bora', 'fiji': 'Fiji',
            # European
            'berlin': 'Berlin', 'munich': 'Munich', 'prague': 'Prague',
            'vienna': 'Vienna', 'budapest': 'Budapest', 'athens': 'Athens',
            'lisbon': 'Lisbon', 'madrid': 'Madrid', 'milan': 'Milan', 'venice': 'Venice',
            'florence': 'Florence', 'dublin': 'Dublin', 'edinburgh': 'Edinburgh',
            'copenhagen': 'Copenhagen', 'stockholm': 'Stockholm', 'oslo': 'Oslo',
            # Middle East
            'abu dhabi': 'Abu Dhabi', 'doha': 'Doha', 'qatar': 'Qatar',
            'riyadh': 'Riyadh', 'jeddah': 'Jeddah', 'jerusalem': 'Jerusalem',
            'tel aviv': 'Tel Aviv', 'oman': 'Oman', 'muscat': 'Muscat',
        }
        for key, value in destinations.items():
            if key in msg_lower:
                result['destination'] = value
                logger.info(f"[SimpleExtract] Found destination: {value}")
                break

        # Travelers - handle various patterns
        # First check for solo/single traveler phrases
        solo_patterns = [
            r'\bjust\s*me\b', r'\bme\s*only\b', r'\bonly\s*me\b', r'\bmyself\b',
            r'\bsolo\b', r'\balone\b', r'\bsingle\s*traveler\b', r'\b1\s*person\b',
            r'\bone\s*person\b', r'\bjust\s*1\b', r'\bjust\s*one\b', r'\bonly\s*1\b',
            r'\bonly\s*one\b', r'\bi\s*am\s*alone\b', r'\bgoing\s*alone\b',
            r'^\s*1\s*$', r'^\s*me\s*$', r'^\s*one\s*$',
            r'just\s*me\s*\(\s*1\s*\)',  # "Just me (1)" - exact match for suggestion
        ]
        for pattern in solo_patterns:
            if re.search(pattern, msg_lower):
                result['travelers'] = 1
                logger.info(f"[SimpleExtract] Found solo traveler: 1")
                break

        # Couple/pair patterns
        if 'travelers' not in result:
            couple_patterns = [r'\bcouple\b', r'\bpair\b', r'\bus\s*two\b', r'\btwo\s*of\s*us\b', r'\bmy\s*partner\b', r'\bwith\s*spouse\b', r'\bwith\s*wife\b', r'\bwith\s*husband\b']
            for pattern in couple_patterns:
                if re.search(pattern, msg_lower):
                    result['travelers'] = 2
                    logger.info(f"[SimpleExtract] Found couple: 2")
                    break

        # Numeric patterns - updated to match suggestions exactly
        if 'travelers' not in result:
            traveler_patterns = [
                # Match suggestions like "2 travelers", "4 travelers (family)"
                r'(\d+)\s*travelers?\s*(?:\([^)]*\))?',
                r'(\d+)\s*(?:people|persons|travellers|adults|guests|pax)',
                r'(?:for|with)\s*(\d+)\s*(?:people|persons|travelers|adults)?',
                r'(\d+)\s*of\s*us',
                r'we\s*are\s*(\d+)',
                r'group\s*of\s*(\d+)',  # "Group of 6"
                r'family\s*of\s*(\d+)',
                r'^\s*(\d+)\s*$',  # Just a number
            ]
            for pattern in traveler_patterns:
                match = re.search(pattern, msg_lower)
                if match:
                    num = int(match.group(1))
                    if 1 <= num <= 20:
                        result['travelers'] = num
                        logger.info(f"[SimpleExtract] Found travelers: {num}")
                        break

        # Word-based numbers for travelers
        word_nums = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                     'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                     'a': 1, 'an': 1, 'couple': 2, 'few': 3}

        if 'travelers' not in result:
            for word, num in word_nums.items():
                # Match word + people/travelers context (skip a/an/couple/few alone)
                if word not in ['a', 'an', 'couple', 'few']:
                    if re.search(rf'\b{word}\b.*(?:people|person|travelers|adults|of us)', msg_lower):
                        result['travelers'] = num
                        logger.info(f"[SimpleExtract] Found travelers (word): {num}")
                        break

        # Dates - comprehensive pattern matching
        today = datetime.now()
        dates_found = False

        # Helper to parse number from word or digit
        def parse_num(s):
            return word_nums.get(s.lower(), int(s) if s.isdigit() else 1)

        # "in X days/weeks/months" or just "X days/weeks/months" pattern
        time_pattern = re.search(r'(?:in\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a|an|couple|few)\s+(day|days|week|weeks|month|months)(?:\s+(?:from now|later|away|time))?', msg_lower)
        if time_pattern:
            num = parse_num(time_pattern.group(1))
            unit = time_pattern.group(2)

            if 'day' in unit:
                start = today + timedelta(days=num)
            elif 'week' in unit:
                start = today + timedelta(weeks=num)
            else:  # month
                start = today + timedelta(days=num * 30)

            result['travel_dates'] = {
                'start': start.strftime('%Y-%m-%d'),
                'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
            }
            dates_found = True
            logger.info(f"[SimpleExtract] Found dates: {num} {unit}")

        # "tomorrow" / "today"
        if not dates_found and 'tomorrow' in msg_lower:
            start = today + timedelta(days=1)
            result['travel_dates'] = {
                'start': start.strftime('%Y-%m-%d'),
                'end': (start + timedelta(days=3)).strftime('%Y-%m-%d')
            }
            dates_found = True
            logger.info(f"[SimpleExtract] Found dates: tomorrow")

        if not dates_found and ('today' in msg_lower or 'tonight' in msg_lower):
            result['travel_dates'] = {
                'start': today.strftime('%Y-%m-%d'),
                'end': (today + timedelta(days=3)).strftime('%Y-%m-%d')
            }
            dates_found = True
            logger.info(f"[SimpleExtract] Found dates: today")

        # "next week" / "next month" / "next year"
        if not dates_found and 'next week' in msg_lower:
            start = today + timedelta(days=7)
            result['travel_dates'] = {
                'start': start.strftime('%Y-%m-%d'),
                'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
            }
            dates_found = True
            logger.info(f"[SimpleExtract] Found dates: next week")

        if not dates_found and 'next month' in msg_lower:
            start = today + timedelta(days=30)
            result['travel_dates'] = {
                'start': start.strftime('%Y-%m-%d'),
                'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
            }
            dates_found = True
            logger.info(f"[SimpleExtract] Found dates: next month")

        if not dates_found and 'next year' in msg_lower:
            start = datetime(today.year + 1, 1, 15)
            result['travel_dates'] = {
                'start': start.strftime('%Y-%m-%d'),
                'end': (start + timedelta(days=7)).strftime('%Y-%m-%d')
            }
            dates_found = True
            logger.info(f"[SimpleExtract] Found dates: next year")

        # Weekend patterns
        if not dates_found:
            weekend_match = re.search(r'(this|next|coming|upcoming)\s*weekend', msg_lower)
            if weekend_match or 'weekend' in msg_lower:
                days_until_sat = (5 - today.weekday()) % 7
                if days_until_sat == 0:
                    days_until_sat = 7
                # "next weekend" means the weekend after this one
                if weekend_match and weekend_match.group(1) == 'next':
                    days_until_sat += 7
                start = today + timedelta(days=days_until_sat)
                result['travel_dates'] = {
                    'start': start.strftime('%Y-%m-%d'),
                    'end': (start + timedelta(days=2)).strftime('%Y-%m-%d')
                }
                dates_found = True
                logger.info(f"[SimpleExtract] Found dates: weekend")

        # Months dictionary
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7,
            'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

        # Date range within month FIRST (e.g., "March 15-20", "March 15 to 20")
        # Check this before month range to avoid "15-20" being parsed as months
        if not dates_found:
            range_match = re.search(r'(\w+)\s+(\d{1,2})\s*(?:-|to)\s*(\d{1,2})', msg_lower)
            if range_match and range_match.group(1) in months:
                month_num = months[range_match.group(1)]
                start_day = int(range_match.group(2))
                end_day = int(range_match.group(3))
                year = today.year
                if month_num < today.month:
                    year += 1
                try:
                    start = datetime(year, month_num, start_day)
                    end = datetime(year, month_num, end_day)
                    result['travel_dates'] = {
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    }
                    dates_found = True
                    logger.info(f"[SimpleExtract] Found date range: {range_match.group(0)}")
                except ValueError:
                    pass

        # Month range pattern (e.g., "March to April", "from March to May")
        if not dates_found:
            month_range = re.search(r'(?:from\s+)?(\w+)\s+(?:to|through|thru|-)\s+(\w+)', msg_lower)
            if month_range:
                m1, m2 = month_range.group(1), month_range.group(2)
                if m1 in months and m2 in months:
                    year = today.year
                    if months[m1] < today.month:
                        year += 1
                    start = datetime(year, months[m1], 15)
                    end_year = year if months[m2] >= months[m1] else year + 1
                    end = datetime(end_year, months[m2], 15)
                    result['travel_dates'] = {
                        'start': start.strftime('%Y-%m-%d'),
                        'end': end.strftime('%Y-%m-%d')
                    }
                    dates_found = True
                    logger.info(f"[SimpleExtract] Found month range: {m1} to {m2}")

        # Single month name (e.g., "in March", "March 2026", "early March", "around March")
        if not dates_found:
            for month_name, month_num in months.items():
                if re.search(rf'\b{month_name}\b', msg_lower):
                    # Check for year
                    year_match = re.search(r'20(\d{2})', message)
                    year = int(f"20{year_match.group(1)}") if year_match else today.year

                    # If month already passed this year, use next year
                    if month_num < today.month and year == today.year:
                        year += 1

                    # Check for specific day (e.g., "March 15" or "15th March")
                    day_match = re.search(rf'{month_name}\s+(\d{{1,2}})|(\d{{1,2}})\s*(st|nd|rd|th)?\s*(of\s+)?{month_name}', msg_lower)
                    if day_match:
                        day = int(day_match.group(1) or day_match.group(2))
                    elif 'early' in msg_lower or 'beginning' in msg_lower or 'start of' in msg_lower:
                        day = 5
                    elif 'mid' in msg_lower or 'middle' in msg_lower:
                        day = 15
                    elif 'late' in msg_lower or 'end of' in msg_lower:
                        day = 25
                    elif 'around' in msg_lower or 'sometime' in msg_lower or 'maybe' in msg_lower:
                        day = 15
                    else:
                        day = 15  # Default to middle of month

                    try:
                        start = datetime(year, month_num, min(day, 28))
                        result['travel_dates'] = {
                            'start': start.strftime('%Y-%m-%d'),
                            'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
                        }
                        dates_found = True
                        logger.info(f"[SimpleExtract] Found dates: {month_name} {day}, {year}")
                    except ValueError:
                        day = 28
                        start = datetime(year, month_num, day)
                        result['travel_dates'] = {
                            'start': start.strftime('%Y-%m-%d'),
                            'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
                        }
                        dates_found = True
                    break

        # ISO date pattern (e.g., "2026-03-15")
        if not dates_found:
            iso_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', message)
            if iso_match:
                try:
                    start = datetime(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
                    result['travel_dates'] = {
                        'start': start.strftime('%Y-%m-%d'),
                        'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
                    }
                    dates_found = True
                    logger.info(f"[SimpleExtract] Found ISO date: {iso_match.group(0)}")
                except ValueError:
                    pass

        # US date format (e.g., "03/15/2026", "3/15/26")
        if not dates_found:
            us_date = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', message)
            if us_date:
                try:
                    month = int(us_date.group(1))
                    day = int(us_date.group(2))
                    year = int(us_date.group(3))
                    if year < 100:
                        year += 2000
                    start = datetime(year, month, day)
                    result['travel_dates'] = {
                        'start': start.strftime('%Y-%m-%d'),
                        'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
                    }
                    dates_found = True
                    logger.info(f"[SimpleExtract] Found US date: {us_date.group(0)}")
                except ValueError:
                    pass

        # European date format (e.g., "15/03/2026", "15.03.2026")
        if not dates_found:
            eu_date = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})', message)
            if eu_date:
                try:
                    day = int(eu_date.group(1))
                    month = int(eu_date.group(2))
                    year = int(eu_date.group(3))
                    if year < 100:
                        year += 2000
                    # Validate - if day > 12 and month <= 12, it's likely EU format
                    if day > 12 and month <= 12:
                        start = datetime(year, month, day)
                        result['travel_dates'] = {
                            'start': start.strftime('%Y-%m-%d'),
                            'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
                        }
                        dates_found = True
                        logger.info(f"[SimpleExtract] Found EU date: {eu_date.group(0)}")
                except ValueError:
                    pass

        # Year only (e.g., "in 2026", "2027")
        if not dates_found:
            year_only = re.search(r'\b(202[5-9]|203[0-9])\b', message)
            if year_only:
                year = int(year_only.group(1))
                # Default to mid-year
                start = datetime(year, 6, 15) if year > today.year else today + timedelta(days=30)
                result['travel_dates'] = {
                    'start': start.strftime('%Y-%m-%d'),
                    'end': (start + timedelta(days=7)).strftime('%Y-%m-%d')
                }
                dates_found = True
                logger.info(f"[SimpleExtract] Found year: {year}")

        # Season patterns
        if not dates_found:
            if 'summer' in msg_lower:
                year = today.year if today.month < 6 else today.year + 1
                start = datetime(year, 7, 1)
                result['travel_dates'] = {
                    'start': start.strftime('%Y-%m-%d'),
                    'end': (start + timedelta(days=7)).strftime('%Y-%m-%d')
                }
                dates_found = True
                logger.info(f"[SimpleExtract] Found season: summer")
            elif 'winter' in msg_lower:
                year = today.year if today.month < 12 else today.year + 1
                start = datetime(year, 12, 20)
                result['travel_dates'] = {
                    'start': start.strftime('%Y-%m-%d'),
                    'end': (start + timedelta(days=7)).strftime('%Y-%m-%d')
                }
                dates_found = True
                logger.info(f"[SimpleExtract] Found season: winter")
            elif 'spring' in msg_lower:
                year = today.year if today.month < 3 else today.year + 1
                start = datetime(year, 4, 1)
                result['travel_dates'] = {
                    'start': start.strftime('%Y-%m-%d'),
                    'end': (start + timedelta(days=7)).strftime('%Y-%m-%d')
                }
                dates_found = True
                logger.info(f"[SimpleExtract] Found season: spring")
            elif 'fall' in msg_lower or 'autumn' in msg_lower:
                year = today.year if today.month < 9 else today.year + 1
                start = datetime(year, 10, 1)
                result['travel_dates'] = {
                    'start': start.strftime('%Y-%m-%d'),
                    'end': (start + timedelta(days=7)).strftime('%Y-%m-%d')
                }
                dates_found = True
                logger.info(f"[SimpleExtract] Found season: fall")

        # Holiday patterns
        if not dates_found:
            if 'christmas' in msg_lower:
                year = today.year if today.month < 12 or (today.month == 12 and today.day < 20) else today.year + 1
                result['travel_dates'] = {
                    'start': f'{year}-12-23',
                    'end': f'{year}-12-28'
                }
                dates_found = True
                logger.info(f"[SimpleExtract] Found holiday: christmas")
            elif 'new year' in msg_lower or 'newyear' in msg_lower:
                year = today.year + 1
                result['travel_dates'] = {
                    'start': f'{year}-12-30',
                    'end': f'{year + 1}-01-03'
                }
                dates_found = True
                logger.info(f"[SimpleExtract] Found holiday: new year")
            elif 'thanksgiving' in msg_lower:
                year = today.year if today.month < 11 else today.year + 1
                # 4th Thursday of November
                result['travel_dates'] = {
                    'start': f'{year}-11-25',
                    'end': f'{year}-11-30'
                }
                dates_found = True
                logger.info(f"[SimpleExtract] Found holiday: thanksgiving")

        # Cabin class
        if 'business' in msg_lower:
            result['cabin_class'] = 'business'
        elif 'first class' in msg_lower:
            result['cabin_class'] = 'first'
        elif 'economy' in msg_lower:
            result['cabin_class'] = 'economy'

        # Budget
        budget_match = re.search(r'\$\s*(\d+[,\d]*)', message)
        if budget_match:
            result['budget_usd'] = int(budget_match.group(1).replace(',', ''))
            logger.info(f"[SimpleExtract] Found budget: {result['budget_usd']}")

        if result:
            logger.info(f"[SimpleExtract] Extracted: {result}")

        return result

    def _get_missing_fields(self, collected: Dict) -> List[str]:
        """Get list of missing required fields."""
        missing = []
        for field in self.REQUIRED_FIELDS:
            if field not in collected or not collected[field]:
                missing.append(field)
        return missing

    def _build_gathering_response(self, collected: Dict, missing: List[str]) -> Dict[str, Any]:
        """Build response asking for missing information."""
        # Acknowledge what we have
        ack_parts = []
        if collected.get('destination'):
            ack_parts.append(f"**{collected['destination']}** - great choice!")

        # Ask for the next missing field
        next_field = missing[0]

        if next_field == 'destination':
            question = "Where would you like to travel?"
            suggestions = ["Dubai", "Tokyo", "Paris", "London", "Bali"]
            hint = "destination"
        elif next_field == 'travel_dates':
            question = "When are you planning to travel?"
            suggestions = ["Next week", "March 15-20", "In 2 weeks", "Next month"]
            hint = "dates"
        elif next_field == 'travelers':
            question = "How many travelers will be joining?"
            suggestions = ["Just me (1)", "2 travelers", "4 travelers (family)", "Group of 6"]
            hint = "travelers"
        else:
            question = f"Could you tell me about {next_field}?"
            suggestions = []
            hint = next_field

        ack = f"{' '.join(ack_parts)}\n\n" if ack_parts else ""

        return {
            "success": True,
            "type": "conversation",
            "message": f"{ack}{question}",
            "suggestions": suggestions,
            "input_hint": hint,
            "collected_info": collected,
            "missing_fields": missing
        }

    def _build_confirmation_response(self, collected: Dict, session: Dict) -> Dict[str, Any]:
        """Build response confirming trip details before search."""
        dest = collected.get('destination', 'your destination')
        dates = collected.get('travel_dates', {})
        travelers = collected.get('travelers', 1)
        cabin = collected.get('cabin_class', 'economy')
        budget = collected.get('budget_usd')

        date_str = f"{dates.get('start', 'TBD')} to {dates.get('end', 'TBD')}" if dates else "dates TBD"
        budget_str = f"${budget:,}" if budget else "flexible"

        message = f"""Perfect! Here's what I have for your trip:

🌍 **Destination:** {dest}
📅 **Dates:** {date_str}
👥 **Travelers:** {travelers}
✈️ **Class:** {cabin.title()}
💰 **Budget:** {budget_str}

Would you like me to search for travel packages?"""

        return {
            "success": True,
            "type": "confirmation",
            "message": message,
            "collected_info": collected,
            "suggestions": ["Yes, search for packages", "Change destination", "Change dates", "Add preferences"]
        }

    async def _handle_confirm_stage(self, message: str, session: Dict) -> Dict[str, Any]:
        """Handle confirmation of search."""
        msg_lower = message.lower()

        if any(word in msg_lower for word in ['yes', 'search', 'find', 'go', 'proceed', 'sure', 'ok', 'okay', 'yep']):
            # User confirmed - search for packages
            return await self._search_packages(session)
        elif any(word in msg_lower for word in ['change', 'modify', 'edit', 'update', 'different']):
            # User wants to change something
            session["stage"] = ConversationStage.GATHERING_INFO
            return {
                "success": True,
                "type": "conversation",
                "message": "No problem! What would you like to change?",
                "suggestions": ["Change destination", "Change dates", "Change number of travelers", "Change budget"],
                "collected_info": session.get("collected_info", {})
            }
        else:
            # Treat as additional info
            return await self._process_travel_info(message, session)

    async def _search_packages(self, session: Dict) -> Dict[str, Any]:
        """Search for travel packages based on collected info."""
        collected = session["collected_info"]

        # Create Intent Mandate
        intent_mandate = self._create_intent_mandate(
            intent_data=collected,
            user_id=session["user_id"],
            original_message="Conversational search"
        )

        log_mandate_event(logger, "CREATED", "IntentMandate", intent_mandate.mandate_id)

        # Sign the mandate
        mandate_dict = intent_mandate.model_dump()
        mandate_dict["signature"] = sign_mandate(mandate_dict)
        intent_mandate = IntentMandate(**mandate_dict)

        log_mandate_event(logger, "SIGNED", "IntentMandate", intent_mandate.mandate_id)

        # Get packages from merchant
        packages = await self._get_travel_packages(intent_mandate)

        if packages:
            session["intent_mandate"] = intent_mandate.model_dump()
            session["packages"] = [p.model_dump() for p in packages]
            session["stage"] = ConversationStage.SHOWING_PACKAGES

            return {
                "success": True,
                "type": "packages",
                "message": f"🎉 I found {len(packages)} great packages for your {collected.get('destination', '')} trip!\n\nPlease select a package to continue:",
                "intent_mandate": intent_mandate.model_dump(),
                "packages": [p.model_dump() for p in packages],
                "collected_info": collected
            }
        else:
            return {
                "success": True,
                "type": "conversation",
                "message": "I couldn't find packages matching your criteria. Would you like to try different dates or destination?",
                "suggestions": ["Try different dates", "Try different destination", "Increase budget"],
                "collected_info": collected
            }

    async def _handle_packages_stage(self, message: str, session: Dict) -> Dict[str, Any]:
        """Handle package selection stage."""
        msg_lower = message.lower()

        # Check if user is selecting a package
        if any(word in msg_lower for word in ['value', 'budget', 'cheap', 'affordable']):
            return self._select_package_by_tier(session, 'value')
        elif any(word in msg_lower for word in ['recommended', 'best', 'suggest']):
            return self._select_package_by_tier(session, 'recommended')
        elif any(word in msg_lower for word in ['premium', 'luxury', 'best', 'top']):
            return self._select_package_by_tier(session, 'premium')

        # User might want to see packages again or change something
        if any(word in msg_lower for word in ['show', 'see', 'packages', 'options']):
            return {
                "success": True,
                "type": "packages",
                "message": "Here are your package options:",
                "packages": session.get("packages", []),
                "intent_mandate": session.get("intent_mandate"),
                "collected_info": session.get("collected_info", {})
            }

        return {
            "success": True,
            "type": "conversation",
            "message": "Which package would you like? You can say 'value', 'recommended', or 'premium', or select from the cards above.",
            "suggestions": ["Value package", "Recommended package", "Premium package", "Show packages again"],
            "packages": session.get("packages", [])
        }

    def _select_package_by_tier(self, session: Dict, tier: str) -> Dict[str, Any]:
        """Select a package by tier and move to checkout details."""
        packages = session.get("packages", [])

        selected = None
        for pkg in packages:
            if pkg.get("tier") == tier:
                selected = pkg
                break

        if not selected and packages:
            selected = packages[0]  # Default to first package

        if selected:
            session["selected_package"] = selected
            session["stage"] = ConversationStage.CHECKOUT_DETAILS

            return {
                "success": True,
                "type": "checkout_start",
                "message": f"""Excellent choice! You selected the **{selected.get('tier', 'value').title()}** package for **${selected.get('total_usd', 0):,}**.

To proceed with secure AP2 checkout, I'll need a few details:

**What's your full name?**""",
                "selected_package": selected,
                "suggestions": [],
                "input_hint": "name",
                "checkout_fields_needed": ["name", "email", "address"]
            }

        return {
            "success": True,
            "type": "conversation",
            "message": "I couldn't find that package. Please select from the available options.",
            "packages": packages
        }

    async def _handle_checkout_details_stage(self, message: str, session: Dict) -> Dict[str, Any]:
        """Collect checkout details: name, email, address."""
        checkout = session.get("checkout_details", {})

        if "name" not in checkout:
            # This message should be the name
            checkout["name"] = message.strip()
            session["checkout_details"] = checkout
            return {
                "success": True,
                "type": "conversation",
                "message": f"Thanks, **{checkout['name']}**! 📧 What's your email address?",
                "suggestions": [],
                "input_hint": "email",
                "checkout_progress": {"name": checkout["name"]}
            }

        if "email" not in checkout:
            # Validate email format
            if "@" in message and "." in message:
                checkout["email"] = message.strip()
                session["checkout_details"] = checkout
                return {
                    "success": True,
                    "type": "conversation",
                    "message": "Great! 🏠 And your billing address? (City, Country is fine)",
                    "suggestions": ["New York, USA", "London, UK", "Dubai, UAE"],
                    "input_hint": "address",
                    "checkout_progress": {"name": checkout["name"], "email": checkout["email"]}
                }
            else:
                return {
                    "success": True,
                    "type": "conversation",
                    "message": "That doesn't look like a valid email. Please enter your email address:",
                    "suggestions": [],
                    "input_hint": "email"
                }

        if "address" not in checkout:
            checkout["address"] = message.strip()
            session["checkout_details"] = checkout
            session["stage"] = ConversationStage.PAYMENT_SELECTION

            # Get payment methods
            payment_methods = await self._get_payment_methods_list(session)

            return {
                "success": True,
                "type": "payment_selection",
                "message": f"""Perfect! Here's your checkout summary:

👤 **Name:** {checkout['name']}
📧 **Email:** {checkout['email']}
🏠 **Address:** {checkout['address']}
🎫 **Package:** {session['selected_package']['tier'].title()} - ${session['selected_package']['total_usd']:,}

Please select a payment method:""",
                "checkout_details": checkout,
                "selected_package": session["selected_package"],
                "payment_methods": payment_methods,
                "suggestions": [f"Pay with {pm['network']} ****{pm['last4']}" for pm in payment_methods[:3]]
            }

        # All details collected, shouldn't reach here
        return await self._handle_payment_selection_stage(message, session)

    async def _get_payment_methods_list(self, session: Dict) -> List[Dict]:
        """Get available payment methods."""
        try:
            response = await self.a2a_client.send_message(
                target_url=f"{CREDENTIALS_AGENT_URL}/a2a/credentials_agent",
                text="List available payment methods",
                data={"user_id": session["user_id"]}
            )

            result = response.get("result", {})
            for part in result.get("parts", []):
                if part.get("kind") == "data":
                    methods = part.get("data", {}).get("payment_methods", [])
                    if methods:
                        return methods
        except Exception as e:
            logger.warning(f"Failed to get payment methods: {e}")

        # Return mock payment methods
        return [
            {"token": "tok_visa_4242", "type": "CARD", "network": "Visa", "last4": "4242"},
            {"token": "tok_mc_5555", "type": "CARD", "network": "Mastercard", "last4": "5555"},
            {"token": "tok_amex_1111", "type": "CARD", "network": "Amex", "last4": "1111"}
        ]

    async def _handle_payment_selection_stage(self, message: str, session: Dict) -> Dict[str, Any]:
        """Handle payment method selection and process payment."""
        msg_lower = message.lower()

        # Detect which payment method
        payment_methods = await self._get_payment_methods_list(session)
        selected_method = None

        for pm in payment_methods:
            if pm["network"].lower() in msg_lower or pm["last4"] in message:
                selected_method = pm
                break

        if not selected_method and payment_methods:
            # Default to first if mentioned 'pay' or similar
            if any(word in msg_lower for word in ['pay', 'first', 'visa', 'card', 'yes', 'proceed']):
                selected_method = payment_methods[0]

        if selected_method:
            # Process payment
            session["stage"] = ConversationStage.PROCESSING
            return await self._process_full_checkout(session, selected_method)

        return {
            "success": True,
            "type": "payment_selection",
            "message": "Please select a payment method to complete your booking:",
            "payment_methods": payment_methods,
            "suggestions": [f"Pay with {pm['network']} ****{pm['last4']}" for pm in payment_methods[:3]]
        }

    async def _process_full_checkout(self, session: Dict, payment_method: Dict) -> Dict[str, Any]:
        """Process the full checkout with cart and payment mandates."""
        checkout = session["checkout_details"]
        package = session["selected_package"]
        intent_mandate = session["intent_mandate"]

        # Build line items
        line_items = self._build_line_items(package)

        # Calculate amounts
        subtotal = sum(item["total_usd"] for item in line_items)
        taxes = subtotal * 0.095
        fees = subtotal * 0.025
        total = subtotal + taxes + fees

        amounts = {
            "subtotal_usd": round(subtotal, 2),
            "taxes_usd": round(taxes, 2),
            "fees_usd": round(fees, 2),
            "total_usd": round(total, 2),
            "currency": "USD"
        }

        # Create Cart Mandate
        cart_mandate = CartMandate(
            intent_mandate_id=intent_mandate["mandate_id"],
            cart_hash=hash_cart(line_items),
            payer=Payer(
                user_id=session["user_id"],
                email=checkout["email"],
                display_name=checkout["name"],
                credential_provider_url=CREDENTIALS_AGENT_URL
            ),
            payee=Payee(
                merchant_id=MERCHANT_ID,
                merchant_name=MERCHANT_NAME,
                merchant_agent_url=MERCHANT_AGENT_URL
            ),
            line_items=[LineItem(**item) for item in line_items],
            payment_method=PaymentMethod(
                type=payment_method.get("type", "CARD"),
                token=payment_method["token"],
                last4=payment_method.get("last4", "****"),
                network=payment_method.get("network", "Visa")
            ),
            shipping_details=ShippingDetails(
                billing_email=checkout["email"],
                billing_address={"address": checkout["address"]}
            ),
            amounts=Amounts(**amounts),
            refund_policy=RefundPolicy(),
            risk_payload=generate_risk_token(session["user_id"], total)
        )

        # Sign cart mandate
        cart_dict = cart_mandate.model_dump()
        cart_dict["user_signature"] = generate_device_signature(session["user_id"], cart_mandate.mandate_id)
        cart_dict["merchant_signature"] = sign_mandate(cart_dict)
        cart_mandate = CartMandate(**cart_dict)
        session["cart_mandate"] = cart_mandate.model_dump()

        log_mandate_event(logger, "CREATED", "CartMandate", cart_mandate.mandate_id)
        log_mandate_event(logger, "SIGNED", "CartMandate", cart_mandate.mandate_id)

        # Create Payment Mandate
        payment_mandate = PaymentMandate(
            cart_mandate_id=cart_mandate.mandate_id,
            intent_mandate_id=intent_mandate["mandate_id"],
            agent_presence="HUMAN_PRESENT",
            payment_details=PaymentDetails(
                method_name=payment_method.get("type", "CARD"),
                token_url=f"{CREDENTIALS_AGENT_URL}/tokens/{payment_method['token']}",
                total=Amounts(**amounts),
                refund_period_days=30
            ),
            user_authorization=generate_user_authorization(
                session["user_id"],
                cart_mandate.mandate_id,
                total
            ),
            shopping_agent_id=self.agent_id,
            issuer_signals=IssuerSignals(session_id=str(uuid.uuid4()))
        )

        session["payment_mandate"] = payment_mandate.model_dump()
        log_mandate_event(logger, "CREATED", "PaymentMandate", payment_mandate.mandate_id)

        # Process payment through payment agent
        try:
            response = await self.a2a_client.send_payment_mandate(
                target_url=f"{PAYMENT_AGENT_URL}/a2a/payment_agent",
                payment_mandate=payment_mandate.model_dump(),
                cart_mandate=cart_mandate.model_dump(),
                intent_mandate=intent_mandate
            )

            result = response.get("result", {})
            for part in result.get("parts", []):
                if part.get("kind") == "data":
                    confirmation = part.get("data", {}).get("confirmation")
                    if confirmation:
                        session["stage"] = ConversationStage.COMPLETED
                        session["confirmation"] = confirmation

                        return {
                            "success": True,
                            "type": "payment_complete",
                            "message": f"""✅ **Payment Successful!**

🎫 **Confirmation:** {confirmation.get('confirmation_number', 'N/A')}
💳 **Amount:** ${confirmation.get('amount_charged', total):,.2f}
📧 **Receipt sent to:** {checkout['email']}

**AP2 Mandate Chain:**
• Intent Mandate: `{intent_mandate['mandate_id'][:16]}...`
• Cart Mandate: `{cart_mandate.mandate_id[:16]}...`
• Payment Mandate: `{payment_mandate.mandate_id[:16]}...`

Your trip to **{session['collected_info'].get('destination', 'your destination')}** is confirmed! ✈️

Thank you for using AP2 Travel! Would you like to plan another trip?""",
                            "confirmation": confirmation,
                            "mandates": {
                                "intent": intent_mandate,
                                "cart": cart_mandate.model_dump(),
                                "payment": payment_mandate.model_dump()
                            },
                            "suggestions": ["Plan another trip", "View my booking"]
                        }
        except Exception as e:
            logger.error(f"Payment failed: {e}")

        return {
            "success": False,
            "type": "error",
            "message": "Payment processing failed. Please try again.",
            "suggestions": ["Try again", "Use different payment method"]
        }

    def _create_intent_mandate(
        self,
        intent_data: Dict[str, Any],
        user_id: str,
        original_message: str
    ) -> IntentMandate:
        """Create an IntentMandate from parsed intent data."""

        shopping_intent = ShoppingIntent(
            destination=intent_data.get("destination", ""),
            origin=intent_data.get("origin"),
            travel_dates=intent_data.get("travel_dates", {}),
            budget_usd=intent_data.get("budget_usd", 5000),
            travelers=intent_data.get("travelers", 1),
            cabin_class=intent_data.get("cabin_class", "economy"),
            preferences=intent_data.get("preferences", [])
        )

        spending_limits = SpendingLimits(
            max_total_usd=intent_data.get("budget_usd", 5000) * 1.2,  # 20% buffer
            max_per_transaction_usd=intent_data.get("budget_usd", 5000)
        )

        return IntentMandate(
            user_id=user_id,
            natural_language_description=intent_data.get(
                "natural_language_description",
                f"Trip to {shopping_intent.destination}"
            ),
            shopping_intent=shopping_intent,
            spending_limits=spending_limits,
            refundability_required="refundable" in str(intent_data.get("preferences", [])).lower(),
            user_cart_confirmation_required=True,
            prompt_playback=f"User wants {intent_data.get('natural_language_description', original_message)}"
        )

    async def _get_travel_packages(
        self,
        intent_mandate: IntentMandate
    ) -> List[TravelPackage]:
        """Send intent mandate to merchant agent and get travel packages."""
        try:
            response = await self.a2a_client.send_intent_mandate(
                target_url=f"{MERCHANT_AGENT_URL}/a2a/merchant_agent",
                intent_mandate=intent_mandate.model_dump(),
                risk_data=generate_risk_token(
                    intent_mandate.user_id,
                    intent_mandate.spending_limits.max_total_usd
                )
            )

            # Check for errors in response
            if "error" in response:
                logger.error(f"Merchant returned error: {response['error']}")
                return []

            # Extract packages from response
            result = response.get("result", {})
            parts = result.get("parts", [])

            logger.info(f"Merchant response has {len(parts)} parts")

            for part in parts:
                if part.get("kind") == "data":
                    data = part.get("data", {})
                    logger.info(f"Found data part with keys: {list(data.keys())}")
                    if "packages" in data:
                        packages = [TravelPackage(**p) for p in data["packages"]]
                        logger.info(f"Parsed {len(packages)} packages from response")
                        return packages

            logger.warning("No packages found in merchant response parts")
            return []

        except Exception as e:
            logger.error(f"Failed to get packages from merchant: {e}", exc_info=True)
            return []

    async def select_package(
        self,
        session_id: str,
        package_id: str,
        user_email: str = "user@example.com",
        user_name: str = "John Smith"
    ) -> Dict[str, Any]:
        """User selects a package, generate partial cart mandate."""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        # Find selected package
        selected = None
        for pkg in session["packages"]:
            if pkg["package_id"] == package_id:
                selected = pkg
                break

        if not selected:
            return {"success": False, "error": "Package not found"}

        session["selected_package"] = selected

        # Build line items from package
        line_items = self._build_line_items(selected)

        # Calculate amounts
        subtotal = sum(item["total_usd"] for item in line_items)
        taxes = subtotal * 0.095  # ~9.5% taxes
        fees = subtotal * 0.025  # ~2.5% fees

        amounts = {
            "subtotal_usd": round(subtotal, 2),
            "taxes_usd": round(taxes, 2),
            "fees_usd": round(fees, 2),
            "total_usd": round(subtotal + taxes + fees, 2),
            "currency": "USD"
        }

        # Create partial cart mandate (without payment method yet)
        partial_cart = {
            "intent_mandate_id": session["intent_mandate"]["mandate_id"],
            "line_items": line_items,
            "amounts": amounts,
            "payer": {
                "user_id": session["user_id"],
                "email": user_email,
                "display_name": user_name,
                "credential_provider_url": CREDENTIALS_AGENT_URL
            },
            "payee": {
                "merchant_id": MERCHANT_ID,
                "merchant_name": MERCHANT_NAME,
                "merchant_agent_url": MERCHANT_AGENT_URL
            }
        }

        session["partial_cart"] = partial_cart

        return {
            "success": True,
            "session_id": session_id,
            "partial_cart": partial_cart,
            "requires_payment_selection": True
        }

    def _build_line_items(self, package: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert package items to cart line items."""
        items = []
        travelers = package.get("travelers", 1)

        # Flights
        for flight in package.get("flights", []):
            items.append({
                "item_id": flight.get("flight_id", str(uuid.uuid4())[:8]),
                "item_type": "flight",
                "description": f"{flight.get('airline', 'Airline')} {flight.get('flight_number', '')} - {flight.get('cabin_class', 'Economy')}",
                "quantity": travelers,
                "unit_price_usd": flight.get("price_per_person_usd", 500),
                "total_usd": flight.get("price_per_person_usd", 500) * travelers,
                "details": flight
            })

        # Hotels
        for hotel in package.get("hotels", []):
            nights = hotel.get("nights", 1)
            items.append({
                "item_id": hotel.get("hotel_id", str(uuid.uuid4())[:8]),
                "item_type": "hotel",
                "description": f"{hotel.get('name', 'Hotel')} - {hotel.get('room_type', 'Standard')} ({nights} nights)",
                "quantity": nights,
                "unit_price_usd": hotel.get("price_per_night_usd", 200),
                "total_usd": hotel.get("price_per_night_usd", 200) * nights,
                "details": hotel
            })

        # Activities
        for activity in package.get("activities", []):
            items.append({
                "item_id": activity.get("activity_id", str(uuid.uuid4())[:8]),
                "item_type": "activity",
                "description": activity.get("name", "Activity"),
                "quantity": travelers,
                "unit_price_usd": activity.get("price_per_person_usd", 50),
                "total_usd": activity.get("price_per_person_usd", 50) * travelers,
                "details": activity
            })

        return items

    async def get_payment_methods(self, session_id: str) -> Dict[str, Any]:
        """Get available payment methods from credentials agent."""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        try:
            response = await self.a2a_client.send_message(
                target_url=f"{CREDENTIALS_AGENT_URL}/a2a/credentials_agent",
                text="List available payment methods",
                data={"user_id": session["user_id"]}
            )

            result = response.get("result", {})
            parts = result.get("parts", [])

            for part in parts:
                if part.get("kind") == "data":
                    data = part.get("data", {})
                    if "payment_methods" in data:
                        return {
                            "success": True,
                            "payment_methods": data["payment_methods"]
                        }

            return {"success": False, "error": "No payment methods returned"}

        except Exception as e:
            logger.error(f"Failed to get payment methods: {e}")
            # Return mock payment methods
            return {
                "success": True,
                "payment_methods": [
                    {"token": "tok_visa_4242", "type": "CARD", "network": "Visa", "last4": "4242"},
                    {"token": "tok_mc_5555", "type": "CARD", "network": "Mastercard", "last4": "5555"},
                    {"token": "tok_amex_1111", "type": "CARD", "network": "Amex", "last4": "1111"}
                ]
            }

    async def create_cart_mandate(
        self,
        session_id: str,
        payment_token: str
    ) -> Dict[str, Any]:
        """Create and sign full cart mandate with selected payment method."""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        if "partial_cart" not in session:
            return {"success": False, "error": "No cart selected"}

        partial = session["partial_cart"]

        # Get payment method details
        payment_methods = (await self.get_payment_methods(session_id)).get("payment_methods", [])
        selected_payment = next(
            (pm for pm in payment_methods if pm["token"] == payment_token),
            {"token": payment_token, "type": "CARD", "network": "Visa", "last4": "****"}
        )

        # Calculate cart hash
        cart_hash = hash_cart(partial["line_items"])

        # Create full cart mandate
        cart_mandate = CartMandate(
            intent_mandate_id=partial["intent_mandate_id"],
            cart_hash=cart_hash,
            payer=Payer(**partial["payer"]),
            payee=Payee(**partial["payee"]),
            line_items=[LineItem(**item) for item in partial["line_items"]],
            payment_method=PaymentMethod(
                type=selected_payment.get("type", "CARD"),
                token=selected_payment["token"],
                last4=selected_payment.get("last4", "****"),
                network=selected_payment.get("network", "Visa")
            ),
            shipping_details=ShippingDetails(
                billing_email=partial["payer"]["email"]
            ),
            amounts=Amounts(**partial["amounts"]),
            refund_policy=RefundPolicy(),
            risk_payload=generate_risk_token(
                partial["payer"]["user_id"],
                partial["amounts"]["total_usd"],
                session_id
            )
        )

        # Sign the cart mandate
        cart_dict = cart_mandate.model_dump()
        cart_dict["user_signature"] = generate_device_signature(
            partial["payer"]["user_id"],
            cart_mandate.mandate_id
        )
        cart_dict["merchant_signature"] = sign_mandate(cart_dict)

        cart_mandate = CartMandate(**cart_dict)
        session["cart_mandate"] = cart_mandate.model_dump()

        log_mandate_event(logger, "CREATED", "CartMandate", cart_mandate.mandate_id)
        log_mandate_event(logger, "SIGNED", "CartMandate", cart_mandate.mandate_id)

        return {
            "success": True,
            "cart_mandate": cart_mandate.model_dump()
        }

    async def process_payment(self, session_id: str) -> Dict[str, Any]:
        """Create payment mandate and process payment."""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        cart_mandate = session.get("cart_mandate")
        intent_mandate = session.get("intent_mandate")

        if not cart_mandate:
            return {"success": False, "error": "No cart mandate found"}

        # Create payment mandate
        payment_mandate = PaymentMandate(
            cart_mandate_id=cart_mandate["mandate_id"],
            intent_mandate_id=intent_mandate["mandate_id"],
            agent_presence="HUMAN_PRESENT",
            payment_details=PaymentDetails(
                method_name=cart_mandate["payment_method"]["type"],
                token_url=f"{CREDENTIALS_AGENT_URL}/tokens/{cart_mandate['payment_method']['token']}",
                total=Amounts(**cart_mandate["amounts"]),
                refund_period_days=30
            ),
            user_authorization=generate_user_authorization(
                session["user_id"],
                cart_mandate["mandate_id"],
                cart_mandate["amounts"]["total_usd"]
            ),
            shopping_agent_id=self.agent_id,
            issuer_signals=IssuerSignals(
                session_id=session_id
            )
        )

        session["payment_mandate"] = payment_mandate.model_dump()

        log_mandate_event(logger, "CREATED", "PaymentMandate", payment_mandate.mandate_id)

        # Send to payment agent
        try:
            response = await self.a2a_client.send_payment_mandate(
                target_url=f"{PAYMENT_AGENT_URL}/a2a/payment_agent",
                payment_mandate=payment_mandate.model_dump(),
                cart_mandate=cart_mandate,
                intent_mandate=intent_mandate
            )

            result = response.get("result", {})
            parts = result.get("parts", [])

            for part in parts:
                if part.get("kind") == "data":
                    data = part.get("data", {})
                    if "confirmation" in data:
                        session["confirmation"] = data["confirmation"]
                        return {
                            "success": True,
                            "confirmation": data["confirmation"]
                        }

            return {"success": False, "error": "Payment processing failed"}

        except Exception as e:
            logger.error(f"Payment processing failed: {e}")
            return {"success": False, "error": str(e)}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current session state."""
        return self.sessions.get(session_id)

    async def close(self):
        """Cleanup resources."""
        await self.a2a_client.close()


# Singleton instance
shopping_agent = ShoppingAgent()
