import json, sys, unittest
from pathlib import Path
from jsonschema import Draft202012Validator
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from csv_to_json import normalize
from validate import rule_x402_payment_routes

BASE_ROUTE = {"endpoint": "https://mcp.coinmarketcap.com/x402/mcp", "network": "eip155:8453", "asset": "0x833589fCD6eDb6E08f4C7C32D4f71b54bdA02913", "scheme": "exact", "sourceUrl": "https://coinmarketcap.com/api/documentation/ai-agent-hub/x402"}
ALGO_ROUTE = {"network": "algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=", "asset": "31566704", "scheme": "exact", "sourceUrl": "https://algometrics.org/", "lastVerifiedAt": "2026-10-24"}

def mcp_row(x402="TRUE", routes=None):
    row = {"slug": "test-mcp", "provider": "Test", "offer": "", "actionButtons": '["[Docs](https://example.com)"]', "serverType": "analytics", "hostingType": "Hosted", "transportType": "http", "mcpEndpoint": "https://mcp.example.com/mcp", "authType": "None", "credentialKey": "", "selfHostedCommand": "", "selfHostedArgs": "", "selfHostedRequiredEnvVars": "", "x402": x402, "onChainWrite": "FALSE", "agentSkills": '["query"]', "tag": '["x402"]', "description": "Test", "planType": "Pay-As-You-Go", "planName": "", "price": "$0.01", "trial": "FALSE", "starred": "FALSE"}
    if routes is not None: row["x402PaymentRoutes"] = routes
    return row

class TestX402PaymentRoutes(unittest.TestCase):
    def test_routes_schema_rules_and_column_meta(self):
        v = Draft202012Validator(json.loads((TOOLS / "schema.json").read_text(encoding="utf-8")))
        for r_cell in (None, "", json.dumps([BASE_ROUTE, ALGO_ROUTE])):
            norm, errs = normalize({"mcpservers": [mcp_row("FALSE" if not r_cell else "TRUE", r_cell)]})
            self.assertEqual(errs, [])
            self.assertTrue(v.is_valid(norm))
            self.assertEqual(rule_x402_payment_routes(norm["mcpservers"]), [])
        parsed = normalize({"mcpservers": [mcp_row("TRUE", json.dumps([BASE_ROUTE, ALGO_ROUTE]))]})[0]["mcpservers"][0]["x402PaymentRoutes"]
        self.assertIsInstance(parsed[1]["asset"], str)
        self.assertNotIn("endpoint", parsed[1])
        for bad_raw in ('[{"network":"eip155:8453"', "eip155:8453,USDC"):
            self.assertTrue(normalize({"mcpservers": [mcp_row("TRUE", bad_raw)]})[1])
        base_ok = normalize({"mcpservers": [mcp_row("TRUE", json.dumps([BASE_ROUTE]))]})[0]["mcpservers"][0]
        self.assertFalse(v.is_valid({"mcpservers": [{**base_ok, "x402PaymentRoutes": [{**ALGO_ROUTE, "asset": 31566704}]}]}))
        self.assertFalse(v.is_valid({"mcpservers": [{**base_ok, "x402PaymentRoutes": [{"network": "eip155:8453"}]}]}))
        self.assertTrue(rule_x402_payment_routes([{**base_ok, "x402": False}]))
        self.assertTrue(rule_x402_payment_routes([{**base_ok, "x402PaymentRoutes": [BASE_ROUTE, {**BASE_ROUTE, "sourceUrl": "https://other.example.com"}]}]))
        self.assertTrue(rule_x402_payment_routes([{**base_ok, "x402PaymentRoutes": [{**ALGO_ROUTE, "network": "algorand:mainnet"}]}]))
        meta = json.loads((TOOLS.parent / "meta" / "columns.json").read_text(encoding="utf-8"))["x402PaymentRoutes"]
        self.assertEqual((meta["key"], meta["sorting"], meta["cellType"], meta["group"]), ("x402PaymentRoutes", "arrayLength", "arrayPopover", "pricing"))
