"""
AP2 Cryptographic Utilities
Simulated VDC signing for demo purposes
"""

import hashlib
import hmac
import json
import uuid
import base64
from typing import Any, Dict
from datetime import datetime

# Demo signing secret (not for production)
SECRET_KEY = "voyager-ap2-demo-secret-2025"


def sign_mandate(mandate_dict: Dict[str, Any]) -> str:
    """
    Simulate device-backed HMAC-SHA256 signature for a mandate.
    In production, this would use secure enclave / HSM signing.
    """
    # Remove existing signature before signing
    mandate_copy = {k: v for k, v in mandate_dict.items() if k not in ['signature', 'user_signature', 'merchant_signature']}
    payload = json.dumps(mandate_copy, sort_keys=True, default=str)
    signature = hmac.new(
        SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_signature(mandate_dict: Dict[str, Any], signature: str) -> bool:
    """
    Verify a mandate's HMAC-SHA256 signature.
    Returns True if signature is valid.
    """
    expected = sign_mandate(mandate_dict)
    return hmac.compare_digest(expected, signature)


def hash_cart(cart_items: list) -> str:
    """
    Generate SHA256 hash of cart contents for tamper detection.
    Any modification to the cart will produce a different hash.
    """
    content = json.dumps(cart_items, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()


def verify_cart_hash(cart_items: list, expected_hash: str) -> bool:
    """
    Verify that cart contents match the expected hash.
    """
    actual_hash = hash_cart(cart_items)
    return hmac.compare_digest(actual_hash, expected_hash)


def generate_risk_token(user_id: str, amount: float, session_id: str = None) -> str:
    """
    Generate a simulated JWT-like risk payload.
    In production, this would contain actual risk assessment data.
    """
    payload = {
        "user_id": user_id,
        "amount": amount,
        "risk_score": 0.12,  # Low risk for demo
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": session_id or str(uuid.uuid4()),
        "device_trust": "high",
        "behavioral_score": 0.95
    }
    # Simulate JWT structure (header.payload.signature)
    header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
    payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(
        SECRET_KEY.encode(),
        f"{header}.{payload_b64}".encode(),
        hashlib.sha256
    ).hexdigest()[:32]
    return f"{header}.{payload_b64}.{signature}"


def decode_risk_token(risk_token: str) -> Dict[str, Any]:
    """
    Decode and extract the risk payload from a token.
    """
    try:
        parts = risk_token.split(".")
        if len(parts) == 3:
            payload_b64 = parts[1]
            payload_json = base64.b64decode(payload_b64).decode()
            return json.loads(payload_json)
    except Exception:
        pass
    return {"error": "Invalid token"}


def generate_user_authorization(
    user_id: str,
    cart_mandate_id: str,
    total_amount: float
) -> str:
    """
    Generate a hash binding user approval to a specific cart mandate.
    This proves the user authorized THIS exact transaction.
    """
    binding_data = {
        "user_id": user_id,
        "cart_mandate_id": cart_mandate_id,
        "total_amount": total_amount,
        "approved_at": datetime.utcnow().isoformat()
    }
    return hashlib.sha256(
        json.dumps(binding_data, sort_keys=True).encode()
    ).hexdigest()


def generate_device_signature(user_id: str, mandate_id: str) -> str:
    """
    Simulate device-backed signature (like biometric confirmation).
    In production, this would use Secure Enclave / TEE.
    """
    data = f"{user_id}:{mandate_id}:{datetime.utcnow().isoformat()}"
    return hmac.new(
        f"{SECRET_KEY}-device".encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()


def generate_merchant_signature(merchant_id: str, cart_hash: str) -> str:
    """
    Generate merchant's signature on a cart.
    Proves the merchant attests to the cart contents and pricing.
    """
    data = f"{merchant_id}:{cart_hash}:{datetime.utcnow().isoformat()}"
    return hmac.new(
        f"{SECRET_KEY}-merchant".encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()


def generate_transaction_id() -> str:
    """Generate a unique transaction ID."""
    return f"TXN-{uuid.uuid4().hex[:10]}"


def generate_authorization_code() -> str:
    """Generate a simulated authorization code (6 digits)."""
    import random
    return f"AUTH-{random.randint(100000, 999999)}"


def generate_pnr(prefix: str = "VY") -> str:
    """Generate a simulated PNR/confirmation code."""
    import random
    import string
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{chars}"
