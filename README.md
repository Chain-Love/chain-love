# Chain.Love Web3 Database

This repository documents blockchain service providers - wallets, explorers, analytics, bridges, dev tools, sdks, faucets, apis, oracles, indexing services, etc. - in a structured way.

The goal is to build a **clean, comparable dataset** that developers and researchers can rely on.

## Data model (how to think about this repo)

Use this relationship graph:

`provider -> offer -> listing`

- **Provider**: identity metadata (name, logo, links, description).
- **Offer**: a category-specific product/plan sold by a provider.
- **Listing**: where an offer is available (for one network or all networks).

## Repository structure

Conceptual structure used in contribution docs:

```
references/
  providers/
    providers.csv    # provider identities
    images/          # local provider logos in jpg/png
    csv/logoPath
  offers/            # offers of the providers
listings/
  specific-networks/<chain>/  # per-chain listing instances
  all-networks/      # listing instances merged into every chain
```

## How to Consume

### Visualize data
Go to https://chain.love and select the network you would like to explore. Take a look also at [our AI](https://chatgpt.com/g/g-68bf52c0b60c8191a56c6f98959b97ec-chain-love) that is based on this open-source database!

### Programmatically
Go to [Releases](https://github.com/Chain-Love/chain-love/releases) to fetch latest JSONs we produce.

## How to Contribute
We recommend using our [Contribution Wizard](https://app.chain.love/contributor/web3-data). For manual contributions, please, see [CONTRIBUTING](CONTRIBUTING.md).

⭐ Star this repository before submitting a contribution.

### Star History

<a href="https://www.star-history.com/?repos=chain-love%2Fchain-love&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=chain-love/chain-love&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=chain-love/chain-love&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=chain-love/chain-love&type=date&legend=top-left" />
 </picture>
</a>
