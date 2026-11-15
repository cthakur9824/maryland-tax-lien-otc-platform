import os
import re
import json
import glob
import html
import openpyxl
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "raw")
SCRATCH_DIR = os.path.join(BASE_DIR, "scratch")

# Known Colorado TylerHost counties and their subdomains
COLORADO_TYLER_SUBDOMAINS = {
    "conejos": "conejoscountyco-treasurer.tylerhost.net",
    "gilpin": "gilpincountyco-treasurer.tylerhost.net",
    "archuleta": "archuletacountyco-treasurer.tylerhost.net",
    "costilla": "costillacountyco-treasurer.tylerhost.net",
    "alamosa": "alamosacountyco-treasurer.tylerhost.net",
    "riogrande": "riograndecountyco-treasurer.tylerhost.net",
    "chaffee": "chaffeecountyco-treasurer.tylerhost.net",
    "custer": "custercountyco-treasurer.tylerhost.net",
    "fremont": "fremontcountyco-treasurer.tylerhost.net",
    "huerfano": "huerfanocountyco-treasurer.tylerhost.net",
    "lasanimas": "lasanimascountyco-treasurer.tylerhost.net",
    "park": "parkcountyco-treasurer.tylerhost.net",
    "lake": "lakecountyco-treasurer.tylerhost.net",
    "clearcreek": "clearcreekcountyco-treasurer.tylerhost.net",
    "grand": "grandcountyco-treasurer.tylerhost.net",
    "garfield": "garfieldcountyco-treasurer.tylerhost.net",
    "delta": "deltacountyco-treasurer.tylerhost.net",
    "montrose": "montrosecountyco-treasurer.tylerhost.net",
    "montezuma": "montezumacountyco-treasurer.tylerhost.net",
}

COUNTY_ASSESSOR_URLS = {
    "conejos": "https://www.arcgis.com/apps/mapviewer/index.html?layers=7846faeb502b491e93956a358ba7fbc0",
    "gilpin": "https://gilpin.infoenvoy.net/Details/{parcel}",
    "gunnison": "https://property.spatialest.com/co/gunnison#/property/{parcel}",
    "fulton": "https://beacon.schneidercorp.com/Application.aspx?App=FultonCountyIN&PageType=Search",
}

COUNTY_TREASURER_URLS = {
    "conejos": "https://conejoscountyco-treasurer.tylerhost.net/treasurer/treasurerweb/account.jsp?account={parcel}",
    "gilpin": "https://gilpincountyco-treasurer.tylerhost.net/treasurer/treasurerweb/account.jsp?account={parcel}",
    "gunnison": "https://www.gunnisoncounty.org/143/Treasurer",
    "fulton": "https://www.co.fulton.in.us/department/index.php?structureid=21",
}

STATE_NAMES_MAP = {
    "colorado": "CO",
    "co": "CO",
    "indiana": "IN",
    "in": "IN",
    "maryland": "MD",
    "md": "MD",
}

_INDEX_CACHE = {
    "mtime_sig": None,
    "by_county": {},     # county_key -> list of records
    "by_parcel": {},     # normalized_parcel -> list of records
    "counties_meta": {}  # county_key -> {"county": "Conejos", "state": "CO", "source_file": ...}
}


def _norm_parcel(p):
    return re.sub(r"[^A-Z0-9]", "", str(p or "").upper())


def parse_acreage_from_legal(legal_str):
    if not legal_str:
        return 0.0
    s = str(legal_str).upper()
    m_ac = re.findall(r'(?<!\d)(\d*\.\d+|\d+)\s*(?:ACRES|ACRE|AC\.?)\b', s)
    if m_ac:
        return round(sum(float(x) for x in m_ac), 2)
    tna_matches = re.findall(r'\bTNA\s+(\d*\.\d+|\d+)(?:\s+(\d+)\s*/\s*(\d+))?', s)
    if tna_matches:
        total_tna = 0.0
        for whole, num, den in tna_matches:
            val = float(whole)
            if num and den and float(den) != 0:
                val += float(num) / float(den)
            total_tna += val
        if total_tna > 0:
            return round(total_tna, 2)
    return 0.0


