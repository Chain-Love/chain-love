## Summary

Completed data deduplication, enrichment, and validation for the Base, Linea, Solana, Aptos, Algorand, and Cardano networks. This includes ensuring data consistency, applying the `!provider` inheritance model, adding missing high-value API providers, and verifying compliance with the Style Guide and Quality Contract.

## Type of change
- [x] Add data rows
- [x] Update data rows
- [ ] Remove data rows
- [ ] Schema change <!-- (requires linked DBIP below) -->
- [x] Documentation/metadata only
- [x] Data deduplication/Refactoring (e.g., applying inheritance cleanup)

## Scope
- Networks affected: Base, Linea, Solana, Aptos, Algorand, Cardano
- Categories affected: apis, wallets, explorers (where applicable)

- Additional notes, additional context / screenshots:
  - This PR finalizes the remaining networks in Batch 1 (Linea, Solana, Aptos) and initiates Batch 2 with Algorand and Cardano.
  - All changes adhere strictly to the "Golden Rule" of empty cells and the Provider Inheritance model, ensuring minimal, high-quality, and non-redundant data.
  - New high-value RPC providers (e.g., Alchemy, Infura, QuickNode, Ankr, Blockfrost, PureStake, Tatum, Chainstack) have been added or updated for these networks where appropriate.

## Key Improvements (if applicable)
- **Inheritance Cleanup**: Purged redundant data cells across `networks/base/`, `networks/linea/`, `networks/solana/`, `networks/aptos/`, `networks/algorand/`, and `networks/cardano/`. All shared metadata is now correctly inherited from the global `providers/` folder using the `!provider` syntax.
- **Data Normalization**: Standardized all boolean values to uppercase `TRUE`/`FALSE` and removed "null" strings to ensure perfect JSON generation.
- **Schema Compliance**: Verified that all CSVs have the exact column count matching the headers.

## Links
- Related issue(s)/ DB Improvement Proposal (if schema-related): N/A

## Validation checklist
<!-- Please ensure you understand everything and agrees with what is written below. Violations may result in reward slashes of database grant population program -->

- [x] **I followed the Style Guide and Column Definitions. I'm aware of what is `!provider` syntax, and that entities in `/networks` sub-folders inherits records from `/providers` folder**
  - Style Guide: `https://github.com/Chain-Love/chain-love/wiki/Style-Guide`
  - Column Definitions: `https://github.com/Chain-Love/chain-love/wiki`
- [x] **I personally opened and verified every new link I'm adding. I can confirm, that all the links I'm adding are valid.**
- [x] **If I added new entries - I personally confirmed that the provider I'm adding (modifying) currently supports the adjusted network(s). I've also verified that value in every cell I'm changing is correct according to my best understanding**
- [x] **This PR is not a blind AI-generated submission**

## Optional
- Rewards address (for data patching rewards): 0x94D532457f640abc7ACE133BCeaa6b8D19725098
- Twitter (X) post link (for +10% of rewards to this PR): https://x.com/iamsemek/status/2030050498250703086
​
​
​
​
​
​
​
​
​
​
