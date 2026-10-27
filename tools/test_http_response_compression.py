import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(__file__))
from validate import Validator, rule_http_response_compression
from csv_to_json import Category, get_column_order, normalize

class TestHttpResponseCompression(unittest.TestCase):
    def test_compression_contract(self):
        c1 = {"encoding": "zstd", "networks": ["solana"], "methods": ["getBlock"], "sourceUrl": "https://a.com"}
        c2 = dict(c1, sourceUrl="https://b.com"); nets = {"solana", "ethereum"}
        self.assertEqual(rule_http_response_compression([{"httpResponseCompression": [c1]}], network_name="solana", repository_networks=nets), [])
        self.assertTrue(any("Duplicate" in e for e in rule_http_response_compression([{"httpResponseCompression": [c1, c2]}], network_name="solana", repository_networks=nets)))
        self.assertTrue(any("not a valid" in e for e in rule_http_response_compression([{"httpResponseCompression": [{"encoding": "zstd", "networks": ["bad"], "methods": ["m"]}]}], repository_networks=nets)))
        v = Validator(); v.add_rule(lambda d, network_name=None: (_ for _ in ()).throw(TypeError("fail")))
        with self.assertRaises(TypeError): v.validate([{}], network_name="solana")
        norm, errs = normalize({"apis": [{"slug": "s", "httpResponseCompression": '[{"encoding":"zstd","networks":["solana"],"methods":["m"]}]'}]})
        self.assertEqual(errs, []); self.assertIsInstance(norm["apis"][0]["httpResponseCompression"], list)
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f: f.write("slug,httpResponseCompression\n"); p = f.name
        try: self.assertIn("httpResponseCompression", get_column_order([Category("apis", p)], [])["apis"])
        finally: os.unlink(p)
        mpath = os.path.join(os.path.dirname(__file__), "..", "meta", "columns.json")
        if os.path.isfile(mpath):
            with open(mpath, "r", encoding="utf-8") as f: self.assertEqual(json.load(f).get("httpResponseCompression", {}).get("key"), "httpResponseCompression")

if __name__ == "__main__": unittest.main()
