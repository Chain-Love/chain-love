import os, sys, json, unittest
sys.path.insert(0, os.path.dirname(__file__))
from validate import rule_http_response_compression

class TestHttpResponseCompression(unittest.TestCase):
    def test_invariants_and_column_meta(self):
        c1 = {"encoding": "zstd", "networks": ["solana"], "methods": ["getBlock"], "sourceUrl": "https://a.com"}
        c2 = {"encoding": "zstd", "networks": ["solana"], "methods": ["getBlock"], "sourceUrl": "https://b.com"}
        bad = {"encoding": "zstd", "networks": ["not-a-repo-net"], "methods": ["getBlock"], "sourceUrl": "https://a.com"}
        mis = {"encoding": "zstd", "networks": ["ethereum"], "methods": ["getBlock"], "sourceUrl": "https://a.com"}
        nets = {"solana", "ethereum"}

        self.assertEqual(rule_http_response_compression([{"httpResponseCompression": [c1]}], network_name="solana", repository_networks=nets), [])
        self.assertTrue(any("Duplicate" in e for e in rule_http_response_compression([{"httpResponseCompression": [c1, c2]}], network_name="solana", repository_networks=nets)))
        self.assertTrue(any("not a valid repository network" in e for e in rule_http_response_compression([{"httpResponseCompression": [bad]}], repository_networks=nets)))
        self.assertTrue(any("does not match listing" in e for e in rule_http_response_compression([{"httpResponseCompression": [mis]}], network_name="solana", repository_networks=nets)))

        meta_path = os.path.join(os.path.dirname(__file__), "..", "meta", "columns.json")
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f: meta = json.load(f)
            self.assertIn("httpResponseCompression", meta)
            self.assertEqual(meta["httpResponseCompression"]["key"], "httpResponseCompression")

if __name__ == "__main__":
    unittest.main()
