import json

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_parsed_liens.json", "r") as f:
    liens = json.load(f)

# Sort all liens by Assessment descending and calculate metrics
# Let's filter into actionable tiers:
# Tier A: Mega Equity / Sub-2% LTV (Assessment $200k - $733k, Lien < $15k)
# Tier B: Sweet Spot Residential & Land (Assessment $50k - $200k, Lien < $3k)
# Tier C: Micro Liens / High ROI (Lien < $1,000, Assessment > $20k)

tier_a = [r for r in liens if r["assessment"] >= 200000 and r["ltv_pct"] <= 5.0]
tier_b = [r for r in liens if 50000 <= r["assessment"] < 200000 and r["ltv_pct"] <= 4.0]
tier_c = [r for r in liens if r["total_due"] < 1000 and r["assessment"] >= 20000]

tier_a.sort(key=lambda x: x["ltv_pct"])
tier_b.sort(key=lambda x: x["ltv_pct"])
tier_c.sort(key=lambda x: x["ltv_pct"])

print(f"Tier A (Mega Equity $200k+): {len(tier_a)}")
for r in tier_a:
    print(f"List #{r['list_no']:<4} | Acct: {r['account_no']} | Owner: {r['owner'][:30]:<30} | Assessment: ${r['assessment']:>8,f} | Lien: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']}%")

print(f"\nTier B (Sweet Spot $50k-$200k): {len(tier_b)}")
for r in tier_b[:10]:
    print(f"List #{r['list_no']:<4} | Acct: {r['account_no']} | Owner: {r['owner'][:30]:<30} | Assessment: ${r['assessment']:>8,f} | Lien: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']}%")

print(f"\nTier C (Micro Liens < $1,000): {len(tier_c)}")
for r in tier_c:
    print(f"List #{r['list_no']:<4} | Acct: {r['account_no']} | Owner: {r['owner'][:30]:<30} | Assessment: ${r['assessment']:>8,f} | Lien: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']}%")
