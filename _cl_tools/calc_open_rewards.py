import json
import csv
import re
import urllib.request
import time

RATE = 0.06
CELL_CAP = 200
REWARD_CAP = 12.0
PAID_NETWORKS = {"algorand", "arbitrum", "avalanche", "ethereum", "somnia", "filecoin", "base"}


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "cl-reward"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def net(path):
    m = re.search(r"specific-networks/([^/]+)/", path)
    return m.group(1) if m else None


def parse(line):
    try:
        return next(csv.reader([line]))
    except Exception:
        return []


def cells_from_patch(patch):
    if not patch:
        return 0
    plus, minus = [], []
    for line in patch.split("\n"):
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+") and not line.startswith("++"):
            plus.append(line[1:])
        elif line.startswith("-") and not line.startswith("--"):
            minus.append(line[1:])
    cells = 0
    if plus and minus:
        p = min(len(plus), len(minus))
        for i in range(p):
            if "," not in plus[i]:
                continue
            o, n = parse(minus[i]), parse(plus[i])
            L = max(len(o), len(n))
            o += [""] * (L - len(o))
            n += [""] * (L - len(n))
            cells += sum(1 for a, b in zip(o, n) if b.strip() and b.strip() != a.strip())
        for line in plus[p:]:
            if "," in line:
                cells += sum(1 for c in parse(line) if c.strip())
    else:
        for line in plus:
            if "," in line:
                cells += sum(1 for c in parse(line) if c.strip())
    return cells


def file_eligible(path):
    n = net(path)
    if n:
        return n in PAID_NETWORKS
    if path.startswith("listings/all-networks/"):
        return True
    return False


def est_pr(num):
    files = fetch(
        f"https://api.github.com/repos/Chain-Love/chain-love/pulls/{num}/files?per_page=100"
    )
    total_cells = 0
    eligible_cells = 0
    file_lines = []
    for f in files:
        fn = f["filename"]
        if not fn.endswith(".csv"):
            continue
        cc = cells_from_patch(f.get("patch") or "")
        if cc == 0 and f.get("additions"):
            cc = max(1, f["additions"] // 2)
        elig = file_eligible(fn)
        total_cells += cc
        if elig:
            eligible_cells += cc
        label = net(fn) or (
            "all-networks" if "all-networks" in fn else "references/other"
        )
        file_lines.append((fn, cc, elig, label))
    capped_cells = min(eligible_cells, CELL_CAP)
    reward = min(capped_cells * RATE, REWARD_CAP)
    return total_cells, eligible_cells, capped_cells, reward, file_lines


def main():
    open_prs = [
        1843, 1842, 1841, 1838, 1837, 1836, 1834, 1833, 1829, 1828, 1827, 1826,
        1820, 1819, 1818, 1817, 1798, 1797, 1763, 1762, 1761, 1757, 1756, 1751,
    ]
    print(f"Rules: paid networks={sorted(PAID_NETWORKS)}, cap={CELL_CAP} cells / ${REWARD_CAP}")
    print()
    grand = 0.0
    for num in open_prs:
        pr_meta = fetch(
            f"https://api.github.com/repos/Chain-Love/chain-love/pulls/{num}"
        )
        total, elig, capped, reward, files = est_pr(num)
        grand += reward
        elig_nets = sorted({n for _, _, e, n in files if e})
        inelig = sum(c for _, c, e, _ in files if not e)
        title = pr_meta["title"][:55]
        print(
            f"#{num} | total={total} elig={elig} capped={capped} | ${reward:.2f} | {title}"
        )
        if elig_nets:
            print(f"       paid paths: {elig_nets}")
        if inelig:
            print(f"       unpaid cells (providers/offers/refs): {inelig}")
        time.sleep(2.0)
    print()
    print(f"TOTAL (24 open PRs): ${grand:.2f}")


if __name__ == "__main__":
    main()
