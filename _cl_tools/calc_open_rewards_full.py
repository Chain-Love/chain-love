import re
import csv
import urllib.request
import time

RATE = 0.06
CELL_CAP = 200
REWARD_CAP = 12.0
IMAGE_REWARD = 0.20  # historical rate from March payout (#686)
PAID_NETWORKS = {
    "algorand",
    "arbitrum",
    "avalanche",
    "ethereum",
    "somnia",
    "filecoin",
    "base",
}

OPEN_PRS = [
    1843, 1842, 1841, 1838, 1837, 1836, 1834, 1833, 1829, 1828, 1827, 1826,
    1820, 1819, 1818, 1817, 1798, 1797, 1763, 1762, 1761, 1757, 1756, 1751,
]

TITLES = {
    1751: "Add bleap, digitap, flinchpay, switchere and topper to Ramps csv",
    1756: "add jiffyscan to explorers",
    1757: "ad Wormhole to explorers",
    1761: "Add itez, kado, meso, unlimit crypto, utorg to ramps",
    1762: "Add Blockscan to explorers",
    1763: "Add Chainlens to Explorers",
    1797: "Add bitzaro, bvnk, bybarter, kodoramp and lunu to ramps",
    1798: "Add onmeta, swapped, swipelux, topper, coinbase-ramp to ramps",
    1817: "Add belo, Fiat24, 1money, Alixpay and settleNetwork to ramps",
    1818: "Add bridge, lightspark, breet and coinflow to ramps",
    1819: "Add bisq, eldorado, openpeer, paycrest and sphereone to ramps",
    1820: "Add straitsX, assetux, transfi and cybrid to ramps",
    1826: "Add uviscan to explorers",
    1827: "Add 10 faucets to ethereum",
    1828: "Add 10 faucets to ethereum (batch 2)",
    1829: "Add 10 faucets to ethereum (batch 3)",
    1833: "Add 10 faucets to ethereum (batch 4)",
    1834: "Add 10 faucets to ethereum (batch 5)",
    1836: "Add peckshield to security",
    1837: "Add Kudelski to security",
    1838: "Add Quantstamp to security",
    1841: "Add verified social fields to providers",
    1842: "Add verified social fields to providers.csv (2)",
    1843: "Add supportEmail to entries in provider.csv",
}


def parse(line):
    try:
        return next(csv.reader([line]))
    except Exception:
        return []


def net(path):
    m = re.search(r"specific-networks/([^/]+)/", path)
    return m.group(1) if m else None


def bucket(path):
    n = net(path)
    if n:
        return "networks" if n in PAID_NETWORKS else None
    if path == "references/providers/providers.csv":
        return "providers"
    if path.startswith("references/offers/") and path.endswith(".csv"):
        return "offers"
    if path.startswith("references/providers/images/") and path.endswith(".png"):
        return "images"
    if path.startswith("listings/all-networks/"):
        return "networks"
    return None


def cells_in_part(part):
    lines = part.split("\n")
    plus = [ln for ln in lines if ln.startswith("+") and not ln.startswith("+++")]
    minus = [ln for ln in lines if ln.startswith("-") and not ln.startswith("---")]
    cells = 0
    if plus and minus:
        p = min(len(plus), len(minus))
        for i in range(p):
            if "," not in plus[i][1:]:
                continue
            o, n = parse(minus[i][1:]), parse(plus[i][1:])
            L = max(len(o), len(n))
            o += [""] * (L - len(o))
            n += [""] * (L - len(n))
            cells += sum(1 for a, b in zip(o, n) if b.strip() and b.strip() != a.strip())
        for ln in plus[p:]:
            if "," in ln[1:]:
                cells += sum(1 for x in parse(ln[1:]) if x.strip())
    else:
        for ln in plus:
            if "," in ln[1:]:
                cells += sum(1 for x in parse(ln[1:]) if x.strip())
    return cells


def images_in_part(part):
    return sum(
        1
        for ln in part.split("\n")
        if ln.startswith("+++") and "/dev/null" in ln and ln.endswith(".png")
    )


def fetch_diff(num):
    url = f"https://github.com/Chain-Love/chain-love/pull/{num}.diff"
    req = urllib.request.Request(url, headers={"User-Agent": "cl-reward"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def analyze_pr(num):
    diff = fetch_diff(num)
    parts = re.split(r"^diff --git ", diff, flags=re.M)
    counts = {"networks": 0, "providers": 0, "offers": 0, "images": 0}
    for part in parts[1:]:
        m = re.match(r"a/(.+?) b/(.+?)\n", part)
        if not m:
            continue
        path = m.group(2)
        b = bucket(path)
        if b == "images":
            counts["images"] += images_in_part(part)
        elif b in counts:
            counts[b] += cells_in_part(part)
    cell_total = counts["networks"] + counts["providers"] + counts["offers"]
    capped_cells = min(cell_total, CELL_CAP)
    cell_reward = min(capped_cells * RATE, REWARD_CAP)
    image_reward = counts["images"] * IMAGE_REWARD
    total_reward = round(cell_reward + image_reward, 2)
    return counts, cell_total, capped_cells, cell_reward, image_reward, total_reward


def main():
    print("Rules: $0.06/cell (networks+providers+offers), cap 200 cells/$12 per PR")
    print(f"Images: ${IMAGE_REWARD} each | Paid networks: {sorted(PAID_NETWORKS)}\n")
    grand = 0.0
    for num in sorted(OPEN_PRS):
        counts, cell_total, capped, cell_rew, img_rew, total = analyze_pr(num)
        grand += total
        title = TITLES.get(num, "?")
        print(
            f"#{num} | {title}\n"
            f"       nets={counts['networks']} prov={counts['providers']} "
            f"offers={counts['offers']} imgs={counts['images']} | "
            f"cells={cell_total} capped={capped} | "
            f"${cell_rew:.2f} cells + ${img_rew:.2f} imgs = ${total:.2f}"
        )
        time.sleep(0.8)
    print(f"\nTOTAL: ${grand:.2f}")


if __name__ == "__main__":
    main()
