import sys, os, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set stdout UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, r"c:\Obsedian\RealEstateResearch\RealEstateResearch")
from sdat_engine import search_maryland_property
from title_search_engine import analyze_maryland_title

master_path = r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json"

with open(master_path, "r", encoding="utf-8") as f:
    items = json.load(f)

# Focus on strong investment candidates: Assessed >= $30k and LTV <= 10%
candidates = [it for it in items if (it.get("assessment") or 0) >= 25000 and (it.get("ltv_pct") or 100) <= 12.0]
# Sort by assessment value & LTV
candidates.sort(key=lambda x: (x.get("ltv_pct") or 100, -(x.get("assessment") or 0)))

print(f"Screening {len(candidates)} high-potential OTC investment candidates...")

graded_results = []

for idx, it in enumerate(candidates):
    acct = str(it.get("account_no") or "").strip()
    list_no = it.get("list_no")
    tax_lien = it.get("total_due") or it.get("bid_amount") or 0.0
    assessed = it.get("assessment") or it.get("sdat_total_value") or 0.0
    
    # Query SDAT
    props = search_maryland_property(acct, county="ANNE ARUNDEL")
    if not props:
        addr = it.get("address")
        if addr:
            props = search_maryland_property(addr, county="ANNE ARUNDEL")
            
    if not props:
        print(f"[{idx+1}/{len(candidates)}] Could not fetch SDAT for Acct {acct} ({it.get('address')})")
        continue
        
    prop = props[0]
    tax_info = {
        "tax_lien_amount": tax_lien,
        "assessed_value": assessed,
        "owner_of_record": it.get("owner"),
        "tax_sale_flag": True
    }
    
    title_res = analyze_maryland_title(prop, tax_info)
    prop_val = prop.get("total_assessed") or assessed or 1
    ltv = (tax_lien / prop_val) * 100.0 if prop_val > 0 else 999.0
    
    entry = {
        "list_no": list_no,
        "account_no": acct,
        "address": prop.get("address") or it.get("address"),
        "city": prop.get("city") or it.get("city"),
        "zipcode": prop.get("zip") or it.get("zipcode"),
        "owner": prop.get("owner") or it.get("owner"),
        "land_value": prop.get("land_val") or it.get("land_value") or 0,
        "structure_value": prop.get("structure_val") or it.get("improvement_value") or 0,
        "total_assessed": prop_val,
        "tax_lien_amount": tax_lien,
        "ltv_pct": round(ltv, 2),
        "zoning": prop.get("zoning") or it.get("zoning"),
        "land_area": prop.get("land_area") or f"{it.get('acres', 0)} Acres",
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
        "google_maps_url": it.get("google_maps_url") or f"https://www.google.com/maps/search/?api=1&query={prop.get('address', '')}+{prop.get('city', '')}+MD",
        "sdat_url": prop.get("sdat_web_url") or it.get("sdat_url") or "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
    }
    
    graded_results.append(entry)
    print(f"[{idx+1}/{len(candidates)}] List #{list_no} | {entry['address']}, {entry['city']} | Assessed: ${prop_val:,.0f} | Lien: ${tax_lien:,.2f} (LTV {ltv:.2f}%) | {title_res['badge']} Grade {title_res['grade']} (Score: {title_res['score']})")

grade_a = [r for r in graded_results if r["grade"] == "A"]
grade_b = [r for r in graded_results if r["grade"] == "B"]
grade_c = [r for r in graded_results if r["grade"] == "C"]
grade_d = [r for r in graded_results if r["grade"] == "D"]
grade_f = [r for r in graded_results if r["grade"] == "F"]

out_data = {
    "total_screened": len(graded_results),
    "grade_a": grade_a,
    "grade_b": grade_b,
    "grade_c": grade_c,
    "grade_d": grade_d,
    "grade_f": grade_f
}

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\otc_graded_deals.json", "w", encoding="utf-8") as f:
    json.dump(out_data, f, indent=2)

print("\nScreening complete. Saved to scratch/otc_graded_deals.json")
