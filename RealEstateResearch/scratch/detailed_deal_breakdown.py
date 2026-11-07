import json

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json", "r", encoding="utf-8") as f:
    records = json.load(f)

# Group by owner to find builder/subdivision packages
owner_groups = {}
for r in records:
    o = r.get("owner", "UNKNOWN")
    owner_groups.setdefault(o, []).append(r)

packages = {k: v for k, v in owner_groups.items() if len(v) > 1}

print(f"=== MULTI-PARCEL PACKAGES ({len(packages)}) ===")
for owner, pk_records in packages.items():
    total_assessed = sum(r.get("assessment", 0) for r in pk_records)
    total_due = sum(r.get("total_due", 0) for r in pk_records)
    ltv = (total_due / total_assessed * 100) if total_assessed > 0 else 0
    print(f"\nDeveloper/Owner: {owner} ({len(pk_records)} parcels)")
    print(f"  Total Assessed: ${total_assessed:,.2f} | Total Lien Capital: ${total_due:,.2f} | Blended LTV: {ltv:.2f}%")
    for r in pk_records:
        print(f"    - List #{r.get('list_no')}: Acct {r.get('account_no')} | {r.get('address', 'N/A')}, {r.get('city', 'N/A')} | Assessed: ${r.get('assessment', 0):,.2f} | Lien: ${r.get('total_due', 0):,.2f} | Zoning: {r.get('zoning')}")

print("\n" + "="*80)
print("=== TOP INDIVIDUAL DEALS BY STRATEGY ===")

# Filter records
valid = [r for r in records if r.get("assessment", 0) >= 20000 and r.get("ltv_pct", 100) < 5.0]
valid.sort(key=lambda x: x.get("ltv_pct", 100))

print(f"\nTotal Top Tier Valid Liens (Assessed >= $20k, LTV < 5%): {len(valid)}")
for i, r in enumerate(valid):
    addr = r.get("address", "N/A")
    city = r.get("city", "N/A")
    impr = r.get("improvement_value") or 0
    lnd = r.get("land_value") or 0
    acres = r.get("acres") or 0
    yr = r.get("year_built") or "N/A"
    print(f"{i+1:2d}. List #{r['list_no']:<4} | Acct: {r['account_no']} | {addr}, {city} | {r['owner']} | Assessed: ${r['assessment']:>9,.2f} | Lien Due: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']:>5.2f}% | Land: ${lnd:>7,.2f} | Impr: ${impr:>7,.2f} | Acres: {acres:>5.2f} | Zoning: {r.get('zoning')} | Maps: {r.get('google_maps_url', 'N/A')}")
