import json
from title_search_engine import analyze_maryland_title

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json", "r", encoding="utf-8") as f:
    aa_records = json.load(f)

print(f"Loaded {len(aa_records)} Anne Arundel records.")

results = []
for rec in aa_records:
    if not rec.get("matched"):
        continue
        
    # Reconstruct prop dict compatible with analyze_maryland_title
    prop = {
        "jurisdiction": "ANNE",
        "account_id": rec.get("account_no"),
        "address": rec.get("address"),
        "city": rec.get("city"),
        "zipcode": rec.get("zipcode"),
        "owner": rec.get("owner"),
        "owner_mailing": rec.get("owner_mailing", {}),
        "dimensions": {
            "acres": rec.get("acres"),
            "sqft": rec.get("sqft")
        },
        "zoning": {
            "code": rec.get("zoning"),
            "land_use_desc": rec.get("land_use")
        },
        "valuation": {
            "total_value": rec.get("assessment") or rec.get("sdat_total_value"),
            "land_value": rec.get("land_value"),
            "improvement_value": rec.get("improvement_value")
        },
        "transfer_history": {
            "transfer_date": rec.get("last_sale_date"),
            "consideration_price": rec.get("last_sale_price"),
            "deed_liber": rec.get("map"), # let's check exact keys
            "deed_folio": rec.get("parcel")
        },
        "legal": {
            "subdivision": rec.get("subdivision"),
            "lot": rec.get("legal_desc", "").split()[1] if "LT" in str(rec.get("legal_desc", "")) else "N/A",
            "section": "N/A",
            "block": "N/A",
            "map": rec.get("map"),
            "grid": rec.get("grid"),
            "parcel": rec.get("parcel"),
            "legal1": rec.get("legal_desc", "")
        },
        "sdat_web_url": rec.get("sdat_url"),
        "google_maps_url": rec.get("google_maps_url")
    }
    
    # Note: in tax sale context, we pass tax_sale_flag = True if active delinquent lien
    tax_info = {
        "owner_of_record": rec.get("sdat_owner") or rec.get("owner"),
        "tax_sale_flag": False, # for OTC buyers, we evaluate underlying property title quality
        "total_lien_due": rec.get("total_due"),
        "ltv_pct": rec.get("ltv_pct"),
        "list_no": rec.get("list_no"),
        "county": "Anne Arundel County"
    }
    
    title_res = analyze_maryland_title(prop, tax_info)
    
    results.append({
        "list_no": rec.get("list_no"),
        "account_no": rec.get("account_no"),
        "address": rec.get("address"),
        "city": rec.get("city"),
        "owner": rec.get("owner"),
        "assessment": rec.get("assessment", 0),
        "total_due": rec.get("total_due", 0),
        "ltv_pct": rec.get("ltv_pct", 100),
        "acres": rec.get("acres"),
        "zoning": rec.get("zoning"),
        "score": title_res["score"],
        "grade": title_res["grade"],
        "grade_desc": title_res["grade_desc"],
        "badge": title_res["badge"],
        "title_res": title_res,
        "gmaps_url": rec.get("google_maps_url")
    })

print(f"Analyzed {len(results)} records.")

grade_a = [r for r in results if r["grade"] == "A" and r["assessment"] >= 15000 and r["ltv_pct"] <= 10.0]
grade_b = [r for r in results if r["grade"] == "B" and r["assessment"] >= 15000 and r["ltv_pct"] <= 10.0]

print(f"Grade A Deals (Score >= 90): {len(grade_a)}")
print(f"Grade B Deals (Score 75-89): {len(grade_b)}")

grade_a.sort(key=lambda x: x["ltv_pct"])
grade_b.sort(key=lambda x: x["ltv_pct"])

print("\n" + "="*80)
print("=== TOP GRADE A OTC TAX LIEN DEALS ===")
for r in grade_a:
    print(f"List #{r['list_no']:<4} | Score: {r['badge']} {r['score']}/100 (Grade {r['grade']}) | {r['address']}, {r['city']} | Assessed: ${r['assessment']:>9,.2f} | Lien: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']:>5.2f}% | Acres: {r['acres']} | Zoning: {r['zoning']} | Maps: {r['gmaps_url']}")

print("\n" + "="*80)
print("=== TOP GRADE B OTC TAX LIEN DEALS ===")
for r in grade_b:
    print(f"List #{r['list_no']:<4} | Score: {r['badge']} {r['score']}/100 (Grade {r['grade']}) | {r['address']}, {r['city']} | Assessed: ${r['assessment']:>9,.2f} | Lien: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']:>5.2f}% | Acres: {r['acres']} | Zoning: {r['zoning']} | Maps: {r['gmaps_url']}")
