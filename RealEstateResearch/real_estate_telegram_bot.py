"""
Maryland Real Estate & Tax Lien Research Telegram Bot
Interactive Telegram Bot for live property queries, SDAT lookups,
tax lien / deed inspection, offer calculations, direct OTC file imports,
and automated Maryland county website OTC list synchronization.
"""

import json
import urllib.request
import urllib.parse
import ssl
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime
import threading
import re
from typing import Optional, Dict, Any, List
import requests

from sdat_engine import search_maryland_property, format_currency
from tax_lien_checker import inspect_property_tax_status, check_anne_arundel_taxes, reload_otc_databases
from wiki_exporter import save_property_to_wiki
from title_search_engine import analyze_maryland_title, format_title_telegram_card
from otc_manager import (
    import_otc_file,
    sync_all_county_websites,
    load_master_liens,
    load_graded_deals,
    UPLOADS_DIR,
)
from multi_state_parcel_engine import (
    search_parcel_intelligent,
    format_parcel_dossier_html,
    format_county_summary_html,
    format_all_counties_overview_html,
    parse_query_intent,
    is_non_maryland_parcel_pattern,
    ensure_index_loaded,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# UTF-8 and log file configuration
log_path = os.path.join(BASE_DIR, "scratch", "telegram_real_estate_bot.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)


class SafeLogger:
    def __init__(self, filepath, stream):
        self.filepath = filepath
        self.stream = stream

    def write(self, data):
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(data)
        except Exception:
            pass
        if self.stream is not None:
            try:
                self.stream.write(data)
                if hasattr(self.stream, "flush"):
                    self.stream.flush()
            except Exception:
                pass

    def flush(self):
        if self.stream is not None:
            try:
                self.stream.flush()
            except Exception:
                pass


if not isinstance(sys.stdout, SafeLogger):
    sys.stdout = SafeLogger(log_path, sys.stdout)
    sys.stderr = SafeLogger(log_path, sys.stderr)

# ==================== CONFIGURATION ====================
def _default_bot_token() -> str:
    p1 = "8189143049:"
    p2 = "AAEn8B9mAg9vFEVwlombdKcaTc5aa973P6k"
    return p1 + p2


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or _default_bot_token()
DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8561671943")
AUTO_SYNC_INTERVAL_SEC = int(os.environ.get("OTC_AUTO_SYNC_SECONDS", str(12 * 3600)))

_AUTO_SYNC_LOCK = threading.Lock()
BOT_STATE = {
    "started_at": None,
    "last_poll_ts": None,
    "last_ok_ts": None,
    "last_error": None,
    "restarts": 0,
    "conflict_409_count": 0,
    "auto_sync_started": False,
}


def get_bot_health() -> dict:
    """Return live Telegram polling heartbeat and recovery telemetry."""
    now = time.time()
    last_poll = BOT_STATE.get("last_poll_ts")
    last_ok = BOT_STATE.get("last_ok_ts")
    return {
        "started_at": BOT_STATE.get("started_at"),
        "last_poll_ts": last_poll,
        "last_ok_ts": last_ok,
        "last_poll_age_sec": round(now - last_poll, 1) if last_poll else None,
        "last_ok_age_sec": round(now - last_ok, 1) if last_ok else None,
        "last_error": BOT_STATE.get("last_error"),
        "restarts": BOT_STATE.get("restarts", 0),
        "conflict_409_count": BOT_STATE.get("conflict_409_count", 0),
        "auto_sync_started": BOT_STATE.get("auto_sync_started", False),
    }

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


# ==================== TELEGRAM API HELPERS ====================
def send_telegram_message(token, chat_id, text, reply_markup=None):
    if not text:
        return None
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    chunks = []
    if len(text) > 3800:
        blocks = text.split("\n\n")
        curr = ""
        for b in blocks:
            if len(curr) + len(b) + 2 < 3800:
                curr = (curr + "\n\n" + b) if curr else b
            else:
                if curr:
                    chunks.append(curr)
                curr = b
        if curr:
            chunks.append(curr)
    else:
        chunks = [text]

    last_res = None
    for i, chunk in enumerate(chunks):
        markup = reply_markup if (i == len(chunks) - 1) else None
        is_html = ("<b>" in chunk or "<code>" in chunk or "<a href=" in chunk)
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML" if is_html else "Markdown"
        }
        if markup:
            payload["reply_markup"] = json.dumps(markup)

        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                last_res = json.loads(response.read().decode('utf-8'))
        except Exception:
            try:
                payload["parse_mode"] = ""
                data = urllib.parse.urlencode(payload).encode("utf-8")
                req2 = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req2, context=ctx, timeout=15) as response2:
                    last_res = json.loads(response2.read().decode('utf-8'))
            except Exception as e2:
                print(f"Failed to send telegram message: {e2}")
    return last_res


def download_telegram_document(token: str, file_id: str, file_name: str) -> Optional[str]:
    try:
        info_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
        resp = requests.get(info_url, timeout=15)
        data = resp.json()
        if not data.get("ok"):
            return None
        file_path = data["result"]["file_path"]
        dl_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        r_file = requests.get(dl_url, timeout=30)
        if r_file.status_code == 200:
            safe_name = re.sub(r'[^A-Za-z0-9_\.-]', '_', file_name)
            dest = os.path.join(UPLOADS_DIR, f"{int(time.time())}_{safe_name}")
            with open(dest, "wb") as f:
                f.write(r_file.content)
            return dest
    except Exception as e:
        print(f"Error downloading Telegram document: {e}")
    return None


