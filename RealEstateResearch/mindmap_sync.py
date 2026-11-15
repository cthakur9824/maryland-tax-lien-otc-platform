"""
Obsidian Master Mindmap & Canvas Auto-Synchronizer
Generates and keeps up-to-date:
1. Real Estate Research Mindmap.canvas (Native Obsidian JSON Canvas at vault root)
2. wiki/synthesis/Real Estate Research Master Mind Map.md (Multi-State Mermaid Mindmap + Telemetry)
3. wiki/markets/Maryland Mind Map.md (Refreshed Maryland-focused Mermaid Mindmap + Live County Status)
"""

import os
import json
import datetime
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "raw"
SCRATCH_DIR = BASE_DIR / "scratch"
WIKI_DIR = BASE_DIR / "wiki"

CANVAS_PATH = BASE_DIR / "Real Estate Research Mindmap.canvas"
MASTER_MD_PATH = WIKI_DIR / "synthesis" / "Real Estate Research Master Mind Map.md"
MD_MINDMAP_PATH = WIKI_DIR / "markets" / "Maryland Mind Map.md"
INDEX_PATH = BASE_DIR / "index.md"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def collect_live_metrics() -> Dict[str, Any]:
    """Collect live counts and metrics across MD, CO, IN, VA, Wiki, and Raw datasets."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # 1. Maryland OTC Master (deduplicated by county + account_id)
    md_raw = _load_json(SCRATCH_DIR / "maryland_master_otc_liens.json", [])
    md_by_county: Dict[str, set] = {}
    for r in md_raw:
        c = str(r.get("county", "Unknown")).strip()
        a = str(r.get("account_id", "")).strip()
        if a:
            md_by_county.setdefault(c, set()).add(a)
    md_unique_counts = {k: len(v) for k, v in sorted(md_by_county.items(), key=lambda x: -len(x[1]))}
    md_total_unique = sum(md_unique_counts.values())

    # Anne Arundel & OTC Graded
    graded = _load_json(SCRATCH_DIR / "otc_graded_deals.json", {})
    aa_grade_a = len(graded.get("grade_a", []))
    aa_grade_b = len(graded.get("grade_b", []))
    aa_viable_a = sum(
        1 for x in graded.get("grade_a", [])
        if float(x.get("ltv_pct", 999)) < 30.0 and float(x.get("total_assessed", 0)) >= 10000
    )

    # Kent analyzed
    kent = _load_json(SCRATCH_DIR / "kent_county_analyzed_deals.json", {})
    kent_total = kent.get("total_count", md_unique_counts.get("Kent County", 54))
    kent_t1 = len(kent.get("tier1_alpha", []))

    # 2. Colorado 2026 Datasets
    def _grade_bucket(g_str: str) -> str:
        s = str(g_str or "").strip().upper()
        if s == "A" or s.startswith("GRADE A"):
            return "A"
        if s == "B" or s.startswith("GRADE B"):
            return "B"
        if s == "C" or s.startswith("GRADE C"):
            return "C"
        return "D/F"

    conejos_rows = _load_json(SCRATCH_DIR / "conejos_2026_graded_deals.json", [])
    conejos_grades = {"A": 0, "B": 0, "C": 0, "D/F": 0}
    conejos_sub1k_ab = 0
    conejos_face = 0.0
    conejos_actual = 0.0
    for r in conejos_rows:
        b = _grade_bucket(r.get("grade"))
        conejos_grades[b] += 1
        face = float(r.get("face_amount") or 0)
        act = float(r.get("actual_val") or 0)
        conejos_face += face
        conejos_actual += act
        if b in ("A", "B") and 0 < face < 1000:
            conejos_sub1k_ab += 1

    gilpin_rows = _load_json(SCRATCH_DIR / "gilpin_2026_graded_deals.json", [])
    gilpin_grades = {"A": 0, "B": 0, "C": 0, "D/F": 0}
    gilpin_sub1k_ab = 0
    gilpin_face = 0.0
    gilpin_actual = 0.0
    for r in gilpin_rows:
        b = _grade_bucket(r.get("grade"))
        gilpin_grades[b] += 1
        face = float(r.get("face") or 0)
        act = float(r.get("total_actual") or 0)
        gilpin_face += face
        gilpin_actual += act
        if b in ("A", "B") and 0 < face < 1000:
            gilpin_sub1k_ab += 1

    gunnison_data = _load_json(SCRATCH_DIR / "gunnison_2026_graded_deals.json", {})
    gunnison_rows = gunnison_data.get("parcels", []) if isinstance(gunnison_data, dict) else []
    gunnison_grades = {"A": 0, "B": 0, "C": 0, "D/F": 0}
    gunnison_sub1k_ab = 0
    for r in gunnison_rows:
        b = _grade_bucket(r.get("grade"))
        gunnison_grades[b] += 1
        face = float(r.get("face_amount") or 0)
        if b in ("A", "B") and 0 < face < 1000:
            gunnison_sub1k_ab += 1
    gunnison_face = float(gunnison_data.get("total_face_amount") or sum(float(r.get("face_amount") or 0) for r in gunnison_rows))
    gunnison_actual = float(gunnison_data.get("total_actual_value") or sum(float(r.get("total_actual_value") or 0) for r in gunnison_rows))

    # 3. Vault File Inventory
    wiki_files = list(WIKI_DIR.rglob("*.md")) if WIKI_DIR.exists() else []
    xlsx_files = sorted([p.name for p in RAW_DIR.glob("*.xlsx")]) if RAW_DIR.exists() else []
    pdf_files = sorted([p.name for p in RAW_DIR.glob("*.pdf")]) if RAW_DIR.exists() else []
    py_files = sorted([p.name for p in BASE_DIR.glob("*.py")])

    return {
        "now": now_str,
        "today": today_str,
        "md_total_unique": md_total_unique,
        "md_by_county": md_unique_counts,
        "aa_grade_a": aa_grade_a,
        "aa_viable_a": aa_viable_a,
        "aa_grade_b": aa_grade_b,
        "kent_total": kent_total,
        "kent_t1": kent_t1,
        "conejos": {
            "total": len(conejos_rows),
            "grades": conejos_grades,
            "sub1k_ab": conejos_sub1k_ab,
            "face": conejos_face,
            "actual": conejos_actual,
        },
        "gilpin": {
            "total": len(gilpin_rows),
            "grades": gilpin_grades,
            "sub1k_ab": gilpin_sub1k_ab,
            "face": gilpin_face,
            "actual": gilpin_actual,
        },
        "gunnison": {
            "total": len(gunnison_rows),
            "grades": gunnison_grades,
            "sub1k_ab": gunnison_sub1k_ab,
            "face": gunnison_face,
            "actual": gunnison_actual,
        },
        "co_total_parcels": len(conejos_rows) + len(gilpin_rows) + len(gunnison_rows),
        "co_sub1k_ab_total": conejos_sub1k_ab + gilpin_sub1k_ab + gunnison_sub1k_ab,
        "wiki_count": len(wiki_files),
        "xlsx_count": len(xlsx_files),
        "pdf_count": len(pdf_files),
        "py_count": len(py_files),
    }


def _file_rel(path: Path) -> str:
    """Return Obsidian-vault-relative POSIX path."""
    return path.relative_to(BASE_DIR).as_posix()


def build_obsidian_canvas(m: Dict[str, Any]) -> Dict[str, Any]:
    """Build native JSON Canvas (1.0 spec) with groups, text cards, file links, and edges."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    def add_group(nid: str, x: int, y: int, w: int, h: int, label: str, color: str) -> None:
        nodes.append({"id": nid, "type": "group", "x": x, "y": y, "width": w, "height": h, "label": label, "color": color})

    def add_text(nid: str, x: int, y: int, w: int, h: int, text: str, color: str = None) -> None:
        n: Dict[str, Any] = {"id": nid, "type": "text", "x": x, "y": y, "width": w, "height": h, "text": text}
        if color:
            n["color"] = color
        nodes.append(n)

    def add_file(nid: str, x: int, y: int, w: int, h: int, rel_path: str, color: str = None) -> None:
        if not (BASE_DIR / rel_path).exists():
            return
        n: Dict[str, Any] = {"id": nid, "type": "file", "file": rel_path, "x": x, "y": y, "width": w, "height": h}
        if color:
            n["color"] = color
        nodes.append(n)

    def add_edge(eid: str, fn: str, fs: str, tn: str, ts: str, label: str = None, color: str = None) -> None:
        e: Dict[str, Any] = {"id": eid, "fromNode": fn, "fromSide": fs, "toNode": tn, "toSide": ts}
        if label:
            e["label"] = label
        if color:
            e["color"] = color
        edges.append(e)

    md_c = m["md_by_county"]
    pg_cnt = md_c.get("Prince George's County", 207)
    qac_cnt = md_c.get("Queen Anne's County", 2)
    co_tot = m["co_total_parcels"]
    co_sub1k = m["co_sub1k_ab_total"]

    # ==================== CENTRAL HUB ====================
    add_group("grp_hub", -290, -190, 580, 380, "REAL ESTATE RESEARCH MASTER HUB", "5")
    add_text(
        "hub_core", -265, -160, 530, 220,
        f"# Real Estate Research Command Hub\n"
        f"**Last Synced:** `{m['now']}` *(Auto-Updated)*\n\n"
        f"- **Wiki Knowledge Base:** `{m['wiki_count']}` synthesized notes\n"
        f"- **Master Excel/PDF Data:** `{m['xlsx_count']}` workbooks | `{m['pdf_count']}` county PDFs\n"
        f"- **Maryland OTC Portfolio:** `{m['md_total_unique']:,}` unique parcels across 7 active counties + Carroll FY26\n"
        f"- **Colorado 2026 Auctions:** `{co_tot}` enriched parcels (`{co_sub1k}` Sub-$1k Grade A/B flips)\n"
        f"- **Guardrails:** `$333`/deal MD starter | `$5,000` CO auction budget | `14%` CO / `10%-20%` MD yield",
        "5",
    )
    add_file("hub_index", -265, 80, 255, 85, "index.md", "5")
    add_file("hub_master_md", 10, 80, 255, 85, "wiki/synthesis/Real Estate Research Master Mind Map.md", "5")

    # ==================== BRANCH 1 (TOP-LEFT): MARYLAND OTC & COUNTY LIENS ====================
    add_group("grp_md", -1240, -900, 880, 740, "MARYLAND 24-COUNTY TAX LIENS & LIVE OTC", "2")
    add_text(
        "md_overview", -1215, -870, 410, 240,
        f"## Maryland OTC Inventory ({m['md_total_unique']:,} Unique Parcels)\n"
        f"- **Cecil:** `{md_c.get('Cecil County', 587)}` parcels (`taxsale@cecilcountymd.gov` | `410-996-5385`)\n"
        f"- **Prince George's:** `{pg_cnt}` (`TAXSALE@CO.PG.MD.US` | `301-952-3948`, **20% non-owner**)\n"
        f"- **Anne Arundel:** `{md_c.get('Anne Arundel County', 106)}` (`{m['aa_viable_a']}` viable Grade A, `{m['aa_grade_b']}` Grade B)\n"
        f"- **Kent:** `{m['kent_total']}` (`{m['kent_t1']}` Tier-1 Alpha | `financeinfo@kentgov.org`)\n"
        f"- **Wicomico:** `{md_c.get('Wicomico County', 42)}` (`finance@wicomicocounty.org`)\n"
        f"- **Worcester:** `{md_c.get('Worcester County', 5)}` | **Queen Anne's:** `{qac_cnt}`\n"
        f"- **Baltimore City:** Sub-$333 OTC (`18%` interest, `buyintobmore.baltimorecity.gov`)",
        "2",
    )
    add_text(
        "md_aa_picks", -785, -870, 400, 275,
        "## Anne Arundel OTC Direct Buy Picks\n"
        "- **Email:** `taxsale@aacounty.org` | **Tel:** `(410) 222-1735`\n"
        "- **Finance:** `financeinfo@aacounty.org` | `(410) 222-1144`\n"
        "- **Sub-$1k Picks:**\n"
        "  - `#749` (`500202604103` Henry Ave) — **$383.57** / $30.9k W2 (1.24% LTV)\n"
        "  - `#58` (`188090034122` Galesville slip) — **$436.99** / $28.7k (1.52% LTV)\n"
        "  - `#283` (`311990041926` 843 W Benfield Rd) — **$901.75**\n"
        "- **Single-Parcel Commercial:** `#528` (`400001785100` Dare St Odenton, **$1,974.30** / $450.8k = **0.44% LTV**), `#742` (**$1,011.58**), `#747` (**$1,845.76**)\n"
        "- **7-Lot Assembly:** `#430, #434-#439` (145-169 Forest Rd, **$8,818.39** total / $654.2k assmt)",
        "2",
    )
    add_text(
        "md_carroll", -1215, -610, 410, 215,
        "## Carroll County FY26 Live Tax Sale (June 30, 2026)\n"
        "- **Direct Clerk Email:** `bgesell@carrollcountymd.gov` | `(410) 386-2965`\n"
        "- **Policy:** No public OTC cart; **3 parcels** struck off to `Bidder #1: Carroll County` (`14%` non-owner interest; foreclosure opens Dec 30, 2026):\n"
        "  1. `04010914` Old Finksburg Rd (`1.76 ac R-400`): **$16,790.94** / $187.6k (8.95% LTV)\n"
        "  2. `04015517` 2235 Carrollton Rd (`0.772 ac Agric`): **$13,422.28** / $136.9k (9.80% LTV)\n"
        "  3. `14430541` Dorsey Ln (`0.694 ac Par C`): **$1,168.93** / $3.4k *(residual caution)*",
        "2",
    )
    add_file("md_file_mindmap", -785, -575, 195, 85, "wiki/markets/Maryland Mind Map.md", "2")
    add_file("md_file_24", -580, -575, 195, 85, "wiki/synthesis/Maryland Tax Lien OTC and Surplus Directory - 24 Jurisdictions.md", "2")
    add_file("md_file_aa_doc", -785, -475, 195, 85, "wiki/synthesis/Deal Analysis - Anne Arundel County Tax Liens 2026.md", "2")
    add_file("md_file_carroll_doc", -580, -475, 195, 85, "wiki/markets/Carroll County Land and Tax Sale Market.md", "2")
    add_file("md_file_master_xlsx", -1215, -375, 270, 95, "raw/Maryland_24_Counties_Tax_Lien_OTC_Master_2026.xlsx", "2")
    add_file("md_file_aa_xlsx", -930, -375, 270, 95, "raw/Anne_Arundel_County_MD_2026_Grade_A_OTC_Deals.xlsx", "2")
    add_file("md_file_screen", -645, -375, 260, 95, "wiki/tax-sales/Maryland OTC Tax Liens - Title Confluence Screen.md", "2")

    # ==================== BRANCH 2 (TOP-RIGHT): COLORADO 2026 TAX LIEN AUCTIONS ====================
    add_group("grp_co", 360, -900, 900, 740, "COLORADO 2026 TAX LIEN AUCTIONS (14% INTEREST | 3-YR REDEMPTION)", "4")
    con = m["conejos"]
    gil = m["gilpin"]
    gun = m["gunnison"]
    add_text(
        "co_summary", 385, -870, 420, 235,
        f"## Colorado 2026 Enriched Portfolio (`{co_tot}` Parcels)\n"
        f"- **Conejos County:** `{con['total']}` parcels (`{con['grades']['A']}` A, `{con['grades']['B']}` B | `{con['sub1k_ab']}` Sub-$1k A/B) — Live TylerHost + 2026 SLVGIS polygon centroids\n"
        f"- **Gilpin County:** `{gil['total']}` parcels (`{gil['grades']['A']}` A, `{gil['grades']['B']}` B | `{gil['sub1k_ab']}` Sub-$1k A/B) — Live InfoEnvoy Assessor + GIS (`R*` real vs `N*` MRO)\n"
        f"- **Gunnison County:** `{gun['total']}` parcels (`{gun['grades']['A']}` A, `{gun['grades']['B']}` B | `{gun['sub1k_ab']}` Sub-$1k A/B) — `$61.25M` actual value on `$777.3k` face bids\n"
        f"- **Combined Sub-$1k Grade A/B Flip Queue:** **`{co_sub1k}` deals**\n"
        f"- **Dossier Links:** Every parcel includes Assessor Card, Treasurer Tax Account & GPS Maps Pin.",
        "4",
    )
    add_text(
        "co_strategy", 825, -870, 410, 235,
        "## $5k Budget, Ag Ranch & Trap Rules\n"
        "- **Gunnison $5k Budget Plan:** 5 Grade A improved lots (`$4,931.14` direct / `$5,000` max proxy) backed by `$1.80M` value (`$690/yr` @ 14%)\n"
        "- **Ag Grazing Assessment Anomaly (C.R.S. § 39-1-103(5)(a)):**\n"
        "  - `R072243` (35.02 ac Ohio Creek Valley): `$14k` Ag roll / **$320k sold comp** (`$233.03` lien)\n"
        "  - `R071510 / R071511 / R033389` (223.2 ac Hwy 149): **$320k comp** (`$769.54` combined)\n"
        "- **Conejos 40-80 Ac Flips & Trap Avoidance:** Reject Conejos `5170` severed mineral (`R017432`) & Gilpin `N*` mining claims (`0` surface acres).",
        "4",
    )
    add_file("co_file_gunnison", 385, -615, 275, 95, "wiki/tax-sales/Gunnison County Colorado 2026 Tax Lien Sale - Underwriting Matrix.md", "4")
    add_file("co_file_gilpin", 675, -615, 275, 95, "wiki/tax-sales/Gilpin County Colorado 2026 Tax Lien Sale - Underwriting Matrix.md", "4")
    add_file("co_file_conejos", 965, -615, 270, 95, "wiki/tax-sales/Conejos County Colorado 2026 Tax Lien Sale - Underwriting Matrix.md", "4")
    add_file("co_xlsx_under1k", 385, -495, 275, 95, "raw/Colorado_2026_Under_1000_Face_Grade_A_B_Flip_Deals.xlsx", "4")
    add_file("co_xlsx_5k", 675, -495, 275, 95, "raw/2026 Gunnison County Colorado Tax Lien Sale - Ready_To_Bid_5K_Budget.xlsx", "4")
    add_file("co_xlsx_top25", 965, -495, 270, 95, "raw/2026 Gunnison County Colorado Tax Lien Sale - Ready_To_Bid_Top25.xlsx", "4")
    add_file("co_xlsx_conejos_m", 385, -375, 420, 95, "raw/Conejos_County_CO_2026_Tax_Lien_Due_Diligence_Master.xlsx", "4")
    add_file("co_xlsx_gilpin_m", 820, -375, 415, 95, "raw/2026 Gilpin County Colorado Tax Lien Sale - Ready_To_Bid_Best_Deals.xlsx", "4")

    # ==================== BRANCH 3 (BOTTOM-LEFT): MID-ATLANTIC DEEDS, IN & NATIONWIDE OTC ====================
    add_group("grp_reg", -1240, 260, 880, 620, "MID-ATLANTIC DEEDS (VA/DE/NJ), INDIANA & NATIONWIDE OTC", "6")
    add_text(
        "reg_summary", -1215, 290, 410, 240,
        "## Multi-State Tax Sale & Land Corridors\n"
        "- **Virginia (95 Counties / 38 Cities):** Judicial (`Va Code § 58.1-3965`) & Nonjudicial (`§ 58.1-3975`) Tax Deeds — **0 post-sale redemption**; Special Commissioner deeds.\n"
        "- **Hampton Roads VA Land:** Chesapeake, Hampton, Yorktown, Poquoson perc/public utility infill lots (`$30k/$60k/$90k` buy boxes).\n"
        "- **Delaware Monition Sales:** New Castle, Kent, Sussex sheriff sales (`1-yr` redemption @ **15% penalty**).\n"
        "- **New Jersey Municipalities:** `564` towns (`0%` bid-down + premium, `2-yr` redemption).\n"
        "- **Indiana (Fulton County):** Nov 2026 Sheriff Sale routing integrated into parcel engine.",
        "6",
    )
    add_file("reg_va_deed", -785, 290, 195, 90, "wiki/markets/Virginia Judicial Tax Deed and Independent Cities Market.md", "6")
    add_file("reg_de_deed", -580, 290, 195, 90, "wiki/markets/Delaware Monition and Tax Deed Market.md", "6")
    add_file("reg_nj_lien", -785, 395, 195, 90, "wiki/markets/New Jersey Municipal Tax Sale Market.md", "6")
    add_file("reg_mid_dir", -580, 395, 195, 90, "wiki/synthesis/Regional Mid-Atlantic Tax Sale Master Directory - MD VA NJ DE.md", "6")
    add_file("reg_otc_portals", -1215, 550, 270, 95, "wiki/synthesis/Over-The-Counter Tax Lien Sourcing Portals and Direct Links.md", "6")
    add_file("reg_14_states", -930, 550, 270, 95, "wiki/synthesis/Tax Lien State Directory - 14 Investor Certificate Jurisdictions.md", "6")
    add_file("reg_50_matrix", -645, 550, 260, 95, "wiki/synthesis/50-State Statutory Tax Sale Matrix.md", "6")
    add_file("reg_hr_xlsx", -1215, 665, 270, 95, "raw/Hampton_Roads_Active_Lots_2026-09-01.xlsx", "6")
    add_file("reg_hr_buybox", -930, 665, 270, 95, "wiki/synthesis/Buy Box - Hampton Roads Infill Land and Lots.md", "6")
    add_file("reg_in_xlsx", -645, 665, 260, 95, "raw/Fulton County Indiana Sheriff Sale (November 2026) - Full Export.xlsx", "6")

    # ==================== BRANCH 4 (BOTTOM-CENTER): LAND PLAYBOOKS, SELLER FINANCE & DOSSIERS ====================
    add_group("grp_play", -310, 260, 620, 620, "DUE DILIGENCE, LAND FLIPPING & PROPERTY DOSSIERS", "3")
    add_text(
        "play_rules", -285, 290, 570, 170,
        "## Core Deal Rules & Monetization Engines\n"
        "- **4-Stage Due Diligence Funnel:** SDAT -> GIS/Flood/Perc -> PACER Bankruptcy/Liens -> MAO (< 30% LTV target).\n"
        "- **Title & Exit:** Quiet Title / Tax Title Services (TTS) certification -> **Seller Financing / Land Contracts** (Contract for Deed, triple-net buyer maintenance, Dodd-Frank checks).\n"
        "- **Analyzed Property Dossiers:** `1883 Cedar Dr (Severn MD)`, `629 Queenstown Rd`, `19036 Chandlee Mill Rd`, `27040 Oxley Dr`, `Glen Dr (Westminster)`, `Dennett Rd (Oakland)`, `Araby Church Rd`.\n"
        "- **Multifamily Benchmarks:** South FL Q2 2026 (`Miami 4.75% cap`, `Ft Lauderdale 5.10%`, `West Palm Beach 5.25%`).",
        "3",
    )
    add_file("play_funnel", -285, 480, 180, 85, "wiki/concepts/Property Due Diligence Funnel.md", "3")
    add_file("play_seller", -95, 480, 185, 85, "wiki/concepts/Seller Financing and Land Contracts.md", "3")
    add_file("play_quiet", 100, 480, 185, 85, "wiki/concepts/Tax Title Clearance and Quiet Title Actions.md", "3")
    add_file("play_blueprint", -285, 580, 180, 85, "wiki/synthesis/Summary - Blueprint Chetan Thakur.md", "3")
    add_file("play_guardrail", -95, 580, 185, 85, "wiki/synthesis/Maryland Tax Lien Deal Structuring - Budget and Guardrails.md", "3")
    add_file("play_lots30k", 100, 580, 185, 85, "wiki/synthesis/Maryland Lots Under 30k.md", "3")
    add_file("play_cedar", -285, 680, 280, 85, "wiki/Analysis - 1883 Cedar Drive Severn MD.md", "3")
    add_file("play_sofla", 10, 680, 275, 85, "wiki/synthesis/Summary - South Florida Multifamily Q2 2026 Report.md", "3")

    # ==================== BRANCH 5 (BOTTOM-RIGHT): LIVE AUTOMATION, ROUTER & AUTO-SYNC ====================
    add_group("grp_bot", 360, 260, 900, 620, "LIVE AUTOMATION, MULTI-STATE BOT & AUTO-SYNC PIPELINE", "1")
    add_text(
        "bot_arch", 385, 290, 420, 235,
        "## Live Platform (`@RealestateResearch_bot` & Web UI)\n"
        "- **Web Dashboard:** `http://localhost:8080` (`app.py` + Render 24/7 keep-alive).\n"
        "- **Telegram Commands:** `/tax`, `/parcel`, `/5k`, `/gilpin`, `/gradea`, `/deals [county]`, `/sync`, `/import`.\n"
        "- **Multi-State Intelligence (`multi_state_parcel_engine.py`):**\n"
        "  - Auto-routes `R0*`/`N0*`/`M0*` CO IDs -> Conejos (`TylerHost`), Gilpin (`InfoEnvoy`), Gunnison (`Spatialest`) instead of false MD SDAT fallbacks.\n"
        "  - Emits direct **Assessor Card**, **Treasurer Account**, & **Google Maps GPS** links.\n"
        "- **Continuous Sync:** `12h` county crawler (`otc_manager.py`) + `mindmap_sync.py` auto-refreshes this Canvas & Mermaid mindmaps on every ingestion!",
        "1",
    )
    add_file("bot_doc", 825, 290, 410, 110, "wiki/Synthesis - Maryland SDAT and Tax Lien Telegram Intelligence Bot.md", "1")
    add_file("bot_log", 825, 415, 410, 110, "log.md", "1")
    add_file("bot_app", 385, 550, 200, 85, "app.py", "1")
    add_file("bot_tg", 595, 550, 210, 85, "real_estate_telegram_bot.py", "1")
    add_file("bot_router", 815, 550, 210, 85, "multi_state_parcel_engine.py", "1")
    add_file("bot_sync", 1035, 550, 200, 85, "mindmap_sync.py", "1")
    add_file("bot_otc", 385, 665, 275, 85, "otc_manager.py", "1")
    add_file("bot_title", 675, 665, 275, 85, "title_search_engine.py", "1")
    add_file("bot_claude", 965, 665, 270, 85, "CLAUDE.md", "1")

    # ==================== EDGES ====================
    add_edge("e_hub_md", "hub_core", "left", "md_aa_picks", "right", "Maryland OTC", "2")
    add_edge("e_hub_co", "hub_core", "right", "co_summary", "left", "Colorado 2026", "4")
    add_edge("e_hub_reg", "hub_core", "bottom", "reg_summary", "top", "VA / DE / NJ / IN", "6")
    add_edge("e_hub_play", "hub_core", "bottom", "play_rules", "top", "Playbooks & Dossiers", "3")
    add_edge("e_hub_bot", "hub_core", "bottom", "bot_arch", "top", "Live Auto-Sync", "1")
    add_edge("e_bot_md", "bot_sync", "top", "md_overview", "bottom", "12h OTC Crawl", "1")

    return {"nodes": nodes, "edges": edges}


