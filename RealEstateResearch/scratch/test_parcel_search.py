import re
import requests
import json

def parse_map_grid_parcel(query: str):
    clean = query.strip().upper()
    
    map_m = re.search(r'\bMAP\s*[:#]?\s*([0-9A-Z]+)', clean)
    grid_m = re.search(r'\bGRID\s*[:#]?\s*([0-9A-Z]+)', clean)
    parcel_m = re.search(r'\b(?:PARCEL|PAR|PRCL)\s*[:#]?\s*([0-9A-Z]+)', clean)
    
    map_val = map_m.group(1) if map_m else None
    grid_val = grid_m.group(1) if grid_m else None
    parcel_val = parcel_m.group(1) if parcel_m else None
    
    if map_val and parcel_val:
        # Zero pad if numeric (e.g. Map 14 -> 0014, Parcel 21 -> 0021)
        map_pad = map_val.zfill(4) if map_val.isdigit() else map_val
        parcel_pad = parcel_val.zfill(4) if parcel_val.isdigit() else parcel_val
        
        where = f"(MAP = '{map_pad}' OR MAP LIKE '%{map_val}%') AND (PARCEL = '{parcel_pad}' OR PARCEL LIKE '%{parcel_val}%')"
        if grid_val:
            grid_pad = grid_val.zfill(4) if grid_val.isdigit() else grid_val
            where += f" AND (GRID = '{grid_pad}' OR GRID LIKE '%{grid_val}%')"
        return where
    return None

# Test Map 14 Parcel 21 in Anne Arundel
where_clause = parse_map_grid_parcel("Map 0014 Parcel 0021")
print("Generated Where:", where_clause)

params = {
    "where": f"{where_clause} AND JURSCODE = 'ANNE'",
    "outFields": "ACCTID,ADDRESS,CITY,ZIPCODE,MAP,GRID,PARCEL,ACRES,NFMTTLVL",
    "f": "json",
    "resultRecordCount": 3
}

r = requests.get("https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query", params=params, headers={"User-Agent": "Mozilla/5.0"})
print("Status:", r.status_code)
data = r.json()
for f in data.get("features", []):
    print("Found:", f["attributes"])