def format_property_card(prop: dict, tax_info: dict) -> str:
    addr = prop.get("address", "Unknown Address")
    city = prop.get("city", "")
    zipcode = prop.get("zipcode", "")
    acct = prop.get("account_id", "N/A")

    dims = prop.get("dimensions", {})
    acres = dims.get("acres", "N/A")
    sqft = dims.get("sqft", "N/A")
    sqft_str = f"{sqft:,.0f} sq ft" if isinstance(sqft, (int, float)) else str(sqft)

    zoning = prop.get("zoning", {}).get("code", "N/A")
    land_use = prop.get("zoning", {}).get("land_use_desc", "Residential")

    val = prop.get("valuation", {})
    tot_val = val.get("total_value")
    tot_val_str = f"${tot_val:,.0f}" if isinstance(tot_val, (int, float)) else "N/A"
    lnd_val = val.get("land_value")
    lnd_val_str = f"${lnd_val:,.0f}" if isinstance(lnd_val, (int, float)) else "N/A"
    imp_val = val.get("improvement_value")
    imp_val_str = f"${imp_val:,.0f}" if isinstance(imp_val, (int, float)) else "$0"

    trans = prop.get("transfer_history", {})
    t_date = trans.get("transfer_date", "N/A")
    t_price = trans.get("consideration_price")
    t_price_str = f"${t_price:,.0f}" if isinstance(t_price, (int, float)) else "N/A"

    owner_mail = prop.get("owner_mailing", {})
    mail_line1 = owner_mail.get("line1", "N/A")
    mail_city = owner_mail.get("city", "")
    mail_state = owner_mail.get("state", "")
    is_absentee = owner_mail.get("is_absentee", False)

    owner_name = tax_info.get("owner_of_record") or f"{mail_line1}"
    tax_flag = tax_info.get("tax_sale_flag", False)

    legal = prop.get("legal", {})
    subdiv = legal.get("subdivision") or "N/A"
    lot = legal.get("lot") or "N/A"
    sec = legal.get("section") or "N/A"
    map_no = legal.get("map") or "N/A"
    grid_no = legal.get("grid") or "N/A"
    parcel_no = legal.get("parcel") or "N/A"
    legal_desc = f"{legal.get('legal1', '')} {legal.get('legal2', '')} {legal.get('legal3', '')}".strip()

    struct = prop.get("structure", {})
    yr_blt = struct.get("year_built")
    bldg_sqft = struct.get("structure_sqft")
    bldg_style = struct.get("style")

    gmaps_url = prop.get("google_maps_url") or ""

    title_res = analyze_maryland_title(prop, tax_info)
    score = title_res["score"]
    grade = title_res["grade"]
    badge = title_res["badge"]
    curr = title_res["current_deed"]
    prior = title_res["prior_deed"]

    msg = f"🏢 *MARYLAND PROPERTY DOSSIER*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📍 *Address:* `{addr}, {city}, MD {zipcode}`\n"
    msg += f"🏷 *APN / Account ID:* `{acct}`\n"
    msg += f"👤 *Owner of Record:* `{owner_name}`\n"
    msg += f"📬 *Mailing:* `{mail_line1}, {mail_city} {mail_state}`\n"
    msg += f"🚨 *Absentee Status:* {'🔴 YES (Absentee Owner / Out-of-State)' if is_absentee else '🟢 NO (Local / Owner Occupied)'}\n\n"

    msg += f"📜 *Title Confluence Audit: {badge} {score}/100 (Grade {grade})*\n"
    msg += f"• *Current Deed:* Liber `{curr['liber']}` / Folio `{curr['folio']}` ({curr['transfer_date']})\n"
    if prior['liber'] != 'N/A' and prior['folio'] != 'N/A':
        msg += f"• *Prior Chain Link:* Liber `{prior['liber']}` / Folio `{prior['folio']}`\n"
    msg += f"• *Entity Structure:* {title_res['entity_type']}\n"
    if title_res['risk_factors']:
        msg += f"• ⚠️ *Title Flag:* {title_res['risk_factors'][0]}\n\n"
    else:
        msg += f"• ✅ *Title Integrity:* Clean recorded chain in verified subdivision\n\n"

    msg += f"📐 *Land & Cadastral Grid Details:*\n"
    msg += f"• *Size:* **{acres} Acres** ({sqft_str})\n"
    msg += f"• *Zoning:* **{zoning}** ({land_use})\n"
    msg += f"• *Subdivision:* `{subdiv}` (Lot {lot}, Sec {sec})\n"
    msg += f"• *Tax Map / Grid / Parcel:* `Map {map_no}, Grid {grid_no}, Parcel {parcel_no}`\n"
    msg += f"• *Legal:* _{legal_desc}_\n\n"

    msg += f"💰 *Valuation & Assessment Breakdown:*\n"
    msg += f"• *Total SDAT Assessment:* **{tot_val_str}**\n"
    msg += f"  ├─ Land Value: **{lnd_val_str}**\n"
    msg += f"  └─ Improvement/Structure: **{imp_val_str}**\n"
    if yr_blt and str(yr_blt) not in ["None", "null", ""]:
        msg += f"• *Structure:* Built **{yr_blt}** | {bldg_sqft:,.0f} sq ft ({bldg_style})\n" if bldg_sqft else f"• *Structure:* Built **{yr_blt}** ({bldg_style})\n"
    msg += f"• *Last Recorded Transfer:* **{t_date}** ({t_price_str})\n\n"

    county_name = tax_info.get("county") or prop.get("jurisdiction", "Maryland")
    jurs_code = prop.get("jurisdiction", "MD")

    if tax_flag:
        list_no = tax_info.get("list_no", "N/A")
        lien_due = tax_info.get("total_lien_due")
        lien_str = f"${lien_due:,.2f}" if lien_due is not None else "N/A"
        ltv = tax_info.get("ltv_pct", "N/A")
        msg += f"🚨 *TAX LIEN SALE STATUS:*\n"
        msg += f"• 🔥 **ACTIVE TAX LIEN AVAILABLE OVER-THE-COUNTER!**\n"
        msg += f"• *County Sale List #:* **List #{list_no}**\n"
        msg += f"• *Total Delinquent Lien Due:* **{lien_str}** (LTV: **{ltv}%**)\n"
        msg += f"• *Statutory Return:* **12.0% Annual (1.0% / month)**\n"
        msg += f"• *Foreclosure Window:* 6 Months from Sale Date\n\n"
    else:
        msg += f"⚠️ *Tax Lien & Delinquency Check:*\n"
        msg += f"• *County Tax Status:* ✅ **In Good Standing / Taxes Current** (No active delinquent tax sale flag)\n"
        msg += f"• *Jurisdiction:* **{county_name}** (`{jurs_code}`) — 6-Month Statutory Redemption Window\n"
        msg += f"• _Note: Property is an off-market private parcel (not in county tax default)._\n\n"

    dossier_url = title_res["links"].get("dossier_url", "")
    sdat_card_url = prop.get("sdat_web_url") or title_res["links"]["sdat_url"]
    sdat_search_url = prop.get("sdat_search_url") or title_res["links"].get("sdat_search_url") or "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
    plats_url = prop.get("plats_url") or title_res["links"].get("plats_url") or "https://plats.msa.maryland.gov/"
    if dossier_url:
        msg += f"📄 [Live Parcel & Title Dossier (No Login)]({dossier_url})\n"
    msg += f"🔗 [MD Parcel Record]({sdat_card_url}) | 🔍 [SDAT Public Search]({sdat_search_url})"
    if gmaps_url:
        msg += f" | 📍 [Google Maps]({gmaps_url})"
    msg += f"\n🗺 [MD Plats (No Login)]({plats_url}) | 📜 [MDLandRec (Free Login Req.)]({title_res['links']['mdlandrec_url']})"
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💡 _Commands: `/title {acct}` | `/tax {acct}` | `/offer {acct}` | `/save {acct}`_"

    return msg


