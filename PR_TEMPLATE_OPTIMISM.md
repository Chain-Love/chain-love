## Summary 
Deep enrichment of the Optimism ecosystem data, fully refactored to align with the Chain.Love Style Guide and the Provider Reference architecture. This PR resolves all issues related to data duplication by leveraging global inheritance.

## Type of change 
- [x] Add data rows 
- [x] Update data rows 
- [x] Data deduplication/Refactoring

## Scope 
- **Networks affected**: optimism
- **Categories affected**: rpc, wallet, explorer, indexing, bridge, analytic, devTool, oracle, faucet

## Key Improvements
- **Inheritance Cleanup**: Purged over 530 redundant data cells in `networks/optimism/`. All shared metadata is now correctly inherited from the global `providers/` folder using the `!provider` syntax.
- **Data Normalization**: Standardized all boolean values to uppercase `TRUE`/`FALSE` and removed "null" strings to ensure perfect JSON generation.
- **Schema Compliance**: Verified that all CSVs have the exact column count matching the headers.

## Validation checklist 
- [x] I followed the Style Guide and Column Definitions 
- [x] Rows are placed in the correct folder(s) and CSV(s) 
- [x] No duplicate entries (by provider + chain + relevant key columns) 
- [x] CSV formatting: comma-delimited, quote fields as needed, UTF-8, no BOM 
- [x] Values match defined types/enums per Column Definitions 

## Optional 
- Rewards address: 0x94D532457f640abc7ACE133BCeaa6b8D19725098
- Twitter (X) post link: https://x.com/iamsemek/status/2016164246086709378
