"""
Maryland Real Estate & Over-The-Counter (OTC) Tax Lien Live Web Platform + Bot Server
Serves the interactive Web Dashboard, REST API (Live Lookup, File Upload Importer,
Automated County Website Sync, CSV Export), and runs the Telegram Bot + Auto-Sync daemon.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import time
import base64
import urllib.parse
import urllib.request
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from sdat_engine import search_maryland_property
from tax_lien_checker import inspect_property_tax_status, reload_otc_databases
from title_search_engine import analyze_maryland_title
from otc_manager import (
    import_otc_file,
    sync_all_county_websites,
    load_master_liens,
    load_graded_deals,
    UPLOADS_DIR,
    CSV_OUTPUT_PATH,
    SYNC_STATUS_PATH,
    COUNTY_DEFAULTS,
)
from real_estate_telegram_bot import run_bot_loop

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8080"))
ENABLE_TELEGRAM_BOT = os.environ.get("ENABLE_TELEGRAM_BOT", "true").lower() in ("1", "true", "yes")


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Maryland Tax Lien & OTC Live Intelligence Platform</title>
  <style>
    :root {
      --bg: #0b1120;
      --surface: #111827;
      --surface2: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --green: #22c55e;
      --amber: #f59e0b;
      --red: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding-bottom: 60px;
    }
    header {
      background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
      border-bottom: 1px solid var(--border);
      padding: 20px 28px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }
    header h1 { font-size: 1.35rem; font-weight: 700; letter-spacing: -0.02em; }
    header p { color: var(--muted); font-size: 0.88rem; margin-top: 2px; }
    .header-actions { display: flex; gap: 10px; flex-wrap: wrap; }
    .btn {
      background: var(--accent);
      color: #0f172a;
      border: none;
      padding: 9px 16px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.86rem;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: opacity 0.15s;
    }
    .btn:hover { opacity: 0.9; }
    .btn-secondary {
      background: var(--surface2);
      color: var(--text);
      border: 1px solid var(--border);
    }
    .btn-green { background: var(--green); color: #052e16; }
    .container { max-width: 1440px; margin: 0 auto; padding: 24px 28px; }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .kpi-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 20px;
    }
    .kpi-label { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
    .kpi-val { font-size: 1.75rem; font-weight: 700; margin-top: 4px; color: var(--text); }
    .kpi-sub { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }
    .tabs {
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 20px;
      flex-wrap: wrap;
    }
    .tab-btn {
      background: transparent;
      color: var(--muted);
      border: none;
      padding: 11px 18px;
      font-size: 0.92rem;
      font-weight: 600;
      cursor: pointer;
      border-bottom: 2px solid transparent;
    }
    .tab-btn.active {
      color: var(--accent);
      border-bottom-color: var(--accent);
    }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }
    .filter-bar {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 16px;
      margin-bottom: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }
    input, select {
      background: var(--surface2);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 8px 12px;
      border-radius: 7px;
      font-size: 0.88rem;
    }
    input[type="text"] { min-width: 240px; }
    .table-wrap {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow-x: auto;
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
    th, td {
      padding: 11px 14px;
      text-align: left;
      border-bottom: 1px solid #1e293b;
      white-space: nowrap;
    }
    th {
      background: #0f172a;
      color: var(--muted);
      font-weight: 600;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    tr:hover td { background: rgba(56, 189, 248, 0.04); }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 700;
    }
    .badge-a { background: rgba(34, 197, 94, 0.18); color: #4ade80; border: 1px solid rgba(34,197,94,0.4); }
    .badge-b { background: rgba(56, 189, 248, 0.18); color: #38bdf8; border: 1px solid rgba(56,189,248,0.4); }
    .badge-warn { background: rgba(245, 158, 11, 0.18); color: #fbbf24; }
    .badge-danger { background: rgba(239, 68, 68, 0.18); color: #f87171; }
    .panel-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 22px;
      margin-bottom: 20px;
    }
    .panel-box h3 { margin-bottom: 8px; font-size: 1.08rem; }
    .panel-box p { color: var(--muted); font-size: 0.88rem; margin-bottom: 16px; }
    .status-toast {
      margin-top: 14px;
      padding: 12px 16px;
      border-radius: 8px;
      background: var(--surface2);
      border: 1px solid var(--border);
      font-size: 0.88rem;
      display: none;
      white-space: pre-wrap;
    }
    a.link { color: var(--accent); text-decoration: none; }
    a.link:hover { text-decoration: underline; }
    code {
      background: var(--surface2);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.82rem;
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>🏛️ Maryland Tax Lien & OTC Live Intelligence Platform</h1>
      <p>24-County Over-The-Counter (OTC) Master Inventory • Title Confluence Grading • Automated County Web Sync • Live Telegram Bot</p>
    </div>
    <div class="header-actions">
      <button class="btn btn-green" onclick="triggerCountySync()">🔄 Sync County Websites Now</button>
      <a class="btn btn-secondary" href="/api/export/csv" target="_blank">📥 Download Master CSV</a>
      <button class="btn btn-secondary" onclick="switchTab('import')">📎 Import OTC List</button>
    </div>
  </header>

  <div class="container">
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total Master OTC Liens</div>
        <div class="kpi-val" id="kpi-total">—</div>
        <div class="kpi-sub" id="kpi-counties">Across Maryland jurisdictions</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Grade A Deals (Viable)</div>
        <div class="kpi-val" style="color: var(--green);" id="kpi-grade-a">—</div>
        <div class="kpi-sub">Score ≥ 90/100 &amp; LTV &lt; 30%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Grade B Deals</div>
        <div class="kpi-val" style="color: var(--accent);" id="kpi-grade-b">—</div>
        <div class="kpi-sub">Score 75–89/100 Low-Risk Title</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Sub-$333 Guardrail Deals</div>
        <div class="kpi-val" style="color: var(--amber);" id="kpi-micro">—</div>
        <div class="kpi-sub">Tier 1 Micro-Capital Liens</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Auto-Sync Engine</div>
        <div class="kpi-val" style="font-size: 1.05rem; margin-top: 10px;" id="kpi-sync">Active (12h Cycle)</div>
        <div class="kpi-sub">Telegram Bot &amp; Web Crawler Online</div>
      </div>
    </div>

    <div id="global-toast" class="status-toast" style="margin-bottom: 18px;"></div>

    <div class="tabs">
      <button class="tab-btn active" id="tabbtn-gradea" onclick="switchTab('gradea')">🏆 Grade A &amp; B Title Confluence Deals</button>
      <button class="tab-btn" id="tabbtn-master" onclick="switchTab('master')">🗂️ All-County OTC Master List</button>
      <button class="tab-btn" id="tabbtn-import" onclick="switchTab('import')">📥 Import OTC File &amp; Auto-Sync</button>
      <button class="tab-btn" id="tabbtn-lookup" onclick="switchTab('lookup')">🔍 Live SDAT &amp; Title Search</button>
    </div>

    <!-- TAB 1: GRADE A & B DEALS -->
    <div class="tab-panel active" id="panel-gradea">
      <div class="filter-bar">
        <input type="text" id="grade-search" placeholder="Search address, city, owner, account #..." oninput="renderGradedTable()" />
        <select id="grade-filter" onchange="renderGradedTable()">
          <option value="A_VIABLE">Grade A Only — Viable Equity (30 Deals, LTV &lt; 30%)</option>
          <option value="A_ALL">Grade A — All 33 Parcels (Includes 3 High-LTV Slivers)</option>
          <option value="B">Grade B — Clean Low-Risk Deals (64 Parcels)</option>
          <option value="ALL">All Graded Deals (Grade A + Grade B)</option>
        </select>
        <select id="grade-max-bid" onchange="renderGradedTable()">
          <option value="9999999">Any Lien Amount</option>
          <option value="500">Lien ≤ $500</option>
          <option value="1500">Lien ≤ $1,500</option>
          <option value="3500">Lien ≤ $3,500</option>
          <option value="10000">Lien ≤ $10,000</option>
        </select>
        <span id="grade-count-label" style="color: var(--muted); font-size: 0.85rem; margin-left: auto;"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>List #</th>
              <th>SDAT Account #</th>
              <th>Owner of Record</th>
              <th>Address &amp; City</th>
              <th>Assessed Value</th>
              <th>Tax Lien Due</th>
              <th>LTV %</th>
              <th>Title Score</th>
              <th>Recorded Deed (Liber/Folio)</th>
              <th>Prior Deed</th>
              <th>Subdivision / Lot</th>
              <th>Area &amp; Zoning</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody id="graded-tbody"></tbody>
        </table>
      </div>
    </div>

    <!-- TAB 2: MASTER OTC INVENTORY -->
    <div class="tab-panel" id="panel-master">
      <div class="filter-bar">
        <input type="text" id="master-search" placeholder="Search account ID, owner, street, description..." oninput="renderMasterTable()" />
        <select id="master-county" onchange="renderMasterTable()">
          <option value="">All Maryland Counties</option>
        </select>
        <select id="master-tier" onchange="renderMasterTable()">
          <option value="">All Investment Tiers</option>
          <option value="Tier 1">Tier 1: Alpha / Micro-Lien</option>
          <option value="Tier 2">Tier 2: High Equity</option>
          <option value="Tier 3">Tier 3: Infill / Cluster</option>
          <option value="Tier 4">Tier 4: High Risk / Toxic</option>
        </select>
        <select id="master-max-bid" onchange="renderMasterTable()">
          <option value="9999999">Any Opening Bid</option>
          <option value="334">Bid ≤ $333 ($1k Guardrail)</option>
          <option value="1000">Bid ≤ $1,000</option>
          <option value="2500">Bid ≤ $2,500</option>
          <option value="10000">Bid ≤ $10,000</option>
        </select>
        <span id="master-count-label" style="color: var(--muted); font-size: 0.85rem; margin-left: auto;"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>County</th>
              <th>List #</th>
              <th>Account / APN ID</th>
              <th>Owner of Record</th>
              <th>Property Address / Description</th>
              <th>Assessed Value</th>
              <th>Opening Bid / Lien</th>
              <th>LTV %</th>
              <th>Equity Spread</th>
              <th>Interest &amp; Window</th>
              <th>Investment Tier</th>
              <th>County Contact</th>
            </tr>
          </thead>
          <tbody id="master-tbody"></tbody>
        </table>
      </div>
    </div>

    <!-- TAB 3: IMPORT & AUTO-SYNC -->
    <div class="tab-panel" id="panel-import">
      <div class="panel-box">
        <h3>📎 Upload &amp; Import New County Over-The-Counter (OTC) List</h3>
        <p>Upload any county tax sale or remaining liens file (<code>.csv</code>, <code>.xlsx</code>, <code>.pdf</code>, or <code>.json</code>). The platform automatically standardizes the records, runs SDAT &amp; Title Confluence grading on low-LTV candidates, updates the master database, and hot-reloads the Telegram bot.</p>
        <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center;">
          <input type="file" id="otc-file-input" accept=".csv,.xlsx,.xls,.pdf,.json" />
          <select id="otc-county-hint">
            <option value="">Auto-Detect County from File</option>
            <option value="Anne Arundel County">Anne Arundel County</option>
            <option value="Baltimore City">Baltimore City</option>
            <option value="Baltimore County">Baltimore County</option>
            <option value="Carroll County">Carroll County</option>
            <option value="Cecil County">Cecil County</option>
            <option value="Caroline County">Caroline County</option>
            <option value="Charles County">Charles County</option>
            <option value="Frederick County">Frederick County</option>
            <option value="Harford County">Harford County</option>
            <option value="Howard County">Howard County</option>
            <option value="Kent County">Kent County</option>
            <option value="Prince George's County">Prince George's County</option>
            <option value="Queen Anne's County">Queen Anne's County</option>
            <option value="Wicomico County">Wicomico County</option>
            <option value="Worcester County">Worcester County</option>
          </select>
          <button class="btn" onclick="uploadOtcFile()">🚀 Import &amp; Grade OTC List</button>
        </div>
        <div id="import-status" class="status-toast"></div>
      </div>

      <div class="panel-box">
        <h3>🌐 Intelligent County Website Crawler &amp; Auto-Sync</h3>
        <p>Our background crawler automatically scans official Maryland county tax sale portals &amp; DocumentCenters every 12 hours (and on-demand via <code>/sync</code> in Telegram or the button below) to pull newly published Over-The-Counter PDF, Excel, and CSV lists.</p>
        <button class="btn btn-green" onclick="triggerCountySync()">🔄 Crawl &amp; Sync All County Websites Now</button>
        <div id="sync-detail-box" class="status-toast" style="display: block; margin-top: 14px;">Loading latest sync report...</div>
      </div>
    </div>

    <!-- TAB 4: LIVE SDAT & TITLE LOOKUP -->
    <div class="tab-panel" id="panel-lookup">
      <div class="panel-box">
        <h3>🔍 Live Maryland SDAT Cadastre, Title Chain &amp; OTC Lien Lookup</h3>
        <p>Enter any Maryland street address or SDAT Account / Parcel ID to query live state assessment records, Liber/Folio deed history, Title Confluence Score (0–100), and county OTC lien status.</p>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <input type="text" id="live-lookup-input" placeholder="e.g. 400001785100 or 1883 Cedar Dr, Severn MD" style="min-width: 360px;" onkeydown="if(event.key==='Enter') runLiveLookup()" />
          <button class="btn" onclick="runLiveLookup()">🔍 Search Property &amp; Title</button>
        </div>
        <div id="lookup-result" class="status-toast"></div>
      </div>
    </div>
  </div>

  <script>
    let GRADED_DATA = { grade_a: [], grade_b: [] };
    let MASTER_DATA = [];
    let OWNER_LOOKUP = {};

    function switchTab(tab) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.getElementById('tabbtn-' + tab).classList.add('active');
      document.getElementById('panel-' + tab).classList.add('active');
    }

    function fmtMoney(n, decimals = 0) {
      const num = Number(n || 0);
      return '$' + num.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    }

    async function loadAllData() {
      try {
        const res = await fetch('/api/data');
        const data = await res.json();
        GRADED_DATA = data.graded || { grade_a: [], grade_b: [] };
        MASTER_DATA = data.master || [];
        OWNER_LOOKUP = {};
        MASTER_DATA.forEach(r => {
          if (r.account_id && r.owner) OWNER_LOOKUP[String(r.account_id).trim()] = r.owner;
        });

        const viableA = (GRADED_DATA.grade_a || []).filter(d => Number(d.ltv_pct) < 30);
        const microDeals = MASTER_DATA.filter(r => Number(r.opening_bid) > 0 && Number(r.opening_bid) <= 450 && Number(r.ltv_pct) < 25);
        const counties = [...new Set(MASTER_DATA.map(r => r.county).filter(Boolean))].sort();

        document.getElementById('kpi-total').textContent = MASTER_DATA.length.toLocaleString();
        document.getElementById('kpi-counties').textContent = counties.length + ' Active MD Counties';
        document.getElementById('kpi-grade-a').textContent = viableA.length + ' (' + (GRADED_DATA.grade_a || []).length + ' total)';
        document.getElementById('kpi-grade-b').textContent = (GRADED_DATA.grade_b || []).length;
        document.getElementById('kpi-micro').textContent = microDeals.length;
        if (data.sync && data.sync.last_sync) {
          document.getElementById('kpi-sync').textContent = data.sync.last_sync;
          document.getElementById('sync-detail-box').textContent = JSON.stringify(data.sync, null, 2);
        } else {
          document.getElementById('sync-detail-box').textContent = 'Ready to sync. Click "Crawl & Sync All County Websites Now" above.';
        }

        const cSelect = document.getElementById('master-county');
        const currentVal = cSelect.value;
        cSelect.innerHTML = '<option value="">All Maryland Counties (' + MASTER_DATA.length + ')</option>';
        counties.forEach(c => {
          const count = MASTER_DATA.filter(r => r.county === c).length;
          const opt = document.createElement('option');
          opt.value = c;
          opt.textContent = c + ' (' + count + ')';
          cSelect.appendChild(opt);
        });
        cSelect.value = currentVal;

        renderGradedTable();
        renderMasterTable();
      } catch (e) {
        console.error('Error loading data:', e);
      }
    }

    function renderGradedTable() {
      const q = (document.getElementById('grade-search').value || '').toLowerCase();
      const mode = document.getElementById('grade-filter').value;
      const maxBid = Number(document.getElementById('grade-max-bid').value || 9999999);

      let rows = [];
      if (mode === 'A_VIABLE') {
        rows = (GRADED_DATA.grade_a || []).filter(d => Number(d.ltv_pct) < 30);
      } else if (mode === 'A_ALL') {
        rows = [...(GRADED_DATA.grade_a || [])];
      } else if (mode === 'B') {
        rows = [...(GRADED_DATA.grade_b || [])];
      } else {
        rows = [...(GRADED_DATA.grade_a || []), ...(GRADED_DATA.grade_b || [])];
      }

      rows.sort((a, b) => Number(a.ltv_pct) - Number(b.ltv_pct) || Number(b.total_assessed) - Number(a.total_assessed));

      rows = rows.filter(d => {
        if (Number(d.tax_lien_amount) > maxBid) return false;
        if (!q) return true;
        const ownerName = OWNER_LOOKUP[String(d.account_no)] || d.owner || '';
        const hay = `${d.list_no} ${d.account_no} ${ownerName} ${d.address} ${d.city} ${d.zoning} ${(d.plat && d.plat.subdivision) || ''}`.toLowerCase();
        return hay.includes(q);
      });

      document.getElementById('grade-count-label').textContent = `Showing ${rows.length} graded parcels`;

      const tbody = document.getElementById('graded-tbody');
      tbody.innerHTML = rows.map((d, i) => {
        const ownerName = OWNER_LOOKUP[String(d.account_no)] || d.owner || 'N/A';
        const ltv = Number(d.ltv_pct || 0);
        const ltvBadge = ltv < 5 ? 'badge-a' : (ltv < 30 ? 'badge-b' : 'badge-danger');
        const gradeBadge = d.grade === 'A' ? 'badge-a' : 'badge-b';
        const currDeed = d.current_deed ? `L.${d.current_deed.liber} / F.${d.current_deed.folio}` : 'N/A';
        const priorDeed = d.prior_deed ? `L.${d.prior_deed.liber} / F.${d.prior_deed.folio}` : 'N/A';
        const subdiv = d.plat ? `${d.plat.subdivision !== 'N/A' ? d.plat.subdivision : ''} (Lot ${d.plat.lot || 'N/A'})` : 'N/A';
        return `<tr>
          <td>${i + 1}</td>
          <td><strong>#${d.list_no || '—'}</strong></td>
          <td><code>${d.account_no}</code></td>
          <td>${ownerName}</td>
          <td>${(d.address || '').replace('None ', '')}, ${d.city || ''}</td>
          <td><strong>${fmtMoney(d.total_assessed)}</strong></td>
          <td><strong>${fmtMoney(d.tax_lien_amount, 2)}</strong></td>
          <td><span class="badge ${ltvBadge}">${ltv.toFixed(2)}%</span></td>
          <td><span class="badge ${gradeBadge}">${d.title_score} (${d.grade})</span></td>
          <td><code>${currDeed}</code></td>
          <td><code>${priorDeed}</code></td>
          <td>${subdiv}</td>
          <td>${d.land_area || ''} • <code>${d.zoning || 'R5'}</code></td>
          <td><a class="link" href="${d.google_maps_url || '#'}" target="_blank">Map</a></td>
        </tr>`;
      }).join('');
    }

    function renderMasterTable() {
      const q = (document.getElementById('master-search').value || '').toLowerCase();
      const county = document.getElementById('master-county').value;
      const tier = document.getElementById('master-tier').value;
      const maxBid = Number(document.getElementById('master-max-bid').value || 9999999);

      let rows = MASTER_DATA.filter(r => {
        if (county && r.county !== county) return false;
        if (tier && !String(r.tier || '').includes(tier)) return false;
        if (Number(r.opening_bid) > maxBid) return false;
        if (!q) return true;
        const hay = `${r.county} ${r.list_no} ${r.account_id} ${r.owner} ${r.address}`.toLowerCase();
        return hay.includes(q);
      });

      document.getElementById('master-count-label').textContent = `Showing ${ Math.min(rows.length, 300) } of ${rows.length} matching parcels`;

      const tbody = document.getElementById('master-tbody');
      tbody.innerHTML = rows.slice(0, 300).map(r => {
        const ltv = Number(r.ltv_pct || 0);
        const ltvClass = ltv <= 10 ? 'badge-a' : (ltv <= 35 ? 'badge-b' : (ltv <= 70 ? 'badge-warn' : 'badge-danger'));
        return `<tr>
          <td><strong>${r.county}</strong></td>
          <td><code>${r.list_no}</code></td>
          <td><code>${r.account_id}</code></td>
          <td>${r.owner}</td>
          <td>${r.address || '—'}</td>
          <td><strong>${fmtMoney(r.assessed_value)}</strong></td>
          <td><strong>${fmtMoney(r.opening_bid, 2)}</strong></td>
          <td><span class="badge ${ltvClass}">${ltv.toFixed(1)}%</span></td>
          <td>${fmtMoney(r.equity_spread)}</td>
          <td>${r.statutory_interest || '12%'} (${r.redemption_window || '6m'})</td>
          <td>${r.tier || ''}</td>
          <td style="font-size:0.78rem; color:var(--muted);">${r.contact_info || ''}</td>
        </tr>`;
      }).join('');
    }

    async function uploadOtcFile() {
      const fileInput = document.getElementById('otc-file-input');
      const countyHint = document.getElementById('otc-county-hint').value;
      const statusBox = document.getElementById('import-status');
      if (!fileInput.files || !fileInput.files[0]) {
        statusBox.style.display = 'block';
        statusBox.textContent = '⚠️ Please choose a .csv, .xlsx, .pdf, or .json OTC list file first.';
        return;
      }
      const file = fileInput.files[0];
      statusBox.style.display = 'block';
      statusBox.textContent = `⏳ Uploading & parsing ${file.name}...`;

      const reader = new FileReader();
      reader.onload = async function(evt) {
        const base64Content = evt.target.result.split(',')[1];
        try {
          const resp = await fetch('/api/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              filename: file.name,
              county: countyHint,
              content_base64: base64Content
            })
          });
          const res = await resp.json();
          statusBox.textContent = JSON.stringify(res, null, 2);
          await loadAllData();
        } catch (err) {
          statusBox.textContent = '❌ Upload error: ' + err;
        }
      };
      reader.readAsDataURL(file);
    }

    async function triggerCountySync() {
      const toast = document.getElementById('global-toast');
      toast.style.display = 'block';
      toast.textContent = '🔄 Crawling official Maryland county websites & DocumentCenters for updated Over-The-Counter (OTC) tax lien lists...';
      try {
        const resp = await fetch('/api/sync', { method: 'POST' });
        const res = await resp.json();
        toast.textContent = `✅ Auto-Sync Complete (${res.last_sync}): Checked ${res.portals_checked} county portals, pulled ${res.files_downloaded} OTC files, added ${res.new_liens_added} new liens, refreshed ${res.liens_updated} existing liens. Total Master OTC Inventory: ${res.total_master_liens} parcels.`;
        document.getElementById('sync-detail-box').textContent = JSON.stringify(res, null, 2);
        await loadAllData();
      } catch (err) {
        toast.textContent = '❌ Sync error: ' + err;
      }
    }

    async function runLiveLookup() {
      const q = document.getElementById('live-lookup-input').value.trim();
      const box = document.getElementById('lookup-result');
      if (!q) return;
      box.style.display = 'block';
      box.textContent = `🔍 Querying Maryland SDAT Cadastre & Title Confluence Engine for "${q}"...`;
      try {
        const resp = await fetch('/api/lookup?q=' + encodeURIComponent(q));
        const res = await resp.json();
        box.textContent = JSON.stringify(res, null, 2);
      } catch (err) {
        box.textContent = '❌ Lookup error: ' + err;
      }
    }

    loadAllData();
  </script>
</body>
</html>
"""


