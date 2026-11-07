import os
import datetime
import re
from typing import Dict, Any, List

from title_search_engine import analyze_maryland_title, format_title_wiki_section

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
WIKI_DIR = os.path.join(WORKSPACE_DIR, "wiki")
INDEX_PATH = os.path.join(WORKSPACE_DIR, "index.md")
LOG_PATH = os.path.join(WORKSPACE_DIR, "log.md")


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', '', name).strip()
    return cleaned

def fmt_currency_val(val: Any) -> str:
    if val is None or val == "":
        return "$0.00"
    try:
        num = float(val)
        return f"${num:,.2f}"
    except (ValueError, TypeError):
        return str(val)

def generate_markdown_dossier(property_rec: Dict[str, Any], tax_info: Dict[str, Any]) -> str:
    addr = property_rec.get("address", "Unknown Address")
    city = property_rec.get("city", "")
    zipcode = property_rec.get("zipcode", "")
    full_addr = f"{addr}, {city}, MD {zipcode}".strip(", ")
    
    acct = property_rec.get("account_id", "N/A")
    zoning = property_rec.get("zoning", {}).get("code", "N/A")
    land_use = property_rec.get("zoning", {}).get("land_use_desc", "N/A")
    
    dims = property_rec.get("dimensions", {})
    acres = dims.get("acres", "N/A")
    sqft = dims.get("sqft")
    sqft_str = f"{sqft:,.1f} sq. ft." if isinstance(sqft, (int, float)) else str(sqft)
    
    val = property_rec.get("valuation", {})
    total_val_str = fmt_currency_val(val.get("total_value"))
    land_val_str = fmt_currency_val(val.get("land_value"))
    impr_val_str = fmt_currency_val(val.get("improvement_value"))
    
    trans = property_rec.get("transfer_history", {})
    t_date = trans.get("transfer_date", "N/A")
    t_price = trans.get("consideration_price")
    t_price_str = fmt_currency_val(t_price) if t_price is not None else "N/A"
    liber = trans.get("deed_liber", "N/A")
    folio = trans.get("deed_folio", "N/A")
    
    owner_mail = property_rec.get("owner_mailing", {})
    mail_line1 = owner_mail.get("line1", "")
    mail_city = owner_mail.get("city", "")
    mail_state = owner_mail.get("state", "")
    mail_zip = owner_mail.get("zip", "")
    is_absentee = owner_mail.get("is_absentee", False)
    
    legal = property_rec.get("legal", {})
    subdiv = legal.get("subdivision", "N/A")
    lot = legal.get("lot", "N/A")
    sec = legal.get("section", "N/A")
    map_no = legal.get("map", "N/A")
    grid_no = legal.get("grid", "N/A")
    parcel_no = legal.get("parcel", "N/A")
    
    legal_str = f"{legal.get('legal1', '')} {legal.get('legal2', '')} {legal.get('legal3', '')}".strip()
    
    owner_rec = tax_info.get("owner_of_record") or f"{mail_line1} ({mail_city}, {mail_state})"
    tax_flag = tax_info.get("tax_sale_flag", False)
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    title_res = analyze_maryland_title(property_rec, tax_info)
    title_section = format_title_wiki_section(title_res)
    
    md = f"""# Analysis - {full_addr}

**Property Address**: `{full_addr}`  
**APN / Account ID**: `{acct}`  
**Date Analyzed**: {now_str}  
**Jurisdiction**: {property_rec.get('jurisdiction', 'MD')}  
**SDAT Record Link**: [{acct}]({property_rec.get('sdat_web_url', '')})  

---

## 📍 Parcel Identification & Legal Description
* **Subdivision**: {subdiv}
* **Lot / Section**: Lot {lot}, Section {sec}
* **Tax Map / Grid / Parcel**: Map {map_no}, Grid {grid_no}, Parcel {parcel_no}
* **Legal Description**: `{legal_str}`

---

## 📐 Land & Zoning Attributes
* **Lot Size / Acreage**: **{acres} Acres** ({sqft_str})
* **Zoning Classification**: **{zoning}** ({land_use})
* **Critical Area Status**: Outside Chesapeake Bay Critical Area (Standard Development Rules)

---

## 👤 Ownership & Mailing Profile
* **Owner of Record**: **{owner_rec}**
* **Mailing Address**: `{mail_line1}, {mail_city}, {mail_state} {mail_zip}`
* **Absentee Owner Status**: **{'🔴 YES (Absentee Landlord / Out-of-State)' if is_absentee else '🟢 NO (Owner Occupied / Local)'}**

---

## 💰 Valuation & Assessment History
* **Total Assessed Value**: **{total_val_str}**
* **Land Assessment**: {land_val_str}
* **Improvement Assessment**: {impr_val_str}

---

{title_section}

---

## ⚠️ Tax Lien & Delinquency Inspection
* **County Tax Status**: {'⚠️ Active Tax Sale / Delinquency Warning' if tax_flag else '✅ No Active County Tax Sale Listed'}
* **County Tax Portal**: [{tax_info.get('county', 'County Portal')}]({tax_info.get('portal_url', '')})
* **Statutory Context**: Maryland operates as a Tax Lien state with a 6-month statutory redemption window and super-priority status.

---

## 🎯 Acquisition & Offer Strategy
* **Target Wholesale / Low Basis Opening**: $120,000 – $145,000 (Taking advantage of recent recorded {t_price_str} basis)
* **Target Negotiation Range**: $160,000 – $180,000
* **Maximum Allowable Offer (MAO)**: $195,000 – $205,000
* **Mandatory Contingencies**:
  1. 45–60 day Feasibility Study & Soil Perc Test Contingency.
  2. Public Works utility extension cost verification.
  3. General Warranty Deed + Owner's Title Insurance Commitment.

---

## 🔗 Related Knowledge Base Links
* [[Regional Mid-Atlantic Tax Sale Master Directory - MD VA NJ DE]]
* [[Tax Title Clearance and Quiet Title Actions]]
* [[Maryland Tax Lien Investing]]
* [[Maryland Tax Sale Due Diligence and Parcel Screening]]
* [[Property Due Diligence Funnel]]
* [[Zoning]]
"""
    return md


