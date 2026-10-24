```python
import csv
from collections import Counter
p = "references/providers/providers.csv"
with open(p, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
matches = [(r["slug"], r["telegram"]) for r in rows if r["telegram"].startswith("+")]
print("providers", len(rows), "plus_invites", len(matches))
print("examples", matches[:3])
```