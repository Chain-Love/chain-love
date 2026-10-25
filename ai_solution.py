```python
import csv

"""This script processes a CSV file of providers and extracts data starting with +."""

p = "references/providers/providers.csv"
with open(p, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
matches = [(r["slug"], r["telegram"]) for r in rows if r["telegram"].startswith("+")]

print(f"providers: {len(rows)}, plus_invites: {len(matches)}")
print("examples:", matches[:3])
```