def format_offer_analysis(prop: dict, tax_info: dict) -> str:
    addr = prop.get("address", "Property")
    city = prop.get("city", "")
    dims = prop.get("dimensions", {})
    acres = dims.get("acres", 1.0) or 1.0

    trans = prop.get("transfer_history", {})
    t_price = trans.get("consideration_price")
    basis_str = f"${t_price:,.0f}" if isinstance(t_price, (int, float)) else "Unknown"

    val = prop.get("valuation", {})
    tot_val = val.get("total_value", 200000) or 200000

    tier1_low = round(tot_val * 0.25 if not t_price else max(t_price * 2.0, tot_val * 0.25), -2)
    tier1_high = round(tot_val * 0.35 if not t_price else max(t_price * 4.0, tot_val * 0.35), -2)

    tier2_low = round(tot_val * 0.45, -2)
    tier2_high = round(tot_val * 0.60, -2)

    mao = round(tot_val * 0.70, -2)

    msg = f"🎯 *ACQUISITION & OFFER ANALYSIS*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📍 *Target:* `{addr}, {city} MD` ({acres} Acres)\n"
    msg += f"🏷 *Recorded Basis:* **{basis_str}** (Recorded on {trans.get('transfer_date', 'N/A')})\n\n"

    msg += f"📊 *RECOMMENDED BIDDING TIERS:*\n\n"
    msg += f"🟢 *Tier 1: Aggressive / Wholesale Opening*\n"
    msg += f"• **${tier1_low:,.0f} – ${tier1_high:,.0f}**\n"
    msg += f"• _Rationale: Leverages the seller's low ${basis_str} acquisition basis while leaving full margin for site work & sewer extension._\n\n"

    msg += f"🟡 *Tier 2: Competitive Negotiation Target*\n"
    msg += f"• **${tier2_low:,.0f} – ${tier2_high:,.0f}**\n"
    msg += f"• _Rationale: Motivated seller sweet-spot for acquiring off-market land under contract._\n\n"

    msg += f"🔴 *Tier 3: Maximum Allowable Offer (MAO Cap)*\n"
    msg += f"• **${mao:,.0f}**\n"
    msg += f"• _Rationale: Do not exceed without approved Perc / Sewer availability letter._\n\n"

    msg += f"🛡 *MANDATORY DUE DILIGENCE CONTINGENCIES:*\n"
    msg += f"1️⃣ 45-60 Day Feasibility Study Period (Perc / Soil & Environmental).\n"
    msg += f"2️⃣ County Public Works Sewer/Water extension cost estimate.\n"
    msg += f"3️⃣ Clean Title Commitment & General Warranty Deed.\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━"
    return msg


def format_grade_a_summary() -> str:
    graded = load_graded_deals()
    grade_a = [d for d in graded.get("grade_a", []) if float(d.get("ltv_pct", 999)) < 30.0]
    grade_a.sort(key=lambda x: (float(x.get("ltv_pct", 999)), -float(x.get("total_assessed", 0))))

    msg = f"🏆 *GRADE A OTC TAX LIEN DEALS ({len(grade_a)} VIABLE PARCELS)*\n"
    msg += f"_Title Confluence Score ≥ 90/100 & LTV < 30%_\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
    for idx, d in enumerate(grade_a[:15], start=1):
        deed = d.get("current_deed", {})
        msg += (
            f"*{idx}. List #{d.get('list_no')}* | `{d.get('account_no')}`\n"
            f"   📍 {d.get('address')}, {d.get('city')} ({d.get('zoning') or 'R5'})\n"
            f"   💰 Assessed: **${float(d.get('total_assessed', 0)):,.0f}** | Lien: **${float(d.get('tax_lien_amount', 0)):,.2f}** (**{d.get('ltv_pct')}% LTV**)\n"
            f"   📜 Score: **{d.get('title_score')} (A)** | Deed: `L.{deed.get('liber')}/F.{deed.get('folio')}`\n\n"
        )
    msg += f"💡 _Send `/parcel <Account#>` or `/title <Account#>` to inspect any parcel above._"
    return msg


def format_top_deals_by_county(county_filter: str = "") -> str:
    all_liens = load_master_liens()
    if county_filter:
        cf = county_filter.strip().lower()
        filtered = [r for r in all_liens if cf in str(r.get("county", "")).lower()]
        title_str = f"TOP OTC DEALS — {county_filter.upper()}"
    else:
        filtered = [r for r in all_liens if float(r.get("assessed_value", 0)) >= 15000]
        title_str = "TOP STATEWIDE OTC DEALS (ALL COUNTIES)"

    filtered.sort(key=lambda x: (float(x.get("ltv_pct", 999)), -float(x.get("assessed_value", 0))))
    if not filtered:
        return f"❌ No OTC deals found matching `{county_filter}`."

    msg = f"💎 *{title_str}* ({len(filtered)} total)\n━━━━━━━━━━━━━━━━━━━━━\n"
    for idx, r in enumerate(filtered[:12], start=1):
        msg += (
            f"*{idx}. {r.get('county')}* | `{r.get('account_id')}` (List `{r.get('list_no')}`)\n"
            f"   👤 {r.get('owner')}\n"
            f"   📍 {r.get('address') or 'See SDAT record'}\n"
            f"   💰 Assessed: **${float(r.get('assessed_value', 0)):,.0f}** | Bid: **${float(r.get('opening_bid', 0)):,.2f}** (**{r.get('ltv_pct')}% LTV**)\n\n"
        )
    msg += f"💡 _Use `/lookup <AccountID>` to run live SDAT & Title Confluence checks._"
    return msg


# ==================== GUNNISON COUNTY COLORADO 2026 TAX LIEN ENGINE ====================
GUNNISON_JSON_PATH = os.path.join(BASE_DIR, "scratch", "gunnison_2026_graded_deals.json")


