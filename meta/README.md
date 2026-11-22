## Meta files guide

This folder contains only metadata files (`categories.json`, `columns.json` and `non-evm-networks.json`).

Please consult root [README.md](../README.md) for the instructions on how to populate `categories.json` and `columns.json`.

`non-evm-networks.json` lists the network folders (as in `listings/specific-networks/`) that do not serve EVM JSON-RPC: `csv_to_json.py` does not copy `listings/all-networks/apis.csv` rows whose technology mentions EVM to these networks.
