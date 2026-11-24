"""
Maryland Title Search & Confluence Intelligence Engine
Performs deep deed chain analysis, prior liber/folio tracing, plat book validation,
Title Confluence Scoring (0-100 / Grade A-F), and generates direct verification links
for MDLandRec.net and Maryland Judiciary Case Search.
"""

import urllib.parse
import re
from typing import Dict, Any, List, Tuple

# Maryland County Code mapping for MDLandRec and Court records
COUNTY_CODE_MAP = {
    "ALLE": {"code": "01", "name": "Allegany County", "circuit": "Allegany County Circuit Court"},
    "ANNE": {"code": "02", "name": "Anne Arundel County", "circuit": "Anne Arundel County Circuit Court"},
    "BALT_CITY": {"code": "03", "name": "Baltimore City", "circuit": "Baltimore City Circuit Court"},
    "BALT_CO": {"code": "04", "name": "Baltimore County", "circuit": "Baltimore County Circuit Court"},
    "CALV": {"code": "05", "name": "Calvert County", "circuit": "Calvert County Circuit Court"},
    "CARO": {"code": "06", "name": "Caroline County", "circuit": "Caroline County Circuit Court"},
    "CARR": {"code": "07", "name": "Carroll County", "circuit": "Carroll County Circuit Court"},
    "CECI": {"code": "08", "name": "Cecil County", "circuit": "Cecil County Circuit Court"},
    "CHAR": {"code": "09", "name": "Charles County", "circuit": "Charles County Circuit Court"},
    "DORC": {"code": "10", "name": "Dorchester County", "circuit": "Dorchester County Circuit Court"},
    "FRED": {"code": "11", "name": "Frederick County", "circuit": "Frederick County Circuit Court"},
    "GARR": {"code": "12", "name": "Garrett County", "circuit": "Garrett County Circuit Court"},
    "HARF": {"code": "13", "name": "Harford County", "circuit": "Harford County Circuit Court"},
    "HOWA": {"code": "14", "name": "Howard County", "circuit": "Howard County Circuit Court"},
    "KENT": {"code": "15", "name": "Kent County", "circuit": "Kent County Circuit Court"},
    "MONT": {"code": "16", "name": "Montgomery County", "circuit": "Montgomery County Circuit Court"},
    "PRIN": {"code": "17", "name": "Prince George's County", "circuit": "Prince George's County Circuit Court"},
    "QUEE": {"code": "18", "name": "Queen Anne's County", "circuit": "Queen Anne's County Circuit Court"},
    "STMA": {"code": "19", "name": "St. Mary's County", "circuit": "St. Mary's County Circuit Court"},
    "SOME": {"code": "20", "name": "Somerset County", "circuit": "Somerset County Circuit Court"},
    "TALB": {"code": "21", "name": "Talbot County", "circuit": "Talbot County Circuit Court"},
    "WASH": {"code": "22", "name": "Washington County", "circuit": "Washington County Circuit Court"},
    "WICO": {"code": "23", "name": "Wicomico County", "circuit": "Wicomico County Circuit Court"},
    "WORC": {"code": "24", "name": "Worcester County", "circuit": "Worcester County Circuit Court"}
}

def clean_val(val: Any) -> str:
    if val is None or val == "" or str(val).lower() in ["none", "null", "nan"]:
        return "N/A"
    return str(val).strip()