def fetch_tylerhost_live(county_key, account_id):
    """Live scraper for any Colorado County TylerHost EagleWeb/TreasurerWeb portal."""
    ck = county_key.lower().replace(" ", "")
    host = COLORADO_TYLER_SUBDOMAINS.get(ck, f"{ck}countyco-treasurer.tylerhost.net")
    acc = str(account_id).strip().upper()
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    try:
        s.post(
            f"https://{host}/treasurer/treasurerweb/loginPOST.jsp",
            data={"submit": "Login", "guest": "true"},
            timeout=10
        )
        r = s.get(
            f"https://{host}/treasurer/treasurerweb/account.jsp?account={acc}",
            timeout=10
        )
        if r.status_code != 200 or "Tax Account" not in r.text:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        summary_div = soup.find("div", id="taxAccountSummary")
        if not summary_div:
            return None

        info = {
            "county": county_key.title(),
            "state": "CO",
            "parcel": acc,
            "state_parcel_id": "",
            "owner": "",
            "mailing_address": "",
            "situs_address": "",
            "legal": "",
            "tax_district": "",
            "mill_levy": 0.0,
            "land_val": 0.0,
            "imp_val": 0.0,
            "actual_val": 0.0,
            "assessed_val": 0.0,
            "total_billed": 0.0,
            "full_payment_due": 0.0,
            "prop_classes": [],
            "abstract_codes": [],
            "treasurer_link": f"https://{host}/treasurer/treasurerweb/account.jsp?account={acc}",
            "assessor_link": COUNTY_ASSESSOR_URLS.get(ck, f"https://{host}/treasurer/treasurerweb/account.jsp?account={acc}").format(parcel=acc)
        }

        for row in summary_div.find_all("div", class_="hasLabel"):
            divs = row.find_all("div", class_="label")
            if len(divs) >= 2:
                k = divs[0].get_text(" ", strip=True).replace("\xa0", " ").strip()
                v = divs[1].get_text(" ", strip=True).replace("\xa0", " ").strip()
                if k == "Parcel Number":
                    info["state_parcel_id"] = v
                elif k == "Owners":
                    info["owner"] = v
                elif k == "Address":
                    info["mailing_address"] = v
                elif k == "Situs Address":
                    info["situs_address"] = v
                elif k == "Legal":
                    info["legal"] = v

        pay_div = soup.find("div", id="paymentLinks")
        if pay_div:
            for tr in pay_div.find_all("tr"):
                txt = tr.get_text(" ", strip=True)
                if "Full Payment" in txt:
                    m_due = re.search(r'\$([\d,]+\.\d{2})', txt)
                    if m_due:
                        info["full_payment_due"] = float(m_due.group(1).replace(",", ""))

        val_div = soup.find("div", id="taxAccountValueSummary")
        if val_div:
            mill_sum = 0.0
            seen_classes = set()
            for tr in val_div.find_all("tr"):
                tds = [td.get_text(" ", strip=True).replace("\xa0", " ").strip() for td in tr.find_all(["td", "th"])]
                if len(tds) == 3:
                    c0, c1, c2 = tds[0], tds[1], tds[2]
                    if "TAX DISTRICT" in c0.upper() or c1 in ("School", "Non-School"):
                        if c0 and not info["tax_district"]:
                            info["tax_district"] = c0
                        try:
                            mill_sum += float(c2.replace(",", ""))
                        except ValueError:
                            pass
                    elif c0.startswith("Total Value"):
                        try:
                            act = float(c1.replace(",", "").replace("$", ""))
                            ass = float(c2.replace(",", "").replace("$", ""))
                            if act >= info["actual_val"]:
                                info["actual_val"] = act
                            if ass >= info["assessed_val"]:
                                info["assessed_val"] = ass
                        except ValueError:
                            pass
                    elif c0 == "Total Billed":
                        try:
                            info["total_billed"] = float(c2.replace(",", "").replace("$", ""))
                        except ValueError:
                            pass
                    elif " - " in c0 and c1 not in ("Actual", "Authority Type", ""):
                        if c0 not in seen_classes:
                            seen_classes.add(c0)
                            info["prop_classes"].append(c0)
                            m_code = re.search(r'-\s*(\d{4})\b', c0)
                            code = m_code.group(1) if m_code else ""
                            if code:
                                info["abstract_codes"].append(code)
                            try:
                                val_act = float(c1.replace(",", "").replace("$", ""))
                            except ValueError:
                                val_act = 0.0
                            try:
                                val_ass = float(c2.replace(",", "").replace("$", ""))
                            except ValueError:
                                val_ass = 0.0
                            if val_ass > 0 and info["assessed_val"] == 0:
                                info["assessed_val"] += val_ass
                            is_imp = False
                            if code:
                                c_num = int(code)
                                if (1200 <= c_num <= 1299) or (2200 <= c_num <= 2299) or (3200 <= c_num <= 3299) or (4200 <= c_num <= 4299):
                                    is_imp = True
                            elif any(w in c0.upper() for w in ["RESIDENCE", "REESIDENCE", "IMPROVEMENT", "BLDG", "BUILDING", "STRUCT", "MANUF", "MOBILE"]):
                                is_imp = True
                            if is_imp:
                                info["imp_val"] += val_act
                            else:
                                info["land_val"] += val_act
            if mill_sum > 0:
                info["mill_levy"] = round(mill_sum, 4)
            if info["actual_val"] == 0 and (info["land_val"] + info["imp_val"]) > 0:
                info["actual_val"] = info["land_val"] + info["imp_val"]

        # Enrich live Conejos lookups with GIS parcel polygon coordinates & acreage
        if ck == "conejos" and info.get("state_parcel_id"):
            num_pid = str(info["state_parcel_id"]).strip().lstrip("R")
            try:
                gis_url = "https://services7.arcgis.com/qznFlX1g8SfaPebZ/arcgis/rest/services/Conejos_Parcels_2026-View/FeatureServer/0/query"
                rg = requests.get(gis_url, params={
                    "where": f"Parcel='{num_pid}'",
                    "outFields": "Parcel,Acres,Shape_Area",
                    "outSR": "4326",
                    "returnGeometry": "true",
                    "f": "json"
                }, timeout=8).json()
                feats = rg.get("features", [])
                if feats:
                    att = feats[0].get("attributes", {})
                    geom = feats[0].get("geometry", {})
                    rings = geom.get("rings", [])
                    if float(att.get("Acres") or 0) > 0:
                        info["acres"] = round(float(att["Acres"]), 2)
                    if float(att.get("Shape_Area") or 0) > 0:
                        info["sqft"] = round(float(att["Shape_Area"]), 0)
                    if rings and rings[0]:
                        pts = rings[0]
                        lat = round(sum(p[1] for p in pts) / len(pts), 6)
                        lon = round(sum(p[0] for p in pts) / len(pts), 6)
                        info["lat"] = lat
                        info["lon"] = lon
                        info["google_maps_url"] = f"https://www.google.com/maps?q={lat},{lon}"
                        info["assessor_link"] = f"https://www.arcgis.com/apps/mapviewer/index.html?layers=7846faeb502b491e93956a358ba7fbc0&center={lon},{lat}&level=16"
            except Exception:
                pass

        return info
    except Exception:
        return None


