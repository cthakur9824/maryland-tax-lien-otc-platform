import os
import re
from pathlib import Path

vault_root = Path(r"c:\Obsedian\RealEstateResearch\RealEstateResearch")
wiki_dir = vault_root / "wiki"
raw_dir = vault_root / "raw"

# Gather all wiki page stems
all_wiki_files = {}
for p in wiki_dir.rglob("*.md"):
    all_wiki_files[p.stem] = p

print(f"Total Wiki Pages Found: {len(all_wiki_files)}")

# Check links
broken_links = []
valid_links = 0
for stem, filepath in all_wiki_files.items():
    content = filepath.read_text(encoding="utf-8")
    # find [[Page Name]]
    links = re.findall(r'\[\[(.*?)\]\]', content)
    for link in links:
        # handle alias like [[Page Name|Display Text]]
        target = link.split("|")[0].strip()
        if target not in all_wiki_files:
            broken_links.append((filepath.name, target))
        else:
            valid_links += 1

print(f"Valid Wiki Links Checked: {valid_links}")
if broken_links:
    print(f"BROKEN LINKS ({len(broken_links)}):")
    for src, tgt in broken_links:
        print(f"  {src} -> [[{tgt}]] (NOT FOUND)")
else:
    print("Zero broken wiki links! All link targets exist.")

# Check index.md
index_file = vault_root / "index.md"
index_content = index_file.read_text(encoding="utf-8")
index_links = re.findall(r'\[\[(.*?)\]\]', index_content)
missing_from_index = []
for stem in all_wiki_files:
    if stem not in index_links:
        missing_from_index.append(stem)

if missing_from_index:
    print(f"\nWiki Pages Missing from index.md ({len(missing_from_index)}):")
    for m in missing_from_index:
        print(f"  - {m}")
else:
    print("\nAll wiki pages are successfully cataloged in index.md!")
