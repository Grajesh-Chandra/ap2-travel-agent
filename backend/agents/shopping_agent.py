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
        Process a user message based on current conversation stage.
        """
        session_id, session = self._get_or_create_session(session_id, user_id)
        session["conversation_history"].append({"role": "user", "content": message})

        logger.info(f"Processing message in stage {session['stage']}: {message[:100]}...")

        # Route to appropriate handler based on stage
        stage = session["stage"]

        if stage == ConversationStage.GREETING:
            response = await self._handle_greeting_stage(message, session)
        elif stage == ConversationStage.GATHERING_INFO:
            response = await self._handle_gathering_stage(message, session)
        elif stage == ConversationStage.CONFIRMING_SEARCH:
            response = await self._handle_confirm_stage(message, session)
        elif stage == ConversationStage.SHOWING_PACKAGES:
            response = await self._handle_packages_stage(message, session)
        elif stage == ConversationStage.CHECKOUT_DETAILS:
            response = await self._handle_checkout_details_stage(message, session)
        elif stage == ConversationStage.PAYMENT_SELECTION:
            response = await self._handle_payment_selection_stage(message, session)
        else:
            response = await self._handle_greeting_stage(message, session)

        response["session_id"] = session_id
        response["stage"] = session["stage"]
        response["agent_id"] = self.agent_id
        session["conversation_history"].append({"role": "assistant", "content": response})

        return response

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
                "message": "Hello! 👋 Welcome to AP2 Travel - where your dream trips meet secure, transparent checkout!\n\nI'm here to help you plan an amazing journey. Where would you like to go?",
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
            'india': 'India', 'australia': 'Sydney', 'brazil': 'Brazil',
            'mexico': 'Mexico', 'canada': 'Canada', 'iceland': 'Iceland',
            'switzerland': 'Switzerland', 'austria': 'Austria', 'portugal': 'Portugal',
            'morocco': 'Morocco', 'egypt': 'Egypt', 'south africa': 'South Africa'
        }
        for key, value in destinations.items():
            if key in msg_lower:
                result['destination'] = value
                logger.info(f"[SimpleExtract] Found destination: {value}")
                break

        # Travelers - handle various patterns
        traveler_patterns = [
            r'(\d+)\s*(?:people|persons|travelers|travellers|adults|guests)',
            r'(?:for|with)\s*(\d+)',
            r'^(\d+)$',  # Just a number
        ]
        for pattern in traveler_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                num = int(match.group(1))
                if 1 <= num <= 10:
                    result['travelers'] = num
                    logger.info(f"[SimpleExtract] Found travelers: {num}")
                    break

        # Word-based numbers
        word_nums = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                     'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
        for word, num in word_nums.items():
            if word in msg_lower and 'travelers' not in result:
                result['travelers'] = num
                logger.info(f"[SimpleExtract] Found travelers (word): {num}")
                break

        # Dates
        if 'next week' in msg_lower:
            start = datetime.now() + timedelta(days=7)
            result['travel_dates'] = {
                'start': start.strftime('%Y-%m-%d'),
                'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
            }
            logger.info(f"[SimpleExtract] Found dates: next week")
        elif 'next month' in msg_lower:
            start = datetime.now() + timedelta(days=30)
            result['travel_dates'] = {
                'start': start.strftime('%Y-%m-%d'),
                'end': (start + timedelta(days=5)).strftime('%Y-%m-%d')
            }
            logger.info(f"[SimpleExtract] Found dates: next month")
        elif 'this weekend' in msg_lower:
            # Find next Saturday
            today = datetime.now()
            days_until_sat = (5 - today.weekday()) % 7
            if days_until_sat == 0:
                days_until_sat = 7
            start = today + timedelta(days=days_until_sat)
            result['travel_dates'] = {
                'start': start.strftime('%Y-%m-%d'),
                'end': (start + timedelta(days=2)).strftime('%Y-%m-%d')
            }
            logger.info(f"[SimpleExtract] Found dates: this weekend")

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
