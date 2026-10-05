"""Example usage for AgenticWebhookSignatureVerifier."""
import sys
import json
from client import AgenticWebhookSignatureVerifier

sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=== Agentic Webhook Signature Verifier Demo ===")
    verifier = AgenticWebhookSignatureVerifier(default_tolerance_seconds=300)

    secret = "whsec_super_secret_webhook_key"
    payload = json.dumps({"type": "order.completed", "order_id": "ORD-9912", "amount_usd": 149.50})

    # 1. Compute & Verify Shopify Webhook
    print("\n--- 1. Testing Shopify Ingress Verification ---")
    shopify_sig = verifier.compute_signature("SHOPIFY", payload, secret)
    res_shopify = verifier.verify_and_route_webhook("SHOPIFY", payload, shopify_sig, secret)
    print("Shopify Verification:", json.dumps(res_shopify, indent=2))

    # 2. Compute & Verify Stripe Webhook with Timestamp
    print("\n--- 2. Testing Stripe Ingress with Replay Window Protection ---")
    stripe_sig = verifier.compute_signature("STRIPE", payload, secret)
    res_stripe = verifier.verify_and_route_webhook("STRIPE", payload, stripe_sig, secret)
    print("Stripe Verification:", json.dumps(res_stripe, indent=2))

    # 3. Test Rejection of Tampered Payload
    print("\n--- 3. Testing Tampered Payload Rejection ---")
    tampered_payload = json.dumps({"type": "order.completed", "order_id": "ORD-9912", "amount_usd": 0.01})
    res_tampered = verifier.verify_and_route_webhook("STRIPE", tampered_payload, stripe_sig, secret)
    print("Tampered Result:", json.dumps(res_tampered, indent=2))

if __name__ == "__main__":
    main()