def build_master_mindmap_md(m: Dict[str, Any]) -> str:
    """Generate wiki/synthesis/Real Estate Research Master Mind Map.md."""
    md_c = m["md_by_county"]
    con = m["conejos"]
    gil = m["gilpin"]
    gun = m["gunnison"]

    return f"""---
category: synthesis
tags: [mind-map, obsidian-canvas, multi-state, maryland, colorado, virginia, delaware, new-jersey, indiana, tax-liens, otc-tax-liens, automation]
created: 2026-11-15
updated: {m['today']}
sources:
  - "[Real Estate Research Index](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/index.md)"
  - "[Maryland Multi-County Tax Lien OTC Master Directory 2026](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/wiki/synthesis/Maryland%20Multi-County%20Tax%20Lien%20OTC%20Master%20Directory%202026.md)"
  - "[Colorado Sub-$1,000 Grade A/B Flip Deals Workbook](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Colorado_2026_Under_1000_Face_Grade_A_B_Flip_Deals.xlsx)"
  - "[Anne Arundel County Grade A OTC Deals Workbook](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Anne_Arundel_County_MD_2026_Grade_A_OTC_Deals.xlsx)"
  - "[Carroll County FY 2026 Tax Sale Results](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Carroll_FY26_Results.pdf)"
---

# Real Estate Research Master Mind Map

> [!NOTE] Auto-Synchronized Obsidian Mindmap (`Last Updated: {m['now']}`)
> This master mindmap—together with the interactive Obsidian Canvas board ([`Real Estate Research Mindmap.canvas`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/Real%20Estate%20Research%20Mindmap.canvas)) and [[Maryland Mind Map]]—is automatically regenerated by [`mindmap_sync.py`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/mindmap_sync.py) whenever OTC county syncs, parcel ingestions, or wiki exports run.

---

## 🧠 Complete Research Mind Map (Mermaid)

```mermaid
mindmap
  root((Real Estate Research<br>{m['wiki_count']} Wiki Notes | {m['xlsx_count']} Workbooks))
    Maryland Tax Liens & OTC
      Live Inventory ({m['md_total_unique']:,} Unique Parcels)
        Cecil County ({md_c.get('Cecil County', 587)})
        Prince George's ({md_c.get("Prince George's County", 207)}) 20% Interest
        Anne Arundel ({md_c.get('Anne Arundel County', 106)}) {m['aa_viable_a']} Viable Grade A
        Kent County ({m['kent_total']}) {m['kent_t1']} Tier-1 Alpha
        Wicomico ({md_c.get('Wicomico County', 42)}) | Worcester ({md_c.get('Worcester County', 5)}) | QAC ({md_c.get("Queen Anne's County", 2)})
      Anne Arundel Direct OTC Picks
        Email taxsale@aacounty.org | 410-222-1735
        Sub-$1k (#749 $383, #58 $437, #283 $902)
        Commercial (#528 $1,974 / $450.8k 0.44% LTV)
        7-Lot Forest Rd (#430 & #434-#439 $8,818)
      Carroll County FY26 Live (Jun 30)
        Email bgesell@carrollcountymd.gov | 410-386-2965
        Only 3 County-Held Bidder #1 (14% Interest)
        04010914 ($16.7k / $187.6k) & 04015517 ($13.4k / $136.9k)
        14430541 ($1,169 / $3.4k Residual Caution)
      Baltimore City
        Sub-$333 OTC Liens (18% Yield)
        Buy Into Bmore ($1 - $3,000 Surplus Lots)
    Colorado 2026 Auctions (14% Yield)
      Enriched Totals ({m['co_total_parcels']} Parcels | {m['co_sub1k_ab_total']} Sub-$1k A/B)
      Gunnison County ({gun['total']} Parcels)
        {gun['grades']['A']} Grade A | {gun['grades']['B']} Grade B | $5k Budget Plan
        Ag Anomaly C.R.S. 39-1-103 (R072243, R071510)
      Gilpin County ({gil['total']} Parcels)
        {gil['grades']['A']} Grade A | {gil['grades']['B']} Grade B | InfoEnvoy & GIS
        Filter Out N-Account Mining Claims
      Conejos County ({con['total']} Parcels)
        {con['grades']['A']} Grade A | {con['grades']['B']} Grade B | {con['sub1k_ab']} Sub-$1k Flips
        TylerHost + SLVGIS Centroids | Reject 5170 Minerals
    Mid-Atlantic, Indiana & National
      Virginia Tax Deeds (0 Post-Sale Redemption)
        Va Code 58.1-3965 & 3975 (95 Counties / 38 Cities)
        Hampton Roads Buy Box ($30k / $60k / $90k Tiers)
      Delaware Monition (1-Yr @ 15% Penalty)
      New Jersey (564 Towns | 2-Yr Redemption)
      Indiana (Fulton County Nov 2026 Sheriff Sale)
      National Portals (RealAuction, GovEase, SRI, ALDOR)
    Land Playbooks & Conventional Deals
      4-Stage Due Diligence Funnel & MAO
      Well, Septic, Wet-Season Perc & MALPF Ag Zoning
      Quiet Title / TTS -> Seller Financing Land Contracts
      South FL Multifamily (Miami 4.75%, Ft Laud 5.10%, WPB 5.25%)
      Analyzed Dossiers (1883 Cedar, 629 Queenstown, 19036 Chandlee)
    Live Tech Stack & Auto-Sync
      Web Dashboard localhost:8080 (app.py)
      Telegram Bot (@RealestateResearch_bot)
      Multi-State Parcel Router (CO/MD/IN + Maps/Assessor)
      12h OTC Auto-Crawler + mindmap_sync.py
```

---

## 📊 Live Research Telemetry Snapshot

| Research Domain | Live Count / Status | Key Actionable Highlight | Primary Vault File / Workbook |
| :--- | :--- | :--- | :--- |
| **Maryland OTC Master** | **`{m['md_total_unique']:,}`** unique parcels *(7 counties)* | `30` viable Anne Arundel Grade A deals (`taxsale@aacounty.org`) + `54` Kent OTC (`7` Tier-1) | [[Maryland Multi-County Tax Lien OTC Master Directory 2026]] / [`Anne_Arundel_County_MD_2026_Grade_A_OTC_Deals.xlsx`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Anne_Arundel_County_MD_2026_Grade_A_OTC_Deals.xlsx) |
| **Carroll County FY26** | **`3`** County-Held (`Bidder #1`) | **`04010914`** (8.95% LTV) & **`04015517`** (9.80% LTV) via `bgesell@carrollcountymd.gov` | [[Carroll County Land and Tax Sale Market]] / [`Carroll_FY26_Results.pdf`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Carroll_FY26_Results.pdf) |
| **Gunnison County, CO** | **`{gun['total']}`** parcels *(`{gun['grades']['A']}` A, `{gun['grades']['B']}` B)* | `\\$5k` Budget Plan (5 lots, `\\$1.80M` value) + Ag ranch plays (`R072243`, `R071510`) | [[Gunnison County Colorado 2026 Tax Lien Sale - Underwriting Matrix]] |
| **Gilpin County, CO** | **`{gil['total']}`** parcels *(`{gil['grades']['A']}` A, `{gil['grades']['B']}` B)* | `15` Sub-`\\$1k` flips + InfoEnvoy Assessor & Treasurer links; `56` N-claims filtered | [[Gilpin County Colorado 2026 Tax Lien Sale - Underwriting Matrix]] |
| **Conejos County, CO** | **`{con['total']}`** parcels *(`{con['grades']['A']}` A, `{con['grades']['B']}` B)* | **`{con['sub1k_ab']}`** Sub-`\\$1k` Grade A/B deals + 40–80 ac tracts (`131` total CO sub-`\\$1k` Workbook) | [[Conejos County Colorado 2026 Tax Lien Sale - Underwriting Matrix]] / [`Colorado_2026_Under_1000_Face_Grade_A_B_Flip_Deals.xlsx`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Colorado_2026_Under_1000_Face_Grade_A_B_Flip_Deals.xlsx) |
| **Mid-Atlantic Deeds** | **VA / DE / NJ / IN** | VA 0-redemption deeds + Hampton Roads Buy Box + Fulton IN Nov 2026 routing | [[Regional Mid-Atlantic Tax Sale Master Directory - MD VA NJ DE]] |
| **Obsidian Canvas Board** | **Auto-Synced** | Interactive zoomable mindmap linking all notes, spreadsheets & contacts | [`Real Estate Research Mindmap.canvas`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/Real%20Estate%20Research%20Mindmap.canvas) |

---

## 🔗 Quick Navigation Across Core Research Branches
* **Interactive Visual Board**: [`Real Estate Research Mindmap.canvas`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/Real%20Estate%20Research%20Mindmap.canvas)
* **Maryland Sector Deep Dive**: [[Maryland Mind Map]] | [[Maryland Tax Lien OTC and Surplus Directory - 24 Jurisdictions]] | [[Deal Analysis - Anne Arundel County Tax Liens 2026]] | [[Deal Analysis - Kent County Tax Liens 2026]] | [[Carroll County Land and Tax Sale Market]]
* **Colorado 2026 Matrices**: [[Conejos County Colorado 2026 Tax Lien Sale - Underwriting Matrix]] | [[Gilpin County Colorado 2026 Tax Lien Sale - Underwriting Matrix]] | [[Gunnison County Colorado 2026 Tax Lien Sale - Underwriting Matrix]]
* **Regional & Strategy**: [[Regional Mid-Atlantic Tax Sale Master Directory - MD VA NJ DE]] | [[Over-The-Counter Tax Lien Sourcing Portals and Direct Links]] | [[Property Due Diligence Funnel]] | [[Seller Financing and Land Contracts]] | [[Buy Box - Hampton Roads Infill Land and Lots]]
* **System & Bot**: [[Synthesis - Maryland SDAT and Tax Lien Telegram Intelligence Bot]] | [[1000 Dollar Maryland Investment Plan - Deal Sourcing and Allocation]] | [[Maryland Tax Lien Deal Structuring - Budget and Guardrails]]
"""


