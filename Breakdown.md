


Chain.Love Data Enrichment & Deduplication Project

Master Requirement, Standards & Execution Document

Version: 1.0
Status: Active
Contributor: Joshua Onyekachukwu
Role: External Data Contributor / Ecosystem Enrichment
Project Type: Open-source, reward-based data improvement



Hello everyone! Chain.Love is looking for the brave heroes that are ready to improve the database of solutions for the common good, and to earn some money!

Here is the deal:

Bring us the pull requests that are improving our database - populating it, making it more usable, etc., and get rewarded in plain USDC/USDT.

Rewards are:

0.05 USDC for one improved cell non-null field after approving your pull-request.

10 USDC for the approved DBIP issue. There are no specific demands here, DBIPs will be verified manually, and if it make sense - it is getting approved.

+10% to the total PR reward if you post about your PR on Twitter and tag us (our account is x.com/chainloveweb3). To receive a reward please make sure to submit a link into your PR (either to the description or in the comments).

Demands for data ingestion are:

Data have to pass our automatic validation system

Data have to be collected or verified manually - PR will be declined or rewards will be reduced for any irrelevant data.

Data have to follow all the instructions from style guide

Don't abuse the system. If you we spot you creating 10 PRs, each adding just one more item to the array in the same cell - only the latest PR will be rewarded.

[From 17 December 2025] PR size should not be bigger than 100 lines of code and/or 200 edited cells.

Example:

Populating this file that took us around 3-4 hours => you may get around 25 USDC.

Populating the whole big network like ethereum that takes usually 2 days would get you around 150 USDC

How to participate?

Simply when opening your Issue or PR - add your public address for the rewards :)

P.S. What is even cooler - people actively participating in this product at early stage may be later eligible for the rewards coming later🤫

P.P.S. Rewards are going to be distributed once a month.

Currently looking for updates on:

Arbitrum (x2 rewards till 15 January 2025)

Algorand

- Astar (removed from 1st December 2025)

BSC (Binance Smart Chain) (new)

Ethereum

Filecoin

- Linea (removed from 1st January 2026)

Optimism

Polygon

- Stellar (removed from 1st January 2026)

Solana

Somnia

Sonic

Sui

TON (Telegram Open Network) new, from 9 January 2025 (x2 rewards for first 10 unique entities in each category)



1. Project Overview

This document defines the full scope, rules, standards, constraints, and execution plan for contributing data to the Chain.Love repository.

It exists to ensure that:

All future work aligns with Chain.Love’s Style Guide, Provider Reference system, and Quality Gateway

Past mistakes are not repeated

An AI agent can:

Understand what has already been done

Understand why certain PRs failed or were partially refactored

Correctly continue the work without polluting the database

Produce PRs that pass both automated and human review

This document is the single source of truth for this contribution effort.

2. Official Task Description (From Chain.Love)

Chain.Love runs a reward-based program for improving its ecosystem database.

Core task

Improve the database by:

Populating missing ecosystem data

Normalizing existing data

Deduplicating repeated information

Making the database more useful for developers

Reward model

0.05 → 0.06 USDC per approved non-null, valuable cell

10 USDC per approved DB Improvement Proposal (DBIP)

+10% bonus if the PR is posted on X (Twitter) and linked

Rewards are distributed monthly

Critical constraints

PRs must follow:

The Style Guide

Provider Reference rules

Automatic validation

Manual reviewer judgment

PR size limit:

≤ 100 lines of code or

≤ 200 edited cells

Official repository & task links

Main repository:
https://github.com/chain-love/chain-love

Grant & rewards discussion:
https://github.com/chain-love/chain-love/discussions/41

Style Guide:
https://github.com/Chain-Love/chain-love/wiki/Style-Guide

Provider References:
https://github.com/Chain-Love/chain-love/wiki/Provider-References

3. Contributor Identity & Links
Contributor

Name: Joshua Onyekachukwu

GitHub (fork):
https://github.com/Joshua-Onyekachukwu/chain-love

Wallet address (rewards):
0x94D532457f640abc7ACE133BCeaa6b8D19725098

X (Twitter) handle:
@iamsemek

4. What Has Already Been Done
PRs submitted (initial phase)

Large-scale enrichment for:

Arbitrum

TON

BSC

Added multiple ecosystem providers:

RPCs

Explorers

Wallets

Dev tools

Faucets

One PR approved cleanly

Standardize filename casing for TON devTool.csv

Approved by maintainer

Indicates correct understanding of structural rules

Three PRs partially rejected / refactored

Reasons:

Replaced intentionally empty cells with []

Filled cells that should inherit from providers

Added non-null values that did not add new information

Maintainer chose to:

