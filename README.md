# Chain.Love Infrastructure Database

This repository documents blockchain service providers - RPCs, wallets, explorers, analytics, bridges, dev tools, faucets, oracles, indexing services, etc. - in a structured way.

The goal is to build a **clean, comparable dataset** that developers and researchers can rely on.

## Repository Structure

```
├── networks/
│   ├── arbitrum/
│   │   ├── rpc.csv
│   │   ├── explorer.csv
│   │   ├── wallet.csv
│   │   └── ...
│   ├── ... (other networks, each with their own service tables)
```

Each **network folder** contains CSVs grouped by service type.

## How to Contribute

1. **Fork this repository**.
2. **Create a new branch** with a descriptive name (e.g. `add-ethereum-network` or `add-ankr-provider`).
3. **Pick the correct CSV** table for your contribution. Example: adding a new RPC provider - edit `rpc.csv` in the correct network folder.
4. **Check the rules** before editing: read the [Style Guide](https://github.com/Chain-Love/chain-love/wiki/Style-Guide) and [Column Definitions](https://github.com/Chain-Love/chain-love/wiki) for formating and consistency.
5. **Add or update your entry** in CSV format.
6. **Validate** your CSV (check formatting, no broken fields).
7. **Commit and push** your branch with a clear message.
8. **Open a Pull Request**, describe the changes, link to any related issues.
9. A maintainer will check, request fixes if needed, and merge.

## Reporting Issues

Use [GitHub Issues](https://github.com/Chain-Love/chain-love/issues).

Supported issue types:

* **Bug Report**: Fix broken database structure or Chain.Love website issue.
* **DB Improvement Proposal (DBIP)**: Suggest changes to the data model (categories, tables, or columns).
* **Blank Issue**: For everything else.


