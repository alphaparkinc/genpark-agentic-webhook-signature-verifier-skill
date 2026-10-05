"""MCP Server for Agentic Webhook Signature Verifier."""
import sys
import json
import time
from client import AgenticWebhookSignatureVerifier

verifier = AgenticWebhookSignatureVerifier()

def handle_call_tool(params):
    name = params.get("name")
    args = params.get("arguments", {})
    if name != "verify_and_route_webhook":
        raise ValueError(f"Unknown tool: {name}")

    action = args.get("action", "verify_and_route_webhook")
    if action == "verify_and_route_webhook":
        return verifier.verify_and_route_webhook(
            provider=args.get("provider", "GENERIC_HMAC"),
            raw_payload=args.get("raw_payload", "{}"),
            signature_header=args.get("signature_header", ""),
            secret_key=args.get("secret_key", ""),
            timestamp_header=args.get("timestamp_header"),
            tolerance_seconds=args.get("tolerance_seconds")
        )
    elif action == "compute_test_signature":
        sig = verifier.compute_signature(
            provider=args.get("provider", "GENERIC_HMAC"),
            raw_payload=args.get("raw_payload", "{}"),
            secret_key=args.get("secret_key", "")
        )
        return {"signature": sig}
    elif action == "get_verifier_stats":
        return verifier.get_verifier_stats()
    else:
        raise ValueError(f"Invalid action: {action}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Running self-test...")
        payload = '{"event": "payment_succeeded", "amount": 2999}'
        secret = "whsec_test_secret_123"
        sig = verifier.compute_signature("GITHUB", payload, secret)
        res = verifier.verify_and_route_webhook("GITHUB", payload, sig, secret)
        assert res["verified"] is True
        assert res["event_type"] == "payment_succeeded"
        print("Self-test PASSED!")
        sys.exit(0)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            msg_id = req.get("id")
            method = req.get("method")
            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "AgenticWebhookSignatureVerifier", "version": "1.0.0"},
                        "capabilities": {"tools": {}}
                    }
                }
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [{
                            "name": "verify_and_route_webhook",
                            "description": "Verify webhook signature authenticity (HMAC-SHA256), prevent replay attacks with timestamp windows, and route verified event payloads to designated subagents.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string", "enum": ["verify_and_route_webhook", "compute_test_signature", "get_verifier_stats"]},
                                    "provider": {"type": "string"},
                                    "raw_payload": {"type": "string"},
                                    "signature_header": {"type": "string"},
                                    "secret_key": {"type": "string"},
                                    "timestamp_header": {"type": "string"},
                                    "tolerance_seconds": {"type": "integer"}
                                },
                                "required": ["action"]
                            }
                        }]
                    }
                }
            elif method == "tools/call":
                res = handle_call_tool(req.get("params", {}))
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
                }
            else:
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
            print(json.dumps(resp), flush=True)
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}
            print(json.dumps(err_resp), flush=True)

if __name__ == "__main__":
    main()