def update_maryland_mindmap(m: Dict[str, Any]) -> None:
    """Refresh wiki/markets/Maryland Mind Map.md with current 24-jurisdiction, AA, and Carroll FY26 research."""
    md_c = m["md_by_county"]
    content = f"""---
category: market
tags: [maryland, mind-map, multifamily, single-family, land, zoning, tax-liens, tax-sales, otc-tax-liens, anne-arundel, carroll-county, prince-georges, baltimore-city]
created: 2026-07-14
updated: {m['today']}
sources:
  - "Synthesized from Maryland Department of the Environment (MDE) and local health department guidelines"
  - "[Blueprint Chetan Thakur](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Blueprint_chetan_thakur.pdf)"
  - "[Maryland 24-Counties Tax Lien OTC Master 2026](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Maryland_24_Counties_Tax_Lien_OTC_Master_2026.xlsx)"
  - "[Anne Arundel County 2026 Remaining Tax Liens List](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Anne-Arundell-list-of-liens.pdf)"
  - "[Carroll County FY 2026 Tax Sale Results](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Carroll_FY26_Results.pdf)"
---

# Maryland Mind Map

This page presents the **live, auto-updated** structural mind map of the Maryland real estate market across residential sectors, utility/perc rules, agricultural zoning, **24-jurisdiction tax lien & OTC acquisition channels**, and direct county purchase desks. *(For all states including Colorado, Virginia, Delaware, New Jersey, and Indiana, see [[Real Estate Research Master Mind Map]] and [`Real Estate Research Mindmap.canvas`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/Real%20Estate%20Research%20Mindmap.canvas).)*

> **Auto-Synced Telemetry (`{m['now']}`):** **`{m['md_total_unique']:,}` unique MD OTC parcels** indexed across **7 synced counties** + **3 live Carroll County FY26 County-Held (`Bidder #1`) certificates**.

---

## Visual Mind Map (Mermaid)

```mermaid
mindmap
  root((Maryland Real Estate<br>{m['md_total_unique']:,} OTC Parcels))
    Multifamily
      Zoning & Density
        High-density R-H, R-3, R-4 & Mixed-Use MXD
        APFO Traffic/School Limits (Montgomery, Howard)
      Infrastructure & Environment
        Mandatory Public Water & Sewer
        Chesapeake Bay Critical Area (1,000 ft)
      Core Submarkets
        Montgomery County I-270
        Prince George's County
        Baltimore City & County
    Single-Family
      Suburban Infill & PUDs
      Rural & Exurban (1-5+ Acres, Well/Septic)
      Forest Conservation & Stormwater ESD
    Land, Utilities & Perc Rules
      Public Sewer (10-Yr Plan S-1 / S-3 / S-5)
      Wells (MDE Licensed + Certificate of Potability)
      Perc Approved Lots (Wet Season Feb-May + 10k sq ft Reserve + BAT Nitrogen)
      Farming Lands (AG Zoning 1/20-50 ac, MALPF & Rural Legacy Easements)
    Tax Sales & OTC Channels (24 Jurisdictions)
      Legal Framework (MD Tax-Property Art)
        10%-20% Statutory Yield | Super-Priority Lien
        6-Mo (Non-Owner) / 9-Mo (Owner) Redemption
        Circuit Court Foreclosure -> Fee-Simple Deed
      Live Active OTC Inventories
        Cecil County ({md_c.get('Cecil County', 587)}) taxsale@cecilcountymd.gov
        Prince George's ({md_c.get("Prince George's County", 207)}) TAXSALE@CO.PG.MD.US (20% Yield)
        Anne Arundel ({md_c.get('Anne Arundel County', 106)}) taxsale@aacounty.org ({m['aa_viable_a']} Grade A)
        Kent County ({m['kent_total']}) financeinfo@kentgov.org ({m['kent_t1']} Tier-1)
        Wicomico ({md_c.get('Wicomico County', 42)}) | Worcester ({md_c.get('Worcester County', 5)}) | QAC ({md_c.get("Queen Anne's County", 2)})
        Carroll FY26 ({3} Bidder #1 Held) bgesell@carrollcountymd.gov (14% Yield)
        Baltimore City (Sub-$333 OTC 18% | Buy Into Bmore $1-$3k)
      Live Verification Stack
        SDAT + MD iMAP + MDLandRec Liber/Folio
        Title Confluence Engine (Grade A/B Screening)
        Telegram Bot @RealestateResearch_bot & localhost:8080
```

---

## Detailed Category Breakdown

### 1. Multifamily Housing
* **Zoning & Density**: High-density zones (`R-H`, `R-3`/`R-4`, `MXD`) requiring public water and sewer and Adequate Public Facilities Ordinance (`APFO`) clearance.
* **Critical Areas**: Projects within 1,000 feet of the Chesapeake Bay or tidal tributaries require Critical Area Commission compliance.

### 2. Single-Family Housing
* **Suburban**: Public water/sewer with Environmental Site Design (`ESD`) stormwater rules.
* **Exurban/Rural**: Larger lots (1–5+ acres) in Carroll, Frederick, and the Eastern Shore relying on private wells, septic systems, and Forest Conservation Act compliance.

### 3. Land & Lots with Public Sewer
* **10-Year Water & Sewerage Categories**: `S-1` (connected), `S-3` (1–3 yrs), `S-5` (5–10 yrs), `W/S-6` (no public service planned). Public sewer eliminates wet-season perc failure risk.

### 4. Land & Lots with Wells & Perc Approval
* **Wells**: Drilled by MDE-licensed drillers; requires a Health Department **Certificate of Potability (COP)**.
* **Perc Tests**: Restricted in many counties to wet season (**February–May**); requires a primary field plus **10,000 sq ft reserve area** (plus Best Available Technology / `BAT` nitrogen units inside Critical Areas).

### 5. Farming Lands
* **Agricultural Zoning (`AG`)**: Density typically capped at 1 dwelling per 20–50 acres, often encumbered by **MALPF** or **Rural Legacy** easements.

### 6. Live Maryland Tax Sale & OTC Acquisition Channels
* **Statutory Framework**: Governed by **MD Tax-Property Article Title 14, Subtitle 8** (`6-month` non-owner / `9-month` owner redemption; super-priority lien earning `10%–20%` statutory interest; judicial Circuit Court foreclosure).
* **Primary Live Acquisition Corridors**:
  * **[[Deal Analysis - Anne Arundel County Tax Liens 2026]]**: `106` remaining liens (`{m['aa_viable_a']}` viable Grade A deals in [`Anne_Arundel_County_MD_2026_Grade_A_OTC_Deals.xlsx`](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/raw/Anne_Arundel_County_MD_2026_Grade_A_OTC_Deals.xlsx)). Top picks include `#749` (\\$383.57), `#58` (\\$436.99), `#283` (\\$901.75), `#528` (\\$1,974.30 @ **0.44% LTV**), `#742`/`#747`, and the 7-lot Forest Rd assembly (`#430, #434–#439`). **Buy Desk:** `taxsale@aacounty.org` | `(410) 222-1735`.
  * **[[Carroll County Land and Tax Sale Market]]**: Live June 30, 2026 results confirmed **3 County-Held (`Bidder #1`) certificates** (`04010914` \\$16,790.94 / \\$187.6k; `04015517` \\$13,422.28 / \\$136.9k; `14430541` \\$1,168.93 / \\$3.4k residual caution) at **14% statutory interest**. **Tax Sale Coordinator:** `bgesell@carrollcountymd.gov` | `(410) 386-2965`.
  * **[[Prince Georges County Tax Sale Market]]**: `{md_c.get("Prince George's County", 207)}` assignment liens (`FY2025` & `FY2026`) earning **20% statutory interest** (`TAXSALE@CO.PG.MD.US` | `(301) 952-3948`).
  * **[[Deal Analysis - Kent County Tax Liens 2026]]**: `{m['kent_total']}` OTC certificates (`{m['kent_t1']}` Tier-1 Alpha micro-liens via `financeinfo@kentgov.org`).
  * **[[Baltimore City Tax Sale Market]]**: Sub-\\$333 residual certificates (**18% yield**) + fixed-price infill lots via `Buy Into Bmore` (\\$1–\\$3,000).
  * **Cecil, Wicomico, Worcester & Queen Anne's**: Live county-held PDF inventories indexed in [[Maryland Multi-County Tax Lien OTC Master Directory 2026]].

---

## 🔗 Related Wiki Pages
* [[Real Estate Research Master Mind Map]]
* [[Maryland Multi-County Tax Lien OTC Master Directory 2026]]
* [[Maryland Tax Lien OTC and Surplus Directory - 24 Jurisdictions]]
* [[Maryland OTC Tax Liens - Title Confluence Screen]]
* [[Deal Analysis - Anne Arundel County Tax Liens 2026]]
* [[Deal Analysis - Kent County Tax Liens 2026]]
* [[Carroll County Land and Tax Sale Market]]
* [[Baltimore City Tax Sale Market]]
* [[Prince Georges County Tax Sale Market]]
* [[Summary - Blueprint Chetan Thakur]]
* [[Maryland Tax Lien Deal Structuring - Budget and Guardrails]]
* [[Land Banks and Cheap Maryland Lots]]
* [[Maryland Lots Under 30k]]
"""
    MD_MINDMAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_MINDMAP_PATH.write_text(content, encoding="utf-8")