def fetch_colorado_statewide_gis(query_str, county_hint=None):
    """Query Official State of Colorado Public Parcels ArcGIS FeatureServer."""
    url = "https://gis.colorado.gov/public/rest/services/Address_and_Parcel/Colorado_Public_Parcels/FeatureServer/0/query"
    q = str(query_str).strip().upper().replace("'", "")
    where_parts = [f"(UPPER(account) = '{q}' OR UPPER(parcel_id) = '{q}' OR UPPER(situsAdd) LIKE '%{q}%')"]
    if county_hint:
        ch = county_hint.strip().upper().replace("'", "")
        where_parts.append(f"UPPER(countyName) LIKE '%{ch}%'")
    params = {
        "where": " AND ".join(where_parts),
        "outFields": "countyName,countyFips,parcel_id,account,situsAdd,sitAddCty,sitAddZip,owner,ownerAdd,ownAddCty,ownAddStt,legalDesc,landAcres,zoningDesc,landUseDsc,apprValTot,asedValTot,URL",
        "resultRecordCount": 5,
        "returnGeometry": "false",
        "f": "json"
    }
    try:
        r = requests.get(url, params=params, timeout=10).json()
        feats = r.get("features", [])
        results = []
        for f in feats:
            a = f.get("attributes", {})
            cnty = (a.get("countyName") or county_hint or "Colorado").title()
            acc = a.get("account") or a.get("parcel_id") or q
            act = float(a.get("apprValTot") or 0.0)
            ass = float(a.get("asedValTot") or 0.0)
            rec = {
                "county": cnty,
                "state": "CO",
                "parcel": str(acc),
                "state_parcel_id": str(a.get("parcel_id") or ""),
                "owner": str(a.get("owner") or "N/A"),
                "situs_address": f"{a.get('situsAdd') or ''} {a.get('sitAddCty') or ''}".strip(),
                "legal": str(a.get("legalDesc") or ""),
                "acres": round(float(a.get("landAcres") or 0.0), 2),
                "actual_val": act,
                "assessed_val": ass,
                "land_val": 0.0,
                "imp_val": 0.0,
                "prop_type": str(a.get("landUseDsc") or a.get("zoningDesc") or "Colorado Parcel"),
                "assessor_link": str(a.get("URL") or COUNTY_ASSESSOR_URLS.get(cnty.lower(), "https://gis.colorado.gov")).format(parcel=acc),
                "treasurer_link": COUNTY_TREASURER_URLS.get(cnty.lower(), f"https://{cnty.lower()}countyco-treasurer.tylerhost.net/treasurer/treasurerweb/account.jsp?account={acc}").format(parcel=acc),
                "is_live_gis_only": True
            }
            results.append(rec)
        return results
    except Exception:
        return []


def fetch_indiana_statewide_gis(parcel_str):
    """Query Official IndianaMap Statewide Parcel Boundaries FeatureServer."""
    url = "https://gisdata.in.gov/server/rest/services/Hosted/Parcel_Boundaries_of_Indiana_Current/FeatureServer/0/query"
    q = str(parcel_str).strip().replace("'", "")
    params = {
        "where": f"state_parcel_id LIKE '%{q}%' OR parcel_id LIKE '%{q}%'",
        "outFields": "state_parcel_id,parcel_id,prop_add,prop_city,prop_state,prop_zip,dlgf_prop_class_code,county_id,tax_county,tax_township,SHAPE__Area",
        "resultRecordCount": 5,
        "returnGeometry": "false",
        "f": "json"
    }
    try:
        r = requests.get(url, params=params, timeout=10).json()
        return [f.get("attributes", {}) for f in r.get("features", [])]
    except Exception:
        return []


