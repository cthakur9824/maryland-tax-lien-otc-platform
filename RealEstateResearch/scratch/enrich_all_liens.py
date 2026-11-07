import json
import time
import requests
import re
from concurrent.futures import ThreadPoolExecutor

MD_PROPERTY_DATA_URL = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query"

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_parsed_liens.json", "r") as f:
    records = json.load(f)

print(f"Enriching {len(records)} parcels with official MD iMAP SDAT data...")

def enrich_single_record(rec):
    acct = rec["account_no"]
    # Anne Arundel County ACCTID in MD iMAP format: 02 + 12-digit account number (e.g. 02100000756300)
    # Or district (first 1-2 digits) + remaining
    # Let's search with wildcard on ACCTID
    params = {
        "where": f"ACCTID LIKE '%{acct}%' OR ACCTID = '02{acct}'",
        "outFields": "OBJECTID,JURSCODE,ACCTID,ADDRESS,CITY,ZIPCODE,OWNADD1,OWNADD2,OWNCITY,OWNSTATE,OWNERZIP,LEGAL1,LEGAL2,LEGAL3,DESCSUBD,ZONING,LU,DESCLU,ACRES,LANDAREA,NFMLNDVL,NFMIMPVL,NFMTTLVL,TRADATE,CONSIDR1,DR1LIBER,DR1FOLIO,YEARBLT,SQFTSTRC,DESCSTYL,SDATWEBADR,OOI",
        "f": "json",
        "returnGeometry": "false"
    }
    
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(MD_PROPERTY_DATA_URL, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            features = data.get("features", [])
            if features:
                attrs = features[0].get("attributes", {})
                
                # Check absentee status
                owner_state = (attrs.get("OWNSTATE") or "").strip().upper()
                is_absentee = (owner_state != "MD" and bool(owner_state)) or attrs.get("OOI") == "N"
                
                acres = attrs.get("ACRES") or attrs.get("LANDAREA")
                sqft = round(float(acres) * 43560, 1) if acres else None
                
                rec["address"] = attrs.get("ADDRESS") or "N/A"
                rec["city"] = attrs.get("CITY") or "N/A"
                rec["zipcode"] = attrs.get("ZIPCODE") or "N/A"
                rec["zoning"] = attrs.get("ZONING") or "N/A"
                rec["land_use"] = attrs.get("DESCLU") or attrs.get("LU") or "N/A"
                rec["acres"] = float(acres) if acres is not None else None
                rec["sqft"] = sqft
                rec["land_value"] = attrs.get("NFMLNDVL")
                rec["improvement_value"] = attrs.get("NFMIMPVL")
                rec["sdat_total_value"] = attrs.get("NFMTTLVL")
                rec["year_built"] = attrs.get("YEARBLT")
                rec["structure_sqft"] = attrs.get("SQFTSTRC")
                rec["style"] = attrs.get("DESCSTYL")
                rec["owner_city_state"] = f"{attrs.get('OWNCITY', '')}, {attrs.get('OWNSTATE', '')}".strip(", ")
                rec["is_absentee"] = is_absentee
                rec["last_sale_date"] = str(attrs.get("TRADATE", ""))
                rec["last_sale_price"] = attrs.get("CONSIDR1")
                rec["sdat_url"] = attrs.get("SDATWEBADR")
                rec["legal_desc"] = f"{attrs.get('LEGAL1', '')} {attrs.get('LEGAL2', '')}".strip()
                rec["subdivision"] = attrs.get("DESCSUBD")
                return rec
    except Exception as e:
        pass
        
    rec["address"] = "N/A"
    rec["city"] = "N/A"
    rec["zoning"] = "N/A"
    rec["land_use"] = "N/A"
    rec["acres"] = None
    rec["is_absentee"] = False
    return rec

enriched_results = []
with ThreadPoolExecutor(max_workers=10) as executor:
    enriched_results = list(executor.map(enrich_single_record, records))

print(f"Successfully enriched {len(enriched_results)} records.")

# Save enriched dataset
with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_liens.json", "w") as f:
    json.dump(enriched_results, f, indent=2)

print("Saved enriched data to scratch/anne_arundel_enriched_liens.json")
