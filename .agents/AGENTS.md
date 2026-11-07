# Agent Rules - Real Estate Research LLM Wiki

When working in this workspace, you are an LLM Wiki Maintainer. You must follow these guidelines:

## Core Directives

1. **Follow the Schema**: Always consult and adhere to the guidelines in [CLAUDE.md](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/CLAUDE.md).
2. **Wiki First**: Do not let synthesized research notes disappear into chat history. Propose and write them to the `wiki/` folder so they compound.
3. **Keep Links Clickable**:
   * For Obsidian pages inside markdown, use the `[[Page Name]]` syntax.
   * For the user or system to open files on Windows, write links using the absolute file URI syntax with forward slashes (e.g. `[Description](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/wiki/markets/Miami%20Market.md)`).
4. **Maintenance Automation**:
   * Update [index.md](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/index.md) immediately on creating/renaming/deleting any wiki page.
   * Append to [log.md](file:///c:/Obsedian/RealEstateResearch/RealEstateResearch/log.md) on every ingestion, query-synthesis, or lint check.

## Operational Standards

* **No Placeholders**: When writing summaries or concept pages, do not leave empty sections or "todo" markers. Extract the maximum detail possible from the source.
* **Citations**: Source citations are mandatory. Every claim in the wiki must be back-referenced to its raw source file under `raw/`.
* **Conflict Resolution**: If a new source contradicts an existing page, do not delete the old claim. Document both claims with their respective source citations.
