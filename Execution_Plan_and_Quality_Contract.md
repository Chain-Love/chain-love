# Chain.Love Data Enrichment: Execution Plan & Quality Contract

**Status:** Draft / Waiting for Approval  
**Date:** 2026-02-08  
**Executor:** AI Agent (Codex-Prime / Trae)  
**Approver:** Joshua Onyekachukwu

---

## 1. Access Confirmation & Environment
I confirm full access to the local development environment:
- **Repository:** `c:\Users\Semek\WebstormProjects\Chain.Love` (Fork of `chain-love/chain-love`)
- **Capabilities:** Read/Write access, Git command execution, Branch creation, PR generation.
- **Context:** I have ingested the `Master Requirement Document` and fully understand the "Style Guide" and "Provider Inheritance" rules.

---

## 2. Network Status & Batching Strategy

Based on the Master Requirement Document, the following networks are identified for processing.

### **Completed / Previously Attempted (Out of Scope for this Plan)**
*   **Arbitrum**
*   **TON**
*   **BSC** (Binance Smart Chain)
*   *(Note: Ethereum, Optimism, and Polygon exist in the repo but are not in the active "Remaining" priority list for this specific campaign.)*

### **Remaining Networks (14 Total)**
These are grouped into batches to manage complexity and reviewer load.

#### **Batch 1: High Priority (Trend & Volume)**
*Rationale: High developer activity, high signal value, likely to have significant data overlap with existing providers.*
1.  **Base** (L2, Coinbase ecosystem)
2.  **Linea** (L2, ConsenSys ecosystem)
3.  **Solana** (High performance L1)
4.  **Aptos** (Move-based L1)

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

---

## 3. The Quality Contract (Standard of Work)

**I commit to the following strict standards. Any deviation is a failure of the task.**

### **A. The "Golden Rule" of Empty Cells**
*   **Rule:** An empty cell is **NOT** an error. It is a feature.
*   **Meaning:** Empty = "Inherit from Provider" OR "Unknown".
*   **Prohibited:** `[]`, `{}`, `null`, `NULL`, `n/a`, `-`, or any cosmetic placeholder.

### **B. Provider Inheritance & Deduplication**
*   **Rule:** Network files must NOT duplicate data found in `providers/*.csv`.
*   **Mechanism:**
    *   Use `!provider:<provider-slug>` in the `slug` column (or relevant ID column).
    *   Leave columns **EMPTY** in the network file if the value should be taken from the provider.
    *   **Only** fill a cell in the network file if it specifically **overrides** the provider (e.g., a specific chain ID, a modified URL).

### **C. Verification & Value**
*   **Rule:** Every non-inherited value must be verified.
*   **Standard:**
    *   URLs must be accessible.
    *   RPC endpoints must be valid.
    *   **No guesswork.** If I cannot verify a data point 100%, I will leave it empty.

### **D. PR Constraints**
*   **Size:** Maximum **100 Lines of Code** or **200 Edited Cells** per PR.
*   **Format:**
    *   Valid JSON (where applicable).
    *   `TRUE` / `FALSE` (uppercase) for booleans.
    *   No trailing commas in JSON.
    *   UTF-8, standard CSV format.

---

## 4. Scope of Work Per Network

For each network in the batches above, the workflow is:

### **Phase 1: Deduplication (Cleanup)**
*   **Action:** Scan existing network CSVs (`api.csv`, `explorer.csv`, etc.).
*   **Logic:** Compare against `providers/*.csv`.
*   **Execution:**
    *   Replace hardcoded values with `!provider:<slug>` where applicable.
    *   **Clear** cells that are identical to the provider's default.
    *   Remove `[]` or `null` garbage values left by previous attempts.

### **Phase 2: Enrichment (New Data)**
*   **Categories:** RPCs (`api.csv`), Explorers (`explorer.csv`), Wallets (`wallet.csv`), DevTools (`devTool.csv`).
*   **Action:** Add **new** providers that are missing.
*   **Logic:**
    *   If the provider exists globally: Add row with `!provider:<slug>`.
    *   If the provider is new/unique: Add full row data (and potentially add to global providers if reusable).

### **Phase 3: Validation**
*   **Automated:** Run `validate_cells.py` and `check_syntax.py`.
*   **Manual:** Review diff to ensure NO "noisy" changes (whitespace, reordering without cause).

---

## 5. Execution Roadmap

1.  **Approve this Plan:** You (User) review and approve this document.
2.  **Start Batch 1 (Base):**
    *   Create branch `feat/enrich-base`.
    *   Perform Deduplication & Cleanup.
    *   Perform Enrichment.
    *   Validate & Commit.
    *   **STOP** and present for review.
3.  **Proceed to Linea, Solana, Aptos:**
    *   Repeat process sequentially.
    *   Ensure PR size limits are respected (split into multiple PRs if Base is too large).
4.  **Review Point:** After Batch 1 is merged/approved, proceed to Batch 2.

**Ready to execute upon your command.**
