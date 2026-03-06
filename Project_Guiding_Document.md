# Chain.Love Data Enrichment & Deduplication: Project Guiding Document

**Version:** 2.0 (Updated after Foundation Repair & Batch 1 Execution)
**Date:** 2026-03-06
**Contributor:** Joshua Onyekachukwu
**Role:** External Data Contributor / Ecosystem Enrichment
**Project Type:** Open-source, reward-based data improvement

---

## 1. Executive Summary & Project Overview

Chain.Love aims to build and maintain a high-quality, comprehensive database of service providers for various blockchain networks, serving as a reliable resource for Web3 developers. Our main task is data enrichment and deduplication, focusing on verified, high-quality data while centralizing common information to reduce redundancy.

**Key Achievements So Far:**
- **Foundation Repair:** All global provider files (`repo/providers/*.csv`) and existing network files (e.g., BSC, TON, Arbitrum, Optimism, Polygon, Solana, Somnia, Sonic, Stellar, Sui, Linea, Base) have been thoroughly cleaned of forbidden values (`[]`, `{}`, `null`, `NULL`, `FALSE`, `TRUE` as strings, and other placeholders).
- **Batch 1 Execution (Base Network):** The Base network has undergone full deduplication and enrichment, aligning with our strict quality standards. This includes harmonizing headers, clearing inherited values, and adding key missing providers.

**Our guiding philosophy is "Less is More":** Network files should be sparse, primarily containing `!provider:<slug>` references. Data is added only if verified and provides genuine new value. Empty cells are intentional, signaling "Inherit" or "No Data."

---

## 2. Core Data Philosophy & Standards (Non-Negotiable)

### A. The Golden Rule: Empty Cells
- **An empty cell is intentional.** It means one of two things:
    - The value is inherited via `!provider:<slug>`.
    - The value is unknown or unverified.
- **Absolute Prohibitions:** The following are never allowed:
    - `[]`, `{}`
    - `null`, `NULL`
    - Placeholder text (e.g., `n/a`, `-`)
    - Guesswork or unverified data
    - Duplicated provider data (if it can be inherited)

### B. Provider Reference System (Mandatory)
- **Purpose:** To deduplicate data and keep global facts in `repo/providers/<category>.csv` as the single source of truth.
- **Mechanism:** Network-specific files (`repo/networks/<chain>/<category>.csv`) reference global providers using `!provider:<provider-slug>` in the `provider` column.
- **Inheritance Rules:**
    - Provider data is copied only into empty cells in the network file.
    - Network values override provider values only if explicitly set (i.e., the cell is not empty).
    - Writing `null` or `[]` (or any forbidden value) blocks inheritance and is incorrect.

### C. Quality Gateway
Every non-empty cell in a network file must pass all of the following:
- Manually verified from a real source.
- Adds new, network-specific value.
- Is not inherited from a global provider.
- Matches column type and formatting rules.
- Would be genuinely useful to a developer.

**Automatic Disqualifiers:** Empty JSON arrays, dummy values, cosmetic but meaningless text, repeated provider facts, low-effort padding.

### D. Data & Structural Standards
- **Booleans:** `TRUE` / `FALSE` (uppercase only).
- **JSON:** Validated, arrays only when semantically required, no trailing commas.
- **Markdown:** Allowed where supported, wrapped correctly in JSON arrays if needed.
- **Structural:**
    - Correct folder placement: `networks/<chain>/<category>.csv` and `providers/<category>.csv`.
    - Exact column count per header.
    - Correct filename casing.
    - UTF-8, comma-delimited, no BOM.

---

## 3. Execution Plan & Workflow

### A. Current Status
- **Foundation Repair:** COMPLETE
- **Batch 1 (Base Network):** COMPLETE (Deduplication, Enrichment, Validation)

### B. Remaining Networks & Batching Strategy
To manage complexity and reviewer load, remaining networks are grouped into batches. The next step is to proceed with the remaining networks in Batch 1, followed by Batch 2 and Batch 3.

#### **Batch 1: High Priority (Remaining)**
*Rationale: High developer activity, high signal value, likely to have significant data overlap with existing providers.*
1.  **Linea** (L2, ConsenSys ecosystem)
2.  **Solana** (High performance L1)
3.  **Aptos** (Move-based L1)

#### **Batch 2: Established L1s**
*Rationale: Mature ecosystems with stable data points.*
1.  **Algorand**
2.  **Cardano**
3.  **Stellar**
4.  **Filecoin**

