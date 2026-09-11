import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csv_to_json import validate_wallet_audit_evidence, AUDIT_PLACEHOLDER_PHRASES


def test_rejects_placeholder_exact():
    result = {"wallets": [{"slug": "demo", "audit": ["audit by third parties"]}]}
    try:
        validate_wallet_audit_evidence(result)
        assert False, "expected ValueError for placeholder"
    except ValueError:
        pass


def test_rejects_placeholder_case_insensitive():
    result = {"wallets": [{"slug": "demo", "audit": ["Not Availale"]}]}
    try:
        validate_wallet_audit_evidence(result)
        assert False, "expected ValueError for misspelled placeholder"
    except ValueError:
        pass


def test_rejects_placeholder_multiword():
    result = {"wallets": [{"slug": "demo", "audit": ["audit internally", "third parties"]}]}
    try:
        validate_wallet_audit_evidence(result)
        assert False, "expected ValueError for vague multiword entry"
    except ValueError:
        pass


def test_accepts_report_link():
    result = {
        "wallets": [
            {"slug": "backpack", "audit": ["[Hacken](https://hacken.io/audits/backpack/)"]}
        ]
    }
    validate_wallet_audit_evidence(result)


def test_accepts_verified_named_auditor():
    result = {"wallets": [{"slug": "rabby", "audit": ["Least Authority"]}]}
    validate_wallet_audit_evidence(result)


def test_accepts_multiple_auditors():
    result = {
        "wallets": [{"slug": "demo", "audit": ["SlowMist", "Cure53", "PeckShield"]}]
    }
    validate_wallet_audit_evidence(result)


def test_blank_cell_ok():
    validate_wallet_audit_evidence({"wallets": [{"slug": "demo", "audit": None}]})
    validate_wallet_audit_evidence({"wallets": [{"slug": "demo", "audit": []}]})


def test_missing_wallets_key_ok():
    validate_wallet_audit_evidence({})


if __name__ == "__main__":
    test_rejects_placeholder_exact()
    test_rejects_placeholder_case_insensitive()
    test_rejects_placeholder_multiword()
    test_accepts_report_link()
    test_accepts_verified_named_auditor()
    test_accepts_multiple_auditors()
    test_blank_cell_ok()
    test_missing_wallets_key_ok()
    print("All audit-evidence regression checks passed.")
