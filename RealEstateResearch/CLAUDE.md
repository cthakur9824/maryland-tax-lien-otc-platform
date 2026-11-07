# LLM Wiki Schema - Real Estate Research

This document defines the schema, conventions, and operational guidelines for the **Real Estate Research** LLM Wiki. Every interaction with this vault must adhere strictly to these rules.

---

## Directory Structure

```
RealEstateResearch/          <- Obsidian Vault Root
├── .obsidian/               <- Obsidian system configuration
├── raw/                     <- Immutable original sources (articles, PDFs, web clips)
│   └── assets/              <- Downloaded images/attachments for raw documents
├── wiki/                    <- Compounding LLM-generated knowledge base pages
│   ├── markets/             <- Geographic market reports (cities, regions, countries)
│   ├── entities/            <- Firms, developers, REITs, investors, agencies
│   ├── concepts/            <- General terms (cap rates, zoning, macro indicators)
│   └── synthesis/           <- Complex comparisons, reports, and portfolio strategies
├── scratch/                 <- Helper scripts, Python code, data parsers
├── index.md                 <- Catalog of the wiki (auto-updated on ingest)
├── log.md                   <- Chronological log of all operations (append-only)
└── CLAUDE.md                <- This schema/configuration file
```

---

## Naming & Linking Conventions

1. **Case & Formatting**: 
   * **Wiki Pages**: Use `Title Case` for all wiki pages (e.g., `wiki/markets/South Florida Market.md`, `wiki/concepts/Cap Rate.md`).
   * **Raw Sources**: Use `YYYY-MM-DD - Descriptive Title.extension` (e.g., `raw/2026-07-14 - Miami Multifamily Market Report.pdf`).
   * **Scratch Scripts**: Use `snake_case` (e.g., `scratch/scrape_zillow.py`).
2. **Wiki Links**: Always link to other wiki pages using standard Obsidian links: `[[Page Name]]` (without directory prefix or `.md` suffix).
   * Example: `According to [[Miami Multifamily Market Report]], the [[Cap Rate]] has compressed...`
3. **Citations**: When synthesizing information, reference the original raw document using markdown file links: `[Source Title](file:///absolute/path/to/raw/source)`.

---

## YAML Frontmatter & Metadata

Every markdown page in the `wiki/` folder must begin with standard YAML frontmatter:

```yaml
---
category: market | entity | concept | synthesis
tags: [real-estate, macro, multifamily, reit, etc]
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources:
  - "[Document Title](file:///path/to/raw/source)"
---
```

---

## Operations

### 1. Ingest Workflow
When a new source is added to `raw/`:
1. **Read & Extract**: Analyze the document thoroughly, extracting key metrics (cap rates, vacancy rates, absorption, pricing trends), claims, entities, and locations.
2. **Review with User**: Discuss key takeaways in chat. Identify which pages in the wiki need to be created or updated.
3. **Write Source Summary**: Create a dedicated summary page under `wiki/synthesis/` (e.g., `wiki/synthesis/Summary - Miami Multifamily Market Report.md`).
4. **Update Entity/Market/Concept Pages**: 
   * Update existing geographic market pages (e.g., `wiki/markets/Miami Market.md`).
   * Update concepts (e.g., `wiki/concepts/Multifamily Housing.md`).
   * Note contradictions (e.g., "Source X claims vacancy is 5%, but Source Y claims it rose to 7%").
5. **Update index.md**: Add the new page and source to the index.
6. **Update log.md**: Append an entry: `## [YYYY-MM-DD] ingest | Added Miami Multifamily Market Report`.

### 2. Query Workflow
When the user asks a question:
1. **Index Search**: Read `index.md` first to locate relevant files.
2. **Deep Read**: Read the target wiki pages to gather synthesized knowledge.
3. **Respond & Citations**: Synthesize the answer, citing specific wiki pages via `[[Page Name]]` and raw sources using local file links.
4. **Capture Insights**: If the response is a complex analysis or comparison, propose creating it as a new synthesis page (e.g., `wiki/synthesis/Comparison - Miami vs Orlando Multifamily.md`).

### 3. Lint Workflow
Periodically run a health check:
1. **Link Verification**: Find broken wiki links (`[[Page]]` targets that do not exist) or orphan pages (pages with zero inbound links).
2. **Contradiction Auditing**: Scan for conflicting metrics (e.g., diverging cap rate projections) and list them for the user.
3. **Gaps & Prompts**: Suggest new concepts that are mentioned in summaries but lack dedicated pages, or recommend web search topics to fill missing data.
