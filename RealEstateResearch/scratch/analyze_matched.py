import json

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json", "r", encoding="utf-8") as f:
    records = json.load(f)

print(f"Total Records: {len(records)}")
matched = [r for r in records if r.get("matched")]
unmatched = [r for r in records if not r.get("matched")]
print(f"Matched: {len(matched)}, Unmatched: {len(unmatched)}")

print("\n--- SAMPLE UNMATCHED ---")
for u in unmatched[:10]:
    print(f"List #{u['list_no']}: Acct: {u['account_no']} | Owner: {u['owner']} | Assessed: ${u['assessment']:,.2f} | Total Due: ${u['total_due']:,.2f}")

print("\n--- ALL MATCHED SORTED BY LOWEST LTV ---")
# Filter out low assessment junk (< $15,000)
good_deals = [r for r in matched if r.get("assessment", 0) >= 20000]
good_deals.sort(key=lambda x: x.get("ltv_pct", 100))

for r in good_deals:
    addr = r.get("address", "N/A")
    city = r.get("city", "N/A")
    impr = r.get("improvement_value") or 0
    lnd = r.get("land_value") or 0
    acres = r.get("acres") or 0
    yr = r.get("year_built") or "N/A"
    zoning = r.get("zoning") or "N/A"
    print(f"List #{r['list_no']:<4} | Acct: {r['account_no']} | {addr}, {city} | Owner: {r['owner']} | Assessed: ${r['assessment']:>9,f} (Land: ${lnd:>7,f}, Impr: ${impr:>7,f}) | Lien Due: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']:>5.2f}% | Acres: {acres:>5.2f} | Built: {yr} | Zoning: {zoning} | GMaps: {r.get('google_maps_url', 'N/A')}")
