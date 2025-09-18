import json
import requests

# --- Config ---
CIK = "0001318605"  # Tesla Inc. (use Apple: 0000320193)
LOCAL_FILE = "companyfacts.json"
DOWNLOAD = True

# --- Step 1: get the JSON ---
if DOWNLOAD:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
    headers = {"User-Agent": "yourname@example.com"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()
else:
    with open(LOCAL_FILE, "r") as f:
        data = json.load(f)

# --- Helper to extract annual values for a tag ---
def extract_tag(cf, tag):
    node = cf.get("facts", {}).get("us-gaap", {}).get(tag)
    if not node:
        return {}
    units = node.get("units", {})
    if "USD" not in units:
        return {}
    out = {}
    for obs in units["USD"]:
        if obs.get("fp") == "FY" and obs.get("fy") and obs.get("val") is not None:
            year = int(obs["fy"])
            out[year] = float(obs["val"])
    return out

# --- Step 2: extract relevant series ---
rev = extract_tag(data, "Revenues") or extract_tag(data, "SalesRevenueNet")
gp = extract_tag(data, "GrossProfit")
cogs = extract_tag(data, "CostOfRevenue") or extract_tag(data, "CostOfGoodsAndServicesSold")

# --- Step 3: derive missing cost of revenue ---
if not cogs and rev and gp:
    cogs = {}
    for year in rev:
        if year in gp:
            cogs[year] = rev[year] - gp[year]

# --- Step 4: print comparison ---
years = sorted(set(rev) | set(gp) | set(cogs))
print("Year | Revenue | Gross Profit | Cost of Revenue (derived if missing)")
print("-" * 70)
for y in years:
    print(
        f"{y} | "
        f"{rev.get(y, '–'):>10} | "
        f"{gp.get(y, '–'):>12} | "
        f"{cogs.get(y, '–'):>18}"
    )
