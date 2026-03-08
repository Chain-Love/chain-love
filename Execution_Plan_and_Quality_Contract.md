# Chain.Love Data Enrichment: Execution Plan & Quality Contract (Superseded)

**Note:** This document has been superseded by [Project_Guiding_Document.md](file:///c%3A%5CUsers%5CSemek%5CWebstormProjects%5CChain.Love%5CProject_Guiding_Document.md), which contains the most up-to-date project plan, status, and execution details.

**Status:** Superseded / Historical Reference
**Date:** 2026-03-06
**Executor:** AI Agent (Codex-Prime / Trae)
**Approver:** Joshua Onyekachukwu

---

## 1. Access Confirmation & Environment
I confirm full access to the local development environment:
- **Repository:** `c:\Users\Semek\WebstormProjects\Chain.Love` (Fork of `chain-love/chain-love`)
- **Capabilities:** Read/Write access, Git command execution, Branch creation, PR generation.
- **Context:** I have ingested the `Master Requirement Document` and fully understand the "Style Guide" and "Provider Inheritance" rules.

---

## 2. Network Status & Batching Strategy (Historical)

Based on the Master Requirement Document, the following networks were identified for processing. This section reflects the plan *prior* to the completion of the Foundation Repair and Batch 1 (Base Network) execution. For the current batching strategy, please refer to the [Project_Guiding_Document.md](file:///c%3A%5CUsers%5CSemek%5CWebstormProjects%5CChain.Love%5CProject_Guiding_Document.md).

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

## 4. Scope of Work Per Network (Refer to Project Guiding Document)

For the current workflow and detailed scope of work per network, please refer to the [Project_Guiding_Document.md](file:///c%3A%5CUsers%5CSemek%5CWebstormProjects%5CChain.Love%5CProject_Guiding_Document.md).