def grade_and_finalize_record(d):
    """Ensure every record has standardized underwriting metrics, property type, and links."""
    county = (d.get("county") or "Unknown").title()
    ck = county.lower().replace(" ", "")
    state = (d.get("state") or "CO").upper()
    parcel = str(d.get("parcel") or "").strip()

    face = float(d.get("face_amount") or d.get("full_payment_due") or d.get("total_billed") or 0.0)
    act = float(d.get("actual_val") or 0.0)
    land = float(d.get("land_val") or 0.0)
    imp = float(d.get("imp_val") or 0.0)
    ass = float(d.get("assessed_val") or 0.0)
    legal = str(d.get("legal_tyler") or d.get("legal") or "")
    legal_up = legal.upper()

    acres = float(d.get("acres") or 0.0)
    if acres <= 0:
        acres = parse_acreage_from_legal(legal_up)
    d["acres"] = acres

    tvr = round((face / act) * 100, 2) if (act > 0 and face > 0) else float(d.get("tvr_pct") or 0.0)
    d["tvr_pct"] = tvr
    if "est_1yr_interest_14pct" not in d:
        d["est_1yr_interest_14pct"] = round(face * 0.14, 2)

    classes_list = d.get("prop_classes") or []
    classes_str = " | ".join(classes_list).upper()
    codes = d.get("abstract_codes") or []

    if not d.get("assessor_link"):
        d["assessor_link"] = COUNTY_ASSESSOR_URLS.get(ck, "https://gis.colorado.gov").format(parcel=parcel)
    if not d.get("treasurer_link"):
        d["treasurer_link"] = COUNTY_TREASURER_URLS.get(ck, f"https://{ck}countyco-treasurer.tylerhost.net/treasurer/treasurerweb/account.jsp?account={parcel}").format(parcel=parcel)

    if state == "IN":
        d.setdefault("prop_type", "Indiana Sheriff Sale (Mortgage Foreclosure)")
        d.setdefault("grade", "Sheriff Sale")
        d.setdefault("bid_decision", f"SHERIFF FORECLOSURE AUCTION — Judgment / Opening Bid ${face:,.2f}")
        d.setdefault("why_pick", f"Fulton County Indiana Sheriff Sale ({d.get('sale_no', 'Foreclosure')}). Verify senior mortgages & title commitments prior to bidding.")
        return d

    # Check if already graded
    if d.get("grade") and d.get("bid_decision") and d.get("why_pick"):
        return d

    is_mineral_severed = (
        "5170" in codes
        or "SEVERED MINERAL" in classes_str
        or "MR ONLY" in legal_up
        or "MINERAL RIGHTS ONLY" in legal_up
        or "MINERALS ONLY" in legal_up
        or re.search(r'\bMRO\b|\bSRO\b', legal_up)
    )
    is_fractional = bool(re.search(r'\b[1-9]/[1-9][0-9]?\s*(?:INT|INTEREST|UND)\b|\bUND(?:IVIDED)?\s+(?:[1-9]/[1-9][0-9]?|\d+(?:\.\d+)?%)|\bUNDIVIDED\b|(?:^|\s|\()(?:\d*\.\d+|\d{1,2})%(?:\s|$|\))', legal_up))
    is_ag = any(str(c).startswith("41") or str(c).startswith("42") for c in codes) or any(w in classes_str for w in ["IRRIGATED", "GRAZING", "MEADOW", "FARM", "RANCH", "AG "])
    is_mining = "5140" in codes or "MINING" in classes_str or "LODE" in legal_up or "MS#" in legal_up

    if not d.get("prop_type"):
        if is_mineral_severed:
            d["prop_type"] = "Severed Mineral Rights (5170)"
        elif is_ag and imp > 0:
            d["prop_type"] = "Agricultural Ranch / Farm + Residence"
        elif is_ag:
            d["prop_type"] = "Agricultural Land (Irrigated / Grazing / Meadow)"
        elif imp > 0:
            d["prop_type"] = "Improved Residential / Commercial"
        elif is_mining:
            d["prop_type"] = "Patented Mining Claim"
        else:
            d["prop_type"] = "Vacant Land / Lot"

    prop_type = d["prop_type"]
    if is_mineral_severed:
        d["grade"] = "Grade F (Trap)"
        d["bid_decision"] = "DO NOT BID — Severed Mineral Rights Trap"
        d["rec_max_proxy"] = 0.0
        d["why_pick"] = f"TRAP: Severed Mineral Interest ({classes_str or 'MR ONLY'}). No surface rights or buildable land. Actual Value is only ${act:,.0f}."
    elif is_fractional and act < 10000:
        d["grade"] = "Grade D (Trap)"
        d["bid_decision"] = "DO NOT BID — Fractional Interest Trap"
        d["rec_max_proxy"] = 0.0
        d["why_pick"] = f"TRAP: Fractional undivided interest ({legal[:60]}) with low actual value (${act:,.0f})."
    elif act <= 0 or (face > 0 and tvr > 10.0):
        d["grade"] = "Grade D (Avoid)"
        d["bid_decision"] = "AVOID — Low Equity / High TVR"
        d["rec_max_proxy"] = 0.0
        d["why_pick"] = f"Low collateral cushion (Actual Value ${act:,.0f}, TVR {tvr:.2f}%)."
    elif (imp > 0 and act >= 50000 and tvr <= 3.5 and not is_fractional) or (is_ag and act >= 35000 and tvr <= 4.0 and not is_fractional) or (act >= 40000 and tvr <= 2.5 and not is_fractional):
        d["grade"] = "Grade A"
        d["bid_decision"] = "STRONG BID (Grade A)"
        d["rec_max_proxy"] = round(face * 1.15, 2)
        d["why_pick"] = f"High-equity {prop_type} (${act:,.0f} Actual Value; Land ${land:,.0f} + Imps ${imp:,.0f}) with {tvr:.2f}% TVR ({classes_str})."
    elif act >= 12000 and tvr <= 5.0 and not is_fractional:
        d["grade"] = "Grade B"
        d["bid_decision"] = "QUALIFIED BID (Grade B)"
        d["rec_max_proxy"] = round(face * 1.08, 2)
        d["why_pick"] = f"Solid {prop_type} (${act:,.0f} Actual Value) at {tvr:.2f}% TVR ({classes_str})."
    else:
        d["grade"] = "Grade C"
        d["bid_decision"] = "SPECULATIVE / FACE BID ONLY"
        d["rec_max_proxy"] = round(face, 2)
        d["why_pick"] = f"Modest value (${act:,.0f} Actual Value, TVR {tvr:.2f}%) — {classes_str or prop_type}."

    return d


def _parse_county_state_from_filename(fname):
    """Extract (County, State) from raw spreadsheet filename."""
    base = os.path.basename(fname)
    m = re.search(r'([A-Za-z\s]+?)\s+County\s+(Colorado|Indiana|Maryland|CO|IN|MD)', base, re.I)
    if m:
        raw_c = m.group(1).strip()
        # Strip leading year if present
        raw_c = re.sub(r'^\d{4}\s+', '', raw_c).strip()
        raw_s = m.group(2).strip().lower()
        return raw_c.title(), STATE_NAMES_MAP.get(raw_s, raw_s.upper())
    m2 = re.search(r'^([A-Za-z]+)_County_(CO|IN|MD)', base, re.I)
    if m2:
        return m2.group(1).title(), m2.group(2).upper()
    return None, None


