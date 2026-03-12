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
