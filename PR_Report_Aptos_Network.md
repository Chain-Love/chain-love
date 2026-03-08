# Pull Request Summary: Aptos Network Data Enrichment

## Overview
This pull request introduces comprehensive data enrichment for the Aptos network within the `Chain.Love` repository. The changes involve deduplication, enrichment of API provider information, and local validation of all `.csv` files related to the Aptos network.

## Changes Implemented

### 1. Deduplication and Cleanup
- Ran `deduplicate.py` on all `.csv` files in `repo/networks/aptos` to remove redundant entries and apply the provider inheritance model.

### 2. API Provider Enrichment
- Added new high-value API providers to `repo/networks/aptos/apis.csv`.

### 3. Local Validation
- Executed `validation.py` to verify all `.csv` files in the `repo/networks/aptos` directory.
- All files passed local validation, confirming no forbidden patterns or formatting issues.

## Affected Files
- `repo/networks/aptos/analytics.csv`
- `repo/networks/aptos/apis.csv`
- `repo/networks/aptos/explorers.csv`
- `repo/networks/aptos/oracles.csv`
- `repo/networks/aptos/sdks.csv`
- `repo/networks/aptos/services.csv`
- `repo/networks/aptos/wallets.csv`

## Validation Details
- **Local Validation Status**: Passed
- **Forbidden Patterns**: None found after processing.
- **Boolean Formatting**: All boolean values in `apis.csv` are `true` or `false` (lowercase) to ensure compatibility with JSON validation.

## Checklist
- [x] All `.csv` files for Aptos network deduplicated.
- [x] `apis.csv` for Aptos network enriched with high-value providers.
- [x] All `.csv` files for Aptos network passed local `validation.py`.
- [x] Code conforms to the Style Guide.
- [x] Provider Reference rules followed.

## Optional
- Rewards address (for data patching rewards):
- Twitter (X) post link (for +10% of rewards to this PR):