def ensure_index_loaded(force=False):
    """Scan RealEstateResearch/raw/ and RealEstateResearch/scratch/ to index all counties & parcels."""
    files_to_watch = glob.glob(os.path.join(RAW_DIR, "*.xlsx")) + glob.glob(os.path.join( SCRATCH_DIR, "*_graded_deals.json"))
    sig = tuple(sorted((f, os.path.getmtime(f)) for f in files_to_watch if os.path.exists(f)))
    if not force and _INDEX_CACHE["mtime_sig"] == sig and _INDEX_CACHE["by_county"]:
        return _INDEX_CACHE

    by_county = {}
    by_parcel = {}
    counties_meta = {}

    def _add_record(rec):
        if not isinstance(rec, dict):
            return
        cnty = (rec.get("county") or "").strip().title()
        st = (rec.get("state") or "CO").strip().upper()
        if not cnty:
            return
        ck = cnty.lower()
        by_county.setdefault(ck, [])
        # Check if parcel already in county list; if so, only fill in missing fields so enriched caches aren't overwritten
        p_norm = _norm_parcel(rec.get("parcel"))
        existing = next((x for x in by_county[ck] if _norm_parcel(x.get("parcel")) == p_norm), None)
        if existing:
            for k, v in rec.items():
                if existing.get(k) in (None, "", 0, 0.0, [], {}) and v not in (None, "", 0, 0.0, [], {}):
                    existing[k] = v
            target_rec = grade_and_finalize_record(existing)
        else:
            target_rec = grade_and_finalize_record(rec)
            by_county[ck].append(target_rec)

        # Index by parcel number (and state_parcel_id if present, and split multi-parcels)
        raw_p_str = str(target_rec.get("parcel") or "")
        tokens = [t.strip() for t in re.split(r'[\s,;]+', raw_p_str) if len(t.strip()) >= 4]
        if target_rec.get("state_parcel_id"):
            tokens.append(str(target_rec["state_parcel_id"]).strip())
        for tok in set(tokens):
            tn = _norm_parcel(tok)
            if tn:
                lst = by_parcel.setdefault(tn, [])
                if target_rec not in lst:
                    lst.append(target_rec)

    # 1. Load pre-enriched JSON caches in scratch/ first (Gunnison, Gilpin, Conejos, etc.)
    json_map = {
        "gunnison": ("Gunnison", "CO", os.path.join(SCRATCH_DIR, "gunnison_2026_graded_deals.json")),
        "gilpin": ("Gilpin", "CO", os.path.join(SCRATCH_DIR, "gilpin_2026_graded_deals.json")),
        "conejos": ("Conejos", "CO", os.path.join(SCRATCH_DIR, "conejos_2026_graded_deals.json")),
    }
    for ck, (c_title, st, jpath) in json_map.items():
        if os.path.exists(jpath):
            try:
                with open(jpath, "r", encoding="utf-8") as f:
                    data_obj = json.load(f)
                if isinstance(data_obj, dict):
                    arr = data_obj.get("parcels") or data_obj.get("all_deals") or data_obj.get("deals") or []
                else:
                    arr = data_obj
                counties_meta[ck] = {"county": c_title, "state": st, "source": os.path.basename(jpath)}
                for item in arr:
                    if isinstance(item, dict):
                        item["county"] = c_title
                        item["state"] = st
                        # Normalize Gunnison / Gilpin field aliases into unified schema
                        if not item.get("parcel") and item.get("parcel_number"):
                            item["parcel"] = item["parcel_number"]
                        if not item.get("state_parcel_id"):
                            item["state_parcel_id"] = item.get("apn_pin") or item.get("pin") or ""
                        if not item.get("sale_no") and item.get("sale_id"):
                            item["sale_no"] = item["sale_id"]
                        if not item.get("face_amount") and item.get("face") is not None:
                            item["face_amount"] = item["face"]
                        if not item.get("actual_val"):
                            item["actual_val"] = item.get("total_actual_value") or item.get("total_actual") or 0.0
                        if not item.get("land_val") and item.get("land_actual_value") is not None:
                            item["land_val"] = item["land_actual_value"]
                        if not item.get("imp_val") and item.get("imps_actual_value") is not None:
                            item["imp_val"] = item["imps_actual_value"]
                        if not item.get("assessed_val") and item.get("total_assessed") is not None:
                            item["assessed_val"] = item["total_assessed"]
                        if not item.get("rec_max_proxy"):
                            item["rec_max_proxy"] = item.get("recommended_max_proxy_bid") or item.get("rec_proxy") or 0.0
                        if not item.get("owner"):
                            item["owner"] = item.get("owner_name") or item.get("owners") or ""
                        if not item.get("situs_address") and item.get("situs"):
                            item["situs_address"] = item["situs"]
                        if not item.get("why_pick"):
                            item["why_pick"] = item.get("underwriting_notes") or item.get("rationale") or ""
                        if not item.get("bid_decision") and item.get("bid_recommendation"):
                            item["bid_decision"] = item["bid_recommendation"]
                        if not item.get("assessor_link") and item.get("assessor_url"):
                            item["assessor_link"] = item["assessor_url"]
                        if not item.get("treasurer_link") and item.get("treasurer_url"):
                            item["treasurer_link"] = item["treasurer_url"]
                        g_raw = str(item.get("grade") or "")
                        if g_raw in ("A", "B", "C", "D", "F"):
                            item["grade"] = f"Grade {g_raw}" + (" (Trap)" if g_raw == "F" else "")
                        _add_record(item)
            except Exception as e:
                print(f"[MultiStateEngine] Error loading {jpath}: {e}")

    # 2. Scan raw/*Full Export.xlsx files so ANY new county export dropped in raw/ is automatically indexed!
    for xfile in sorted(glob.glob(os.path.join(RAW_DIR, "*Full Export*.xlsx"))):
        c_title, st = _parse_county_state_from_filename(xfile)
        if not c_title:
            continue
        ck = c_title.lower()
        counties_meta.setdefault(ck, {"county": c_title, "state": st, "source": os.path.basename(xfile)})
        try:
            wb = openpyxl.load_workbook(xfile, read_only=True, data_only=True)
            ws = wb.active
            for r_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
                if r_idx <= 2 or not row:
                    continue
                if not row[0] and not (len(row) > 3 and row[3]):
                    continue
                parcel_raw = str(row[3] or "").strip()
                if not parcel_raw:
                    continue
                rec = {
                    "county": c_title,
                    "state": st,
                    "item_id": str(row[0] or "").strip(),
                    "sale_no": str(row[1] or "").strip(),
                    "batch": str(row[2] or "").strip(),
                    "parcel": parcel_raw.upper(),
                    "face_amount": float(row[4] or 0.0) if row[4] is not None else 0.0,
                    "district": str(row[9] or "").strip() if len(row) > 9 else "",
                    "owner": str(row[10] or "").strip() if len(row) > 10 else "",
                    "legal": str(row[11] or "").strip() if len(row) > 11 else "",
                    "address": str(row[12] or "").strip() if len(row) > 12 else "",
                }
                _add_record(rec)
            wb.close()
        except Exception as e:
            print(f"[MultiStateEngine] Error indexing {xfile}: {e}")

    _INDEX_CACHE["mtime_sig"] = sig
    _INDEX_CACHE["by_county"] = by_county
    _INDEX_CACHE["by_parcel"] = by_parcel
    _INDEX_CACHE["counties_meta"] = counties_meta
    return _INDEX_CACHE


