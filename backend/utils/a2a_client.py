"""
A2A (Agent-to-Agent) HTTP Message Client
With AP2 Protocol Extensions
"""

import httpx
import json
import uuid
import time
from typing import Any, Dict, Optional
from datetime import datetime

# AP2 Extension Header
AP2_EXTENSION_HEADER = "X-A2A-Extensions"
AP2_EXTENSION_URI = "https://github.com/google-agentic-commerce/ap2/v1"


class A2AClient:
    """
    HTTP client for A2A protocol communication between agents.
    Includes AP2 extension headers for payment-related messages.
    """

    def __init__(
        self,
        agent_name: str,
        agent_url: str,
        timeout: float = 30.0,
        logger=None
    ):
        self.agent_name = agent_name
        self.agent_url = agent_url
        self.timeout = timeout
        self.logger = logger
        self.client = httpx.AsyncClient(timeout=timeout)

    async def send_message(
        self,
        target_url: str,
        text: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        include_ap2: bool = True,
        extra_parts: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Send an A2A message to another agent.

        Args:
            target_url: URL of the target agent's A2A endpoint
            text: Text content of the message
            data: Structured data to include in the message
            include_ap2: Whether to include AP2 extension header
            extra_parts: Additional message parts

        Returns:
            The response from the target agent
        """
        message_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        # Build message parts
        parts = []
        if text:
            parts.append({"kind": "text", "text": text})
        if data:
            parts.append({"kind": "data", "data": data})
        if extra_parts:
            parts.extend(extra_parts)

        # Construct JSON-RPC 2.0 request
        request_body = {
            "id": request_id,
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "configuration": {
                    "acceptedOutputModes": [],
                    "blocking": True
                },
                "message": {
                    "kind": "message",
                    "messageId": message_id,
                    "role": "agent",
                    "parts": parts
                }
            }
        }

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "X-A2A-Agent": self.agent_name,
            "X-A2A-Message-ID": message_id,
        }

        if include_ap2:
            headers[AP2_EXTENSION_HEADER] = AP2_EXTENSION_URI

        # Send request and measure timing
        start_time = time.time()

        # Extract target agent name from URL
        target_agent = "unknown"
        if "merchant" in target_url:
            target_agent = "merchant_agent"
        elif "credentials" in target_url:
            target_agent = "credentials_agent"
        elif "payment" in target_url:
            target_agent = "payment_agent"
        elif "shopping" in target_url:
            target_agent = "shopping_agent"

        if self.logger:
            self.logger.info(
                f"A2A SENT: {self.agent_name} → {target_agent} [message/send]",
                extra={
                    "type": "a2a_message",
                    "direction": "SENT",
                    "from_agent": self.agent_name,
                    "to_agent": target_agent,
                    "method": "message/send",
                    "message_id": message_id,
                    "target_url": target_url
                }
            )

        try:
            response = await self.client.post(
                target_url,
                json=request_body,
                headers=headers
            )
            response.raise_for_status()

            duration_ms = (time.time() - start_time) * 1000
            result = response.json()

            if self.logger:
                self.logger.info(
                    f"A2A RECEIVED: {target_agent} → {self.agent_name} [response] ({duration_ms:.0f}ms)",
                    extra={
                        "type": "a2a_message",
                        "direction": "RECEIVED",
                        "from_agent": target_agent,
                        "to_agent": self.agent_name,
                        "method": "message/send_response",
                        "message_id": message_id,
                        "duration_ms": round(duration_ms, 2),
                        "payload_size": len(json.dumps(request_body))
                    }
                )

            return result

        except httpx.HTTPStatusError as e:
            if self.logger:
                self.logger.error(
                    f"A2A HTTP error: {e.response.status_code}",
                    extra={
                        "type": "a2a_error",
                        "target_url": target_url,
                        "status_code": e.response.status_code,
                        "error": str(e)
                    }
                )
            raise

        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"A2A request failed: {str(e)}",
                    extra={
                        "type": "a2a_error",
                        "target_url": target_url,
                        "error": str(e)
                    }
                )
            raise

    async def send_intent_mandate(
        self,
        target_url: str,
        intent_mandate: Dict[str, Any],
        risk_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send an IntentMandate to a merchant agent."""
        parts = [
            {"kind": "text", "text": "Process this travel intent mandate"},
            {"kind": "data", "data": {"ap2.mandates.IntentMandate": intent_mandate}},
            {"kind": "data", "data": {"shopping_agent_id": self.agent_name}}
        ]

        if risk_data:
            parts.append({"kind": "data", "data": {"risk_data": risk_data}})

        message_id = str(uuid.uuid4())
        request_body = {
            "id": str(uuid.uuid4()),
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "configuration": {"acceptedOutputModes": [], "blocking": True},
                "message": {
                    "kind": "message",
                    "messageId": message_id,
                    "role": "agent",
                    "parts": parts
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            AP2_EXTENSION_HEADER: AP2_EXTENSION_URI,
            "X-A2A-Agent": self.agent_name,
        }

        if self.logger:
            self.logger.info(
                f"A2A SENT: {self.agent_name} → merchant_agent [send_intent_mandate]",
                extra={
                    "type": "a2a_message",
                    "direction": "SENT",
                    "from_agent": self.agent_name,
                    "to_agent": "merchant_agent",
                    "method": "send_intent_mandate",
                    "message_id": message_id,
                    "mandate_id": intent_mandate.get("mandate_id", "unknown")
                }
            )

        start_time = time.time()
        response = await self.client.post(target_url, json=request_body, headers=headers)
        response.raise_for_status()
        result = response.json()
        duration_ms = (time.time() - start_time) * 1000

        if self.logger:
            self.logger.info(
                f"A2A RECEIVED: merchant_agent → {self.agent_name} [intent_mandate_response] ({duration_ms:.0f}ms)",
                extra={
                    "type": "a2a_message",
                    "direction": "RECEIVED",
                    "from_agent": "merchant_agent",
                    "to_agent": self.agent_name,
                    "method": "intent_mandate_response",
                    "duration_ms": round(duration_ms, 2)
                }
            )

        return result

    async def send_cart_mandate(
        self,
        target_url: str,
        cart_mandate: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a CartMandate for credential tokenization."""
        parts = [
            {"kind": "text", "text": "Tokenize payment for this cart"},
            {"kind": "data", "data": {"ap2.mandates.CartMandate": cart_mandate}},
        ]

        message_id = str(uuid.uuid4())
        request_body = {
            "id": str(uuid.uuid4()),
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "configuration": {"acceptedOutputModes": [], "blocking": True},
                "message": {
                    "kind": "message",
                    "messageId": message_id,
                    "role": "agent",
                    "parts": parts
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            AP2_EXTENSION_HEADER: AP2_EXTENSION_URI,
            "X-A2A-Agent": self.agent_name,
        }

        if self.logger:
            self.logger.info(
                f"A2A SENT: {self.agent_name} → credentials_agent [send_cart_mandate]",
                extra={
                    "type": "a2a_message",
                    "direction": "SENT",
                    "from_agent": self.agent_name,
                    "to_agent": "credentials_agent",
                    "method": "send_cart_mandate",
                    "message_id": message_id,
                    "mandate_id": cart_mandate.get("mandate_id", "unknown")
                }
            )

        start_time = time.time()
        response = await self.client.post(target_url, json=request_body, headers=headers)
        response.raise_for_status()
        result = response.json()
        duration_ms = (time.time() - start_time) * 1000

        if self.logger:
            self.logger.info(
                f"A2A RECEIVED: credentials_agent → {self.agent_name} [cart_mandate_response] ({duration_ms:.0f}ms)",
                extra={
                    "type": "a2a_message",
                    "direction": "RECEIVED",
                    "from_agent": "credentials_agent",
                    "to_agent": self.agent_name,
                    "method": "cart_mandate_response",
                    "duration_ms": round(duration_ms, 2)
                }
            )

        return result

    async def send_payment_mandate(
        self,
        target_url: str,
        payment_mandate: Dict[str, Any],
        cart_mandate: Dict[str, Any],
        intent_mandate: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a PaymentMandate for processing."""
        parts = [
            {"kind": "text", "text": "Process this payment mandate"},
            {"kind": "data", "data": {"ap2.mandates.PaymentMandate": payment_mandate}},
            {"kind": "data", "data": {"ap2.mandates.CartMandate": cart_mandate}},
            {"kind": "data", "data": {"ap2.mandates.IntentMandate": intent_mandate}},
        ]

        message_id = str(uuid.uuid4())
        request_body = {
            "id": str(uuid.uuid4()),
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "configuration": {"acceptedOutputModes": [], "blocking": True},
                "message": {
                    "kind": "message",
                    "messageId": message_id,
                    "role": "agent",
                    "parts": parts
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            AP2_EXTENSION_HEADER: AP2_EXTENSION_URI,
            "X-A2A-Agent": self.agent_name,
        }

        if self.logger:
            self.logger.info(
                f"A2A SENT: {self.agent_name} → payment_agent [send_payment_mandate]",
                extra={
                    "type": "a2a_message",
                    "direction": "SENT",
                    "from_agent": self.agent_name,
                    "to_agent": "payment_agent",
                    "method": "send_payment_mandate",
                    "message_id": message_id,
                    "mandate_id": payment_mandate.get("mandate_id", "unknown")
                }
            )

        start_time = time.time()
        response = await self.client.post(target_url, json=request_body, headers=headers)
        response.raise_for_status()
        result = response.json()
        duration_ms = (time.time() - start_time) * 1000

        if self.logger:
            self.logger.info(
                f"A2A RECEIVED: payment_agent → {self.agent_name} [payment_mandate_response] ({duration_ms:.0f}ms)",
                extra={
                    "type": "a2a_message",
                    "direction": "RECEIVED",
                    "from_agent": "payment_agent",
                    "to_agent": self.agent_name,
                    "method": "payment_mandate_response",
                    "duration_ms": round(duration_ms, 2)
                }
            )

        return result

    async def get_agent_card(self, base_url: str) -> Dict[str, Any]:
        """Fetch an agent's well-known card."""
        response = await self.client.get(f"{base_url}/.well-known/agent.json")
        response.raise_for_status()
        return response.json()

    async def health_check(self, base_url: str) -> bool:
        """Check if an agent is healthy."""
        try:
            response = await self.client.get(f"{base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


def build_a2a_response(
    request_id: str,
    text: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build a JSON-RPC 2.0 response for an A2A message.
    """
    if error:
        return {
            "id": request_id,
            "jsonrpc": "2.0",
            "error": error
        }

    parts = []
    if text:
        parts.append({"kind": "text", "text": text})
    if data:
        parts.append({"kind": "data", "data": data})

    return {
        "id": request_id,
        "jsonrpc": "2.0",
        "result": {
            "kind": "message",
            "messageId": str(uuid.uuid4()),
            "role": "agent",
            "parts": parts
        }
    }


def extract_mandate_from_message(message: Dict[str, Any], mandate_type: str) -> Optional[Dict[str, Any]]:
    """
    Extract a specific mandate type from an A2A message.

    Args:
        message: The A2A request body
        mandate_type: One of "IntentMandate", "CartMandate", "PaymentMandate"

    Returns:
        The mandate dict if found, None otherwise
    """
    try:
        parts = message.get("params", {}).get("message", {}).get("parts", [])
        for part in parts:
            if part.get("kind") == "data":
                data = part.get("data", {})
                mandate_key = f"ap2.mandates.{mandate_type}"
                if mandate_key in data:
                    return data[mandate_key]
        return None
    except Exception:
        return None
