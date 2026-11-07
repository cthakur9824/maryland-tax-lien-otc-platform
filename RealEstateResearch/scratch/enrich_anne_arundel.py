import json
import requests
import math
from concurrent.futures import ThreadPoolExecutor

MD_PROPERTY_DATA_URL = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query"

def web_mercator_to_latlon(x: float, y: float) -> tuple[float, float]:
    try:
        lon = (x / 20037508.34) * 180.0
        lat = (y / 20037508.34) * 180.0
        lat = 180.0 / math.pi * (2.0 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
        return round(lat, 6), round(lon, 6)
    except Exception:
        return 0.0, 0.0

def format_date_str(val):
    if not val:
        return "N/A"
    s = str(val).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_parsed_liens.json", "r", encoding="utf-8") as f:
    records = json.load(f)

print(f"Total parsed records: {len(records)}")

def enrich_single(rec):
    acct = rec["account_no"].strip()
    digits = "".join(c for c in acct if c.isdigit())
    
    # Anne Arundel format: District (first 1-2 digits) + remaining account number
    clauses = [f"ACCTID LIKE '%{digits}%'"]
    if len(digits) >= 8:
        clauses.append(f"ACCTID LIKE '%{digits[-8:]}%'")
    
    clause_str = " OR ".join(clauses)
    where_expr = f"({clause_str}) AND (JURSCODE = 'ANNE')"
    
    params = {
        "where": where_expr,
        "outFields": "*",
        "f": "json",
        "returnGeometry": "true",
        "resultRecordCount": 1
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        r = requests.get(MD_PROPERTY_DATA_URL, params=params, headers=headers, timeout=12)
        if r.status_code == 200:
            feats = r.json().get("features", [])
            if feats:
                attrs = feats[0].get("attributes", {})
                geom = feats[0].get("geometry", {})
                
                gx = geom.get("x", 0)
                gy = geom.get("y", 0)
                lat, lon = (0.0, 0.0)
                gmaps_url = ""
                if gx and gy:
                    lat, lon = web_mercator_to_latlon(gx, gy)
                    if lat and lon:
                        gmaps_url = f"https://www.google.com/maps?q={lat},{lon}"
                        
                owner_state = (attrs.get("OWNSTATE") or "").strip().upper()
                premise_zip = (attrs.get("PREMZIP") or attrs.get("ZIPCODE") or "").strip()
                owner_zip = (attrs.get("OWNERZIP") or "").strip()
                
                is_absentee = False
                if owner_state and owner_state != "MD":
                    is_absentee = True
                elif owner_zip and premise_zip and owner_zip[:5] != premise_zip[:5]:
                    is_absentee = True
                elif attrs.get("OOI") == "N":
                    is_absentee = True
                    
                acres = attrs.get("ACRES") or attrs.get("LANDAREA")
                sqft = round(float(acres) * 43560, 1) if acres else None
                
                # Check for address
                addr = attrs.get("ADDRESS")
                if not addr or addr == "None" or addr.startswith("None "):
                    strtnum = attrs.get("STRTNUM") or ""
                    strtnam = attrs.get("STRTNAM") or ""
                    strttyp = attrs.get("STRTTYP") or ""
                    addr = f"{strtnum} {strtnam} {strttyp}".strip()
                    if not addr:
                        addr = f"{attrs.get('LEGAL1', '')} {attrs.get('LEGAL2', '')}".strip()
                
                return {
                    "list_no": rec.get("list_no"),
                    "account_no": rec.get("account_no"),
                    "sdat_acctid": attrs.get("ACCTID"),
                    "owner": rec.get("owner"),
                    "sdat_owner": f"{attrs.get('OWNNAME1', '')} {attrs.get('OWNNAME2', '')}".strip() or rec.get("owner"),
                    "assessment": rec.get("assessment"),
                    "sdat_total_value": attrs.get("NFMTTLVL") or rec.get("assessment"),
                    "land_value": attrs.get("NFMLNDVL"),
                    "improvement_value": attrs.get("NFMIMPVL"),
                    "bid_amount": rec.get("bid_amount"),
                    "bid_premium": rec.get("bid_premium"),
                    "interest": rec.get("interest"),
                    "total_due": rec.get("total_due"),
                    "ltv_pct": rec.get("ltv_pct"),
                    "address": addr,
                    "city": attrs.get("CITY") or attrs.get("PREMCITY") or "N/A",
                    "zipcode": attrs.get("ZIPCODE") or attrs.get("PREMZIP") or "N/A",
                    "zoning": attrs.get("ZONING") or "N/A",
                    "land_use": attrs.get("DESCLU") or attrs.get("LU") or "N/A",
                    "commercial_use": attrs.get("DESCCIUSE"),
                    "acres": float(acres) if acres is not None else None,
                    "sqft": sqft,
                    "year_built": attrs.get("YEARBLT"),
                    "structure_sqft": attrs.get("SQFTSTRC"),
                    "style": attrs.get("DESCSTYL"),
                    "stories": attrs.get("BLDG_STORY"),
                    "owner_mailing": {
                        "address": f"{attrs.get('OWNADD1', '')} {attrs.get('OWNADD2', '')}".strip(),
                        "city": attrs.get("OWNCITY"),
                        "state": attrs.get("OWNSTATE"),
                        "zip": attrs.get("OWNERZIP"),
                    },
                    "is_absentee": is_absentee,
                    "last_sale_date": format_date_str(attrs.get("TRADATE")),
                    "last_sale_price": attrs.get("CONSIDR1"),
                    "legal_desc": f"{attrs.get('LEGAL1', '')} {attrs.get('LEGAL2', '')} {attrs.get('LEGAL3', '')}".strip(),
                    "subdivision": attrs.get("DESCSUBD") or attrs.get("SUBDIVSN"),
                    "map": attrs.get("MAP"),
                    "grid": attrs.get("GRID"),
                    "parcel": attrs.get("PARCEL"),
                    "sdat_url": attrs.get("SDATWEBADR"),
                    "google_maps_url": gmaps_url,
                    "lat": lat,
                    "lon": lon,
                    "matched": True
                }
    except Exception as e:
        print(f"Error on {rec.get('account_no')}: {e}")
        
    return {
        **rec,
        "matched": False
    }

with ThreadPoolExecutor(max_workers=8) as ex:
    enriched_list = list(ex.map(enrich_single, records))

matched_count = sum(1 for r in enriched_list if r.get("matched"))
print(f"Matched {matched_count} of {len(records)} records.")

# Save enriched dataset
with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json", "w", encoding="utf-8") as f:
    json.dump(enriched_list, f, indent=2)

print("Saved to scratch/anne_arundel_enriched_master.json")
