"""
Payment Agent - Payment processor and settlement
Handles PaymentMandate validation and transaction processing
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import PAYMENT_AGENT_ID
from ap2_types import (
    PaymentConfirmation,
    BookingReference,
    Amounts,
)
from utils import (
    get_logger,
    log_mandate_event,
    log_payment_event,
    verify_signature,
    verify_cart_hash,
    generate_transaction_id,
    generate_authorization_code,
    generate_pnr,
)

logger = get_logger("PaymentAgent")


class PaymentAgent:
    """
    Payment processor and settlement agent for AP2 transactions.

    Responsibilities:
    1. Receive PaymentMandate from ShoppingAgent
    2. Validate mandate signatures (simulated)
    3. Verify cart_hash matches CartMandate contents
    4. Check spending limits from IntentMandate
    5. Simulate payment network authorization
    6. Generate payment confirmation with PNR codes
    """

    def __init__(self):
        self.agent_id = PAYMENT_AGENT_ID
        self.transactions: Dict[str, Dict[str, Any]] = {}

    async def process_payment_mandate(
        self,
        payment_mandate: Dict[str, Any],
        cart_mandate: Dict[str, Any],
        intent_mandate: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a PaymentMandate and authorize the transaction.
        """
        logger.info(f"Processing PaymentMandate: {payment_mandate.get('mandate_id', 'unknown')}")
        log_mandate_event(logger, "RECEIVED", "PaymentMandate", payment_mandate.get("mandate_id", ""))

        # Step 1: Validate all mandates
        validation = self._validate_mandates(payment_mandate, cart_mandate, intent_mandate)

        if not validation["valid"]:
            logger.error(f"Mandate validation failed: {validation['errors']}")
            return {
                "success": False,
                "error": "Mandate validation failed",
                "validation_errors": validation["errors"]
            }

        # Step 2: Check spending limits
        total_amount = cart_mandate.get("amounts", {}).get("total_usd", 0)
        spending_limits = intent_mandate.get("spending_limits", {})

        if not self._check_spending_limits(total_amount, spending_limits):
            logger.error("Transaction exceeds spending limits")
            return {
                "success": False,
                "error": "Transaction exceeds authorized spending limits"
            }

        # Step 3: Simulate payment network authorization
        auth_result = await self._authorize_payment(
            payment_mandate=payment_mandate,
            cart_mandate=cart_mandate,
            total_amount=total_amount
        )

        if not auth_result["authorized"]:
            log_payment_event(
                logger,
                "DECLINED",
                auth_result.get("transaction_id", "unknown"),
                total_amount,
                details={"reason": auth_result.get("reason")}
            )
            return {
                "success": False,
                "error": "Payment authorization failed",
                "reason": auth_result.get("reason")
            }

        # Step 4: Generate booking references
        booking_refs = self._generate_booking_references(cart_mandate)

        # Step 5: Create payment confirmation
        confirmation = PaymentConfirmation(
            transaction_id=auth_result["transaction_id"],
            authorization_code=auth_result["authorization_code"],
            status="APPROVED",
            settlement_timestamp=datetime.utcnow().isoformat(),
            liability_assignment="merchant" if payment_mandate.get("agent_presence") == "HUMAN_PRESENT" else "issuer",
            payment_mandate_id=payment_mandate.get("mandate_id", ""),
            cart_mandate_id=cart_mandate.get("mandate_id", ""),
            intent_mandate_id=intent_mandate.get("mandate_id", ""),
            booking_references=booking_refs,
            total_charged=Amounts(**cart_mandate.get("amounts", {})),
            audit_trail="Complete — Intent → Cart → Payment"
        )

        # Store transaction
        self.transactions[confirmation.transaction_id] = {
            "confirmation": confirmation.model_dump(),
            "payment_mandate": payment_mandate,
            "cart_mandate": cart_mandate,
            "intent_mandate": intent_mandate,
            "processed_at": datetime.utcnow().isoformat()
        }

        log_payment_event(
            logger,
            "AUTHORIZED",
            confirmation.transaction_id,
            total_amount,
            details={
                "auth_code": confirmation.authorization_code,
                "liability": confirmation.liability_assignment
            }
        )

        logger.info(f"Payment confirmed: {confirmation.transaction_id}")

        return {
            "success": True,
            "confirmation": confirmation.model_dump()
        }

    def _validate_mandates(
        self,
        payment_mandate: Dict[str, Any],
        cart_mandate: Dict[str, Any],
        intent_mandate: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate all mandate signatures and linkage.
        """
        errors = []

        # Check mandate linkage
        if payment_mandate.get("cart_mandate_id") != cart_mandate.get("mandate_id"):
            errors.append("PaymentMandate cart_mandate_id does not match CartMandate")

        if payment_mandate.get("intent_mandate_id") != intent_mandate.get("mandate_id"):
            errors.append("PaymentMandate intent_mandate_id does not match IntentMandate")

        if cart_mandate.get("intent_mandate_id") != intent_mandate.get("mandate_id"):
            errors.append("CartMandate intent_mandate_id does not match IntentMandate")

        # Verify intent mandate signature (simulated)
        intent_signature = intent_mandate.get("signature")
        if intent_signature:
            # In demo mode, we accept all signatures
            # In production, would call verify_signature()
            log_mandate_event(logger, "VERIFIED", "IntentMandate", intent_mandate.get("mandate_id", ""))

        # Verify cart hash
        line_items = cart_mandate.get("line_items", [])
        expected_hash = cart_mandate.get("cart_hash")

        if expected_hash:
            # Simplified hash check for demo
            log_mandate_event(logger, "VERIFIED", "CartMandate", cart_mandate.get("mandate_id", ""))

        # Check intent mandate not expired
        expires_at = intent_mandate.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                now = datetime.now(expiry.tzinfo) if expiry.tzinfo else datetime.utcnow()
                if expiry < now:
                    errors.append("IntentMandate has expired")
            except Exception as e:
                logger.warning(f"Could not parse expiry: {e}")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }

    def _check_spending_limits(
        self,
        total_amount: float,
        spending_limits: Dict[str, Any]
    ) -> bool:
        """
        Check if transaction is within authorized spending limits.
        """
        max_total = spending_limits.get("max_total_usd", float("inf"))
        max_per_transaction = spending_limits.get("max_per_transaction_usd", float("inf"))

        if total_amount > max_total:
            logger.warning(f"Amount ${total_amount} exceeds max total ${max_total}")
            return False

        if total_amount > max_per_transaction:
            logger.warning(f"Amount ${total_amount} exceeds max per transaction ${max_per_transaction}")
            return False

        return True

    async def _authorize_payment(
        self,
        payment_mandate: Dict[str, Any],
        cart_mandate: Dict[str, Any],
        total_amount: float
    ) -> Dict[str, Any]:
        """
        Simulate payment network authorization.
        In production, this would call actual payment networks.
        """
        logger.info(f"Authorizing payment of ${total_amount}")

        # In demo mode, always approve
        transaction_id = generate_transaction_id()
        authorization_code = generate_authorization_code()

        # Simulate network latency
        import asyncio
        await asyncio.sleep(0.5)

        return {
            "authorized": True,
            "transaction_id": transaction_id,
            "authorization_code": authorization_code,
            "network_response": "APPROVED",
            "processor": "VoyagerPay Demo"
        }

    def _generate_booking_references(
        self,
        cart_mandate: Dict[str, Any]
    ) -> List[BookingReference]:
        """
        Generate PNR/confirmation codes for each booking item.
        """
        booking_refs = []
        line_items = cart_mandate.get("line_items", [])

        # Group items by type
        flights = [item for item in line_items if item.get("item_type") == "flight"]
        hotels = [item for item in line_items if item.get("item_type") == "hotel"]
        activities = [item for item in line_items if item.get("item_type") == "activity"]

        # Generate single PNR for all flights
        if flights:
            booking_refs.append(BookingReference(
                item_type="flight",
                pnr=generate_pnr("EK"),
                confirmation_number=f"FL{uuid.uuid4().hex[:8].upper()}",
                provider=flights[0].get("details", {}).get("airline", "Airline")
            ))

        # Generate confirmation for hotels
        for hotel in hotels:
            hotel_details = hotel.get("details", {})
            booking_refs.append(BookingReference(
                item_type="hotel",
                pnr=generate_pnr("HT"),
                confirmation_number=f"HT{uuid.uuid4().hex[:8].upper()}",
                provider=hotel_details.get("name", "Hotel")
            ))

        # Generate confirmations for activities
        for i, activity in enumerate(activities):
            activity_details = activity.get("details", {})
            booking_refs.append(BookingReference(
                item_type="activity",
                pnr=generate_pnr("AC"),
                confirmation_number=f"AC{uuid.uuid4().hex[:8].upper()}",
                provider=activity_details.get("name", f"Activity {i+1}")
            ))

        return booking_refs

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a processed transaction.
        """
        return self.transactions.get(transaction_id)

    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """
        Get all processed transactions.
        """
        return list(self.transactions.values())


# Singleton instance
payment_agent = PaymentAgent()
