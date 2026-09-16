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


def test_rejects_normalized_punctuation_and_quotes():
    # trailing period / surrounding quotes must not let placeholders slip through
    for entry in ["Audited.", '"audit by third parties"', "not available,", "Unknown;"]:
        result = {"wallets": [{"slug": "demo", "audit": [entry]}]}
        try:
            validate_wallet_audit_evidence(result)
            assert False, f"expected ValueError for normalized variant '{entry}'"
        except ValueError:
            pass


def test_rejects_bare_vague_words():
    for entry in ["yes", "No", "N/A", "none", "multiple", "various"]:
        result = {"wallets": [{"slug": "demo", "audit": [entry]}]}
        try:
            validate_wallet_audit_evidence(result)
            assert False, f"expected ValueError for bare vague word '{entry}'"
        except ValueError:
            pass


def test_accepts_specific_auditor_with_qualifier():
    # 'Audited by CertiK' is a positive claim, not a placeholder
    validate_wallet_audit_evidence(
        {"wallets": [{"slug": "demo", "audit": ["Audited by CertiK"]}]}
    )


if __name__ == "__main__":
    test_rejects_placeholder_exact()
    test_rejects_placeholder_case_insensitive()
    test_rejects_placeholder_multiword()
    test_accepts_report_link()
    test_accepts_verified_named_auditor()
    test_accepts_multiple_auditors()
    test_blank_cell_ok()
    test_missing_wallets_key_ok()
    test_rejects_normalized_punctuation_and_quotes()
    test_rejects_bare_vague_words()
    test_accepts_specific_auditor_with_qualifier()
    print("All audit-evidence regression checks passed.")
