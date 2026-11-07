import json
import requests
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, r"c:\Obsedian\RealEstateResearch\RealEstateResearch")

from title_search_engine import analyze_maryland_title

MD_PROPERTY_DATA_URL = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query"

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json", "r", encoding="utf-8") as f:
    aa_records = json.load(f)

# Candidate filter: Assessed >= $20k and LTV <= 5.0%
candidates = [r for r in aa_records if r.get("assessment", 0) >= 20000 and r.get("ltv_pct", 100) <= 5.0 and r.get("matched")]
print(f"Auditing {len(candidates)} high-equity OTC candidates with Title Search Engine...")

def get_acctid_variants(acct):
    acct = str(acct).strip()
    digits = "".join(c for c in acct if c.isdigit())
    variants = []
    if len(digits) == 12:
        dist = digits[0].zfill(2)
        rest = digits[1:]
        variants.append(f"02{dist}{rest}")
    if len(digits) == 11:
        dist = digits[0].zfill(2)
        rest = digits[1:]
        variants.append(f"02{dist}{rest}")
    variants.append(f"02{digits}")
    return variants

def audit_single(rec):
    acct = rec["account_no"]
    variants = get_acctid_variants(acct)
    where_parts = [f"ACCTID = '{v}'" for v in variants]
    where_expr = f"({' OR '.join(where_parts)}) AND (JURSCODE = 'ANNE')"
    
    params = {
        "where": where_expr,
        "outFields": "ACCTID,JURSCODE,ADDRESS,CITY,ZIPCODE,OWNNAME1,OWNNAME2,OWNADD1,OWNADD2,OWNCITY,OWNSTATE,OWNERZIP,LEGAL1,LEGAL2,LEGAL3,DESCSUBD,SUBDIVSN,LOT,SECTION,BLOCK,MAP,GRID,PARCEL,ZONING,LU,DESCLU,ACRES,LANDAREA,NFMLNDVL,NFMIMPVL,NFMTTLVL,TRADATE,CONSIDR1,DR1LIBER,DR1FOLIO,GR1LIBR1,GR1FOLO1,YEARBLT,SQFTSTRC,DESCSTYL,SDATWEBADR,OOI",
        "f": "json",
        "returnGeometry": "false"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for attempt in range(3):
        try:
            r = requests.get(MD_PROPERTY_DATA_URL, params=params, headers=headers, timeout=12)
            if r.status_code == 200:
                feats = r.json().get("features", [])
                if feats:
                    attrs = feats[0].get("attributes", {})
                    
                    owner_state = (attrs.get("OWNSTATE") or "").strip().upper()
                    is_absentee = (owner_state != "MD" and bool(owner_state)) or attrs.get("OOI") == "N"
                    
                    acres = attrs.get("ACRES") or attrs.get("LANDAREA")
                    sqft = round(float(acres) * 43560, 1) if acres else None
                    
                    owner_full = f"{attrs.get('OWNNAME1', '')} {attrs.get('OWNNAME2', '')}".strip() or rec.get("owner")
                    
                    prop = {
                        "jurisdiction": "ANNE",
                        "account_id": attrs.get("ACCTID"),
                        "address": attrs.get("ADDRESS") or rec.get("address"),
                        "city": attrs.get("CITY") or rec.get("city"),
                        "zipcode": attrs.get("ZIPCODE") or rec.get("zipcode"),
                        "owner": owner_full,
                        "owner_mailing": {
                            "line1": attrs.get("OWNADD1"),
                            "city": attrs.get("OWNCITY"),
                            "state": attrs.get("OWNSTATE"),
                            "zip": attrs.get("OWNERZIP"),
                            "is_absentee": is_absentee
                        },
                        "dimensions": {
                            "acres": float(acres) if acres is not None else rec.get("acres"),
                            "sqft": sqft
                        },
                        "zoning": {
                            "code": attrs.get("ZONING") or rec.get("zoning"),
                            "land_use_desc": attrs.get("DESCLU") or rec.get("land_use")
                        },
                        "valuation": {
                            "total_value": attrs.get("NFMTTLVL") or rec.get("assessment"),
                            "land_value": attrs.get("NFMLNDVL") or rec.get("land_value"),
                            "improvement_value": attrs.get("NFMIMPVL") or rec.get("improvement_value")
                        },
                        "transfer_history": {
                            "transfer_date": str(attrs.get("TRADATE", "")),
                            "consideration_price": attrs.get("CONSIDR1"),
                            "deed_liber": attrs.get("DR1LIBER"),
                            "deed_folio": attrs.get("DR1FOLIO"),
                            "prior_liber": attrs.get("GR1LIBR1"),
                            "prior_folio": attrs.get("GR1FOLO1")
                        },
                        "legal": {
                            "subdivision": attrs.get("DESCSUBD") or attrs.get("SUBDIVSN"),
                            "lot": attrs.get("LOT"),
                            "section": attrs.get("SECTION"),
                            "block": attrs.get("BLOCK"),
                            "map": attrs.get("MAP"),
                            "grid": attrs.get("GRID"),
                            "parcel": attrs.get("PARCEL"),
                            "legal1": attrs.get("LEGAL1"),
                            "legal2": attrs.get("LEGAL2"),
                            "legal3": attrs.get("LEGAL3")
                        },
                        "structure": {
                            "year_built": attrs.get("YEARBLT"),
                            "structure_sqft": attrs.get("SQFTSTRC"),
                            "style": attrs.get("DESCSTYL")
                        },
                        "sdat_web_url": attrs.get("SDATWEBADR") or rec.get("sdat_url"),
                        "google_maps_url": rec.get("google_maps_url")
                    }
                    
                    tax_info = {
                        "owner_of_record": owner_full,
                        "tax_sale_flag": False,
                        "total_lien_due": rec.get("total_due"),
                        "ltv_pct": rec.get("ltv_pct"),
                        "list_no": rec.get("list_no"),
                        "county": "Anne Arundel County"
                    }
                    
                    title_res = analyze_maryland_title(prop, tax_info)
                    
                    return {
                        "list_no": rec.get("list_no"),
                        "account_no": rec.get("account_no"),
                        "sdat_acct": attrs.get("ACCTID"),
                        "address": prop.get("address"),
                        "city": prop.get("city"),
                        "owner": owner_full,
                        "assessment": rec.get("assessment", 0),
                        "total_due": rec.get("total_due", 0),
                        "ltv_pct": rec.get("ltv_pct", 100),
                        "acres": prop["dimensions"]["acres"],
                        "zoning": prop["zoning"]["code"],
                        "land_use": prop["zoning"]["land_use_desc"],
                        "year_built": prop["structure"]["year_built"],
                        "structure_sqft": prop["structure"]["structure_sqft"],
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
                        "gmaps_url": rec.get("google_maps_url")
                    }
        except Exception as e:
            time.sleep(1)
            
    return None

with ThreadPoolExecutor(max_workers=4) as ex:
    audited = list(ex.map(audit_single, candidates))

audited = [r for r in audited if r is not None]

grade_a = [r for r in audited if r["grade"] == "A"]
grade_b = [r for r in audited if r["grade"] == "B"]
other = [r for r in audited if r["grade"] not in ["A", "B"]]

print(f"\n=======================================================")
print(f"TOTAL AUDITED: {len(audited)}")
print(f"  Grade A (Score >= 90): {len(grade_a)}")
print(f"  Grade B (Score 75-89): {len(grade_b)}")
print(f"  Grade C/D/F: {len(other)}")
print(f"=======================================================")

grade_a.sort(key=lambda x: x["ltv_pct"])
grade_b.sort(key=lambda x: x["ltv_pct"])

print("\n--- GRADE A DEALS (Score >= 90) ---")
for r in grade_a:
    c = r["current_deed"]
    p = r["prior_deed"]
    print(f"List #{r['list_no']:<4} | {r['badge']} Score {r['score']}/100 | {r['address']}, {r['city']} | Owner: {r['owner'][:25]:<25} | Assessed: ${r['assessment']:>9,.2f} | Lien: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']:>5.2f}% | Liber {c['liber']}/Folio {c['folio']} | Paid: {c['consideration_str']} ({c['transfer_date']}) | Zoning: {r['zoning']}")

print("\n--- GRADE B DEALS (Score 75-89) ---")
for r in grade_b:
    c = r["current_deed"]
    p = r["prior_deed"]
    print(f"List #{r['list_no']:<4} | {r['badge']} Score {r['score']}/100 | {r['address']}, {r['city']} | Owner: {r['owner'][:25]:<25} | Assessed: ${r['assessment']:>9,.2f} | Lien: ${r['total_due']:>8,.2f} | LTV: {r['ltv_pct']:>5.2f}% | Liber {c['liber']}/Folio {c['folio']} | Paid: {c['consideration_str']} ({c['transfer_date']}) | Zoning: {r['zoning']}")

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\fast_title_audit_results.json", "w", encoding="utf-8") as f:
    json.dump({"grade_a": grade_a, "grade_b": grade_b, "other": other}, f, indent=2)

print("\nSaved full audit results to scratch/fast_title_audit_results.json")
