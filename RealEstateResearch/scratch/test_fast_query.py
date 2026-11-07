import requests, time, json

t0 = time.time()
acct_raw = "100000756300"
dist = int(acct_raw[0])
acct_15 = f"02{dist:02d}{acct_raw[1:]}"

url = "https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_PropertyData/MapServer/0/query"
params = {
    "where": f"ACCTID = '{acct_15}' AND JURSCODE = 'ANNE'",
    "outFields": "*",
    "f": "json",
    "returnGeometry": "false"
}
resp = requests.get(url, params=params, timeout=5)
data = resp.json()
print(f"Time taken: {time.time()-t0:.2f}s | Features found: {len(data.get('features', []))}")
if data.get('features'):
    feat = data['features'][0]['attributes']
    print("Address:", feat.get('ADDRESS'), "| Owner:", feat.get('OWNNAME1'), "| Liber:", feat.get('DR1LIBER'), "| Folio:", feat.get('DR1FOLIO'))