#### **Batch 3: Emerging / Infrastructure**
*Rationale: Newer chains or specific niches, potentially requiring more manual research.*
1.  **Astar**
2.  **Flare**
3.  **Lens**
4.  **Somnia**
5.  **Sonic**
6.  **Sui**

### C. Workflow Per Network (Iterative Process)
For each network in the batches:
1.  **Deduplicate (Cleanup):**
    - Scan existing network CSVs (`api.csv`, `explorer.csv`, etc.).
    - Compare against `providers/*.csv`.
    - Replace hardcoded values with `!provider:<slug>` where applicable.
    - Clear cells that are identical to the provider's default.
    - Remove any remaining forbidden values.
2.  **Enrich (New Data):**
    - Add new providers that are missing from key categories (RPCs, Explorers, Wallets, DevTools, etc.).
    - If the provider exists globally: Add row with `!provider:<slug>`.
    - If the provider is new/unique: Add full row data (and potentially add to global providers if reusable).
3.  **Validate:**
    - Run automated validation scripts (`validation.py`).
    - Manually review changes (diff) to ensure no "noisy" changes (whitespace, reordering without cause).
4.  **Review & Submit:** Prepare a PR-ready diff and message, ensuring all quality gates are met.

---

## 4. Division of Responsibility

### A. Human (Joshua)
- Manual verification of data points.
- Final approval before pushing to main.
- Responding to maintainer feedback.
- Linking wallet address and Twitter (X) post for rewards.

### B. AI Agent (Codex-Prime)
- Scan repository structure and detect inheritance opportunities.
- Flag cells that must remain empty or need clearing.
- Enforce Style Guide rules and prevent forbidden values.
- Prepare PR-ready diffs and messages.
- Execute deduplication, enrichment, and automated validation.

---

## 5. Rewards & PR Constraints

### A. Reward Model
- **0.06 USDC** per approved non-null, valuable cell.
- **10 USDC** per approved DB Improvement Proposal (DBIP).
- **+10% bonus** if the PR is posted on X (Twitter) and linked.
- Rewards are distributed monthly.

### B. Critical Constraints & PR Size
- PRs must follow the Style Guide, Provider Reference rules, and pass automatic validation and manual reviewer judgment.
- **PR size limit:**
    - Maximum **100 lines of code** or
    - Maximum **200 edited cells**.

---

## 6. Generic Pull Request (PR) Template (Mandatory)

All PRs must follow this structure:

```markdown
## Summary
Provide a concise summary of the change and why it’s needed.

## Type of change
- [ ] Add data rows
- [ ] Update data rows
- [ ] Remove data rows
- [ ] Schema change (requires linked DBIP)
- [ ] Documentation/metadata only
- [ ] Data deduplication/Refactoring (e.g., applying inheritance cleanup)

## Scope
- **Networks affected**: [e.g., base, linea]
- **Categories affected**: [e.g., rpc, wallet, explorer]
- Additional notes or constraints:

## Key Improvements (if applicable)
- **Inheritance Cleanup**: [e.g., Purged X redundant data cells in `networks/<chain>/`. All shared metadata is now correctly inherited from the global `providers/` folder using the `!provider` syntax.]
- **Data Normalization**: [e.g., Standardized all boolean values to uppercase `TRUE`/`FALSE` and removed "null" strings to ensure perfect JSON generation.]
- **Schema Compliance**: [e.g., Verified that all CSVs have the exact column count matching the headers.]

## Links
- Related issue(s):
- DB Improvement Proposal (DBIP), if any:

## Validation checklist
- [ ] Followed Style Guide and Column Definitions
- [ ] Correct folder and CSV placement
- [ ] No duplicate entries (by provider + chain + relevant key columns)
- [ ] CSV formatting: comma-delimited, quote fields as needed, UTF-8, no BOM
- [ ] JSON validated (where applicable)
- [ ] Values match defined types/enums per Column Definitions
- [ ] No placeholders, nulls, or empty arrays
- [ ] No unintended whitespace, trailing commas, or empty lines

## Optional
- Rewards address: [Your Wallet Address]
- Twitter (X) post link: [Link to your X post tagging @chainloveweb3]
```

---

**Final Instruction to the AI Agent:** You are not optimizing for the number of filled cells. You are optimizing for signal, correctness, inheritance awareness, and reviewer trust. If a value is uncertain, inherited, duplicated, or cosmetic — leave it empty.
