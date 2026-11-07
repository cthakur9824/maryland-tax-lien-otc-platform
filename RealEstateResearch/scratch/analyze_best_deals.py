import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_liens.json", "r", encoding="utf-8") as f:
    liens = json.load(f)

print(f"Total Liens Analyzed: {len(liens)}")

valid_liens = [r for r in liens if r.get("assessment", 0) >= 15000]
print(f"Valid Liens (Assessment >= $15,000): {len(valid_liens)}")

# Category 1: Single Family Homes & Improved Properties
improved_homes = [
    r for r in valid_liens 
    if (r.get("improvement_value") and r["improvement_value"] > 20000) or (r.get("year_built") and str(r.get("year_built")) not in ["None", "null", ""])
]

# Category 2: Vacant Residential Land & Infill Building Lots
prime_land = [
    r for r in valid_liens 
    if r.get("land_value", 0) >= 20000 and (not r.get("improvement_value") or r["improvement_value"] <= 20000)
    and any(z in str(r.get("zoning", "")) for z in ["R1", "R2", "R5", "RA", "OS", "R"])
]

# Category 3: Low-Risk / High-Yield Liens (LTV < 2.5%, Lien < $5,000, Assessed > $100k)
low_risk_high_yield = [
    r for r in valid_liens 
    if r.get("assessment", 0) >= 100000 and r.get("ltv_pct", 100) < 2.5 and r.get("total_due", 99999) <= 6000
]

improved_homes.sort(key=lambda x: x.get("ltv_pct", 100))
prime_land.sort(key=lambda x: (x.get("ltv_pct", 100), -x.get("assessment", 0)))
low_risk_high_yield.sort(key=lambda x: x.get("ltv_pct", 100))

print("\n=======================================================")
print("[TOP CATEGORY 1: HIGH-VALUE IMPROVED HOMES (Foreclosure or 12% Yield)]")
print("=======================================================")
for r in improved_homes[:10]:
    impr = r.get('improvement_value') or 0
    print(f"List #{r['list_no']:<4} | Acct: {r['account_no']} | Addr: {r.get('address', 'N/A')}, {r.get('city', '')} | Owner: {r['owner']} ({r.get('owner_city_state', 'MD')}) | Assessed: ${r['assessment']:>9,f} (Impr: ${impr:>9,f}) | Lien Due: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']:>5.2f}% | Built: {r.get('year_built', 'N/A')} | Zoning: {r.get('zoning')}")

print("\n=======================================================")
print("[TOP CATEGORY 2: PRIME RESIDENTIAL LAND & BUILDABLE LOTS]")
print("=======================================================")
for r in prime_land[:10]:
    acres = r.get('acres') or 0
    print(f"List #{r['list_no']:<4} | Acct: {r['account_no']} | Addr: {r.get('address', 'N/A')}, {r.get('city', '')} | Owner: {r['owner']} | Zoning: {r.get('zoning')} | Acres: {acres:>5.2f} | Assessed: ${r['assessment']:>9,f} | Lien Due: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']:>5.2f}%")

print("\n=======================================================")
print("[TOP CATEGORY 3: HIGH-YIELD LOW-CAPITAL SECURED LIENS (Lien < $5k, Assessment > $100k)]")
print("=======================================================")
for r in low_risk_high_yield[:12]:
    print(f"List #{r['list_no']:<4} | Acct: {r['account_no']} | Addr: {r.get('address', 'N/A')}, {r.get('city', '')} | Owner: {r['owner']} | Assessed: ${r['assessment']:>9,f} | Lien Due: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']:>5.2f}%")

