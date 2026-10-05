"""
Agentic Webhook Signature Verifier & Ingress Multiplexer (Zero External Dependencies)
Provides constant-time HMAC-SHA256 signature verification, replay attack prevention, and routing.
"""
import time
import math
import hashlib
import hmac
import base64
import json
from typing import Dict, Any, List, Optional

class AgenticWebhookSignatureVerifier:
    def __init__(self, default_tolerance_seconds: int = 300):
        self.default_tolerance = default_tolerance_seconds
        self.processed_events: Dict[str, float] = {}

    def _constant_time_compare(self, val_a: str, val_b: str) -> bool:
        return hmac.compare_digest(val_a, val_b)

    def compute_signature(self, provider: str, raw_payload: str, secret_key: str, timestamp: Optional[int] = None) -> str:
        """Computes expected signature string according to provider specification."""
        provider = provider.upper()
        if provider == "STRIPE":
            ts = timestamp or int(time.time())
            signed_payload = f"{ts}.{raw_payload}"
            computed = hmac.new(secret_key.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
            return f"t={ts},v1={computed}"
        elif provider == "SHOPIFY":
            digest = hmac.new(secret_key.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).digest()
            return base64.b64encode(digest).decode("utf-8")
        elif provider == "GITHUB":
            computed = hmac.new(secret_key.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()
            return f"sha256={computed}"
        elif provider == "SLACK":
            ts = timestamp or int(time.time())
            sig_base = f"v0:{ts}:{raw_payload}"
            computed = hmac.new(secret_key.encode("utf-8"), sig_base.encode("utf-8"), hashlib.sha256).hexdigest()
            return f"v0={computed}"
        else: # GENERIC_HMAC
            return hmac.new(secret_key.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_and_route_webhook(
        self,
        provider: str,
        raw_payload: str,
        signature_header: str,
        secret_key: str,
        timestamp_header: Optional[str] = None,
        tolerance_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Verifies webhook authenticity and checks against replay attack windows.
        """
        provider = provider.upper()
        tolerance = tolerance_seconds or self.default_tolerance
        now = time.time()

        # Parse timestamp & signature based on provider
        extracted_timestamp = None
        extracted_sig = signature_header.strip()

        if provider == "STRIPE":
            parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
            extracted_timestamp = int(parts.get("t", 0))
            extracted_sig = parts.get("v1", "")
            signed_payload = f"{extracted_timestamp}.{raw_payload}"
            expected_sig = hmac.new(secret_key.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        elif provider == "SLACK":
            extracted_timestamp = int(timestamp_header or now)
            sig_base = f"v0:{extracted_timestamp}:{raw_payload}"
            expected_sig = "v0=" + hmac.new(secret_key.encode("utf-8"), sig_base.encode("utf-8"), hashlib.sha256).hexdigest()
        elif provider == "SHOPIFY":
            digest = hmac.new(secret_key.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).digest()
            expected_sig = base64.b64encode(digest).decode("utf-8")
        elif provider == "GITHUB":
            expected_sig = "sha256=" + hmac.new(secret_key.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        else: # GENERIC_HMAC
            expected_sig = hmac.new(secret_key.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()

        # Replay window check if timestamp present
        if extracted_timestamp is not None:
            time_delta = abs(now - extracted_timestamp)
            if time_delta > tolerance:
                return {
                    "verified": False,
                    "reason": f"Timestamp drift {time_delta:.1f}s exceeds tolerance {tolerance}s (possible replay attack)",
                    "provider": provider
                }

        # Constant-time comparison
        is_valid = self._constant_time_compare(extracted_sig, expected_sig)
        if not is_valid:
            return {
                "verified": False,
                "reason": "HMAC signature mismatch",
                "provider": provider
            }

        # Deduplication check
        payload_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        if payload_hash in self.processed_events:
            return {
                "verified": True,
                "is_duplicate": True,
                "reason": "Event already processed previously",
                "payload_hash": payload_hash
            }

        self.processed_events[payload_hash] = now

        # Parse event type for agent routing
        parsed_data = {}
        try:
            parsed_data = json.loads(raw_payload)
        except Exception:
            parsed_data = {"raw_text": raw_payload}

        event_type = parsed_data.get("type") or parsed_data.get("event") or "generic_event"

        return {
            "verified": True,
            "is_duplicate": False,
            "provider": provider,
            "event_type": event_type,
            "payload_hash": payload_hash,
            "routed_agent_target": f"handler_{event_type.replace('.', '_')}",
            "verified_at": now
        }

    def get_verifier_stats(self) -> Dict[str, Any]:
        return {
            "total_verified_events": len(self.processed_events),
            "cache_ttl_seconds": self.default_tolerance
        }
