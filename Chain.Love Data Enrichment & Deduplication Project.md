Chain.Love Data Enrichment & Deduplication Project

Master Requirement, Task Definition, Quality Contract & Execution Document

Version: 1.1
Status: Active
Primary Executor: AI Agent (Autonomous)
Human Supervisor: Joshua Onyekachukwu

1. Purpose of This Document

This document is the single source of truth governing all work done for the Chain.Love data enrichment task.

It exists to ensure that any AI agent reading it can:

Fully understand what task was given

Correctly interpret what Chain.Love wants and does NOT want

Understand what has already happened, including mistakes and maintainer feedback

Execute all future work to perfection, without repeating prior failures

Operate autonomously while respecting strict quality constraints

This document overrides assumptions, shortcuts, and generic data-filling behavior.

2. The Original Task (Authoritative Source)

The following is the official task description provided by Chain.Love.

Task Statement (Verbatim)

Chain.Love is looking for contributors to improve the database of solutions for the common good.
Contributors are rewarded for bringing pull requests that populate, enrich, and make the database more usable.

Rewards

0.05 → 0.06 USDC per approved non-null, valuable cell

10 USDC per approved DB Improvement Proposal (DBIP)

+10% bonus for posting the PR on X and linking it

Rewards are distributed once per month

Requirements

Data must pass automatic validation

Data must be manually collected or verified

Data must follow all Style Guide instructions

System abuse is forbidden

PR size limit:

≤ 100 LOC or

≤ 200 edited cells

Networks explicitly requested

Arbitrum

Algorand

BSC (Binance Smart Chain)

Ethereum

Filecoin

Optimism

Polygon

Solana

Somnia

Sonic

Sui

TON (Telegram Open Network)

3. Task Interpretation (This Is Critical)
What the task ACTUALLY means

The task is not:

“Fill as many empty cells as possible”

“Maximize the number of non-null values”

“Add cosmetic or placeholder data”

The task is:

Improve developer usefulness

Deduplicate repeated information

Centralize shared facts via providers

Add only verified, network-specific data

Preserve database integrity and long-term maintainability

4. Contributor Identity & Required Links
Contributor

Name: Joshua Onyekachukwu

GitHub fork:
https://github.com/Joshua-Onyekachukwu/chain-love

Upstream repository:
https://github.com/chain-love/chain-love

Task discussion:
https://github.com/chain-love/chain-love/discussions/41

Rewards wallet:
0x94D532457f640abc7ACE133BCeaa6b8D19725098

X (Twitter):
@iamsemek

5. What Has Already Happened (Historical Context)
Initial contributions

Large-scale enrichment attempts for:

Arbitrum

TON

BSC

Multiple providers added across categories

Outcome

1 PR approved cleanly (filename casing fix)

3 PRs rejected or partially refactored

Why failures occurred

Empty cells were replaced with []

Cells that should inherit via providers were manually populated

This added noise, not value

Maintainer intervention

Maintainer refactored the PR instead of closing it

Only genuine BSC contributions were rewarded

Clear warning issued about quality and future penalties

6. Maintainer Feedback (Binding Guidance)
Key statement (summarized)

Replacing empty cells with [] pollutes the database

Empty cells are intentional

Future rewards are gated by quality thresholds

Poor-quality cells can reduce per-cell payout

Interpretation

Empty ≠ missing
Empty = inheritance or unknown
[] = harmful noise

7. Absolute Rules (Non-Negotiable)
Forbidden values (never allowed)

[]

{}

null, NULL

Dummy placeholders

Guesswork

Repeated provider values

Any occurrence of the above:

Violates the Style Guide

Triggers reward reduction or PR rejection

8. Provider Reference System (Mandatory Logic)
Purpose

Prevent duplication and keep global facts consistent.

Usage

In network CSVs:

!provider:<provider-slug>

Inheritance rules

Provider values fill only empty cells

Network values override provider values only when explicitly set

Writing null or [] blocks inheritance (this is wrong)

Mental model

Providers = global truth

Networks = exceptions only

9. Quality Gateway (Active Enforcement)

A non-empty cell is valid only if:

It is manually verified

It adds new, network-specific value

It is not inherited

It matches column type

It is useful to a developer

Automatic disqualifiers

Empty arrays

Cosmetic text

Duplicated facts

Padding for rewards

10. Standard of Work Required
Formatting

Booleans: TRUE / FALSE

JSON:

Validated

Arrays only when semantically required

Markdown allowed where supported

Structure

Correct folder placement

Correct filename casing

Exact column count

UTF-8, comma-delimited, no BOM

11. Networks & Execution Plan
Already touched

Arbitrum

TON

BSC

Remaining networks (14)

Algorand

Aptos

Astar

Base

Cardano

Filecoin

Flare

Lens

Linea

Solana

Somnia

Sonic

Stellar

Sui

Approved batches

Batch 1: Base, Linea, Solana, Aptos
Batch 2: Algorand, Cardano, Stellar, Filecoin
Batch 3: Astar, Flare, Lens, Somnia, Sonic, Sui

12. Required Workflow (Strict)

For every network:

Deduplicate via !provider

Clear inherited cells

Add only verified, network-specific data

Validate JSON and formatting

Ensure no forbidden values exist

Keep PR within size limits

Submit with correct PR template

13. PR Template (Mandatory)

(Unchanged; must be followed exactly — omitted here for brevity but still binding)

14. Division of Authority
AI Agent (Primary Executor)

Scans repository

Detects inheritance opportunities

Decides which cells must remain empty

Prevents forbidden values

Prepares PR-ready diffs

Drafts PR messages

Human (Joshua)

Manual verification source confirmation

Final approval before push

Reviewer communication

Wallet & X linking

15. Mandatory Agent Understanding Check

Before performing any task, the AI agent must internally confirm:

It understands the original Chain.Love task

It understands why [] is forbidden

It understands provider inheritance

It understands that empty cells are intentional

It understands that quality > quantity

If any of the above is unclear, the agent must stop and ask.

16. Final Instruction to the AI Agent

You are not optimizing for filled cells.
You are optimizing for signal, correctness, inheritance, and trust.

If a value is uncertain, duplicated, inherited, or cosmetic — leave it empty.