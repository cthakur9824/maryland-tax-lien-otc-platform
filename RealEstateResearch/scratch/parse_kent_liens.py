import pypdf
import re
import json
import os
import requests
import time
import math

PDF_PATH = r"raw\Kent County 2026 Tax Sale - OTC 6.9.26.pdf"
OUTPUT_JSON = r"scratch\kent_county_parsed_liens.json"
MD_PROPERTY_DATA_URL = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query"

def web_mercator_to_latlon(x: float, y: float) -> tuple[float, float]:
    try:
        lon = (x / 20037508.34) * 180.0
        lat = (y / 20037508.34) * 180.0
        lat = 180.0 / math.pi * (2.0 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
        return round(lat, 6), round(lon, 6)
    except Exception:
        return 0.0, 0.0

reader = pypdf.PdfReader(PDF_PATH)
text = reader.pages[0].extract_text()
lines = text.split('\n')

records = []
pattern = re.compile(r'^(\d{8})\s+(.+?)\s+([\d,]+)\s+([\d,]+\.\d{2})\$\s+(.+)$')

for line in lines:
    line_str = line.strip()
    m = pattern.match(line_str)
    if m:
        acct, owner, assessed, bid, legal = m.groups()
        assessed_val = float(assessed.replace(',', ''))
        bid_val = float(bid.replace(',', ''))
        ltv = round((bid_val / assessed_val) * 100, 1) if assessed_val > 0 else 999.0
        spread = assessed_val - bid_val
        records.append({
            'account_id': acct,
            'district': acct[:2],
            'account_num': acct[2:],
            'sdat_account_id': f"14{acct}",
            'owner': owner.strip(),
            'assessed_value': assessed_val,
            'opening_bid': bid_val,
            'ltv_pct': ltv,
            'equity_spread': spread,
            'legal_description': legal.strip()
        })

print(f"Parsed {len(records)} records from PDF.")

# Enrich with SDAT MD iMAP data
print("Enriching with SDAT Property Data...")
enriched_records = []
for i, r in enumerate(records):
    acct = r['account_id']
    # Query MD iMAP for Kent County
    where_expr = f"(ACCTID LIKE '%{acct}%' OR ACCTID LIKE '%{r['account_num']}%') AND (JURSCODE = 'KENT')"
    params = {
        "where": where_expr,
        "outFields": "*",
        "f": "json",
        "returnGeometry": "true"
    }
    try:
        resp = requests.get(MD_PROPERTY_DATA_URL, params=params, timeout=10)
        data = resp.json()
        features = data.get("features", [])
        if features:
            feat = features[0]
            attrs = feat.get("attributes", {})
            geom = feat.get("geometry", {})
            
            gx, gy = geom.get("x", 0), geom.get("y", 0)
            lat, lon = web_mercator_to_latlon(gx, gy) if gx and gy else (0.0, 0.0)
            gmaps_url = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else ""
            
            premise_addr = attrs.get("ADDRESS", "").strip()
            premise_city = attrs.get("PREMCITY", "CHESTERTOWN").strip()
            premise_zip = attrs.get("PREMZIP", attrs.get("ZIPCODE", "")).strip()
            
            owner_name = attrs.get("OWNNAME1", r['owner']).strip()
            owner_mail = f"{attrs.get('OWNADD1', '')} {attrs.get('OWNADD2', '')}".strip()
            owner_city = attrs.get("OWNERCTY", "").strip()
            owner_state = attrs.get("OWNSTATE", "").strip()
            owner_zip = attrs.get("OWNERZIP", "").strip()
            
            is_absentee = False
            if owner_state and owner_state != "MD":
                is_absentee = True
            elif owner_zip and premise_zip and owner_zip[:5] != premise_zip[:5]:
                is_absentee = True
            elif attrs.get("OOI") == "N":
                is_absentee = True
                
            land_val = attrs.get("LANDVAL") or attrs.get("BASELAND") or 0
            imp_val = attrs.get("BLDGVAL") or attrs.get("STRVAL") or attrs.get("IMPRVAL") or 0
            curr_tot = attrs.get("NFMLNDVL", 0) or attrs.get("TOTVAL", 0) or r['assessed_value']
            
            acres = attrs.get("ACRES") or attrs.get("LANDAREA")
            zoning = attrs.get("ZONING", "N/A")
            land_use = attrs.get("LU", "Residential")
            yr_built = attrs.get("YEARBLT") or attrs.get("YRBLT")
            sqft = attrs.get("SQFT") or attrs.get("BLDGAREA")
            
            r['sdat_data'] = {
                'address': premise_addr or r['legal_description'],
                'city': premise_city,
                'zip': premise_zip,
                'owner_name': owner_name,
                'mailing_address': f"{owner_mail}, {owner_city} {owner_state} {owner_zip}".strip(),
                'is_absentee': is_absentee,
                'land_value': float(land_val) if land_val else 0.0,
                'imp_value': float(imp_val) if imp_val else 0.0,
                'acres': float(acres) if acres else None,
                'zoning': zoning,
                'land_use': land_use,
                'year_built': yr_built,
                'bldg_sqft': sqft,
                'map': attrs.get("MAP"),
                'grid': attrs.get("GRID"),
                'parcel': attrs.get("PARCEL"),
                'subdivision': attrs.get("SUBDIVISN"),
                'lat': lat,
                'lon': lon,
                'gmaps_url': gmaps_url
            }
        else:
            r['sdat_data'] = None
    except Exception as e:
        print(f"Error querying SDAT for {acct}: {e}")
        r['sdat_data'] = None
        
    enriched_records.append(r)
    time.sleep(0.1)

os.makedirs("scratch", exist_ok=True)
with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(enriched_records, f, indent=2)

print("\nSaved enriched records to scratch/kent_county_parsed_liens.json.")

print("\n--- TOP 10 LOWEST LTV LIENS (Safest / High Equity Cushion) ---")
for r in sorted(enriched_records, key=lambda x: x['ltv_pct'])[:10]:
    sdat = r.get('sdat_data') or {}
    addr = sdat.get('address') or r['legal_description'][:30]
    subdiv = sdat.get('subdivision') or 'N/A'
    print(f"Acct {r['account_id']} | Bid: ${r['opening_bid']:>9,.2f} | Assessed: ${r['assessed_value']:>8,.0f} | LTV: {r['ltv_pct']:>5.1f}% | Spread: ${r['equity_spread']:>8,.0f} | Loc: {addr[:35]}")

print("\n--- TOP 10 HIGHEST ASSESSED PROPERTIES ---")
for r in sorted(enriched_records, key=lambda x: x['assessed_value'], reverse=True)[:10]:
    sdat = r.get('sdat_data') or {}
    addr = sdat.get('address') or r['legal_description'][:30]
    print(f"Acct {r['account_id']} | Bid: ${r['opening_bid']:>9,.2f} | Assessed: ${r['assessed_value']:>8,.0f} | LTV: {r['ltv_pct']:>5.1f}% | Spread: ${r['equity_spread']:>8,.0f} | Loc: {addr[:35]}")

print("\n--- ALL SUB-$2,000 MICRO-LIENS ---")
for r in sorted([r for r in enriched_records if r['opening_bid'] < 2000], key=lambda x: x['opening_bid']):
    sdat = r.get('sdat_data') or {}
    addr = sdat.get('address') or r['legal_description'][:30]
    print(f"Acct {r['account_id']} | Bid: ${r['opening_bid']:>9,.2f} | Assessed: ${r['assessed_value']:>8,.0f} | LTV: {r['ltv_pct']:>5.1f}% | Spread: ${r['equity_spread']:>8,.0f} | Loc: {addr[:35]}")