def save_property_to_wiki(property_rec: Dict[str, Any], tax_info: Dict[str, Any]) -> str:
    """
    Saves property analysis markdown note, updates index.md, and appends to log.md.
    """
    addr = property_rec.get("address", "Parcel")
    city = property_rec.get("city", "")
    title = f"Analysis - {addr} {city} MD".strip()
    clean_title = sanitize_filename(title)
    
    file_path = os.path.join(WIKI_DIR, f"{clean_title}.md")
    os.makedirs(WIKI_DIR, exist_ok=True)
    
    content = generate_markdown_dossier(property_rec, tax_info)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    # Update index.md if not already present
    wiki_link = f"[[{clean_title}]]"
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            idx_content = f.read()
            
        if wiki_link not in idx_content:
            entry = f"* {wiki_link} - Comprehensive parcel due diligence, zoning, recorded deed basis, and offer analysis for {addr}, {city} MD.\n"
            if "## 📊 Synthesis & Portfolio Strategy" in idx_content:
                parts = idx_content.split("## 📊 Synthesis & Portfolio Strategy\n")
                idx_content = parts[0] + "## 📊 Synthesis & Portfolio Strategy\n" + entry + parts[1]
            else:
                idx_content += f"\n\n## 📍 Parcels & Property Dossiers\n{entry}"
                
            with open(INDEX_PATH, "w", encoding="utf-8") as f:
                f.write(idx_content)
                
    # Append to log.md
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n- **{now_str}** | `INGESTION`: Added parcel analysis for `{addr}, {city} MD` -> `{clean_title}.md` via SDAT & Tax Lien Bot."
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
            
    return file_path
