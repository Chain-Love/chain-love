"""Unit regression tests for validate_runtime_requirements() (DBIP #3751).

Runs with plain `python3` (no pytest) so the required `validate` check can call
it directly inside the network-disabled container.

Coverage intent: the CI job also drives the real pipeline over fixtures, but
those exercise the *happy* path plus one rejected value. These cases pin down
each individual rule of the validator, so a regression names the rule that
broke instead of just turning the job red.
"""
import inspect
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# Assembled CI workspace: csv_to_json.py is copied to the repo root.
# Local checkout: it lives next to this file's parent (tools/).
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE.parent))

import csv_to_json  # noqa: E402  (path set up above on purpose)

VALID_PY_SOURCE = "https://github.com/algorandfoundation/algokit-utils-py/releases/tag/v4.2.3"
VALID_NODE_SOURCE = "https://github.com/algorandfoundation/algokit-utils-ts/releases/tag/v9.2.2"

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}{(': ' + detail) if detail else ''}")
        FAILURES.append(name)


def errors_for(value):
    """Run the validator over a single sdks row carrying `runtimeRequirements`."""
    row = {"slug": "algokit-utils-py"}
    if value is not _MISSING:
        row["runtimeRequirements"] = value
    return csv_to_json.validate_runtime_requirements([row], context="test")


class _Missing:
    pass


_MISSING = _Missing()


def main():
    print(f"using {csv_to_json.__file__}")

    # --- accepted values -------------------------------------------------
    check("blank cell (None) is valid", errors_for(None) == [], str(errors_for(None)))
    check("absent key is valid", errors_for(_MISSING) == [], str(errors_for(_MISSING)))
    check(
        "non-sdks rows without the key are ignored",
        csv_to_json.validate_runtime_requirements(
            [{"slug": "some-wallet"}, "not-a-dict"], context="test"
        ) == [],
    )
    both = {
        "python": {"constraint": "^3.10", "syntax": "poetry", "source": VALID_PY_SOURCE},
        "node": {"constraint": ">=22.0", "syntax": "node-semver", "source": VALID_NODE_SOURCE},
    }
    check("python(poetry) + node(node-semver) accepted", errors_for(both) == [], str(errors_for(both)))
    check(
        "python(pep440) accepted",
        errors_for({"python": {"constraint": ">=3.10", "syntax": "pep440", "source": VALID_PY_SOURCE}}) == [],
    )
    check(
        "only one runtime declared is accepted",
        errors_for({"node": {"constraint": ">=22.0", "syntax": "node-semver", "source": VALID_NODE_SOURCE}}) == [],
    )

    # --- rejected values -------------------------------------------------
    errs = errors_for({})
    check("empty object rejected as a placeholder", len(errs) == 1 and "empty object" in errs[0], str(errs))

    errs = errors_for("python ^3.10")
    check("non-object value rejected", len(errs) == 1 and "must be a JSON object or null" in errs[0], str(errs))

    errs = errors_for({"python": {"constraint": "^3.10", "syntax": "semver", "source": VALID_PY_SOURCE}})
    check(
        "python syntax outside the enum rejected",
        len(errs) == 1 and "syntax must be one of" in errs[0],
        str(errs),
    )

    errs = errors_for({"node": {"constraint": ">=22.0", "syntax": "pep440", "source": VALID_NODE_SOURCE}})
    check(
        "node rejects python-only syntax",
        len(errs) == 1 and "syntax must be one of" in errs[0],
        str(errs),
    )

    errs = errors_for({"rust": {"constraint": ">=1.70", "syntax": "cargo", "source": VALID_PY_SOURCE}})
    check(
        "unknown runtime key rejected",
        len(errs) == 1 and "unknown runtime key" in errs[0],
        str(errs),
    )

    errs = errors_for({"python": {"constraint": "^3.10", "syntax": "poetry"}})
    check(
        "missing source rejected",
        len(errs) == 1 and "source must be a non-empty string" in errs[0],
        str(errs),
    )

    errs = errors_for({"python": {"constraint": "   ", "syntax": "poetry", "source": VALID_PY_SOURCE}})
    check(
        "blank constraint rejected",
        len(errs) == 1 and "constraint must be a non-empty string" in errs[0],
        str(errs),
    )

    errs = errors_for({"python": "^3.10"})
    check("non-object runtime entry rejected", len(errs) == 1 and "must be an object" in errs[0], str(errs))

    errs = errors_for({"python": {"constraint": "^3.10", "syntax": "semver"}, "rust": {}})
    check("multiple violations all reported", len(errs) == 3, f"{len(errs)} errors: {errs}")

    # --- wiring ----------------------------------------------------------
    # A unit test that calls the function directly cannot notice the call being
    # removed from main(). Assert the wiring explicitly so that regression is
    # caught here too, not only by the fixture-driven negative control.
    main_src = inspect.getsource(csv_to_json.main)
    check(
        "main() calls validate_runtime_requirements",
        "validate_runtime_requirements(" in main_src,
    )
    check(
        "main() exits non-zero on runtimeRequirements errors",
        "runtime_req_errors" in main_src and "exit(1)" in main_src,
    )

    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        raise SystemExit(1)
    print("\nAll runtimeRequirements regression checks passed.")


if __name__ == "__main__":
    main()
