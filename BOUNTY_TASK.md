# Bounty Objective: [DBIP] Distinguish live provider docs links from verified project identity
Target: Chain-Love/chain-love Issue #4718
URL: https://github.com/Chain-Love/chain-love/issues/4718

## Issue Description
### Proposal type
Other — provider `website`/`docs` evidence semantics and validation policy (no column addition required).

### Affected scope
- `references/providers/providers.csv`: NEW OR EDITED values of `website` and `docs`.
- `CONTRIBUTING.md` (current link rules cover URL format but not whether a live page belongs to the named provider).
- `.github/workflows/link-check-analysis.yaml`: identity-check reporting for PR-added URLs, without making network-dependent checks a blocking validator on every build.
- The eventual provider column documentation/Style Guide; do **not** modify automatic SDK-release/maintainer/license fields.

### Actual first-party failure case (not a hypothetical vulnerability)

Existing original PR [#4711](https://github.com/Chain-Love/chain-love/pull/4711) initially linked the provider **Huff** to `https://huff.sh/` and `https://docs.huff.sh/`. The original `Link Check` accepted **13/13 links** even though the independent maintainer reviewer [USS-Supervisor's 2026-10-20 CHANGES_REQUESTED review](https://github.com/Chain-Love/chain-love/pull/4711) found those pages now served unrelated Indonesian gambling/slot content. Those domains responded to HTTP but **no longer belonged to the Huff development project**. The correct maintained source was later verified at `https://github.com/huff-language/huff2#differences-vs-huff-rs`; PR #4711 was fixed in place, without claiming that either old site remains safe.

This is reproducible from the repository's `.github/workflows/link-check-analysis.yaml`: its Lychee configuration treats `200,202,204,400,401,403,405,429` as acceptable response codes. A `200` from the *wrong product/owner* is indistinguishable from a maintained first-party docs URL. HTTP success establishes **transport-level reachability, not product identity**.

A second observed identity class was a valid Viem documentation page proposed as generic `wevm` provider-wide docs. The maintainer correctly rejected this product/provider scope mismatch although the page itself was genuine and live. Current link checking cannot tell the two apart.

### Exact problem / beneficiary

A new valid-looking docs link can be a domain takeover, parked/repurposed domain, generic network page, or a different product in the same organization. Reviewers must rediscover the provenance manually while consumer tools can display the inappropriate live content as authoritative docs. Developers and automated agents using the directory may be misdirected. A fail-closed, **explicitly provenance-uncertain** flag would prevent a green HTTP code from being mistaken for a first-party identity check.

This DBIP is deliberately *not* a duplicate of:
- [#3345](https://github.com/Chain-Love/chain-love/issues/3345): manually collected **four specific off-brand/dead offer links**, a dataset cleanup;
- [#3916](https://github.com/Chain-Love/chain-love/issues/3916): social network handle ownership and invite validity;
- [#2937](https://github.com/Chain-Love/chain-love/issues/2937) / [#3120](https://github.com/Chain-Love/chain-love/issues/3120): provider/offer lifecycle metadata schemas;
- [#4045](https://github.com/Chain-Love/chain-love/issues/4045): provider metadata currently bypasses validator rules.

This proposes the **specific reusable new-link / newly-changed-link provenance gate** for **provider website/docs HTML identity**, not re-reporting those rows, inventing another lifecycle field, or duplicating link reachability.

### Detailed minimal proposal (review-first, low false-positive)

1. For new/changed `references/providers/providers.csv` `website`/`docs`, require the PR description to include one **independent first-party ownership trail**: from the canonical provider GitHub organization/README to the docs URL or from the project's official website to its docs URL. A URL in the same row is not itself independent proof.
2. Extend the PR link-check report to expose **separate status** for `reachable` and `provenance`: `first_party_evidenced`, `needs_manual_identity_review`, `not_applicable`. This is a report/verification rule, not an invented new CSV field or a claim of automatic legal ownership determination.
3. If the candidate is a changed bare website/docs domain with no independent provider-owned crosslink, it must show `needs_manual_identity_review` even if HTTP 200. A human reviewer can approve with the cited crosslink, reject unrelated content, or document an unresolved bot-wall. **Do not run an LLM classifier on arbitrary websites and auto-approve from similarity.**
4. The local *unit* tests should use **synthetic HTML/page metadata** only: a fake HTTP200 gambling/parking page for `Huff` must not become identity-verified; official GitHub `huff-language/huff2` README → exact official docs is a positive crosslink; and a valid `viem` product guide must not automatically become `wevm` provider-wide docs.
5. HTTP 401/403/429, anti-bot pages, redirects, discontinued domains and genuine GitHub-hosted maintained projects must **not** be blindly treated as hijacked. Unknowns remain `needs_manual_identity_review` and can be resolved by an explicit original maintainer-provided official crosslink. Keep the routine fast/offline when possible and do not repeatedly fetch personal data or claim third-party security ownership.

### Acceptance criteria / focused test cases

- Positive: official provider README linking directly to maintained provider docs gives separate URL-reachable and identity-evidenced outcomes.
- Negative: mocked valid HTTP200 HTML with a different product/operator and absent official crosslink is **not** marked identity-evidenced; reviewer gets a source link and a clear reason.
- Negative: docs link for one product among multiple provider products (Viem vs wevm) requires scope review, not silently marked provider-wide.
- Unknown: Cloudflare 403/429 is neither automatically approved nor automatically condemned as hijacked.
- Only new/changed provider website/docs fields are checked and reported; no broad crawling of customer data, unsupported claims of token security or automated page classification.
- No new mutable provider columns, no edits to SDK automation-owned fields, no changes to payment/wallet logic. Document the distinction: **HTTP success ≠ first-party identity verified**.

### Contributor disclosure and reward request

This DBIP was prepared with AI-assisted analysis by VM5 Delivery Lab for **one human beneficial owner**; the same owner operates VM1/VM2/VM3/VM5 and is **not several independent contributors**. The source is publicly reviewable; no production or third-party data was modified. This is a **proposal for maintainer discussion**, not a completed implementation, guaranteed security finding, approved payout, or paid work order.

For the [database improvement bounty program #41](https://github.com/Chain-Love/chain-love/discussions/41), the posted **10 native USDC per *approved* DBIP issue** is strictly conditional on independent human approval. Do not count any grant until acceptance and Ethereum-mainnet actual payout have been verified. Original one-owner public EVM reward recipient on Ethereum mainnet: `0x6b01efa0705e91a7aca54271510bf9e594717f34`. No MetaMask private key, gas, signature or escrow needed to submit this issue.

I welcome a rejection if it duplicates an existing approved scope; please link the canonical DBIP rather than awarding the same work twice.


## Instructions for Kuro (Autonomous Solver):
1. Use skills: `systematic-debugging` and `code-review-and-quality`.
2. Inspect the repository structure, locate relevant files, and understand the bug/feature.
3. Apply the minimal, robust fix or implementation.
4. Run any existing test suites or linters in the workspace.
5. Ensure the fix adheres to the project's existing code style.
6. When done, output a summary of files modified and verification results.
