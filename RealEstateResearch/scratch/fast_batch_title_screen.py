import sys, os, json, time, requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, r"c:\Obsedian\RealEstateResearch\RealEstateResearch")
from title_search_engine import analyze_maryland_title

master_path = r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json"

with open(master_path, "r", encoding="utf-8") as f:
    records = json.load(f)

print(f"Loaded {len(records)} candidate parcels from master list.")

# Map raw account numbers
acct_to_record = {}
acct_15_list = []

for r in records:
    raw_acct = str(r.get("account_no") or "").strip()
    if not raw_acct:
        continue
    if len(raw_acct) == 12:
        dist = int(raw_acct[0])
        acct_15 = f"02{dist:02d}{raw_acct[1:]}"
    elif len(raw_acct) == 15:
        acct_15 = raw_acct
    else:
        dist = int(raw_acct[0]) if raw_acct[0].isdigit() else 1
        acct_15 = f"02{dist:02d}{raw_acct[1:].zfill(12)}"
    
    acct_to_record[acct_15] = r
    acct_15_list.append(acct_15)

# Batch query in chunks of 40
CHUNK_SIZE = 40
all_features = []
url = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query"

for i in range(0, len(acct_15_list), CHUNK_SIZE):
    chunk = acct_15_list[i:i+CHUNK_SIZE]
    in_clause = ", ".join([f"'{a}'" for a in chunk])
    where_expr = f"ACCTID IN ({in_clause}) AND JURSCODE = 'ANNE'"
    params = {
        "where": where_expr,
        "outFields": "*",
        "f": "json",
        "returnGeometry": "false"
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        t0 = time.time()
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 200:
            feats = resp.json().get("features", [])
            all_features.extend(feats)
            print(f"Chunk {i//CHUNK_SIZE + 1}: fetched {len(feats)} features in {time.time()-t0:.2f}s")
    except Exception as e:
        print(f"Error fetching chunk {i//CHUNK_SIZE + 1}: {e}")

print(f"\nTotal SDAT cadastral features retrieved: {len(all_features)}")

results = []

def format_date(d_str):
    if not d_str:
        return "N/A"
    s = str(d_str).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s

for feat in all_features:
    attrs = feat.get("attributes", {})
    acct_id = attrs.get("ACCTID", "")
    item = acct_to_record.get(acct_id)
    if not item:
        for k, v in acct_to_record.items():
            if k.endswith(acct_id[4:]) or acct_id.endswith(k[4:]):
                item = v
                break
    if not item:
        item = {}

    list_no = item.get("list_no")
    tax_lien = float(item.get("total_due") or item.get("bid_amount") or 0.0)
    
    premise_state = "MD"
    owner_state = (attrs.get("OWNSTATE") or "").strip().upper()
    premise_zip = (attrs.get("PREMZIP") or attrs.get("ZIPCODE") or "").strip()
    owner_zip = (attrs.get("OWNERZIP") or "").strip()
    
    is_absentee = False
    if owner_state and owner_state != premise_state:
        is_absentee = True
    elif owner_zip and premise_zip and owner_zip[:5] != premise_zip[:5]:
        is_absentee = True
    elif attrs.get("OOI") == "N":
        is_absentee = True
        
    acres = attrs.get("ACRES") or attrs.get("LANDAREA")
    sqft = round(float(acres) * 43560, 1) if acres else None
    
    tot_assmt = float(attrs.get("NFMTTLVL") or attrs.get("TOTASSMT") or attrs.get("CURRASSM") or item.get("assessment") or 0)
    land_val = float(attrs.get("NFMLNDVL") or attrs.get("LANDVAL") or item.get("land_value") or 0)
    imp_val = float(attrs.get("NFMIMPVL") or attrs.get("IMPRVAL") or item.get("improvement_value") or 0)

    # Standard SDAT schema matching sdat_engine.py
    prop = {
        "object_id": attrs.get("OBJECTID"),
        "jurisdiction": attrs.get("JURSCODE") or "ANNE",
        "account_id": acct_id,
        "address": attrs.get("ADDRESS") or f"{attrs.get('STRTNUM', '')} {attrs.get('STRTNAM', '')} {attrs.get('STRTTYP', '')}".strip(),
        "city": attrs.get("CITY") or attrs.get("PREMCITY"),
        "zipcode": attrs.get("ZIPCODE") or attrs.get("PREMZIP"),
        "owner_mailing": {
            "line1": attrs.get("OWNADD1") or attrs.get("OWNNAME1"),
            "line2": attrs.get("OWNADD2"),
            "city": attrs.get("OWNCITY"),
            "state": attrs.get("OWNSTATE"),
            "zip": attrs.get("OWNERZIP"),
            "is_absentee": is_absentee
        },
        "legal": {
            "legal1": attrs.get("LEGAL1"),
            "legal2": attrs.get("LEGAL2"),
            "legal3": attrs.get("LEGAL3"),
            "subdivision": attrs.get("DESCSUBD") or attrs.get("SUBDIVSN"),
            "lot": attrs.get("LOT"),
            "section": attrs.get("SECTION"),
            "block": attrs.get("BLOCK"),
            "map": attrs.get("MAP"),
            "grid": attrs.get("GRID"),
            "parcel": attrs.get("PARCEL")
        },
        "zoning": {
            "code": attrs.get("ZONING"),
            "land_use": attrs.get("LU"),
            "land_use_desc": attrs.get("DESCLU"),
            "commercial_use": attrs.get("DESCCIUSE")
        },
        "dimensions": {
            "acres": float(acres) if acres is not None else None,
            "sqft": sqft,
            "width": attrs.get("WIDTH"),
            "depth": attrs.get("DEPTH")
        },
        "valuation": {
            "land_value": land_val,
            "improvement_value": imp_val,
            "total_value": tot_assmt,
            "last_assessed_date": attrs.get("LASTASSD")
        },
        "transfer_history": {
            "transfer_date": format_date(attrs.get("TRADATE")),
            "consideration_price": float(attrs.get("CONSIDR1", 0) or 0) if attrs.get("CONSIDR1") is not None else None,
            "deed_liber": str(attrs.get("DR1LIBER", "")).strip(),
            "deed_folio": str(attrs.get("DR1FOLIO", "")).strip(),
            "prior_liber": str(attrs.get("GR1LIBR1", "")).strip(),
            "prior_folio": str(attrs.get("GR1FOLO1", "")).strip()
        },
        "structure": {
            "year_built": attrs.get("YEARBLT"),
            "living_area_sqft": attrs.get("BLD_AREA") or attrs.get("STRUSQFT"),
            "style": attrs.get("STRUTYPE") or attrs.get("STYLE")
        },
        "sdat_web_url": f"https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx",
        "raw_data": attrs
    }
    
    # Title analysis for tax lien pre-acquisition
    # Note: tax_sale_flag=False to evaluate the underlying title/deed integrity (since we are buying the lien itself)
    tax_info = {
        "tax_lien_amount": tax_lien,
        "assessed_value": tot_assmt,
        "owner_of_record": prop["owner_mailing"]["line1"],
        "tax_sale_flag": False
    }
    
    title_res = analyze_maryland_title(prop, tax_info)
    ltv = (tax_lien / tot_assmt) * 100.0 if tot_assmt > 0 else 999.0
    
    entry = {
        "list_no": list_no,
        "account_no": item.get("account_no") or acct_id,
        "acct_id_imap": acct_id,
        "address": prop.get("address") or item.get("address"),
        "city": prop.get("city") or item.get("city"),
        "zipcode": prop.get("zipcode") or item.get("zipcode"),
        "owner": prop["owner_mailing"]["line1"] or item.get("owner"),
        "land_value": land_val,
        "structure_value": imp_val,
        "total_assessed": tot_assmt,
        "tax_lien_amount": tax_lien,
        "ltv_pct": round(ltv, 2),
        "zoning": prop["zoning"]["code"] or item.get("zoning"),
        "land_area": f"{acres} Acres" if acres else f"{sqft} Sq Ft",
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
    results.append(entry)

grade_a = [r for r in results if r["grade"] == "A"]
grade_b = [r for r in results if r["grade"] == "B"]
grade_c = [r for r in results if r["grade"] == "C"]
grade_d = [r for r in results if r["grade"] == "D"]
grade_f = [r for r in results if r["grade"] == "F"]

# Sort Grade A & B by Assessed Value descending and LTV ascending
grade_a.sort(key=lambda x: (-x["total_assessed"], x["ltv_pct"]))
grade_b.sort(key=lambda x: (-x["total_assessed"], x["ltv_pct"]))

out_data = {
    "summary": {
        "total_screened": len(results),
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

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\otc_graded_deals.json", "w", encoding="utf-8") as f:
    json.dump(out_data, f, indent=2)

print("\n=== OTC TITLE CONFLUENCE SCREENING COMPLETE ===")
print(f"Total Parcels Analyzed: {len(results)}")
print(f"Grade A (Score >= 90): {len(grade_a)}")
print(f"Grade B (Score 75-89): {len(grade_b)}")
print(f"Grade C (Score 60-74): {len(grade_c)}")
print(f"Grade D (Score 40-59): {len(grade_d)}")
print(f"Grade F (Score < 40):  {len(grade_f)}")

print("\n--- TOP GRADE A DEALS (SCORE >= 90) ---")
for p in grade_a[:15]:
    print(f"List #{p['list_no']} | Acct: {p['account_no']} | {p['address']}, {p['city']} | Assessed: ${p['total_assessed']:,.0f} | Lien: ${p['tax_lien_amount']:,.2f} | LTV: {p['ltv_pct']:.2f}% | Score: {p['title_score']} (Grade {p['grade']}) | Deed: L.{p['current_deed']['liber']}/F.{p['current_deed']['folio']} | Plat: {p['plat']['subdivision']}")

print("\n--- TOP GRADE B DEALS (SCORE 75-89) ---")
for p in grade_b[:15]:
    print(f"List #{p['list_no']} | Acct: {p['account_no']} | {p['address']}, {p['city']} | Assessed: ${p['total_assessed']:,.0f} | Lien: ${p['tax_lien_amount']:,.2f} | LTV: {p['ltv_pct']:.2f}% | Score: {p['title_score']} (Grade {p['grade']}) | Deed: L.{p['current_deed']['liber']}/F.{p['current_deed']['folio']} | Plat: {p['plat']['subdivision']}")