def parse_query_intent(raw_query):
    """
    Extract optional county/state hint and cleaned query from user text.
    Examples:
      'R017432' -> (None, None, 'R017432')
      'Conejos R017432' -> ('conejos', 'CO', 'R017432')
      'R017432 Conejos County' -> ('conejos', 'CO', 'R017432')
      'Gilpin R003229' -> ('gilpin', 'CO', 'R003229')
    """
    idx = ensure_index_loaded()
    q = str(raw_query or "").strip()
    county_hint = None
    state_hint = None

    known_counties = set(idx["counties_meta"].keys()) | set(COLORADO_TYLER_SUBDOMAINS.keys()) | {"gunnison", "fulton"}
    for ck in sorted(known_counties, key=len, reverse=True):
        pat = rf'\b{re.escape(ck)}(?:\s+county)?\b'
        if re.search(pat, q, re.I):
            county_hint = ck
            q = re.sub(pat, ' ', q, flags=re.I).strip()
            if ck in idx["counties_meta"]:
                state_hint = idx["counties_meta"][ck]["state"]
            elif ck == "fulton":
                state_hint = "IN"
            else:
                state_hint = "CO"
            break

    # Strip trailing/leading state code if county was matched
    if county_hint:
        q = re.sub(r'^(?:CO|IN|MD|Colorado|Indiana|Maryland)\b|\b(?:CO|IN|MD|Colorado|Indiana|Maryland)$', '', q, flags=re.I).strip(" ,;-")

    return county_hint, state_hint, (q or raw_query.strip())


def is_non_maryland_parcel_pattern(query_str, county_hint=None, state_hint=None):
    """
    Returns True if the query is clearly a Colorado or Indiana parcel/account ID or county,
    preventing false fallback to Maryland SDAT.
    """
    if county_hint or (state_hint and state_hint != "MD"):
        return True
    q = str(query_str or "").strip().upper()
    # Colorado Assessor Account pattern: R017432, R003229, N011510, M001234, P001234, or 12-digit CO schedule/parcel
    if re.match(r'^[RNMP]\d{4,12}$', q):
        return True
    # Gunnison 12-digit hyphenated parcel e.g. 3701-000-00-001
    if re.match(r'^\d{4}-\d{3}-\d{2}-\d{3}$', q):
        return True
    # Indiana 18-digit state parcel ID e.g. 25-12-19-200-001.012-004
    if re.match(r'^\d{2}-\d{2}-\d{2}-\d{3}-\d{3}\.\d{3}-\d{3}', q):
        return True
    return False


def search_parcel_intelligent(raw_query, county_override=None):
    """
    Master multi-state, multi-county parcel & address resolver.
    Returns a list of matched and live-enriched parcel dicts.
    """
    idx = ensure_index_loaded()
    county_hint, state_hint, cleaned_q = parse_query_intent(raw_query)
    if county_override:
        county_hint = county_override.lower().strip()
        if county_hint in idx["counties_meta"]:
            state_hint = idx["counties_meta"][county_hint]["state"]

    q_up = cleaned_q.strip().upper()
    q_norm = _norm_parcel(q_up)
    matches = []

    # 1. Exact Parcel / Account ID Match across indexed spreadsheets
    if q_norm in idx["by_parcel"]:
        candidates = idx["by_parcel"][q_norm]
        if county_hint:
            candidates = [c for c in candidates if c.get("county", "").lower() == county_hint] or candidates
        for c in candidates:
            # If this record came from a raw spreadsheet and hasn't had live TylerHost valuation fetched yet, enrich it live!
            if c.get("state") == "CO" and float(c.get("actual_val") or 0) == 0 and not c.get("prop_classes"):
                live = fetch_tylerhost_live(c.get("county", ""), c.get("parcel", ""))
                if live:
                    c.update({k: v for k, v in live.items() if v not in (None, "", 0, 0.0, [])})
                    grade_and_finalize_record(c)
            matches.append(c)
        return matches

    # 2. Substring / Sale # / Owner / Address / Legal search within indexed counties
    search_counties = [county_hint] if (county_hint and county_hint in idx["by_county"]) else list(idx["by_county"].keys())
    if q_up.startswith("SALE"):
        s_num = re.sub(r"[^0-9A-Z-]", "", q_up.replace("SALE", ""))
        for ck in search_counties:
            for d in idx["by_county"][ck]:
                if str(d.get("sale_no", "")).upper() == s_num:
                    matches.append(d)
        if matches:
            return matches

    for ck in search_counties:
        for d in idx["by_county"][ck]:
            p_str = str(d.get("parcel", "")).upper()
            sp_str = str(d.get("state_parcel_id", "")).upper()
            addr = str(d.get("situs_address") or d.get("address") or "").upper()
            own = str(d.get("owner") or d.get("owners_tyler") or "").upper()
            leg = str(d.get("legal") or "").upper()
            if (len(q_norm) >= 4 and (q_norm in _norm_parcel(p_str) or (sp_str and q_norm in _norm_parcel(sp_str)))) \
               or (len(q_up) >= 4 and (q_up in addr or q_up in own or q_up in leg)):
                matches.append(d)
                if len(matches) >= 5:
                    break
        if len(matches) >= 5:
            break

    if matches:
        for c in matches:
            if c.get("state") == "CO" and float(c.get("actual_val") or 0) == 0 and not c.get("prop_classes"):
                live = fetch_tylerhost_live(c.get("county", ""), c.get("parcel", ""))
                if live:
                    c.update({k: v for k, v in live.items() if v not in (None, "", 0, 0.0, [])})
                    grade_and_finalize_record(c)
        return matches

    # 3. Not in any spreadsheet -> Perform Live County Portal & Statewide GIS Lookup!
    if re.match(r'^[RNMP]\d{4,12}$', q_up):
        # Try county_hint first, or probe Conejos & Gilpin TylerHost + Colorado Statewide GIS
        probe_counties = [county_hint] if county_hint else ["conejos", "gilpin"]
        for ck in probe_counties:
            if ck in COLORADO_TYLER_SUBDOMAINS:
                live = fetch_tylerhost_live(ck, q_up)
                if live and (live.get("owner") or live.get("actual_val") or live.get("state_parcel_id")):
                    live["is_non_sale_live"] = True
                    matches.append(grade_and_finalize_record(live))
        if not matches:
            gis_hits = fetch_colorado_statewide_gis(q_up, county_hint=county_hint)
            for gh in gis_hits:
                matches.append(grade_and_finalize_record(gh))

    return matches