class LivePlatformHandler(BaseHTTPRequestHandler):
    def log_message(self, format_str, *args):
        pass

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path in ("/health", "/ping"):
            bot_health = {}
            if ENABLE_TELEGRAM_BOT:
                try:
                    from real_estate_telegram_bot import get_bot_health
                    bot_health = get_bot_health()
                except Exception as e:
                    bot_health = {"error": str(e)}
            started_at = KEEPALIVE_STATE.get("started_at") or time.time()
            self._send_json({
                "status": "ok",
                "service": "maryland-tax-lien-otc-platform",
                "uptime_seconds": round(time.time() - started_at, 1),
                "telegram_bot_enabled": ENABLE_TELEGRAM_BOT,
                "bot_health": bot_health,
                "keepalive": {
                    "interval_sec": KEEPALIVE_INTERVAL_SEC,
                    "self_ping_count": KEEPALIVE_STATE.get("self_ping_count", 0),
                    "last_self_ping_ts": KEEPALIVE_STATE.get("last_self_ping_ts"),
                    "last_self_ping_status": KEEPALIVE_STATE.get("last_self_ping_status"),
                },
            })
            return

        if path == "/api/data":
            sync_info = {}
            if os.path.exists(SYNC_STATUS_PATH):
                try:
                    with open(SYNC_STATUS_PATH, "r", encoding="utf-8") as f:
                        sync_info = json.load(f)
                except Exception:
                    pass
            self._send_json({
                "graded": load_graded_deals(),
                "master": load_master_liens(),
                "sync": sync_info
            })
            return

        if path == "/api/export/csv":
            if os.path.exists(CSV_OUTPUT_PATH):
                with open(CSV_OUTPUT_PATH, "rb") as f:
                    csv_bytes = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="Maryland_24_Counties_Tax_Lien_OTC_Master_2026.csv"')
                self.send_header("Content-Length", str(len(csv_bytes)))
                self.end_headers()
                self.wfile.write(csv_bytes)
            else:
                self._send_json({"error": "CSV file not found"}, 404)
            return

        if path == "/api/lookup":
            qs = urllib.parse.parse_qs(parsed.query)
            q = (qs.get("q") or [""])[0].strip()
            if not q:
                self._send_json({"error": "Missing query parameter q"}, 400)
                return
            props = search_maryland_property(q)
            if not props:
                self._send_json({"status": "not_found", "query": q}, 404)
                return
            prop = props[0]
            tax_res = inspect_property_tax_status(prop)
            title_res = analyze_maryland_title(prop, tax_res)
            self._send_json({
                "status": "ok",
                "property": prop,
                "tax_status": tax_res,
                "title_confluence": title_res
            })
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/sync":
            report = sync_all_county_websites()
            self._send_json(report)
            return

        if path == "/api/import":
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body)
            filename = payload.get("filename", "uploaded_otc.csv")
            county_hint = payload.get("county") or None
            b64 = payload.get("content_base64", "")
            file_bytes = base64.b64decode(b64)

            safe_name = f"{int(time.time())}_{os.path.basename(filename)}"
            save_path = os.path.join(UPLOADS_DIR, safe_name)
            with open(save_path, "wb") as f:
                f.write(file_bytes)

            result = import_otc_file(save_path, county_hint=county_hint, enrich_sdat=True)
            self._send_json(result)
            return

        self._send_json({"error": "Not found"}, 404)


