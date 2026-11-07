import requests
import json
import sys

MD_PROPERTY_DATA_URL = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query"

test_accts = [
    "400001785100",
    "100000756300",
    "800090231566",
    "500004476153",
    "400090233360",
    "300013434800",
    "700090007618",
    "600005438352",
    "200090031256",
    "389632355600",
    "157907270900",
    "354018803400"
]

for acct in test_accts:
    digits = "".join(c for c in acct if c.isdigit())
    dist = digits[0].zfill(2)
    rest = digits[1:]
    acctid = f"02{dist}{rest}"
    
    params = {
        "where": f"ACCTID = '{acctid}'",
        "outFields": "ACCTID,ADDRESS,CITY,ZIPCODE,OWNNAME1,OWNNAME2,NFMLNDVL,NFMIMPVL,NFMTTLVL,TRADATE,CONSIDR1,DR1LIBER,DR1FOLIO,GR1LIBR1,GR1FOLO1,DESCSUBD,LOT,SECTION,BLOCK,MAP,GRID,PARCEL,ZONING,LU,DESCLU,YEARBLT,SQFTSTRC,DESCSTYL",
        "f": "json"
    }
    try:
        r = requests.get(MD_PROPERTY_DATA_URL, params=params, timeout=10)
        feats = r.json().get("features", [])
        if feats:
            a = feats[0]["attributes"]
            print(f"FOUND {acct} -> {acctid}: {a.get('ADDRESS')}, {a.get('CITY')} | Owner: {a.get('OWNNAME1')} | Assessed: ${a.get('NFMTTLVL')} | Deed: Liber {a.get('DR1LIBER')}/Folio {a.get('DR1FOLIO')} | Prior: {a.get('GR1LIBR1')}/{a.get('GR1FOLO1')} | Paid: ${a.get('CONSIDR1')} ({a.get('TRADATE')}) | Subdiv: {a.get('DESCSUBD')}, Lot {a.get('LOT')}")
        else:
            print(f"MISS {acct} -> {acctid}")
    except Exception as e:
        print(f"ERROR {acct}: {e}")
