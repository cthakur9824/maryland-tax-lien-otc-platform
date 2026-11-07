import sys, os, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, r"c:\Obsedian\RealEstateResearch\RealEstateResearch")
from sdat_engine import search_maryland_property
from title_search_engine import analyze_maryland_title

master_path = r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json"

with open(master_path, "r", encoding="utf-8") as f:
    records = json.load(f)

print(f"Loaded {len(records)} candidate parcels from master list.")

results = []

def process_item(item):
    acct = str(item.get("account_no") or "").strip()
    list_no = item.get("list_no")
    tax_lien = item.get("total_due") or item.get("bid_amount") or 0.0
    assessed = item.get("assessment") or item.get("sdat_total_value") or 0.0
    
    # Query SDAT
    props = search_maryland_property(acct, county="ANNE ARUNDEL")
    if not props:
        # Fallback query with address
        addr = item.get("address")
        if addr:
            props = search_maryland_property(addr, county="ANNE ARUNDEL")
            
    if not props:
        return None
        
    prop = props[0]
    tax_info = {
        "tax_lien_amount": tax_lien,
        "assessed_value": assessed,
        "owner_of_record": item.get("owner"),
        "tax_sale_flag": True
    }
    
    title_res = analyze_maryland_title(prop, tax_info)
    
    # Calculate real LTV
    prop_val = prop.get("total_assessed") or assessed or 1
    ltv = (tax_lien / prop_val) * 100.0 if prop_val > 0 else 999.0
    
    entry = {
        "list_no": list_no,
        "account_no": acct,
        "address": prop.get("address") or item.get("address"),
        "city": prop.get("city") or item.get("city"),
        "zipcode": prop.get("zip") or item.get("zipcode"),
        "owner": prop.get("owner") or item.get("owner"),
        "land_value": prop.get("land_val") or item.get("land_value") or 0,
        "structure_value": prop.get("structure_val") or item.get("improvement_value") or 0,
        "total_assessed": prop_val,
        "tax_lien_amount": tax_lien,
        "ltv_pct": round(ltv, 2),
        "zoning": prop.get("zoning") or item.get("zoning"),
        "land_area": prop.get("land_area") or f"{item.get('acres', 0)} Acres",
        "title_score": title_res["score"],
        "grade": title_res["grade"],
        "grade_desc": title_res["grade_desc"],
        "badge": title_res["badge"],
        "entity_type": title_res["entity_type"],
        "current_deed": title_res["current_deed"],
        "prior_deed": title_res["prior_deed"],
        "plat": title_res["plat"],
        "positive_factors": title_res["positive_factors"],
        "risk_factors": title_res["risk_factors"],
        "recommended_contingencies": title_res["recommended_contingencies"],
        "google_maps_url": item.get("google_maps_url") or f"https://www.google.com/maps/search/?api=1&query={prop.get('address', '')}+{prop.get('city', '')}+MD",
        "sdat_url": prop.get("sdat_web_url") or item.get("sdat_url") or "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
    }
    return entry

print("Querying SDAT & analyzing title integrity across candidate properties...")
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {executor.submit(process_item, item): item for item in records}
    count = 0
    for future in as_completed(futures):
        count += 1
        res = future.result()
        if res:
            results.append(res)
        if count % 20 == 0:
            print(f"Processed {count}/{len(records)} parcels...")

grade_a = [r for r in results if r["grade"] == "A"]
grade_b = [r for r in results if r["grade"] == "B"]
grade_c = [r for r in results if r["grade"] == "C"]
grade_d = [r for r in results if r["grade"] == "D"]
grade_f = [r for r in results if r["grade"] == "F"]

# Sort by LTV ascending and Assessed Value descending
grade_a.sort(key=lambda x: (x["ltv_pct"], -x["total_assessed"]))
grade_b.sort(key=lambda x: (x["ltv_pct"], -x["total_assessed"]))

out_data = {
    "summary": {
        "total_analyzed": len(results),
        "grade_a_count": len(grade_a),
        "grade_b_count": len(grade_b),
        "grade_c_count": len(grade_c),
        "grade_d_count": len(grade_d),
        "grade_f_count": len(grade_f),
    },
    "grade_a": grade_a,
    "grade_b": grade_b,
    "grade_c": grade_c,
    "grade_d": grade_d,
    "grade_f": grade_f
}

out_path = r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\otc_graded_deals.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out_data, f, indent=2)

print("\n=== TITLE SCREENING AUDIT COMPLETE ===")
print(f"Total Parcels Analyzed: {len(results)}")
print(f"Grade A (Score >= 90): {len(grade_a)}")
print(f"Grade B (Score 75-89): {len(grade_b)}")
print(f"Grade C (Score 60-74): {len(grade_c)}")
print(f"Grade D (Score 40-59): {len(grade_d)}")
print(f"Grade F (Score < 40):  {len(grade_f)}")

print("\n--- GRADE A DEALS (PRISTINE TITLE & CHAIN) ---")
for p in grade_a:
    print(f"List #{p['list_no']} | Acct: {p['account_no']} | {p['address']}, {p['city']} | Assessed: ${p['total_assessed']:,.0f} | Lien: ${p['tax_lien_amount']:,.2f} | LTV: {p['ltv_pct']:.2f}% | Score: {p['title_score']} (Grade {p['grade']}) | Deed: L.{p['current_deed']['liber']}/F.{p['current_deed']['folio']} | Plat: {p['plat']['subdivision']}")

print("\n--- GRADE B DEALS (STRONG / LOW-RISK TITLE) ---")
for p in grade_b:
    print(f"List #{p['list_no']} | Acct: {p['account_no']} | {p['address']}, {p['city']} | Assessed: ${p['total_assessed']:,.0f} | Lien: ${p['tax_lien_amount']:,.2f} | LTV: {p['ltv_pct']:.2f}% | Score: {p['title_score']} (Grade {p['grade']}) | Deed: L.{p['current_deed']['liber']}/F.{p['current_deed']['folio']} | Plat: {p['plat']['subdivision']}")