def format_parcel_dossier_html(d):
    """Render a rich, state- and county-specific HTML card for Telegram with internal details and explicit URLs."""
    county = (d.get("county") or "Unknown").upper()
    state = (d.get("state") or "CO").upper()
    parcel = html.escape(str(d.get("parcel") or "N/A"))
    state_pid = html.escape(str(d.get("state_parcel_id") or d.get("pin") or d.get("apn_pin") or ""))
    sale_no = html.escape(str(d.get("sale_no") or d.get("sale_id") or "N/A"))
    item_id = html.escape(str(d.get("item_id") or "N/A"))
    batch = html.escape(str(d.get("batch") or ""))
    owner = html.escape(str(d.get("owners_tyler") or d.get("owner") or d.get("owners") or "N/A"))
    situs = html.escape(str(d.get("situs_address") or d.get("situs") or d.get("address") or "Unassigned / Rural Parcel"))
    mailing = html.escape(str(d.get("mailing_address") or ""))
    subd = html.escape(str(d.get("subd") or d.get("subdivision") or ""))
    tax_dist = html.escape(str(d.get("tax_district") or d.get("district") or ""))
    legal = html.escape(str(d.get("legal_tyler") or d.get("legal") or "N/A"))
    prop_type = html.escape(str(d.get("prop_type") or "Real Property"))
    classes_str = html.escape(", ".join(d.get("prop_classes") or []) or str(d.get("prop_code_desc") or ""))

    grade = str(d.get("grade") or "Unrated")
    decision = html.escape(str(d.get("bid_decision") or "Verify Due Diligence"))
    why = html.escape(str(d.get("why_pick") or ""))

    face = float(d.get("face_amount") or d.get("full_payment_due") or 0.0)
    proxy = float(d.get("rec_max_proxy") or 0.0)
    act = float(d.get("actual_val") or d.get("total_actual_val") or 0.0)
    land = float(d.get("land_val") or 0.0)
    imp = float(d.get("imp_val") or 0.0)
    ass = float(d.get("assessed_val") or 0.0)
    acres = float(d.get("acres") or 0.0)
    sqft = float(d.get("sqft") or 0.0)
    tvr = float(d.get("tvr_pct") or 0.0)
    int_1yr = float(d.get("est_1yr_interest_14pct") or round(face * 0.14, 2))
    mill = float(d.get("mill_levy") or 0.0)
    total_billed = float(d.get("total_billed") or d.get("est_tax") or 0.0)
    full_due = float(d.get("full_payment_due") or face)

    lat = d.get("lat")
    lon = d.get("lon")
    gmaps_link = d.get("google_maps_url") or (f"https://www.google.com/maps?q={lat},{lon}" if (lat and lon) else "")
    assessor_link = d.get("assessor_link") or "#"
    treasurer_link = d.get("treasurer_link") or "#"

    if "Grade A" in grade:
        badge = "🟢"
    elif "Grade B" in grade:
        badge = "🟡"
    elif "Grade C" in grade:
        badge = "🟠"
    elif "Sheriff" in grade:
        badge = "🏛️"
    else:
        badge = "🔴"

    header_title = f"🏔️ <b>{county} COUNTY, {state} — 2026 TAX LIEN DOSSIER</b>"
    if state == "IN":
        header_title = f"🏛️ <b>{county} COUNTY, {state} — SHERIFF SALE DOSSIER</b>"
    elif d.get("is_non_sale_live") or d.get("is_live_gis_only"):
        header_title = f"🏔️ <b>{county} COUNTY, {state} — LIVE COUNTY RECORD</b>"

    sqft_str = f" ({sqft:,.0f} sq ft)" if sqft > 0 else ""
    gps_str = f"<code>{lat}, {lon}</code>" if (lat and lon) else "N/A"

    lines = [
        header_title,
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏷️ <b>Parcel #:</b> <code>{parcel}</code> (Sale ID: <code>{sale_no}</code> | Item: <code>{item_id}</code>{f' | {batch}' if batch else ''})",
        f"🔢 <b>12-Digit PIN:</b> <code>{state_pid or 'N/A'}</code>",
        f"{badge} <b>Underwriting Grade:</b> <b>{html.escape(grade)}</b> — <b>{decision}</b>",
        "",
        f"📍 <b>Situs Address:</b> <code>{situs}</code>",
    ]
    if subd:
        lines.append(f"🏘️ <b>Subdivision:</b> {subd}")
    if tax_dist or mill > 0:
        lines.append(f"🏛️ <b>Tax District / Mill Levy:</b> {tax_dist or 'County District'} (Mill Levy: <b>{mill:.3f}</b>)")
    lines.extend([
        f"🏗️ <b>Class / Codes:</b> {prop_type}" + (f" (<code>{classes_str}</code>)" if classes_str else ""),
        f"📐 <b>Dimensions:</b> <b>{acres:.2f} Acres</b>{sqft_str} | <b>GPS:</b> {gps_str}",
        f"👤 <b>Owner:</b> <code>{owner}</code>" + (f"\n📬 <b>Mailing:</b> <code>{mailing}</code>" if mailing else ""),
        "",
        f"💰 <b>2026 {county} COUNTY VALUATION &amp; LIEN METRICS:</b>",
    ])

    if state == "IN":
        lines.extend([
            f"• <b>Sheriff Sale Judgment / Face Amount:</b> <b>${face:,.2f}</b>",
            f"• <b>Batch:</b> {batch or 'N/A'}",
        ])
    else:
        lines.extend([
            f"• <b>Face Bid (Direct Bid):</b> <b>${face:,.2f}</b>" + (f" (Annual Billed Tax: ${total_billed:,.2f} | Payoff Due: ${full_due:,.2f})" if total_billed > 0 else ""),
            f"• <b>Rec. Max Proxy Bid:</b> <b>${proxy:,.2f}</b>",
            f"• <b>2026 Land Value:</b> <b>${land:,.0f}</b>",
            f"• <b>2026 Imps Value:</b> <b>${imp:,.0f}</b>",
            f"• <b>2026 Total Actual Value:</b> <b>${act:,.0f}</b> (Assessed: <code>${ass:,.0f}</code>)",
            f"• <b>Tax-to-Value Ratio (TVR):</b> <b>{tvr:.2f}%</b>",
            f"• <b>Est. 1-Yr Interest (@ 14%):</b> <b>${int_1yr:,.2f}</b>",
        ])

    lines.extend([
        "",
        f"📜 <b>UNDERWRITING &amp; LEGAL:</b>",
        f"• <b>Rationale:</b> {why}",
        f"• <b>Legal:</b> <code>{legal[:260]}</code>",
        "",
        f"🔗 [Assessor Card]({html.escape(assessor_link)}) | [Treasurer Tax Account]({html.escape(treasurer_link)})"
    ])
    if gmaps_link:
        lines.append(f"📍 [Google Maps Location]({html.escape(gmaps_link)})")
    return "\n".join(lines)