KEEPALIVE_INTERVAL_SEC = int(os.environ.get("KEEPALIVE_INTERVAL_SEC", "240"))
KEEPALIVE_STATE = {
    "started_at": time.time(),
    "last_self_ping_ts": None,
    "last_self_ping_status": "pending",
    "self_ping_count": 0,
}


def keep_alive_self_ping_worker():
    """
    When RENDER_EXTERNAL_URL (automatically set by Render) or PUBLIC_URL is present,
    pings the public /ping endpoint periodically to supplement external monitors and
    surface connectivity health.
    """
    time.sleep(25)
    while True:
        target_url = (
            os.environ.get("RENDER_EXTERNAL_URL")
            or os.environ.get("PUBLIC_URL")
            or ""
        ).strip().rstrip("/")
        if target_url:
            try:
                req = urllib.request.Request(
                    f"{target_url}/ping",
                    headers={"User-Agent": "Maryland-OTC-KeepAlive/2.0"}
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    _ = resp.read()
                    KEEPALIVE_STATE["last_self_ping_status"] = f"HTTP {resp.status}"
            except Exception as e:
                KEEPALIVE_STATE["last_self_ping_status"] = f"error: {e}"
                print(f"[Keep-Alive Notice] Self-ping to {target_url}/ping: {e}")
            finally:
                KEEPALIVE_STATE["last_self_ping_ts"] = time.time()
                KEEPALIVE_STATE["self_ping_count"] += 1
        time.sleep(KEEPALIVE_INTERVAL_SEC)


def bot_supervisor_worker():
    """
    Watchdog supervisor for the Telegram polling thread. Restarts the polling
    worker cleanly if it ever exits or stops updating its poll heartbeat.
    """
    from real_estate_telegram_bot import BOT_STATE, get_bot_health

    first_launch = True
    while True:
        send_ping = first_launch
        worker = threading.Thread(
            target=run_bot_loop,
            kwargs={"start_auto_sync": True, "send_startup_ping": send_ping},
            daemon=True,
        )
        worker.start()
        first_launch = False

        # Give polling loop up to 90s to enter steady state
        time.sleep(45)
        while worker.is_alive():
            time.sleep(30)
            health = get_bot_health()
            poll_age = health.get("last_poll_age_sec")
            if poll_age is not None and poll_age > 180:
                print(
                    f"[Bot Watchdog] Telegram poll heartbeat stalled ({poll_age}s old); "
                    "spawning replacement polling worker..."
                )
                break

        BOT_STATE["restarts"] = BOT_STATE.get("restarts", 0) + 1
        print(f"[Bot Watchdog] Restarting Telegram bot worker (restart #{BOT_STATE['restarts']}) in 5s...")
        time.sleep(5)


def start_server():
    KEEPALIVE_STATE["started_at"] = time.time()
    try:
        from mindmap_sync import refresh_all_mindmaps
        sync_res = refresh_all_mindmaps()
        print(f"Synced Obsidian Mindmaps & Canvas ({sync_res['nodes']} nodes, {sync_res['edges']} edges).")
    except Exception as e:
        print(f"Notice syncing mindmaps on startup: {e}")

    if ENABLE_TELEGRAM_BOT:
        supervisor_thread = threading.Thread(target=bot_supervisor_worker, daemon=True)
        supervisor_thread.start()
        print("Started self-healing Telegram Bot Supervisor + 12h County OTC Auto-Sync daemon thread.")

    ping_thread = threading.Thread(target=keep_alive_self_ping_worker, daemon=True)
    ping_thread.start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), LivePlatformHandler)
    print(f"Maryland Tax Lien & OTC Live Web Platform listening on http://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    start_server()
