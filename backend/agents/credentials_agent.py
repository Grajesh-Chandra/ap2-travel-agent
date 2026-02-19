"""
Credentials Agent - Payment credential tokenizer
Simulates a payment vault (like Google Pay) for tokenizing payment methods
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import CREDENTIALS_AGENT_ID
from utils import (
    get_logger,
    generate_device_signature,
)

logger = get_logger("CredentialsAgent")


class CredentialsAgent:
    """
    Payment credential tokenizer for secure payment processing.

    Responsibilities:
    1. Simulate a payment credential provider (like Google Pay vault)
    2. Return tokenized payment references (never store real card data)
    3. Provide token URLs for PaymentMandate
    4. Generate device-backed signatures
    """

    def __init__(self):
        self.agent_id = CREDENTIALS_AGENT_ID

        # Mock saved payment methods (simulated wallet)
        self.saved_payment_methods = {
            "demo_user": [
                {
                    "token": "tok_visa_4242",
                    "type": "CARD",
                    "network": "Visa",
                    "last4": "4242",
                    "display_name": "Visa ending in 4242",
                    "is_default": True,
                    "expires": "12/28"
                },
                {
                    "token": "tok_mc_5555",
                    "type": "CARD",
                    "network": "Mastercard",
                    "last4": "5555",
                    "display_name": "Mastercard ending in 5555",
                    "is_default": False,
                    "expires": "03/27"
                },
                {
                    "token": "tok_amex_1111",
                    "type": "CARD",
                    "network": "Amex",
                    "last4": "1111",
                    "display_name": "American Express ending in 1111",
                    "is_default": False,
                    "expires": "09/26"
                }
            ]
        }

    def get_payment_methods(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get available payment methods for a user.
        Returns tokenized references - never actual card numbers.
        """
        logger.info(f"Getting payment methods for user: {user_id}")

        # Return saved methods for known user, or default demo methods
        methods = self.saved_payment_methods.get(
            user_id,
            self.saved_payment_methods.get("demo_user", [])
        )

        logger.info(f"Returning {len(methods)} payment methods")

        return methods

    def tokenize_payment(
        self,
        user_id: str,
        payment_token: str,
        amount_usd: float
    ) -> Dict[str, Any]:
        """
        Create a one-time use tokenization for a payment.
        In production, this would interact with a payment network.
        """
        logger.info(f"Tokenizing payment for user {user_id}, token {payment_token}")

        # Find the payment method
        methods = self.get_payment_methods(user_id)
        selected_method = None

        for method in methods:
            if method["token"] == payment_token:
                selected_method = method
                break

        if not selected_method:
            logger.warning(f"Payment token not found: {payment_token}")
            return {"error": "Payment token not found"}

        # Generate a transaction-specific token
        transaction_token = f"txn_tok_{uuid.uuid4().hex[:12]}"

        # Generate device signature
        device_signature = generate_device_signature(user_id, transaction_token)

        result = {
            "success": True,
            "transaction_token": transaction_token,
            "original_token": payment_token,
            "payment_method": {
                "type": selected_method["type"],
                "network": selected_method["network"],
                "last4": selected_method["last4"]
            },
            "device_signature": device_signature,
            "token_url": f"http://localhost:8002/tokens/{transaction_token}",
            "expires_at": datetime.utcnow().isoformat(),
            "amount_usd": amount_usd
        }

        logger.info(f"Tokenization successful: {transaction_token}")

        return result

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a payment token.
        In production, this would verify with the payment network.
        """
        logger.info(f"Validating token: {token}")

        # For demo purposes, all tokens starting with our prefixes are valid
        is_valid = (
            token.startswith("tok_") or
            token.startswith("txn_tok_")
        )

        return {
            "valid": is_valid,
            "token": token,
            "validated_at": datetime.utcnow().isoformat()
        }

    def get_token_details(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get details about a specific token.
        """
        # Check all users' payment methods
        for user_id, methods in self.saved_payment_methods.items():
            for method in methods:
                if method["token"] == token:
                    return {
                        "token": token,
                        "type": method["type"],
                        "network": method["network"],
                        "last4": method["last4"],
                        "valid": True
                    }

        # Transaction tokens are valid too
        if token.startswith("txn_tok_"):
            return {
                "token": token,
                "type": "CARD",
                "is_transaction_token": True,
                "valid": True
            }

        return None


# Singleton instance
credentials_agent = CredentialsAgent()
