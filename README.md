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

1. **Fork & branch**: Fork the repo and create a descriptive branch (e.g. `add-ankr-provider`).
2. **Choose what to edit**: Pick the right CSV (e.g. `rpc.csv` in the correct network).
3. **Follow the rules**: Check the [Style Guide](https://github.com/Chain-Love/chain-love/wiki/Style-Guide) and [Column Definitions](https://github.com/Chain-Love/chain-love/wiki) for formatting and examples, then edit your entry.
4. **Validate & commit**: Make sure the CSV is correct, then commit and push. You can use the [pre-commit hook](#pre-commit-hook) to validate your changes locally.
5. **Open a PR**: Describe your changes, link related issues. Maintainers will review and merge.

### Pre-commit Hook

Install `python3`:

- macOS: `brew install python3`
- Linux: Most distributions already include Python 3. If not, run `sudo apt-get install python3` (or use your distro’s package manager).
- Windows: Download and install [Python 3](https://www.python.org/downloads/). During installation, check “Add Python to PATH”.

Verify `python3` is installed:

```bash
python3 --version
```

Install `pipx`:

- macOS:
```bash
brew install pipx
pipx ensurepath
```
- Linux:
```bash
sudo apt-get install pipx
pipx ensurepath
```
- Windows:
```powershell
python -m pip install --user pipx
python -m pipx ensurepath
```

Restart your terminal after this step.

Verify `pipx` is installed:

```bash
pipx --version
```

Install `pre-commit`:

```bash
pipx install pre-commit
```

Verify `pre-commit` is installed:

```bash
pre-commit --version
```

Install the hook by running the following command in the root of the repository:

```bash
pre-commit install
```

Now data validation scripts will run before each commit.

## Reporting Issues

Use [GitHub Issues](https://github.com/Chain-Love/chain-love/issues).

Supported issue types:

* **Bug Report**: Fix broken database structure or Chain.Love website issue.
* **DB Improvement Proposal (DBIP)**: Suggest changes to the data model (categories, tables, or columns).
* **Blank Issue**: For everything else.