Refactor instead of closing

Reward only the valid BSC contributions

This confirms:

The research intent was good

The execution model was wrong and is now corrected

5. Maintainer Feedback (Authoritative Interpretation)
Direct maintainer statement (summary)

Empty cells replaced with [] pollute the database

[] adds no value and breaks inheritance logic

Because the database evolves quickly, the maintainer:

Refactored the PR themselves

Preserved only the real contributions

Reward rules have tightened:

Cell reward increased to 0.06 USDC

A quality gateway can now reduce rewards for poor-quality data

Implication

Fewer, cleaner, inheritance-aware cells are now more valuable than bulk edits.

6. Core Data Philosophy (This Is Non-Negotiable)
The Golden Rule

An empty cell is not missing data.
An empty cell is intentional.

It means one of two things:

The value is inherited via !provider

The value is unknown or unverified

Absolute prohibitions

The following are never allowed:

[]

{}

null, NULL

Placeholder text

Guesswork

Duplicated provider data

Any of the above can:

Reduce reward per cell

Trigger partial refactors

Cause PR rejection

7. Provider Reference System (Mandatory)
Purpose

To deduplicate data and keep global facts in one place.

How it works

Global providers live in:
providers/<category>.csv

Network-specific files reference them using:

!provider:<provider-slug>

Inheritance rules

Provider data is copied only into empty cells

Network values override provider values only if explicitly set

Writing null or [] blocks inheritance (this is wrong)

Correct mindset

Providers = global truth

Networks = exceptions and specifics only

8. Quality Gateway (New Enforcement Layer)

Every non-empty cell must pass all of the following:

Manually verified from a real source

Adds new, network-specific value

Is not inherited from a provider

Matches column type and formatting rules

Would be genuinely useful to a developer

Automatic disqualifiers

Empty JSON arrays

Dummy values

Cosmetic but meaningless text

Repeated provider facts

Low-effort padding

9. Standard of Work Required (For All Future PRs)
Data standards

Booleans: TRUE / FALSE only

JSON:

Validated with jsonformatter.org

Arrays only when semantically required

Markdown:

Allowed where supported

Wrapped correctly in JSON arrays if needed

Structural standards

Correct folder placement:

networks/<chain>/<category>.csv

providers/<category>.csv

Exact column count per header

Correct filename casing

UTF-8, comma-delimited, no BOM

10. Networks & Execution Plan
Networks already touched

Arbitrum

TON

BSC

Remaining networks (14 total)

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

Approved batching strategy
Batch 1 – High Priority

Base

Linea

Solana

Aptos

Batch 2 – Established L1s

Algorand

Cardano

Stellar

Filecoin

Batch 3 – Emerging / Infra

Astar

Flare

Lens

Somnia

Sonic

Sui

11. Required Workflow (Step-by-Step)

For every network:

Deduplicate

Replace repeated provider rows with !provider

Clear inherited cells

Enrich

Add only verified, network-specific providers

Validate

Check JSON

Check booleans

Check column counts

Review

Ensure no [], null, or filler exists

Limit

Keep PR under size constraints

Submit

With correct PR template and links

12. PR Message Template (Mandatory)

All PRs must follow this structure (no deviation):

## Summary
Provide a concise summary of the change and why it’s needed.

## Type of change
- [ ] Add data rows
- [ ] Update data rows
- [ ] Remove data rows
- [ ] Schema change (requires linked DBIP)
- [ ] Documentation/metadata only

## Scope
- **Networks affected**:
- **Categories affected**:
- Additional notes or constraints:

## Links
- Related issue(s):
- DB Improvement Proposal (DBIP), if any:

## Validation checklist
- [ ] Followed Style Guide and Column Definitions
- [ ] Correct folder and CSV placement
- [ ] No duplicate entries
- [ ] CSV formatting validated
- [ ] JSON validated
- [ ] No placeholders, nulls, or empty arrays

## Optional
- Rewards address:
- Twitter (X) post link:

13. Division of Responsibility
Human (Joshua)

Manual verification

Final approval before pushing

Responding to maintainers

Linking wallet and X post

AI Agent

Scan repository structure

Detect inheritance opportunities

Flag cells that must remain empty

Enforce Style Guide rules

Prevent forbidden values

Prepare PR-ready diffs and messages

14. Strategic Outcome

If executed correctly:

Approval rate increases

Reward per cell increases

Contributor trust increases

Possibility of:

Network ownership

Fixed grants

Validator roles

15. Final Instruction to the AI Agent

You are not optimizing for the number of filled cells.
You are optimizing for signal, correctness, inheritance awareness, and reviewer trust.

If a value is uncertain, inherited, duplicated, or cosmetic — leave it empty.