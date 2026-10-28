# Five approved DBIPs: CSV migration

Requires the paired tools PR before merge. The existing release default remains
2.0.0; new field names and optional fields are available through the tools'
explicit 2.1.0 export. This is not an authorization to switch public consumers.

- #2481: explorers pricing -> price, preserving every existing value.
- #2681: bridges/oracles economicalSecurity[Note] -> economicSecurity[Note].
- #2682: wallets audit -> auditsPerformed, preserving values (not auditing claims).
- #2561: append trial to storage tables. Unknowns remain blank. The ongoing
  fil-one-object-storage paid offer is FALSE, even though new accounts can use
  an introductory trial. Source checked 2026-10-28: https://docs.fil.one/ documents
  recurring $5.99/TB/month pricing and separately describes the 30-day trial.
  No other storage classification is inferred. Blank listing values inherit.
- #2624: append supportedRoutes to bridge tables. Seed only linea-native's two
  ordered Ethereum/Linea routes for ETH. Source checked 2026-10-28:
  https://docs.linea.build/network/how-to/bridge documents native ETH bridging in
  both directions. No transaction was performed. Other bridge routes stay blank.

All original row values and order are preserved. Header renames retain raw CSV
body bytes; appended fields preserve every original parsed cell. The route field
describes network-level coverage, not a guarantee for any amount or live quote.

Maintainers: update wiki column definitions to match the paired schema migration
guide. The proposal authors retain credit; implementation does not claim their
proposal awards or guarantee any payment.
