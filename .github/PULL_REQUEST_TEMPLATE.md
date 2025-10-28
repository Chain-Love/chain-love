## Summary

Provide a concise summary of the change and why it’s needed.


## Type of change
- [ ] Add data rows
- [ ] Update data rows
- [ ] Remove data rows
- [ ] Schema change (requires linked DBIP)
- [ ] Documentation/metadata only


## Scope
- **Networks affected**: (e.g., ethereum, polygon, arbitrum; or global)
- **Categories affected**: (e.g., rpc, wallet, explorer, indexing, bridge, analytic, devTool, oracle, faucet)

- Additional notes (constraints, naming, normalization), additional context / screenshots: 

## Links
- Related issue(s): (e.g., Closes #XXX)
- DB Improvement Proposal (DBIP), if schema-related: (e.g., #XXX)


## Validation checklist
- [ ] I followed the Style Guide and Column Definitions
  - Style Guide: https://github.com/Chain-Love/chain-love/wiki/Style-Guide
  - Column Definitions: https://github.com/Chain-Love/chain-love/wiki
- [ ] Rows are placed in the correct folder(s) and CSV(s)
  - `networks/<chain>/<category>.csv` for chain-scoped entries
  - `providers/<category>.csv` when the provider/service is chain-agnostic or cross-chain
- [ ] No duplicate entries (by provider + chain + relevant key columns)
- [ ] CSV formatting: comma-delimited, quote fields as needed, UTF-8, no BOM
- [ ] Values match defined types/enums per Column Definitions
- [ ] No unintended whitespace, trailing commas, or empty lines


## Optional
- Rewards address (for data patching rewards):
- Twitter (X) post link (for +10% of rewards to this PR):
