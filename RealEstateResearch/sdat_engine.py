"""
Maryland Real Estate & SDAT Property Engine
Queries the official Maryland Department of Planning / MD iMAP ArcGIS Cadastre Services
Covering all 24 Maryland counties & jurisdictions.
"""

import os
import requests
import json
import re
import math
import urllib.parse
from typing import Dict, Any, Optional, List

# Official Maryland Statewide Property Data MapServer
MD_PROPERTY_DATA_URL = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query"
SDAT_PUBLIC_SEARCH_URL = "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
MD_FINDER_URL = "https://apps.planning.maryland.gov/finderonline/"
MD_PLATS_URL = "https://plats.msa.maryland.gov/"


def build_maryland_public_urls(acct_id: str = "", raw_sdat_url: str = "") -> Dict[str, str]:
    """Return public, non-admin Maryland property & land-record URLs for a parcel."""
    acct_clean = (acct_id or "").strip()
    imap_card_url = ""
    dossier_url = ""
    base_public = (
        os.environ.get("RENDER_EXTERNAL_URL")
        or os.environ.get("PUBLIC_URL")
        or "https://maryland-tax-lien-otc-platform.onrender.com"
    ).strip().rstrip("/")
    if acct_clean:
        where_clause = urllib.parse.quote(f"ACCTID='{acct_clean}'", safe="")
        imap_card_url = (
            "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/"
            f"MD%5FPropertyData/MapServer/0/query?where={where_clause}&outFields=*&f=html"
        )
        dossier_url = f"{base_public}/parcel?q={urllib.parse.quote(acct_clean, safe='')}"

    # Maryland iMAP SDATWEBADR fields frequently point to /RealPropertyAdmin/... which
    # redirects users into a membership login wall; prefer direct public links instead.
    raw_clean = (raw_sdat_url or "").strip()
    is_admin_or_deep_login = any(
        token in raw_clean.lower()
        for token in ("realpropertyadmin", "membership/account/login", "view.aspx", "viewdetails.aspx")
    )
    safe_sdat_url = imap_card_url or SDAT_PUBLIC_SEARCH_URL
    if raw_clean and not is_admin_or_deep_login:
        safe_sdat_url = raw_clean

    return {
        "dossier_url": dossier_url or base_public,
        "sdat_web_url": safe_sdat_url,
        "imap_card_url": imap_card_url or SDAT_PUBLIC_SEARCH_URL,
        "sdat_search_url": SDAT_PUBLIC_SEARCH_URL,
        "finder_url": MD_FINDER_URL,
        "plats_url": MD_PLATS_URL,
        "mdlandrec_url": "https://landrec.msa.maryland.gov/",
    }

COUNTY_JURS_MAP = {
    "ALLEGANY": "ALLE",
    "ANNE ARUNDEL": "ANNE",
    "BALTIMORE CITY": "BALT_CITY",
    "BALTIMORE COUNTY": "BALT_CO",
    "CALVERT": "CALV",
    "CAROLINE": "CARO",
    "CARROLL": "CARR",
    "CECIL": "CECI",
    "CHARLES": "CHAR",
    "DORCHESTER": "DORC",
    "FREDERICK": "FRED",
    "GARRETT": "GARR",
    "HARFORD": "HARF",
    "HOWARD": "HOWA",
    "KENT": "KENT",
    "MONTGOMERY": "MONT",
    "PRINCE GEORGE'S": "PRIN",
    "PRINCE GEORGES": "PRIN",
    "QUEEN ANNE'S": "QUEE",
    "QUEEN ANNES": "QUEE",
    "ST. MARY'S": "STMA",
    "ST MARYS": "STMA",
    "SOMERSET": "SOME",
    "TALBOT": "TALB",
    "WASHINGTON": "WASH",
    "WICOMICO": "WICO",
    "WORCESTER": "WORC"
}

