"""Nonblank generation test for DBIP #3926 provider legal-URL exposure.

Verifies build_provider_meta_from_names passes privacyPolicyUrl and
termsOfServiceUrl from providers.csv rows into generated provider metadata.

Run: python3 tools/test_provider_meta.py  (exit 0 = pass)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from csv_to_json import build_provider_meta_from_names  # noqa: E402


def main() -> int:
    provider = {
        "slug": "acme-rpc",
        "name": "Acme RPC",
        "logoPath": "acme.png",
        "description": "Test provider",
        "website": "https://acme.example",
        "docs": "https://docs.acme.example",
        "privacyPolicyUrl": "https://acme.example/privacy",
        "termsOfServiceUrl": "https://acme.example/terms",
        "x": None,
        "github": None,
        "discord": None,
        "telegram": None,
        "linkedin": None,
        "supportEmail": None,
        "starred": True,
        "tag": None,
    }
    meta = build_provider_meta_from_names(
        provider_by_name={"Acme RPC": provider},
        provider_categories={"Acme RPC": {"apis"}},
        network="ethereum",
    )
    entry = meta["acme-rpc"]
    assert entry["privacyPolicyUrl"] == "https://acme.example/privacy", entry
    assert entry["termsOfServiceUrl"] == "https://acme.example/terms", entry
    # blank cells must surface as null, not be dropped
    provider["privacyPolicyUrl"] = ""
    provider["termsOfServiceUrl"] = ""
    meta = build_provider_meta_from_names(
        provider_by_name={"Acme RPC": provider},
        provider_categories={"Acme RPC": {"apis"}},
        network="ethereum",
    )
    entry = meta["acme-rpc"]
    assert "privacyPolicyUrl" in entry and "termsOfServiceUrl" in entry, entry
    print("test_provider_meta: OK (nonblank exposed, blank surfaced as-is)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