def analyze_maryland_title(prop: Dict[str, Any], tax_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Analyzes property deed chain, legal description, ownership structure,
    and calculates a Title Confluence & Risk Score.
    """
    tax_info = tax_info or {}
    jurs = prop.get("jurisdiction", "ANNE").upper()
    county_meta = COUNTY_CODE_MAP.get(jurs, {"code": "02", "name": "Anne Arundel County", "circuit": "Circuit Court"})
    
    trans = prop.get("transfer_history", {})
    legal = prop.get("legal", {})
    owner_mail = prop.get("owner_mailing", {})
    val = prop.get("valuation", {})
    
    # Deed and chain data
    curr_liber = clean_val(trans.get("deed_liber"))
    curr_folio = clean_val(trans.get("deed_folio"))
    prior_liber = clean_val(trans.get("prior_liber"))
    prior_folio = clean_val(trans.get("prior_folio"))
    trans_date = clean_val(trans.get("transfer_date"))
    
    raw_price = trans.get("consideration_price")
    try:
        price_num = float(raw_price) if raw_price is not None and str(raw_price).strip() != "" else None
    except (ValueError, TypeError):
        price_num = None
        
    tot_val = val.get("total_value")
    try:
        tot_val_num = float(tot_val) if tot_val is not None else 0.0
    except (ValueError, TypeError):
        tot_val_num = 0.0

    # Plat and subdivision data
    subdiv = clean_val(legal.get("subdivision"))
    lot = clean_val(legal.get("lot"))
    sec = clean_val(legal.get("section"))
    blk = clean_val(legal.get("block"))
    map_no = clean_val(legal.get("map"))
    grid_no = clean_val(legal.get("grid"))
    parcel_no = clean_val(legal.get("parcel"))
    legal_desc = f"{clean_val(legal.get('legal1'))} {clean_val(legal.get('legal2'))} {clean_val(legal.get('legal3'))}".replace("N/A", "").strip()
    
    # Ownership & Absentee
    owner_name = tax_info.get("owner_of_record") or clean_val(owner_mail.get("line1"))
    if owner_name == "N/A" and prop.get("owner"):
        owner_name = prop.get("owner")
    is_absentee = owner_mail.get("is_absentee", False)
    owner_state = clean_val(owner_mail.get("state")).upper()
    is_out_of_state = (owner_state != "MD" and owner_state != "N/A")
    
    # Tax delinquency flag
    tax_sale_flag = tax_info.get("tax_sale_flag", False)
    
    # Detect Ownership Entity Type
    entity_type = "Individual / Private Party"
    owner_upper = owner_name.upper()
    if any(k in owner_upper for k in ["LLC", "INC", "CORP", "L.L.C.", "COMPANY", "LTD", "LP", "GROUP", "PARTNERS", "HOLDINGS", "DEVELOPMENT"]):
        entity_type = "Corporate Entity (LLC / Corp)"
    elif any(k in owner_upper for k in ["TRUST", "TRUSTEE", "ESTATE", "HEIRS", "ET AL", "SUCCESSOR", "DECEASED"]):
        entity_type = "Trust / Estate / Joint Heirs"
    elif any(k in owner_upper for k in ["CHURCH", "COUNTY", "MARYLAND", "COMMISSIONERS", "MAYOR", "HOUSING AUTHORITY", "BOARD OF EDUCATION"]):
        entity_type = "Public / Institutional / Exempt"

    # ==================== TITLE CONFLUENCE SCORING ====================
    score = 100
    risk_factors = []
    positive_factors = []
    
    # 1. Chain of Title Integrity
    has_curr_deed = (curr_liber != "N/A" and curr_folio != "N/A")
    has_prior_deed = (prior_liber != "N/A" and prior_folio != "N/A")
    
    if has_curr_deed:
        positive_factors.append(f"Recorded current deed verified (Liber {curr_liber} / Folio {curr_folio}).")
    else:
        score -= 25
        risk_factors.append("Missing or unindexed current deed Liber/Folio in county cadastre.")
        
    if has_prior_deed:
        positive_factors.append(f"Prior chain of title link verified (Prior Liber {prior_liber} / Folio {prior_folio}).")
    else:
        score -= 10
        risk_factors.append("Prior deed reference unindexed; full 30-year manual grantor search required on MDLandRec.")

    # 2. Consideration & Transfer Type
    if price_num is not None:
        if price_num == 0:
            score -= 15
            risk_factors.append("$0 Nominal Consideration: Deed of Gift, Family Transfer, or Estate Distribution (Heirship / Medicaid lien audit required).")
        elif price_num < 1000 and tot_val_num > 20000:
            score -= 10
            risk_factors.append(f"Sub-market consideration (${price_num:,.0f} vs ${tot_val_num:,.0f} assessment) indicates non-arms-length transaction.")
        else:
            positive_factors.append(f"Arms-length consideration recorded (${price_num:,.0f}).")
    else:
        score -= 5
        risk_factors.append("Consideration price unrecorded or missing from digital roll.")

    # 3. Platted Subdivision vs Raw Metes & Bounds
    is_platted = (subdiv != "N/A" or lot != "N/A" or blk != "N/A")
    if is_platted:
        positive_factors.append(f"Formal subdivision parcel (Subdivision: {subdiv}, Lot {lot}). Clean boundary definition.")
    else:
        score -= 12
        risk_factors.append("Unplatted metes-and-bounds or acreage tract; boundary survey & access easement verification required.")

    # 4. Absentee & Entity Complexity
    if entity_type == "Trust / Estate / Joint Heirs":
        score -= 15
        risk_factors.append("Estate/Heirship/Trust ownership: Requires Letters of Administration, Death Certificates, or Court Probate approval.")
    elif is_out_of_state:
        score -= 8
        risk_factors.append(f"Out-of-state absentee owner ({owner_state}): Higher risk of missing notice, delinquent sub-liens, or unprobated heirs.")
    elif is_absentee:
        score -= 3
        risk_factors.append("Non-owner occupied property (investor/rental holding).")

    # 5. Tax & Municipal Super-Priority Lien Risk
    if tax_sale_flag:
        score -= 25
        risk_factors.append("ACTIVE TAX DELINQUENCY / TAX SALE: Super-priority municipal tax lien attached to property.")
    else:
        positive_factors.append("No active tax sale certificate flags identified in county records.")

    # Clamp score between 0 and 100
    score = max(0, min(100, score))
    
    # Assign Grade
    if score >= 90:
        grade = "A"
        grade_desc = "Excellent / Clean Title Profile"
        badge = "🟢"
    elif score >= 75:
        grade = "B"
        grade_desc = "Good / Low-Risk Standard Title"
        badge = "🟢"
    elif score >= 60:
        grade = "C"
        grade_desc = "Moderate Risk / Title Curative Items Required"
        badge = "🟡"
    elif score >= 40:
        grade = "D"
        grade_desc = "High Risk / Clouded Title or Missing Probate"
        badge = "🟠"
    else:
        grade = "F"
        grade_desc = "Severe Defect Risk / Active Tax Sale or Broken Chain"
        badge = "🔴"

    # ==================== GENERATE VERIFICATION URLS ====================
    from sdat_engine import build_maryland_public_urls
    pub_urls = build_maryland_public_urls(
        acct_id=prop.get("account_id") or "",
        raw_sdat_url=prop.get("sdat_web_url") or "",
    )

    # 1. MDLandRec.net Reference (Maryland State Archives requires free login for deed images)
    mdlandrec_url = pub_urls["mdlandrec_url"]
    mdlandrec_query_note = f"County: {county_meta['name']} (Code {county_meta['code']}) | Book: {curr_liber} | Page: {curr_folio}"
    
    # 2. Maryland Judiciary Case Search URL
    # Query owner name in MD Judiciary Case Search
    encoded_owner = urllib.parse.quote(owner_name)
    judiciary_search_url = f"https://casesearch.courts.state.md.us/casesearch/processDisclaimer.jis"
    
    # 3. Public non-admin SDAT / iMAP & Plats URLs
    sdat_url = pub_urls["sdat_web_url"]
    sdat_search_url = pub_urls["sdat_search_url"]
    plats_url = pub_urls["plats_url"]

    # Required Contract Title Contingencies
    recommended_contingencies = [
        "Title Commitment with Standard ALTA Owner's Policy ($0 exceptions on prior mortgages/liens).",
        "Marketable fee-simple title conveyed via General Warranty Deed (or Special Warranty Deed for Corporate/REO).",
        "Clearance of all real estate taxes, water/sewer charges, and municipal benefit assessments through closing date."
    ]
    if price_num == 0 or "Estate" in entity_type:
        recommended_contingencies.append("Affidavit of Heirship & certified copy of probate court discharge / estate letters.")
    if not is_platted:
        recommended_contingencies.append("Boundary survey contingency verifying non-encroached access to public right-of-way.")

    return {
        "score": score,
        "grade": grade,
        "grade_desc": grade_desc,
        "badge": badge,
        "entity_type": entity_type,
        "owner_of_record": owner_name,
        "current_deed": {
            "liber": curr_liber,
            "folio": curr_folio,
            "transfer_date": trans_date,
            "consideration": price_num,
            "consideration_str": f"${price_num:,.0f}" if price_num is not None else "N/A"
        },
        "prior_deed": {
            "liber": prior_liber,
            "folio": prior_folio
        },
        "plat": {
            "subdivision": subdiv,
            "lot": lot,
            "section": sec,
            "block": blk,
            "map": map_no,
            "grid": grid_no,
            "parcel": parcel_no,
            "legal_description": legal_desc
        },
        "positive_factors": positive_factors,
        "risk_factors": risk_factors,
        "recommended_contingencies": recommended_contingencies,
        "county_meta": county_meta,
        "links": {
            "dossier_url": pub_urls["dossier_url"],
            "mdlandrec_url": mdlandrec_url,
            "mdlandrec_note": mdlandrec_query_note,
            "judiciary_url": judiciary_search_url,
            "sdat_url": sdat_url,
            "sdat_search_url": sdat_search_url,
            "plats_url": plats_url,
        }
    }

def format_title_telegram_card(prop: Dict[str, Any], title_res: Dict[str, Any]) -> str:
    """
    Formats an investor-friendly Title Search & Confluence Card for Telegram.
    """
    addr = prop.get("address", "Unknown Address")
    city = prop.get("city", "")
    acct = prop.get("account_id", "N/A")
    c_meta = title_res["county_meta"]
    
    score = title_res["score"]
    grade = title_res["grade"]
    desc = title_res["grade_desc"]
    badge = title_res["badge"]
    
    curr = title_res["current_deed"]
    prior = title_res["prior_deed"]
    plat = title_res["plat"]
    
    msg = f"📜 *MARYLAND TITLE SEARCH & CONFLUENCE REPORT*\n━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📍 *Property:* `{addr}, {city} MD`\n"
    msg += f"🏛 *Jurisdiction:* {c_meta['name']} (Code `{c_meta['code']}`)\n"
    msg += f"🏷 *SDAT Account ID:* `{acct}`\n"
    msg += f"👤 *Owner of Record:* `{title_res['owner_of_record']}`\n"
    msg += f"🏢 *Entity Structure:* {title_res['entity_type']}\n\n"
    
    msg += f"🎯 *TITLE CONFLUENCE SCORE: {badge} {score}/100 (Grade {grade})*\n"
    msg += f"Status: *{desc}*\n\n"
    
    msg += f"📑 *Recorded Deed & Chain of Title:*\n"
    msg += f"• *Current Deed:* Liber `{curr['liber']}` / Folio `{curr['folio']}`\n"
    msg += f"• *Recorded Date:* `{curr['transfer_date']}`\n"
    msg += f"• *Recorded Consideration:* `{curr['consideration_str']}`\n"
    if prior['liber'] != 'N/A' and prior['folio'] != 'N/A':
        msg += f"• *Prior Chain Link:* Liber `{prior['liber']}` / Folio `{prior['folio']}`\n"
    else:
        msg += f"• *Prior Chain Link:* `Unindexed in cadastre (Manual search on MDLandRec)`\n"
        
    msg += f"\n🗺 *Plat & Legal Identification:*\n"
    if plat['subdivision'] != 'N/A':
        msg += f"• *Subdivision:* `{plat['subdivision']}`\n"
    if plat['lot'] != 'N/A':
        msg += f"• *Lot / Block / Sec:* Lot `{plat['lot']}`, Blk `{plat['block']}`, Sec `{plat['section']}`\n"
    msg += f"• *Tax Map/Grid/Parcel:* Map `{plat['map']}`, Grid `{plat['grid']}`, Parcel `{plat['parcel']}`\n"
    if plat['legal_description']:
        msg += f"• *Legal:* `{plat['legal_description'][:80]}`\n"

    msg += f"\n🔍 *Title Confluence Audit:*\n"
    for p in title_res["positive_factors"]:
        msg += f"  ✅ {p}\n"
    for r in title_res["risk_factors"]:
        msg += f"  ⚠️ *Risk:* {r}\n"
        
    msg += f"\n🛡 *Required Closing Contingencies:*\n"
    for c in title_res["recommended_contingencies"][:3]:
        msg += f"  • {c}\n"

    msg += f"\n🔗 *Direct Verification Portals:*\n"
    msg += f"• [Live Parcel & Title Dossier (No Login)]({title_res['links']['dossier_url']})\n"
    msg += f"• [MD Parcel Record (No Login)]({title_res['links']['sdat_url']})\n"
    msg += f"• [SDAT Public Search Portal]({title_res['links'].get('sdat_search_url', 'https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx')})\n"
    msg += f"• [MD Survey Plats (No Login)]({title_res['links'].get('plats_url', 'https://plats.msa.maryland.gov/')})\n"
    msg += f"• [Maryland Judiciary Case Search]({title_res['links']['judiciary_url']})\n"
    msg += f"• [MDLandRec Deeds (Free Login Req.)]({title_res['links']['mdlandrec_url']}) (`{title_res['links']['mdlandrec_note']}`)"
    
    return msg

def format_title_wiki_section(title_res: Dict[str, Any]) -> str:
    """
    Formats markdown section for Obsidian Wiki export.
    """
    curr = title_res["current_deed"]
    prior = title_res["prior_deed"]
    plat = title_res["plat"]
    c_meta = title_res["county_meta"]
    
    md = f"## 📜 Title Search & Chain of Title Dossier\n\n"
    md += f"* **Title Confluence Score**: **{title_res['badge']} {title_res['score']}/100 (Grade {title_res['grade']} - {title_res['grade_desc']})**\n"
    md += f"* **Owner of Record**: **{title_res['owner_of_record']}** ({title_res['entity_type']})\n"
    md += f"* **Recording Jurisdiction**: {c_meta['name']} (Circuit Court / MDLandRec Code: `{c_meta['code']}`)\n\n"
    
    md += f"| Instrument Level | Liber (Book) | Folio (Page) | Transfer Date | Consideration | Conveyance / Notes |\n"
    md += f"| :--- | :---: | :---: | :---: | :---: | :--- |\n"
    md += f"| **Current Recorded Deed** | `{curr['liber']}` | `{curr['folio']}` | `{curr['transfer_date']}` | `{curr['consideration_str']}` | Primary Recorded Title Instrument |\n"
    md += f"| **Prior Chain Link** | `{prior['liber']}` | `{prior['folio']}` | Historic | N/A | Prior Link in Grantor/Grantee Chain |\n\n"
    
    md += f"### 🔍 Title Audit & Confluence Findings\n"
    for p in title_res["positive_factors"]:
        md += f"* ✅ **Positive**: {p}\n"
    for r in title_res["risk_factors"]:
        md += f"* ⚠️ **Risk / Exception**: {r}\n"
        
    md += f"\n### 🛡️ Recommended Purchase & Closing Contingencies\n"
    for c in title_res["recommended_contingencies"]:
        md += f"1. {c}\n"
        
    md += f"\n### 🔗 Primary Title Verification Links\n"
    md += f"* **MDLandRec.net**: [{title_res['links']['mdlandrec_note']}]({title_res['links']['mdlandrec_url']})\n"
    md += f"* **Maryland Judiciary Case Search**: [Search Case Dockets for {title_res['owner_of_record']}]({title_res['links']['judiciary_url']})\n"
    md += f"* **SDAT Real Property Data**: [View State Assessment Record]({title_res['links']['sdat_url']})\n"
    
    return md
