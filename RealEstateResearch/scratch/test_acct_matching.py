import requests
import json

# Test how ACCTID is formatted in MD iMAP for Anne Arundel
sample_accounts = [
    "100000756300",  # District 1
    "400001785100",  # District 4
    "500004476153",  # District 5
    "354028781200",  # District 3
    "700090007618",  # District 7
    "800090231566",  # District 8
    "600005438352",  # District 6
]

for acct in sample_accounts:
    # Try different pattern matches in MD iMAP
    district = acct[0]
    rest = acct[1:]
    # in MD iMAP: JURSCODE = 'ANNE' AND ACCTID LIKE '%...'
    params = {
        "where": f"JURSCODE = 'ANNE' AND (ACCTID LIKE '%{rest[-8:]}%' OR ACCTID LIKE '%{acct[-8:]}%' OR ACCTID LIKE '%{acct}%')",
        "outFields": "ACCTID,ADDRESS,CITY,ZIPCODE,ZONING,DESCLU,NFMTTLVL,NFMLNDVL,NFMIMPVL,ACRES,YEARBLT,SQFTSTRC,DR1LIBER,DR1FOLIO,CONSIDR1,TRADATE",
        "f": "json",
        "resultRecordCount": 3
    }
    r = requests.get("https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query", params=params, headers={"User-Agent": "Mozilla/5.0"})
    data = r.json()
    features = data.get("features", [])
    print(f"\nAccount {acct} (Dist {district}) -> Found {len(features)} records:")
    for f in features:
        a = f["attributes"]
        print(f"  ACCTID: {a['ACCTID']} | Addr: {a.get('ADDRESS')} {a.get('CITY')} | Zoning: {a.get('ZONING')} | Land: ${a.get('NFMLNDVL')} | Impr: ${a.get('NFMIMPVL')} | Total: ${a.get('NFMTTLVL')} | Built: {a.get('YEARBLT')} ({a.get('SQFTSTRC')} sqft) | Acres: {a.get('ACRES')}")
