import sys, json, os

sys.path.insert(0, r"c:\Obsedian\RealEstateResearch\RealEstateResearch")
from title_search_engine import analyze_maryland_title

master_path = r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json"

with open(master_path, "r", encoding="utf-8") as f:
    master = json.load(f)

grade_a = []
grade_b = []
grade_other = []

for item in master:
    prop = item.get("sdat_property") or {}
    tax_info = item.get("tax_info") or {}
    if not prop:
        continue
    analysis = analyze_maryland_title(prop, tax_info)
    entry = {
        "list_no": item.get("list_no"),
        "acct": item.get("acct"),
        "address": prop.get("address") or item.get("address"),
        "city": prop.get("city"),
        "zip": prop.get("zip"),
        "owner": prop.get("owner"),
        "total_assessed": prop.get("total_assessed") or 0,
        "land_val": prop.get("land_val") or 0,
        "structure_val": prop.get("structure_val") or 0,
        "tax_lien_amount": item.get("tax_lien_amount") or 0,
        "ltv_pct": item.get("ltv_pct") or 0,
        "zoning": prop.get("zoning"),
        "land_area": prop.get("land_area"),
        "score": analysis["title_score"],
        "grade": analysis["grade"],
        "liber_folio": analysis["current_deed"]["liber_folio"],
        "prior_deed": analysis["chain_of_title"]["prior_deed_ref"],
        "transfer_date": analysis["current_deed"]["transfer_date"],
        "consideration": analysis["current_deed"]["consideration"],
        "plat_ref": analysis["plat_subdivision"]["plat_ref"],
        "subdivision": analysis["plat_subdivision"]["subdivision_name"],
        "lot": analysis["plat_subdivision"]["lot"],
        "block": analysis["plat_subdivision"]["block"],
        "strengths": analysis["strengths"],
        "risks": analysis["red_flags"]
    }
    if analysis["grade"] == "Grade A":
        grade_a.append(entry)
    elif analysis["grade"] == "Grade B":
        grade_b.append(entry)
    else:
        grade_other.append(entry)

print(f"Total Analyzed: {len(grade_a) + len(grade_b) + len(grade_other)}")
print(f"Grade A: {len(grade_a)}")
print(f"Grade B: {len(grade_b)}")
print(f"Other: {len(grade_other)}")

# Save categorized results to a json file for easy inspection
output = {
    "grade_a": sorted(grade_a, key=lambda x: (x["total_assessed"]), reverse=True),
    "grade_b": sorted(grade_b, key=lambda x: (x["total_assessed"]), reverse=True),
    "grade_other": sorted(grade_other, key=lambda x: (x["total_assessed"]), reverse=True)
}

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\otc_title_grades.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

print("\n--- TOP GRADE A PROPERTIES (ASSESSED > $50K) ---")
for p in output["grade_a"]:
    if p["total_assessed"] >= 50000 or p["ltv_pct"] <= 5.0:
        print(f"List #{p['list_no']} | Acct: {p['acct']} | {p['address']}, {p['city']} | Assessed: ${p['total_assessed']:,.0f} | Lien: ${p['tax_lien_amount']:,.2f} | LTV: {p['ltv_pct']:.2f}% | Score: {p['score']} | Deed: {p['liber_folio']} | Plat: {p['plat_ref']}")

print("\n--- TOP GRADE B PROPERTIES (ASSESSED > $50K) ---")
for p in output["grade_b"]:
    if p["total_assessed"] >= 50000 or p["ltv_pct"] <= 5.0:
        print(f"List #{p['list_no']} | Acct: {p['acct']} | {p['address']}, {p['city']} | Assessed: ${p['total_assessed']:,.0f} | Lien: ${p['tax_lien_amount']:,.2f} | LTV: {p['ltv_pct']:.2f}% | Score: {p['score']} | Deed: {p['liber_folio']} | Plat: {p['plat_ref']}")
