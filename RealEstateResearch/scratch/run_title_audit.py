import json
import sys
import os

sys.path.insert(0, r"c:\Obsedian\RealEstateResearch\RealEstateResearch")

from concurrent.futures import ThreadPoolExecutor
from sdat_engine import search_maryland_property
from title_search_engine import analyze_maryland_title


with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json", "r", encoding="utf-8") as f:
    aa_records = json.load(f)

# Filter candidate records with Assessed >= $20k and LTV <= 5.0%
candidates = [r for r in aa_records if r.get("assessment", 0) >= 20000 and r.get("ltv_pct", 100) <= 5.0]
print(f"Total High-Equity Candidates to Audit with Title Search Engine: {len(candidates)}")

def process_candidate(rec):
    acct = rec.get("account_no")
    props = search_maryland_property(acct, county="ANNE ARUNDEL")
    if props:
        prop = props[0]
        tax_info = {
            "owner_of_record": rec.get("owner"),
            "tax_sale_flag": False,
            "total_lien_due": rec.get("total_due"),
            "ltv_pct": rec.get("ltv_pct"),
            "list_no": rec.get("list_no"),
            "county": "Anne Arundel County"
        }
        title_res = analyze_maryland_title(prop, tax_info)
        return {
            "list_no": rec.get("list_no"),
            "account_no": acct,
            "address": prop.get("address") or rec.get("address"),
            "city": prop.get("city") or rec.get("city"),
            "owner": rec.get("owner"),
            "assessment": rec.get("assessment", 0),
            "total_due": rec.get("total_due", 0),
            "ltv_pct": rec.get("ltv_pct", 100),
            "acres": prop.get("dimensions", {}).get("acres") or rec.get("acres"),
            "zoning": prop.get("zoning", {}).get("code") or rec.get("zoning"),
            "land_use": prop.get("zoning", {}).get("land_use_desc") or rec.get("land_use"),
            "score": title_res["score"],
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
            "links": title_res["links"],
            "gmaps_url": prop.get("google_maps_url") or rec.get("google_maps_url")
        }
    return None

with ThreadPoolExecutor(max_workers=8) as ex:
    audited = list(ex.map(process_candidate, candidates))

audited = [r for r in audited if r is not None]

grade_a = [r for r in audited if r["grade"] == "A"]
grade_b = [r for r in audited if r["grade"] == "B"]
other = [r for r in audited if r["grade"] not in ["A", "B"]]

print(f"\nAudit Completed: {len(audited)} properties audited.")
print(f"  🟢 Grade A (Score >= 90): {len(grade_a)}")
print(f"  🟢 Grade B (Score 75-89): {len(grade_b)}")
print(f"  🟡/🟠 Grade C/D/F: {len(other)}")

grade_a.sort(key=lambda x: x["ltv_pct"])
grade_b.sort(key=lambda x: x["ltv_pct"])

# Save detailed output for report generation
with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\title_audit_results.json", "w", encoding="utf-8") as f:
    json.dump({"grade_a": grade_a, "grade_b": grade_b, "other": other}, f, indent=2)

print("\nSaved audited title results to scratch/title_audit_results.json")