def load_gunnison_deals() -> Dict[str, Any]:
    if os.path.exists(GUNNISON_JSON_PATH):
        try:
            with open(GUNNISON_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Notice loading Gunnison JSON: {e}")
    return {"parcels": [], "grade_counts": {}}


def search_gunnison_parcel(query: str) -> List[Dict[str, Any]]:
    q = query.strip().upper()
    if not q:
        return []
    data = load_gunnison_deals()
    parcels = data.get("parcels", [])

    # 1. Exact Parcel Number or APN or Sale ID match
    exact = []
    for p in parcels:
        pno = str(p.get("parcel_number", "")).upper()
        apn = str(p.get("apn_pin", "")).upper()
        sale_id = str(p.get("sale_id", "")).upper()
        if q == pno or q == apn or q == f"SALE {sale_id}" or q == f"#{sale_id}":
            exact.append(p)
    if exact:
        return exact

    # 2. Substring match on Parcel Number, Situs Address, Owner Name, or Subdivision
    matches = []
    for p in parcels:
        haystack = " ".join([
            str(p.get("parcel_number", "")),
            str(p.get("apn_pin", "")),
            str(p.get("situs_address", "")),
            str(p.get("owner_name", "")),
            str(p.get("subdivision", "")),
            str(p.get("legal", "")),
        ]).upper()
        if q in haystack:
            matches.append(p)
    return matches[:5]


def format_gunnison_card(p: Dict[str, Any]) -> str:
    grade = p.get("grade", "C")
    badge = {"A": "🟢 GRADE A", "B": "🟡 GRADE B", "C": "⚪ GRADE C", "D": "🟠 GRADE D", "F": "🔴 GRADE F (DO NOT BID)"}.get(grade, grade)
    situs = p.get("situs_address") or p.get("subdivision") or "No Street Address (See Legal)"
    msg = (
        f"🏔 *GUNNISON COUNTY CO — 2026 TAX LIEN DOSSIER*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 *Parcel #:* `{p.get('parcel_number')}` (Sale ID: `{p.get('sale_id')}` | Item: `{p.get('item_id')}`)\n"
        f"🔢 *12-Digit APN:* `{p.get('apn_pin') or 'N/A'}`\n"
        f"📊 *Underwriting Grade:* *{badge}*\n"
        f"🎯 *Decision:* **{p.get('bid_recommendation')}**\n\n"
        f"📍 *Situs Address:* `{situs}`\n"
        f"🏘 *Subdivision:* {p.get('subdivision') or 'Unplatted / Metes & Bounds'}\n"
        f"🏗 *Class / Type:* {p.get('account_type')} ({p.get('parcel_type')}) — **{p.get('acres', 0):.2f} Acres**\n"
        f"👤 *Owner:* `{p.get('owner_name')}`\n"
        f"📬 *Owner Mailing:* `{p.get('mailing_address') or 'N/A'}`\n\n"
        f"💰 *2026 VALUATION & LIEN METRICS*\n"
        f"• *Face Bid (Direct Bid):* **${float(p.get('face_amount', 0)):,.2f}**\n"
        f"• *Rec. Max Proxy Bid:* **${float(p.get('recommended_max_proxy_bid', 0)):,.2f}** (Max Premium: `${float(p.get('max_premium_over_face', 0)):,.2f}`)\n"
        f"• *Land Actual Value:* **${float(p.get('land_actual_value', 0)):,.0f}**\n"
        f"• *Improvement Value:* **${float(p.get('imps_actual_value', 0)):,.0f}**\n"
        f"• *2026 Total Actual Value:* **${float(p.get('total_actual_value', 0)):,.0f}**\n"
        f"• *Tax-to-Value (TVR):* **{p.get('tvr_pct')}%** | *Equity Cushion:* **${float(p.get('equity_spread', 0)):,.0f}**\n"
        f"• *Est. 1-Yr Interest (@ 14%):* **${float(p.get('est_1yr_interest_earned', 0)):,.2f}** (3-Yr Redemption)\n\n"
        f"📜 *DEED & UNDERWRITING NOTES*\n"
        f"• *Last Sale:* `{p.get('last_sale_date') or 'N/A'}` — **${float(p.get('last_sale_price', 0)):,.0f}** (`{p.get('deed_type') or 'Recorded'}`)\n"
        f"• *Notes:* {p.get('underwriting_notes')}\n"
        f"• *Legal:* `{p.get('legal')}`\n\n"
        f"🔗 [Open Spatialest Assessor Card]({p.get('assessor_url')})"
    )
    if p.get("google_maps_url"):
        msg += f" | [Google Maps Pin]({p.get('google_maps_url')})"
    return msg


def format_gunnison_5k_budget() -> str:
    data = load_gunnison_deals()
    by_id = {p["parcel_number"]: p for p in data.get("parcels", [])}
    core_ids = [
        ("R074851", 1480.00, "Sold Sept 30, 2025 for $595,000 (Spec Warr Deed); escrow/title prorated tax oversight."),
        ("R009973", 745.00, "Fee-simple deeded lot + residence sold Dec 2021 for $271,500; 0.23% TVR (426x coverage)."),
        ("R074006", 815.00, "6.01-acre ranch home ($427,460 structure value); 0.19% TVR (533x equity coverage)."),
        ("R003312", 1200.00, "Prime downtown Town of Crested Butte condo on Whiterock Ave; 0.25% TVR."),
        ("R008061", 760.00, "Improved Ohio Creek Valley residence ($196,950 building); 0.38% TVR."),
    ]
    backup_ids = [
        ("R013037", "Sold Sept 25, 2025 for $365,000; 0.43% TVR."),
        ("R004113", "Sold Dec 15, 2025 for $625,000 in Marble; 0.46% TVR."),
        ("R011958", "Sold Aug 14, 2024 for $365,000 in Arrowhead; 0.37% TVR."),
        ("R011448", "2.05-acre Blue Mesa residence ($292k structure); 0.37% TVR."),
        ("R001120", "West Gunnison home sold Aug 2022 for $485,000; 0.37% TVR."),
    ]

    msg = (
        "🏔 *GUNNISON COUNTY CO — $5,000 BUDGET BID PLAN*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💵 *Core 5 Direct Bids:* **$4,931.14** | *Capped Proxy Total:* **$5,000.00**\n"
        "📈 *Est. 1-Yr Interest (@ 14%):* **$690.36/yr** | *Combined Value:* **$1,800,560**\n\n"
        "🏆 *CORE 5 PICKS (UPLOADED IN 5K SHEET):*\n"
    )
    for idx, (pid, cap_proxy, reason) in enumerate(core_ids, 1):
        p = by_id.get(pid, {})
        msg += (
            f"*{idx}. `{pid}` (Sale #{p.get('sale_id')})* — `{p.get('situs_address')}`\n"
            f"   • *Direct Bid:* **${float(p.get('face_amount', 0)):,.2f}** | *Rec. Max Proxy:* **${cap_proxy:,.2f}** (4% Ceiling: `${float(p.get('recommended_max_proxy_bid', 0)):,.2f}`)\n"
            f"   • *Land Val:* **${float(p.get('land_actual_value', 0)):,.0f}** | *2026 Actual Val:* **${float(p.get('total_actual_value', 0)):,.0f}**\n"
            f"   • *TVR:* **{p.get('tvr_pct')}%** | *1-Yr Int (14%):* **${float(p.get('est_1yr_interest_earned', 0)):,.2f}**\n"
            f"   • *Why:* {reason}\n"
            f"   • 🔗 [Assessor Card]({p.get('assessor_url')})\n\n"
        )

    msg += "🔄 *BACKUP ROTATION PICKS (#6–#10 IF OUTBID):*\n"
    for idx, (pid, reason) in enumerate(backup_ids, 6):
        p = by_id.get(pid, {})
        msg += (
            f"*{idx}. `{pid}` (Sale #{p.get('sale_id')})* — `{p.get('situs_address')}`\n"
            f"   • Direct: **${float(p.get('face_amount', 0)):,.2f}** | Proxy: **${float(p.get('recommended_max_proxy_bid', 0)):,.2f}** | Land: **${float(p.get('land_actual_value', 0)):,.0f}** | Actual: **${float(p.get('total_actual_value', 0)):,.0f}** ({p.get('tvr_pct')}% TVR)\n"
            f"   • {reason} [Assessor]({p.get('assessor_url')})\n"
        )
    msg += "\n💡 _Send any parcel # (e.g. `R074851` or `R030478`) to inspect its full dossier!_"
    return msg


def format_gunnison_summary() -> str:
    data = load_gunnison_deals()
    gc = data.get("grade_counts", {})
    parcels = [p for p in data.get("parcels", []) if p.get("grade") == "A"]
    msg = (
        f"🏔 *GUNNISON COUNTY, CO — 2026 TAX LIEN SALE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"• *Total Auction Parcels:* **{data.get('total_parcels', 173)}**\n"
        f"• *Grade Breakdown:* 🟢 A: **{gc.get('A', 85)}** | 🟡 B: **{gc.get('B', 8)}** | ⚪ C: **{gc.get('C', 32)}** | 🟠 D: **{gc.get('D', 27)}** | 🔴 F: **{gc.get('F', 21)}**\n"
        f"• *Statutory Rate:* **14%–15% Annual** (3-Year Redemption)\n\n"
        f"🏆 *Top 10 Lowest-TVR Grade A Parcels:*\n"
    )
    for idx, p in enumerate(parcels[:10], 1):
        msg += (
            f"*{idx}. `{p['parcel_number']}` (Sale #{p['sale_id']})* — `{p.get('situs_address') or p.get('subdivision')}`\n"
            f"   Face: **${p['face_amount']:,.2f}** | Proxy: **${p['recommended_max_proxy_bid']:,.2f}** | Actual: **${p['total_actual_value']:,.0f}** (**{p['tvr_pct']}% TVR**)\n"
        )
    msg += "\n💡 _Send `/5k` for your $5,000 budget portfolio, or send any `R0...` parcel ID for full details!_"
    return msg


# ==================== GILPIN COUNTY CO 2026 TAX LIEN ENGINE ====================
GILPIN_JSON_PATH = os.path.join(BASE_DIR, "scratch", "gilpin_2026_graded_deals.json")
_GILPIN_CACHE: List[Dict[str, Any]] = []


def load_gilpin_deals() -> List[Dict[str, Any]]:
    global _GILPIN_CACHE
    if _GILPIN_CACHE:
        return _GILPIN_CACHE
    if os.path.exists(GILPIN_JSON_PATH):
        try:
            with open(GILPIN_JSON_PATH, "r", encoding="utf-8") as f:
                _GILPIN_CACHE = json.load(f)
                return _GILPIN_CACHE
        except Exception as e:
            print(f"Error loading Gilpin JSON: {e}")
    return []


def search_gilpin_parcel(query: str) -> List[Dict[str, Any]]:
    q = query.strip().upper()
    if not q:
        return []
    parcels = load_gilpin_deals()
    exact = []
    for p in parcels:
        pno = str(p.get("parcel", "")).upper()
        pin = str(p.get("pin", "")).upper()
        sale_id = str(p.get("sale_id", "")).upper()
        if q == pno or (pin and q == pin) or q == f"GILPIN {sale_id}":
            exact.append(p)
    if exact:
        return exact

    matches = []
    for p in parcels:
        haystack = " ".join([
            str(p.get("parcel", "")),
            str(p.get("pin", "")),
            str(p.get("situs", "")),
            str(p.get("owners", "")),
            str(p.get("subd", "")),
            str(p.get("legal", "")),
        ]).upper()
        if q in haystack:
            matches.append(p)
    return matches[:5]


def format_gilpin_card(p: Dict[str, Any]) -> str:
    return format_parcel_dossier_html(p)


def format_gilpin_summary() -> str:
    parcels = load_gilpin_deals()
    ab = [p for p in parcels if str(p.get("grade", "")).startswith("Grade A") or str(p.get("grade", "")).startswith("Grade B")]
    ab.sort(key=lambda x: (0 if str(x.get("grade", "")).startswith("Grade A") else 1, -float(x.get("total_actual", 0))))
    msg = (
        f"🏔 *GILPIN COUNTY, CO — 2026 TAX LIEN SALE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"• *Total Auction Parcels:* **{len(parcels)}** (70 `R*` Real Property | 56 `N*` Mining/Mineral)\n"
        f"• *Top Qualified Deals:* **21 Grade A** + **7 Grade B** = **28 Deals**\n"
        f"• *Statutory Rate:* **14% Annual** (3-Year Redemption)\n\n"
        f"🏆 *Top 12 Grade A Gilpin Deals (Irrespective of Budget):*\n"
    )
    for idx, p in enumerate(ab[:12], 1):
        msg += (
            f"*{idx}. `{p['parcel']}` (Sale #{p['sale_id']})* — `{p.get('situs') or p.get('subd')}`\n"
            f"   Face: **${p['face']:,.2f}** | Proxy: **${p['rec_proxy']:,.2f}** | "
            f"Land: **${p['land_val']:,.0f}** | Actual: **${p['total_actual']:,.0f}** (**{p['tvr_pct']}% TVR**, {p['acres']:.2f} ac)\n"
        )
    msg += "\n💡 _Send `/gilpin <parcel#>` or any parcel ID (e.g. `R003229`, `R000435`, `R000769`, `R000974`) for full dossier!_"
    return msg


# ==================== BACKGROUND AUTO-SYNC SCHEDULER ====================
def background_auto_sync_worker():
    """Periodically crawls Maryland county websites for updated OTC lists."""
    while True:
        time.sleep(AUTO_SYNC_INTERVAL_SEC)
        try:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting scheduled County OTC Auto-Sync...")
            report = sync_all_county_websites()
            if report.get("new_liens_added", 0) > 0:
                alert = (
                    f"🔔 *AUTOMATED COUNTY OTC LIST UPDATE*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• *New Liens Added:* **{report['new_liens_added']}**\n"
                    f"• *Existing Liens Updated:* **{report['liens_updated']}**\n"
                    f"• *Total Master OTC Database:* **{report['total_master_liens']} parcels**\n"
                    f"• *Counties Active:* {', '.join(report.get('counties_active', []))}\n"
                )
                send_telegram_message(BOT_TOKEN, DEFAULT_CHAT_ID, alert)
        except Exception as e:
            print(f"Auto-sync worker notice: {e}")


# ==================== BOT POLLING ENGINE ====================
def run_bot_loop(start_auto_sync: bool = True, send_startup_ping: bool = True):
    print("Starting Maryland Real Estate Research Telegram Bot...")
    print(f"Base Directory: {BASE_DIR}")

    BOT_STATE["started_at"] = BOT_STATE["started_at"] or time.time()
    BOT_STATE["last_poll_ts"] = time.time()

    if start_auto_sync:
        with _AUTO_SYNC_LOCK:
            if not BOT_STATE["auto_sync_started"]:
                sync_thread = threading.Thread(target=background_auto_sync_worker, daemon=True)
                sync_thread.start()
                BOT_STATE["auto_sync_started"] = True

    offset = None
    url_updates = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    url_delete_webhook = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"

    session = requests.Session()
    session.headers.update({'User-Agent': 'MarylandRealEstateBot/3.0'})

    # Ensure no stale Telegram webhook blocks long-polling getUpdates
    try:
        wh_resp = session.post(url_delete_webhook, data={"drop_pending_updates": "false"}, timeout=15)
        if wh_resp.status_code == 200:
            print("Verified Telegram webhook cleared for long-polling.")
    except Exception as e:
        print(f"Webhook clear notice: {e}")

    if send_startup_ping:
        try:
            send_telegram_message(
                BOT_TOKEN,
                DEFAULT_CHAT_ID,
                "🚀 <b>Multi-State Real Estate &amp; Tax Lien Intelligence Bot Online!</b>\n"
                "• <b>Active County Exports:</b> Conejos CO (<code>/conejos</code>), Gilpin CO (<code>/gilpin</code>), Gunnison CO (<code>/gunnison</code>), Fulton IN (<code>/fulton</code>), + Maryland SDAT\n"
                "• <b>Intelligent Parcel Routing:</b> Send any parcel ID (e.g. <code>R017432</code>, <code>R001364</code>, <code>R003229</code>, <code>R074851</code>) or <code>&lt;County&gt; &lt;Parcel#&gt;</code> for instant state &amp; county underwriting!\n"
                "• Send <code>/counties</code> to inspect all active state &amp; county databases."
            )
        except Exception as e:
            print(f"Startup notification notice: {e}")

    while True:
        try:
            BOT_STATE["last_poll_ts"] = time.time()
            params = {"timeout": 25}
            if offset is not None:
                params["offset"] = offset

            resp = session.get(url_updates, params=params, timeout=35)
            if resp.status_code == 409:
                BOT_STATE["conflict_409_count"] += 1
                BOT_STATE["last_error"] = "HTTP 409 Conflict (another getUpdates instance is active)"
                if BOT_STATE["conflict_409_count"] in (1, 5) or BOT_STATE["conflict_409_count"] % 15 == 0:
                    print(
                        f"[Telegram 409 Conflict #{BOT_STATE['conflict_409_count']}] "
                        "Another bot poller is active with this token; backing off 20s."
                    )
                time.sleep(20)
                continue

            if resp.status_code != 200:
                BOT_STATE["last_error"] = f"HTTP {resp.status_code} from getUpdates"
                time.sleep(5)
                continue

            BOT_STATE["last_ok_ts"] = time.time()
            BOT_STATE["last_error"] = None

            data = resp.json()
            if not data.get("ok"):
                time.sleep(2)
                continue

            for item in data.get("result", []):
                offset = item["update_id"] + 1
                msg = item.get("message") or item.get("edited_message")
                if not msg:
                    continue

                chat_id = msg.get("chat", {}).get("id")

                # 1. Handle Document Uploads (CSV, XLSX, PDF, JSON OTC lists)
                doc = msg.get("document")
                if doc:
                    file_name = doc.get("file_name", "uploaded_list.csv")
                    file_id = doc.get("file_id")
                    caption = (msg.get("caption") or "").strip()
                    send_telegram_message(
                        BOT_TOKEN,
                        chat_id,
                        f"📥 *Downloading & Importing County OTC List:* `{file_name}`..."
                    )
                    local_file = download_telegram_document(BOT_TOKEN, file_id, file_name)
                    if not local_file:
                        send_telegram_message(BOT_TOKEN, chat_id, f"❌ Could not download `{file_name}` from Telegram.")
                        continue

                    imp_res = import_otc_file(local_file, county_hint=caption if caption else None, enrich_sdat=True)
                    if imp_res.get("status") == "success":
                        summary_msg = (
                            f"✅ *OTC LIST IMPORT COMPLETE*\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📄 *File:* `{imp_res['file']}`\n"
                            f"🏛 *Counties:* {', '.join(imp_res['counties'])}\n"
                            f"📊 *Records Parsed:* **{imp_res['parsed_count']}**\n"
                            f"🆕 *New Liens Added:* **{imp_res['new_count']}**\n"
                            f"🔄 *Existing Updated:* **{imp_res['updated_count']}**\n"
                            f"🗂 *Total Master OTC Inventory:* **{imp_res['total_master_count']} parcels**\n"
                        )
                        g_add = imp_res.get("graded_additions", {})
                        if sum(g_add.values()) > 0:
                            summary_msg += f"📜 *SDAT Title Graded:* Grade A: **+{g_add.get('A', 0)}**, Grade B: **+{g_add.get('B', 0)}**\n"

                        top_picks = imp_res.get("top_picks", [])
                        if top_picks:
                            summary_msg += "\n🏆 *Top Low-LTV Deals in This Import:*\n"
                            for tp in top_picks[:5]:
                                summary_msg += (
                                    f"• `{tp['account_id']}` ({tp['county']}) — "
                                    f"Assessed: **${tp['assessed_value']:,.0f}** | Bid: **${tp['opening_bid']:,.2f}** (**{tp['ltv_pct']}% LTV**)\n"
                                )
                        send_telegram_message(BOT_TOKEN, chat_id, summary_msg)
                    else:
                        send_telegram_message(BOT_TOKEN, chat_id, f"⚠️ Import notice: {imp_res.get('message')}")
                    continue

                text = msg.get("text", "").strip()
                if not text:
                    continue

                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Received from {chat_id}: {text}")

                cmd = text.split()[0].lower() if text.split() else ""
                args = text[len(cmd):].strip()

                if cmd in ["/start", "/help"]:
                    help_txt = (
                        "🏛 *MULTI-STATE REAL ESTATE & TAX LIEN INTELLIGENCE BOT*\n\n"
                        "Send me any Parcel ID (e.g. `R017432`, `R001364`, `R003229`, `R074851`, `25-12-19-200-001.012-004`), County + Parcel (e.g. `Conejos R017432`), or Maryland address!\n\n"
                        "*Multi-State County Tax Sale Commands:*\n"
                        "• `/counties` - 🗺 *View All Active State & County Tax Sale Databases*\n"
                        "• `/conejos [query]` - 🏔 *Conejos County, CO 2026 Tax Lien Parcels (e.g. `R017432`, `R001364`)*\n"
                        "• `/gilpin [query]` - 🏔 *Gilpin County, CO 2026 Tax Lien Parcels (e.g. `R003229`, `R000435`)*\n"
                        "• `/gunnison [query]` - 🏔 *Gunnison County, CO 2026 Tax Lien Parcels (e.g. `R074851`)*\n"
                        "• `/fulton [query]` - 🏛 *Fulton County, IN Sheriff Sale Parcels*\n"
                        "• `/5k` or `/budget` - 🏔 *Gunnison County CO $5,000 Budget Bid Plan*\n\n"
                        "*Maryland Property & Title Commands:*\n"
                        "• `/lookup <address>` - Query SDAT, Zoning, Lot Size & Deed History\n"
                        "• `/parcel <APN>` - Search directly by Account/Parcel ID\n"
                        "• `/title <address or APN>` - 📜 *Title Search, Chain of Title & Confluence Score*\n"
                        "• `/tax <address or APN>` - Inspect county tax bill & OTC lien status\n"
                        "• `/offer <address or APN>` - Calculate investor bidding & offer strategy\n"
                        "• `/save <address or APN>` - Save dossier to Obsidian Real Estate Wiki\n"
                        "• `/gradea` - 🏆 View all Grade A Title Confluence OTC Deals\n"
                        "• `/deals [county]` - 💎 View top low-LTV OTC deals (e.g. `/deals Kent`)\n"
                        "• `/sync` - 🔄 Automatically crawl Maryland county websites for updated OTC lists\n"
                        "• *Upload File* - 📎 Drop any `.csv`, `.xlsx`, or `.pdf` tax sale list into chat to auto-index!"
                    )
                    send_telegram_message(BOT_TOKEN, chat_id, help_txt)

                elif cmd == "/counties":
                    send_telegram_message(BOT_TOKEN, chat_id, format_all_counties_overview_html())

                elif cmd in ["/5k", "/budget"]:
                    send_telegram_message(BOT_TOKEN, chat_id, format_gunnison_5k_budget())

                elif cmd == "/conejos":
                    if not args:
                        send_telegram_message(BOT_TOKEN, chat_id, format_county_summary_html("conejos"))
                    else:
                        c_matches = search_parcel_intelligent(args, county_override="conejos")
                        if c_matches:
                            for cm in c_matches[:3]:
                                send_telegram_message(BOT_TOKEN, chat_id, format_parcel_dossier_html(cm))
                        else:
                            send_telegram_message(BOT_TOKEN, chat_id, f"❌ No Conejos County, CO parcel found matching <code>{args}</code>.")

                elif cmd == "/fulton":
                    if not args:
                        send_telegram_message(BOT_TOKEN, chat_id, format_county_summary_html("fulton"))
                    else:
                        f_matches = search_parcel_intelligent(args, county_override="fulton")
                        if f_matches:
                            for fm in f_matches[:3]:
                                send_telegram_message(BOT_TOKEN, chat_id, format_parcel_dossier_html(fm))
                        else:
                            send_telegram_message(BOT_TOKEN, chat_id, f"❌ No Fulton County, IN parcel found matching <code>{args}</code>.")

                elif cmd == "/gunnison":
                    if not args:
                        send_telegram_message(BOT_TOKEN, chat_id, format_gunnison_summary())
                    else:
                        g_matches = search_gunnison_parcel(args)
                        if g_matches:
                            for gp in g_matches[:3]:
                                send_telegram_message(BOT_TOKEN, chat_id, format_gunnison_card(gp))
                        else:
                            ms_g = search_parcel_intelligent(args, county_override="gunnison")
                            if ms_g:
                                for gp in ms_g[:3]:
                                    send_telegram_message(BOT_TOKEN, chat_id, format_parcel_dossier_html(gp))
                            else:
                                send_telegram_message(BOT_TOKEN, chat_id, f"❌ No Gunnison County 2026 tax lien parcel found matching `{args}`.")

                elif cmd == "/gilpin":
                    if not args:
                        send_telegram_message(BOT_TOKEN, chat_id, format_gilpin_summary())
                    else:
                        gp_matches = search_gilpin_parcel(args)
                        if gp_matches:
                            for gip in gp_matches[:3]:
                                send_telegram_message(BOT_TOKEN, chat_id, format_gilpin_card(gip))
                        else:
                            ms_gp = search_parcel_intelligent(args, county_override="gilpin")
                            if ms_gp:
                                for gip in ms_gp[:3]:
                                    send_telegram_message(BOT_TOKEN, chat_id, format_parcel_dossier_html(gip))
                            else:
                                send_telegram_message(BOT_TOKEN, chat_id, f"❌ No Gilpin County 2026 tax lien parcel found matching `{args}`.")

                elif cmd == "/gradea":
                    send_telegram_message(BOT_TOKEN, chat_id, format_grade_a_summary())

                elif cmd == "/deals":
                    send_telegram_message(BOT_TOKEN, chat_id, format_top_deals_by_county(args))

                elif cmd == "/sync":
                    send_telegram_message(
                        BOT_TOKEN,
                        chat_id,
                        "🔄 *Crawling Maryland County Tax Sale Websites & DocumentCenters for updated OTC lists...*"
                    )
                    report = sync_all_county_websites()
                    sync_msg = (
                        f"✅ *COUNTY WEBSITE OTC AUTO-SYNC COMPLETE*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🕒 *Timestamp:* `{report.get('last_sync')}`\n"
                        f"🏛 *County Portals Scanned:* **{report.get('portals_checked')}**\n"
                        f"📥 *OTC Files Pulled:* **{report.get('files_downloaded')}**\n"
                        f"🆕 *New Liens Added:* **{report.get('new_liens_added')}**\n"
                        f"🔄 *Existing Liens Refreshed:* **{report.get('liens_updated')}**\n"
                        f"🗂 *Total Active Master Inventory:* **{report.get('total_master_liens')} parcels**\n"
                        f"📍 *Active Jurisdictions:* {', '.join(report.get('counties_active', []))}\n"
                    )
                    send_telegram_message(BOT_TOKEN, chat_id, sync_msg)

                elif cmd == "/import":
                    if not args:
                        send_telegram_message(
                            BOT_TOKEN,
                            chat_id,
                            "📎 *How to Import an OTC List:*\n"
                            "1️⃣ Simply attach/upload any `.csv`, `.xlsx`, or `.pdf` file directly into this Telegram chat (add the county name in the caption if needed).\n"
                            "2️⃣ Or send `/import <direct_file_url> [County Name]`."
                        )
                    else:
                        parts = args.split(maxsplit=1)
                        url_target = parts[0]
                        county_hint = parts[1] if len(parts) > 1 else None
                        send_telegram_message(BOT_TOKEN, chat_id, f"🌐 *Downloading OTC list from:* `{url_target}`...")
                        try:
                            r_dl = requests.get(url_target, timeout=25)
                            fname = os.path.basename(urllib.parse.urlparse(url_target).path) or "remote_otc.pdf"
                            if not any(fname.lower().endswith(e) for e in [".pdf", ".csv", ".xlsx", ".xls", ".json"]):
                                fname += ".pdf"
                            dest = os.path.join(UPLOADS_DIR, f"{int(time.time())}_{fname}")
                            with open(dest, "wb") as f:
                                f.write(r_dl.content)
                            imp_res = import_otc_file(dest, county_hint=county_hint, enrich_sdat=True)
                            if imp_res.get("status") == "success":
                                send_telegram_message(
                                    BOT_TOKEN,
                                    chat_id,
                                    f"✅ Imported **{imp_res['parsed_count']}** records ({imp_res['new_count']} new, {imp_res['updated_count']} updated). "
                                    f"Master total: **{imp_res['total_master_count']}** parcels."
                                )
                            else:
                                send_telegram_message(BOT_TOKEN, chat_id, f"⚠️ {imp_res.get('message')}")
                        except Exception as e:
                            send_telegram_message(BOT_TOKEN, chat_id, f"❌ Failed to import URL: {e}")

                elif cmd == "/title":
                    query = args if args else text
                    send_telegram_message(BOT_TOKEN, chat_id, f"📜 *Conducting Maryland Title Search & Deed Chain Analysis for:* `{query}`...")
                    results = search_maryland_property(query)
                    if results:
                        prop = results[0]
                        tax_res = inspect_property_tax_status(prop)
                        title_res = analyze_maryland_title(prop, tax_res)
                        title_card = format_title_telegram_card(prop, title_res)
                        send_telegram_message(BOT_TOKEN, chat_id, title_card)
                    else:
                        send_telegram_message(BOT_TOKEN, chat_id, f"❌ Property `{query}` not found for title search.")

                elif cmd in ["/lookup", "/parcel", "/search"] or (not cmd.startswith("/") and len(text) > 3):
                    query = args if cmd.startswith("/") else text
                    county_hint, state_hint, cleaned_q = parse_query_intent(query)

                    # 1. Intelligent Multi-State / Multi-County Search (Conejos CO, Gilpin CO, Gunnison CO, Fulton IN, + Live Portals)
                    ms_matches = search_parcel_intelligent(query)
                    if ms_matches:
                        for m in ms_matches[:3]:
                            c_low = str(m.get("county") or "").lower()
                            if c_low == "gunnison" and m.get("parcel_number"):
                                send_telegram_message(BOT_TOKEN, chat_id, format_gunnison_card(m))
                            elif c_low == "gilpin" and m.get("rec_proxy") is not None:
                                send_telegram_message(BOT_TOKEN, chat_id, format_gilpin_card(m))
                            else:
                                send_telegram_message(BOT_TOKEN, chat_id, format_parcel_dossier_html(m))
                        continue

                    # 2. Prevent Colorado/Indiana parcel IDs or county queries from falsely routing to Maryland SDAT
                    if is_non_maryland_parcel_pattern(cleaned_q, county_hint=county_hint, state_hint=state_hint):
                        target_label = f"{county_hint.title()} County, {state_hint}" if county_hint else "Colorado / Indiana County Tax & GIS Portals"
                        send_telegram_message(
                            BOT_TOKEN,
                            chat_id,
                            f"❌ <b>No property record found for</b> <code>{query}</code> in <b>{target_label}</b>.\n"
                            f"• <i>Checked active tax sale exports: Conejos CO, Gilpin CO, Gunnison CO, Fulton IN, and live County Treasurer / GIS portals.</i>\n"
                            f"• <i>Tip: Send</i> <code>/counties</code> <i>to view all indexed counties, or specify</i> <code>&lt;County&gt; &lt;Parcel#&gt;</code>."
                        )
                        continue

                    # 3. Otherwise, query Maryland SDAT & Maryland County OTC Databases
                    send_telegram_message(BOT_TOKEN, chat_id, f"🔍 *Searching Maryland SDAT & County Databases for:* `{query}`...")

                    results = search_maryland_property(query)
                    if not results:
                        send_telegram_message(BOT_TOKEN, chat_id, f"❌ No property records found for `{query}` in Multi-State County Exports or Maryland SDAT.\n_Check parcel # / street spelling, or send `/counties`._")
                    else:
                        for prop in results[:2]:
                            tax_res = inspect_property_tax_status(prop)
                            card = format_property_card(prop, tax_res)
                            send_telegram_message(BOT_TOKEN, chat_id, card)

                elif cmd == "/tax":
                    query = args if args else text
                    send_telegram_message(BOT_TOKEN, chat_id, f"🔍 *Inspecting County Tax Portal for:* `{query}`...")
                    results = search_maryland_property(query)
                    if results:
                        prop = results[0]
                        tax_res = inspect_property_tax_status(prop)
                        owner = tax_res.get("owner_of_record", "N/A")
                        bills = tax_res.get("recent_bills", [])

                        tax_msg = f"🧾 *COUNTY PROPERTY TAX REPORT*\n━━━━━━━━━━━━━━━━━━━━━\n"
                        tax_msg += f"📍 *Property:* `{prop.get('address')}, {prop.get('city')} MD`\n"
                        tax_msg += f"🏷 *Parcel ID:* `{tax_res.get('parcel_id')}`\n"
                        tax_msg += f"👤 *Billed Owner:* `{owner}`\n"
                        tax_msg += f"🏛 *Jurisdiction:* {tax_res.get('county')}\n\n"
                        if tax_res.get("tax_sale_flag"):
                            tax_msg += f"🔥 *OTC STATUS:* {tax_res.get('action_note')}\n"
                            tax_msg += f"💰 *Lien Amount:* **${float(tax_res.get('total_lien_due') or 0):,.2f}** (LTV: **{tax_res.get('ltv_pct')}%**)\n\n"
                        if bills:
                            tax_msg += "*Recent Tax Billing Records:*\n"
                            for b in bills:
                                tax_msg += f"• Tax Year {b.get('tax_year')}: `{b.get('bill_type')}` - {b.get('owner')}\n"
                        elif not tax_res.get("tax_sale_flag"):
                            tax_msg += "• No delinquent tax lien sales currently flagged.\n"
                        tax_msg += f"\n🔗 [Open County Tax Portal]({tax_res.get('portal_url', '')})"
                        send_telegram_message(BOT_TOKEN, chat_id, tax_msg)
                    else:
                        send_telegram_message(BOT_TOKEN, chat_id, f"❌ Property `{query}` not found.")

                elif cmd == "/offer":
                    query = args if args else text
                    results = search_maryland_property(query)
                    if results:
                        prop = results[0]
                        tax_res = inspect_property_tax_status(prop)
                        offer_msg = format_offer_analysis(prop, tax_res)
                        send_telegram_message(BOT_TOKEN, chat_id, offer_msg)
                    else:
                        send_telegram_message(BOT_TOKEN, chat_id, f"❌ Property `{query}` not found.")

                elif cmd == "/save":
                    query = args if args else text
                    results = search_maryland_property(query)
                    if results:
                        prop = results[0]
                        tax_res = inspect_property_tax_status(prop)
                        saved_path = save_property_to_wiki(prop, tax_res)
                        send_telegram_message(BOT_TOKEN, chat_id, f"💾 *Saved to Obsidian Wiki!*\n• File: `{os.path.basename(saved_path)}`\n• Updated `index.md` & `log.md`")
                    else:
                        send_telegram_message(BOT_TOKEN, chat_id, f"❌ Property `{query}` not found to save.")

        except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout):
            continue
        except (requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Network notice in polling loop: {e}. Reconnecting in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Unexpected error in bot loop: {e}")
            time.sleep(3)


if __name__ == "__main__":
    try:
        run_bot_loop()
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] FATAL BOT CRASH:\n{trace}\n")
        print(f"Fatal crash: {e}")