def format_county_summary_html(county_key):
    """Render a summary of top Grade A & B deals and traps for a given county."""
    idx = ensure_index_loaded()
    ck = str(county_key or "").lower().strip()
    deals = idx["by_county"].get(ck, [])
    meta = idx["counties_meta"].get(ck, {"county": ck.title(), "state": "CO"})
    c_name = meta["county"].upper()
    st = meta["state"].upper()

    if not deals:
        return f"❌ No indexed parcels found for <b>{html.escape(ck.title())} County</b>."

    if st == "IN":
        lines = [
            f"🏛️ <b>{c_name} COUNTY, {st} — SHERIFF SALE SUMMARY ({len(deals)} Parcels)</b>",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
        for i, d in enumerate(deals[:10], 1):
            p = html.escape(str(d.get("parcel") or ""))
            s = html.escape(str(d.get("sale_no") or ""))
            f_amt = float(d.get("face_amount") or 0.0)
            addr = html.escape(str(d.get("address") or "").replace("\n", ", "))
            own = html.escape(str(d.get("owner") or ""))
            lines.append(
                f"{i}. <code>{p}</code> (Case <code>{s}</code>)\n"
                f"   💰 Judgment/Face: <b>${f_amt:,.2f}</b> | 👤 {own}\n"
                f"   📍 {addr}"
            )
        lines.append("\n💡 <i>Send any Parcel # above for the full Sheriff Sale Dossier!</i>")
        return "\n".join(lines)

    grade_a = [d for d in deals if "Grade A" in str(d.get("grade", ""))]
    grade_b = [d for d in deals if "Grade B" in str(d.get("grade", ""))]
    traps = [d for d in deals if "Trap" in str(d.get("grade", ""))]

    lines = [
        f"🏔️ <b>{c_name} COUNTY, {st} — 2026 TAX LIEN SUMMARY ({len(deals)} Parcels)</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🟢 <b>Grade A (Strong Bid):</b> {len(grade_a)} parcels",
        f"🟡 <b>Grade B (Qualified Bid):</b> {len(grade_b)} parcels",
        f"🔴 <b>Severed Mineral / Fractional Traps:</b> {len(traps)} parcels",
        "",
        f"🏆 <b>TOP {c_name} COUNTY DEALS TO BID:</b>",
    ]
    top_list = (grade_a + grade_b)[:10]
    for i, d in enumerate(top_list, 1):
        p = html.escape(str(d.get("parcel") or ""))
        s = html.escape(str(d.get("sale_no") or ""))
        f_amt = float(d.get("face_amount") or 0.0)
        act = float(d.get("actual_val") or d.get("total_actual_val") or 0.0)
        tvr = float(d.get("tvr_pct") or 0.0)
        pt = html.escape(str(d.get("prop_type") or "")[:30])
        ac = float(d.get("acres") or 0.0)
        ac_str = f" | {ac:.1f} Ac" if ac > 0 else ""
        lines.append(
            f"{i}. <code>{p}</code> (Sale #{s}) — <b>{html.escape(str(d.get('grade')))}</b>\n"
            f"   💵 Face: <b>${f_amt:,.2f}</b> | 🏦 Val: <b>${act:,.0f}</b> (TVR {tvr:.2f}%)\n"
            f"   🏷️ {pt}{ac_str}"
        )
    lines.append(f"\n💡 <i>Send any Parcel ID (e.g. <code>{top_list[0]['parcel'] if top_list else 'R017432'}</code>) for the full {c_name.title()} County Dossier!</i>")
    return "\n".join(lines)


def format_all_counties_overview_html():
    """List all indexed states, counties, parcel counts, and commands."""
    idx = ensure_index_loaded()
    lines = [
        "🗺️ <b>ACTIVE MULTI-STATE &amp; COUNTY TAX SALE DATABASES</b>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    for ck, meta in sorted(idx["counties_meta"].items()):
        deals = idx["by_county"].get(ck, [])
        c_title = meta["county"]
        st = meta["state"]
        ga = sum(1 for d in deals if "Grade A" in str(d.get("grade", "")))
        gb = sum(1 for d in deals if "Grade B" in str(d.get("grade", "")))
        tr = sum(1 for d in deals if "Trap" in str(d.get("grade", "")))
        if st == "CO":
            lines.append(
                f"🏔️ <b>{c_title} County, {st}</b> (<code>/{ck}</code>) — <b>{len(deals)} parcels</b>\n"
                f"   🟢 Grade A: {ga} | 🟡 Grade B: {gb} | 🔴 Traps: {tr}"
            )
        else:
            lines.append(
                f"🏛️ <b>{c_title} County, {st}</b> (<code>/{ck}</code>) — <b>{len(deals)} foreclosure parcels</b>"
            )
    lines.extend([
        "🦀 <b>Maryland Statewide SDAT &amp; County OTC</b> (24 Jurisdictions)",
        "",
        "💡 <b>How Intelligent Search Works:</b>",
        "• Send any Parcel ID directly (e.g. <code>R017432</code>, <code>R001364</code>, <code>R003229</code>, <code>R074851</code>, <code>25-12-19-200-001.012-004</code>).",
        "• Or specify County + Parcel (e.g. <code>Conejos R017432</code>, <code>Gilpin R003229</code>, <code>Gunnison R074851</code>).",
        "• Drop any new County `.xlsx` export into `raw/` or Telegram chat and it is auto-indexed immediately!"
    ])
    return "\n".join(lines)

