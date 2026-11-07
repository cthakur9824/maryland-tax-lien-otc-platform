import json
import os
import pypdf
import re

PDF_PATH = r"raw\Kent County 2026 Tax Sale - OTC 6.9.26.pdf"

reader = pypdf.PdfReader(PDF_PATH)
text = reader.pages[0].extract_text()
lines = text.split('\n')

records = []
pattern = re.compile(r'^(\d{8})\s+(.+?)\s+([\d,]+)\s+([\d,]+\.\d{2})\$\s+(.+)$')

for line in lines:
    line_str = line.strip()
    m = pattern.match(line_str)
    if m:
        acct, owner, assessed, bid, legal = m.groups()
        assessed_val = float(assessed.replace(',', ''))
        bid_val = float(bid.replace(',', ''))
        ltv = round((bid_val / assessed_val) * 100, 1) if assessed_val > 0 else 999.0
        spread = assessed_val - bid_val
        
        # Categorize location / subdivision
        legal_upper = legal.upper()
        if "CHESAPEAKE LANDING" in legal_upper:
            loc = "Chesapeake Landing"
        elif "TOLCHESTER" in legal_upper:
            loc = "Tolchester Estates"
        elif "COLEMANS" in legal_upper:
            loc = "Colemans"
        elif "BUTLERTOWN" in legal_upper:
            loc = "Butlertown"
        elif "MILLINGTON" in legal_upper:
            loc = "Millington"
        elif "ROCK HALL" in legal_upper:
            loc = "Rock Hall"
        elif "CHESTERTOWN" in legal_upper:
            loc = "Chestertown"
        elif "MELITOTA" in legal_upper:
            loc = "Melitota"
        elif "STILL POND" in legal_upper:
            loc = "Still Pond"
        else:
            loc = "Rural Kent"

        records.append({
            'account_id': acct,
            'district': acct[:2],
            'account_num': acct[2:],
            'owner': owner.strip(),
            'assessed_value': assessed_val,
            'opening_bid': bid_val,
            'ltv_pct': ltv,
            'equity_spread': spread,
            'location_tag': loc,
            'legal_description': legal.strip()
        })

print(f"Total Parsed Records: {len(records)}")

# Group into Tiers:
# Tier 1: Top Alpha / Low LTV & Micro-Liens (LTV < 25% or Bid < $2,000)
# Tier 2: Solid Residential Equity (Assessed $50k+, LTV 25%-50%, Spread $30k+)
# Tier 3: Chesapeake Landing / Subdivision Clusters (DUCHKA LLC, Churn Creek, Reed)
# Tier 4: High Risk / Underwater / Red Flag (LTV > 80%)

tier1 = [r for r in records if r['ltv_pct'] <= 25.0 or r['opening_bid'] < 2000]
tier2 = [r for r in records if r not in tier1 and r['assessed_value'] >= 50000 and r['ltv_pct'] <= 50.0]
tier3 = [r for r in records if r not in tier1 and r not in tier2 and r['ltv_pct'] <= 70.0]
tier4 = [r for r in records if r not in tier1 and r not in tier2 and r not in tier3]

print(f"\n=== TIER 1: TOP ALPHA / ULTRA-LOW LTV & MICRO-LIENS ({len(tier1)} deals) ===")
for r in sorted(tier1, key=lambda x: x['ltv_pct']):
    print(f"Acct: {r['account_id']} | Bid: ${r['opening_bid']:>9,.2f} | Assessed: ${r['assessed_value']:>8,.0f} | LTV: {r['ltv_pct']:>5.1f}% | Spread: ${r['equity_spread']:>8,.0f} | Loc: {r['location_tag']:<18} | {r['legal_description']}")

print(f"\n=== TIER 2: HIGH EQUITY RESIDENTIAL DEALS ({len(tier2)} deals) ===")
for r in sorted(tier2, key=lambda x: x['equity_spread'], reverse=True):
    print(f"Acct: {r['account_id']} | Bid: ${r['opening_bid']:>9,.2f} | Assessed: ${r['assessed_value']:>8,.0f} | LTV: {r['ltv_pct']:>5.1f}% | Spread: ${r['equity_spread']:>8,.0f} | Loc: {r['location_tag']:<18} | {r['legal_description']}")

print(f"\n=== TIER 3: SUBDIVISION CLUSTERS & INFILL LOTS ({len(tier3)} deals) ===")
for r in sorted(tier3, key=lambda x: x['opening_bid']):
    print(f"Acct: {r['account_id']} | Bid: ${r['opening_bid']:>9,.2f} | Assessed: ${r['assessed_value']:>8,.0f} | LTV: {r['ltv_pct']:>5.1f}% | Spread: ${r['equity_spread']:>8,.0f} | Loc: {r['location_tag']:<18} | {r['legal_description']}")

print(f"\n=== TIER 4: HIGH RISK / UNDERWATER / AVOID ({len(tier4)} deals) ===")
for r in sorted(tier4, key=lambda x: x['ltv_pct'], reverse=True):
    print(f"Acct: {r['account_id']} | Bid: ${r['opening_bid']:>9,.2f} | Assessed: ${r['assessed_value']:>8,.0f} | LTV: {r['ltv_pct']:>5.1f}% | Spread: ${r['equity_spread']:>8,.0f} | Loc: {r['location_tag']:<18} | {r['legal_description']}")

# Also save organized JSON
os.makedirs("scratch", exist_ok=True)
with open("scratch/kent_county_analyzed_deals.json", "w", encoding="utf-8") as f:
    json.dump({
        "total_count": len(records),
        "total_opening_bid_volume": sum(r['opening_bid'] for r in records),
        "total_assessed_value": sum(r['assessed_value'] for r in records),
        "tier1_alpha": tier1,
        "tier2_high_equity": tier2,
        "tier3_clusters": tier3,
        "tier4_avoid": tier4
    }, f, indent=2)
