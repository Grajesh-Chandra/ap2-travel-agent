"""
AP2 (Agent Payments Protocol) Data Models
Verifiable Digital Credentials (VDCs) for Travel Checkout
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class PaymentMethodType(str, Enum):
    CARD = "CARD"
    WALLET = "WALLET"


class AgentPresence(str, Enum):
    HUMAN_PRESENT = "HUMAN_PRESENT"
    HUMAN_NOT_PRESENT = "HUMAN_NOT_PRESENT"


class MandateType(str, Enum):
    INTENT = "IntentMandate"
    CART = "CartMandate"
    PAYMENT = "PaymentMandate"


# ═══════════════════════════════════════════════════════════════
# INTENT MANDATE - User's signed authorization for shopping
# ═══════════════════════════════════════════════════════════════

class ShoppingIntent(BaseModel):
    destination: str
    origin: Optional[str] = None
    travel_dates: Dict[str, str] = Field(default_factory=dict)  # {start, end}
    budget_usd: float
    travelers: int = 1
    cabin_class: Optional[str] = "economy"
    preferences: List[str] = Field(default_factory=list)


class SpendingLimits(BaseModel):
    max_total_usd: float
    max_per_transaction_usd: float


class IntentMandate(BaseModel):
    mandate_id: str = Field(default_factory=lambda: f"im_{uuid.uuid4().hex[:12]}")
    mandate_type: str = MandateType.INTENT.value
    version: str = "ap2/v1"
    issued_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    expires_at: str = Field(
        default_factory=lambda: (datetime.utcnow() + timedelta(minutes=30)).isoformat() + "Z"
    )
    user_id: str
    natural_language_description: str
    shopping_intent: ShoppingIntent
    chargeable_payment_methods: List[str] = ["CARD", "WALLET"]
    spending_limits: SpendingLimits
    refundability_required: bool = True
    user_cart_confirmation_required: bool = True  # Human-present mode
    prompt_playback: str = ""  # Agent's interpretation
    signature: str = ""  # Simulated HMAC-SHA256

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ═══════════════════════════════════════════════════════════════
# CART MANDATE - Exact booking with tamper-proof hash
# ═══════════════════════════════════════════════════════════════

class Payer(BaseModel):
    user_id: str
    email: str
    display_name: str
    credential_provider_url: str = "http://localhost:8002"


class Payee(BaseModel):
    merchant_id: str
    merchant_name: str
    merchant_agent_url: str


class LineItem(BaseModel):
    item_id: str
    item_type: str  # flight, hotel, activity
    description: str
    quantity: int = 1
    unit_price_usd: float
    total_usd: float
    details: Dict[str, Any] = Field(default_factory=dict)


class PaymentMethod(BaseModel):
    type: str = "CARD"
    token: str
    last4: str
    network: str  # Visa, Mastercard, Amex


class Amounts(BaseModel):
    subtotal_usd: float
    taxes_usd: float
    fees_usd: float
    total_usd: float
    currency: str = "USD"


class RefundPolicy(BaseModel):
    refundable: bool = True
    refund_period_days: int = 30
    conditions: str = "Full refund within 30 days of booking"


class ShippingDetails(BaseModel):
    billing_email: str
    billing_address: Optional[Dict[str, str]] = None


class CartMandate(BaseModel):
    mandate_id: str = Field(default_factory=lambda: f"cm_{uuid.uuid4().hex[:12]}")
    mandate_type: str = MandateType.CART.value
    version: str = "ap2/v1"
    intent_mandate_id: str  # Links back to IntentMandate
    issued_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    cart_hash: str = ""  # SHA256 of cart contents
    payer: Payer
    payee: Payee
    line_items: List[LineItem]
    payment_method: PaymentMethod
    shipping_details: ShippingDetails
    amounts: Amounts
    refund_policy: RefundPolicy = Field(default_factory=RefundPolicy)
    risk_payload: str = ""  # Simulated JWT-like risk token
    user_signature: str = ""  # Simulated device-backed signature
    merchant_signature: str = ""


# ═══════════════════════════════════════════════════════════════
# PAYMENT MANDATE - Payment network signal for authorization
# ═══════════════════════════════════════════════════════════════

class PaymentDetails(BaseModel):
    payment_id: str = Field(default_factory=lambda: f"pay_{uuid.uuid4().hex[:12]}")
    method_name: str = "CARD"
    token_url: str  # CredentialsProvider endpoint
    total: Amounts
    refund_period_days: int = 30


class IssuerSignals(BaseModel):
    risk_score: float = 0.12
    device_fingerprint: str = ""
    session_id: str = ""
    geolocation: Optional[str] = None


class PaymentMandate(BaseModel):
    mandate_id: str = Field(default_factory=lambda: f"pm_{uuid.uuid4().hex[:12]}")
    mandate_type: str = MandateType.PAYMENT.value
    version: str = "ap2/v1"
    cart_mandate_id: str
    intent_mandate_id: str
    agent_presence: str = AgentPresence.HUMAN_PRESENT.value
    payment_details: PaymentDetails
    user_authorization: str = ""  # Hash binding user approval
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    shopping_agent_id: str
    issuer_signals: IssuerSignals = Field(default_factory=IssuerSignals)


# ═══════════════════════════════════════════════════════════════
# PAYMENT CONFIRMATION - Transaction result
# ═══════════════════════════════════════════════════════════════

class BookingReference(BaseModel):
    item_type: str
    pnr: str
    confirmation_number: str
    provider: str


class PaymentConfirmation(BaseModel):
    transaction_id: str = Field(default_factory=lambda: f"TXN-{uuid.uuid4().hex[:10]}")
    authorization_code: str = ""
    status: str = "APPROVED"
    settlement_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    liability_assignment: str = "merchant"  # Human-present default
    payment_mandate_id: str
    cart_mandate_id: str
    intent_mandate_id: str
    booking_references: List[BookingReference] = Field(default_factory=list)
    total_charged: Amounts = None
    audit_trail: str = "Complete — Intent → Cart → Payment"


# ═══════════════════════════════════════════════════════════════
# A2A MESSAGE STRUCTURES WITH AP2 EXTENSIONS
# ═══════════════════════════════════════════════════════════════

class A2AMessagePart(BaseModel):
    kind: str  # "text" or "data"
    text: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class A2AMessage(BaseModel):
    kind: str = "message"
    messageId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str = "agent"
    parts: List[A2AMessagePart] = Field(default_factory=list)


class A2AConfiguration(BaseModel):
    acceptedOutputModes: List[str] = Field(default_factory=list)
    blocking: bool = True


class A2AParams(BaseModel):
    configuration: A2AConfiguration = Field(default_factory=A2AConfiguration)
    message: A2AMessage


class A2ARequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    jsonrpc: str = "2.0"
    method: str = "message/send"
    params: A2AParams


class A2AResponse(BaseModel):
    id: str
    jsonrpc: str = "2.0"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════
# TRAVEL PACKAGE MODELS
# ═══════════════════════════════════════════════════════════════

class Flight(BaseModel):
    flight_id: str
    airline: str
    flight_number: str
    departure_city: str
    arrival_city: str
    departure_time: str
    arrival_time: str
    cabin_class: str
    price_per_person_usd: float
    refundable: bool = True


class Hotel(BaseModel):
    hotel_id: str
    name: str
    location: str
    star_rating: int
    price_per_night_usd: float
    nights: int
    check_in: str
    check_out: str
    room_type: str
    refundable: bool = True


class Activity(BaseModel):
    activity_id: str
    name: str
    description: str
    price_per_person_usd: float
    duration: str
    included: List[str] = Field(default_factory=list)


class TravelPackage(BaseModel):
    package_id: str = Field(default_factory=lambda: f"pkg_{uuid.uuid4().hex[:8]}")
    tier: str  # "value", "recommended", "premium"
    flights: List[Flight]
    hotels: List[Hotel]
    activities: List[Activity]
    total_usd: float
    travelers: int
    nights: int
    description: str = ""


# ═══════════════════════════════════════════════════════════════
# USER SESSION & CHAT MODELS
# ═══════════════════════════════════════════════════════════════

class UserMessage(BaseModel):
    message: str
    user_id: str = "demo_user"
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    intent_mandate: Optional[IntentMandate] = None
    packages: Optional[List[TravelPackage]] = None
    session_id: str
    agent_id: str