def web_mercator_to_latlon(x: float, y: float) -> tuple[float, float]:
    """Converts Web Mercator EPSG:3857 coordinates to WGS84 (Lat, Lon)"""
    try:
        lon = (x / 20037508.34) * 180.0
        lat = (y / 20037508.34) * 180.0
        lat = 180.0 / math.pi * (2.0 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
        return round(lat, 6), round(lon, 6)
    except Exception:
        return 0.0, 0.0

def parse_address_components(address_str: str) -> Dict[str, str]:
    cleaned = address_str.strip().upper()
    cleaned = re.sub(r'[,\.]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    zip_match = re.search(r'\b(20\d{3}|21\d{3})\b', cleaned)
    zipcode = zip_match.group(1) if zip_match else ""
    
    num_match = re.match(r'^(\d+)\s+(.+)$', cleaned)
    street_num = ""
    street_name = ""
    
    if num_match:
        street_num = num_match.group(1)
        rest = num_match.group(2)
        rest = re.sub(r'\bMD\b|\bMARYLAND\b', '', rest).strip()
        if zipcode:
            rest = rest.replace(zipcode, '').strip()
        
        cities = ["SEVERN", "BALTIMORE", "ANNAPOLIS", "GLEN BURNIE", "COLUMBIA", "SILVER SPRING", 
                  "BOWIE", "ROCKVILLE", "GAITHERSBURG", "LAUREL", "ODENTON", "HANOVER", "PASADENA", "ELLICOTT CITY", "SANDY SPRING"]
        for c in cities:
            if rest.endswith(c):
                rest = rest[:-len(c)].strip()
                
        street_name = rest
    else:
        street_name = cleaned
        
    return {
        "raw": address_str,
        "street_num": street_num,
        "street_name": street_name,
        "zipcode": zipcode
    }

def format_date_str(val: Any) -> str:
    if not val:
        return "N/A"
    s = str(val).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s

def format_currency(val: Any) -> str:
    if val is None or val == "":
        return "N/A"
    try:
        num = float(val)
        return f"${num:,.2f}" if num % 1 else f"${int(num):,}"
    except (ValueError, TypeError):
        return str(val)

def search_maryland_property(query: str, county: Optional[str] = None) -> List[Dict[str, Any]]:
    clean_query = query.strip().upper()
    digits_only = re.sub(r'\D', '', clean_query)
    is_apn = len(digits_only) >= 8 and (clean_query.isdigit() or '-' in clean_query)
    
    where_clauses = []
    
    # Detect county from query if not explicitly passed
    detected_county = county
    if not detected_county:
        for c_name in sorted(COUNTY_JURS_MAP.keys(), key=len, reverse=True):
            if re.search(rf'\b{re.escape(c_name)}\b', clean_query):
                detected_county = c_name
                break

    # 1. Check for Map / Grid / Parcel pattern
    map_m = re.search(r'\bMAP\s*[:#]?\s*([0-9A-Z]+)', clean_query)
    grid_m = re.search(r'\bGRID\s*[:#]?\s*([0-9A-Z]+)', clean_query)
    parcel_m = re.search(r'\b(?:PARCEL|PAR|PRCL)\s*[:#]?\s*([0-9A-Z]+)', clean_query)
    
    if map_m and parcel_m:
        map_val = map_m.group(1)
        parcel_val = parcel_m.group(1)
        map_pad = map_val.zfill(4) if map_val.isdigit() else map_val
        parcel_pad = parcel_val.zfill(4) if parcel_val.isdigit() else parcel_val
        
        clause = f"(MAP = '{map_pad}' OR MAP LIKE '%{map_val}%') AND (PARCEL = '{parcel_pad}' OR PARCEL LIKE '%{parcel_val}%')"
        if grid_m:
            grid_val = grid_m.group(1)
            grid_pad = grid_val.zfill(4) if grid_val.isdigit() else grid_val
            clause += f" AND (GRID = '{grid_pad}' OR GRID LIKE '%{grid_val}%')"
        where_clauses.append(clause)
        
    elif is_apn or (len(digits_only) >= 8 and any(k in clean_query for k in ["APN", "ACCT", "ACCOUNT", "PIN", "PARCEL"])):
        # Match against ACCTID with multiple variations
        where_clauses.append(f"ACCTID LIKE '%{digits_only}%'")
        if len(digits_only) >= 8:
            where_clauses.append(f"ACCTID LIKE '%{digits_only[-8:]}%'")
    else:
        parsed = parse_address_components(query)
        if parsed["street_num"] and parsed["street_name"]:
            first_word_name = parsed["street_name"].split()[0] if parsed["street_name"] else ""
            where_clauses.append(f"(STRTNUM = {parsed['street_num']} AND (STRTNAM LIKE '%{first_word_name}%' OR ADDRESS LIKE '%{parsed['street_num']}%{first_word_name}%'))")
        
        clean_no_punct = re.sub(r'[^A-Z0-9\s]', ' ', clean_query)
        words = [w for w in clean_no_punct.split() if w not in ["MD", "MARYLAND", "DR", "DRIVE", "RD", "ROAD", "ST", "STREET", "AVE", "AVENUE", "LN", "LANE", "WAY", "CT", "COURT", "MAP", "GRID", "PARCEL", "ANNE", "ARUNDEL", "BALTIMORE", "HOWARD", "MONTGOMERY"]]
        if len(words) >= 2:
            w_num = words[0] if words[0].isdigit() else ""
            w_name = words[1] if words[0].isdigit() else words[0]
            if w_num:
                where_clauses.append(f"(ADDRESS LIKE '%{w_num}%{w_name}%')")
            else:
                where_clauses.append(f"(ADDRESS LIKE '%{w_name}%')")
        elif words:
            where_clauses.append(f"(ADDRESS LIKE '%{words[0]}%' OR ACCTID LIKE '%{words[0]}%')")

    if not where_clauses:
        where_clauses.append(f"ADDRESS LIKE '%{clean_query}%'")

    where_expr = " OR ".join(where_clauses)
    
    if detected_county:
        county_upper = detected_county.strip().upper()
        jurs = COUNTY_JURS_MAP.get(county_upper, county_upper[:4])
        where_expr = f"({where_expr}) AND (JURSCODE = '{jurs}')"

    params = {
        "where": where_expr,
        "outFields": "*",
        "f": "json",
        "returnGeometry": "true",
        "resultRecordCount": 5
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.get(MD_PROPERTY_DATA_URL, params=params, headers=headers, timeout=12)
        if resp.status_code != 200:
            return []
            
        data = resp.json()
        features = data.get("features", [])
        
        results = []
        for feat in features:
            attrs = feat.get("attributes", {})
            geom = feat.get("geometry", {})
            
            # Lat/Lon calculation from Web Mercator geometry
            gx = geom.get("x", 0)
            gy = geom.get("y", 0)
            lat, lon = (0.0, 0.0)
            google_maps_url = ""
            if gx and gy:
                lat, lon = web_mercator_to_latlon(gx, gy)
                if lat and lon:
                    google_maps_url = f"https://www.google.com/maps?q={lat},{lon}"
            
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
            
            rec = {
                "object_id": attrs.get("OBJECTID"),
                "jurisdiction": attrs.get("JURSCODE"),
                "account_id": attrs.get("ACCTID"),
                "address": attrs.get("ADDRESS") or f"{attrs.get('STRTNUM', '')} {attrs.get('STRTNAM', '')} {attrs.get('STRTTYP', '')}".strip(),
                "city": attrs.get("CITY") or attrs.get("PREMCITY"),
                "zipcode": attrs.get("ZIPCODE") or attrs.get("PREMZIP"),
                "owner_mailing": {
                    "line1": attrs.get("OWNADD1"),
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
                    "land_value": attrs.get("NFMLNDVL"),
                    "improvement_value": attrs.get("NFMIMPVL"),
                    "total_value": attrs.get("NFMTTLVL"),
                    "last_assessed_date": attrs.get("LASTASSD")
                },
                "transfer_history": {
                    "transfer_date": format_date_str(attrs.get("TRADATE")),
                    "consideration_price": attrs.get("CONSIDR1"),
                    "deed_liber": attrs.get("DR1LIBER"),
                    "deed_folio": attrs.get("DR1FOLIO"),
                    "prior_liber": attrs.get("GR1LIBR1"),
                    "prior_folio": attrs.get("GR1FOLO1")
                },
                "structure": {
                    "year_built": attrs.get("YEARBLT"),
                    "structure_sqft": attrs.get("SQFTSTRC"),
                    "style": attrs.get("DESCSTYL"),
                    "construction": attrs.get("DESCCNST"),
                    "stories": attrs.get("BLDG_STORY"),
                    "units": attrs.get("BLDG_UNITS")
                },
                "census": {
                    "tract": attrs.get("CT2020"),
                    "block_group": attrs.get("BG2020")
                },
                "sdat_web_url": build_maryland_public_urls(attrs.get("ACCTID") or "", attrs.get("SDATWEBADR") or "")["sdat_web_url"],
                "sdat_search_url": SDAT_PUBLIC_SEARCH_URL,
                "finder_url": MD_FINDER_URL,
                "plats_url": MD_PLATS_URL,
                "google_maps_url": google_maps_url,
                "coordinates": {
                    "lat": lat,
                    "lon": lon,
                    "x": attrs.get("DIGXCORD"),
                    "y": attrs.get("DIGYCORD")
                }
            }
            results.append(rec)
            
        return results
    except Exception as e:
        print(f"Error querying MD Property Data: {e}")
        return []

if __name__ == "__main__":
    import sys
    test_q = sys.argv[1] if len(sys.argv) > 1 else "400001785100"
    print(f"Searching for: {test_q}...")
    res = search_maryland_property(test_q)
    print(f"Found {len(res)} results:")
    for r in res:
        print(json.dumps(r, indent=2))