def ensure_index_entry() -> None:
    """Ensure [[Real Estate Research Master Mind Map]] is listed in index.md."""
    if not INDEX_PATH.exists():
        return
    txt = INDEX_PATH.read_text(encoding="utf-8")
    link = "[[Real Estate Research Master Mind Map]]"
    if link in txt:
        return
    entry = f"* {link} - Auto-synced multi-state research mind map & Obsidian Canvas hub covering Maryland (24 counties + Carroll FY26), Colorado (Conejos/Gilpin/Gunnison), Mid-Atlantic tax deeds (VA/DE/NJ), Indiana, land playbooks, and live automation.\n"
    anchor = "## 📊 Synthesis & Portfolio Strategy\n"
    if anchor in txt:
        parts = txt.split(anchor, 1)
        txt = parts[0] + anchor + entry + parts[1]
    else:
        txt += f"\n{anchor}{entry}"
    INDEX_PATH.write_text(txt, encoding="utf-8")


def refresh_all_mindmaps() -> Dict[str, Any]:
    """Refresh Obsidian Canvas, Master Mind Map markdown, Maryland Mind Map, and index.md."""
    metrics = collect_live_metrics()
    canvas_obj = build_obsidian_canvas(metrics)
    CANVAS_PATH.write_text(json.dumps(canvas_obj, indent=2), encoding="utf-8")

    MASTER_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASTER_MD_PATH.write_text(build_master_mindmap_md(metrics), encoding="utf-8")

    update_maryland_mindmap(metrics)
    ensure_index_entry()
    return {
        "canvas": str(CANVAS_PATH),
        "master_md": str(MASTER_MD_PATH),
        "md_mindmap": str(MD_MINDMAP_PATH),
        "nodes": len(canvas_obj["nodes"]),
        "edges": len(canvas_obj["edges"]),
        "metrics": metrics,
    }


if __name__ == "__main__":
    res = refresh_all_mindmaps()
    print(f"Synced Canvas ({res['nodes']} nodes, {res['edges']} edges) -> {res['canvas']}")
    print(f"Synced Master Mindmap -> {res['master_md']}")
    print(f"Synced Maryland Mindmap -> {res['md_mindmap']}")
