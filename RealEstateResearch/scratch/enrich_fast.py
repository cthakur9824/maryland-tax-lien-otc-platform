import json
import requests
import math
import sys
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

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_parsed_liens.json", "r", encoding="utf-8") as f:
    records = json.load(f)

print(f"Total parsed records: {len(records)}")

def get_acctid_variants(acct):
    acct = str(acct).strip()
    digits = "".join(c for c in acct if c.isdigit())
    variants = []
    # If 12 digits: e.g. 400001785100 -> District '04' + '00001785100' -> '020400001785100'
    if len(digits) == 12:
        dist = digits[0].zfill(2)
        rest = digits[1:]
        variants.append(f"02{dist}{rest}")
    # If 11 digits:
    if len(digits) == 11:
        dist = digits[0].zfill(2)
        rest = digits[1:]
        variants.append(f"02{dist}{rest}")
    variants.append(f"02{digits}")
    return variants

def enrich_record(rec):
    acct = rec["account_no"]
    variants = get_acctid_variants(acct)
    
    where_parts = [f"ACCTID = '{v}'" for v in variants]
    where_expr = f"({' OR '.join(where_parts)}) AND (JURSCODE = 'ANNE')"
    
    params = {
        "where": where_expr,
        "outFields": "*",
        "f": "json",
        "returnGeometry": "true"
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(MD_PROPERTY_DATA_URL, params=params, headers=headers, timeout=8)
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
                is_absentee = (owner_state != "MD" and bool(owner_state)) or attrs.get("OOI") == "N"
                
                acres = attrs.get("ACRES") or attrs.get("LANDAREA")
                sqft = round(float(acres) * 43560, 1) if acres else None
                
                addr = attrs.get("ADDRESS")
                if not addr or addr == "None" or addr.startswith("None "):
                    snum = attrs.get("STRTNUM") or ""
                    snam = attrs.get("STRTNAM") or ""
                    styp = attrs.get("STRTTYP") or ""
                    addr = f"{snum} {snam} {styp}".strip()
                    if not addr:
                        addr = f"{attrs.get('LEGAL1', '')} {attrs.get('LEGAL2', '')}".strip()
                        
                return {
                    **rec,
                    "matched": True,
                    "address": addr,
                    "city": attrs.get("CITY") or attrs.get("PREMCITY") or "N/A",
                    "zipcode": attrs.get("ZIPCODE") or attrs.get("PREMZIP") or "N/A",
                    "sdat_owner": f"{attrs.get('OWNNAME1', '')} {attrs.get('OWNNAME2', '')}".strip(),
                    "land_value": attrs.get("NFMLNDVL") or 0,
                    "improvement_value": attrs.get("NFMIMPVL") or 0,
                    "sdat_total_value": attrs.get("NFMTTLVL") or rec.get("assessment", 0),
                    "zoning": attrs.get("ZONING") or "N/A",
                    "land_use": attrs.get("DESCLU") or attrs.get("LU") or "N/A",
                    "acres": float(acres) if acres is not None else None,
                    "sqft": sqft,
                    "year_built": attrs.get("YEARBLT"),
                    "structure_sqft": attrs.get("SQFTSTRC"),
                    "style": attrs.get("DESCSTYL"),
                    "stories": attrs.get("BLDG_STORY"),
                    "legal_desc": f"{attrs.get('LEGAL1', '')} {attrs.get('LEGAL2', '')} {attrs.get('LEGAL3', '')}".strip(),
                    "subdivision": attrs.get("DESCSUBD") or attrs.get("SUBDIVSN"),
                    "map": attrs.get("MAP"),
                    "grid": attrs.get("GRID"),
                    "parcel": attrs.get("PARCEL"),
                    "google_maps_url": gmaps_url,
                    "sdat_url": attrs.get("SDATWEBADR"),
                    "lat": lat,
                    "lon": lon,
                    "owner_mailing": {
                        "address": f"{attrs.get('OWNADD1', '')} {attrs.get('OWNADD2', '')}".strip(),
                        "city": attrs.get("OWNCITY"),
                        "state": attrs.get("OWNSTATE"),
                        "zip": attrs.get("OWNERZIP")
                    },
                    "is_absentee": is_absentee
                }
    except Exception as e:
        pass
        
    return {
        **rec,
        "matched": False
    }

with ThreadPoolExecutor(max_workers=12) as ex:
    results = list(ex.map(enrich_record, records))

matched = [r for r in results if r.get("matched")]
print(f"Done! Matched {len(matched)} / {len(records)} records.")

with open(r"c:\Obsedian\RealEstateResearch\RealEstateResearch\scratch\anne_arundel_enriched_master.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("Saved to scratch/anne_arundel_enriched_master.json")
