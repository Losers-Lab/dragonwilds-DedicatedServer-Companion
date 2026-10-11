#!/usr/bin/env python3
"""
Dragonwilds Wiki Downloader & LLM Context Extractor
===================================================
Downloads all articles, guides, updates, and transcripts from the official
RuneScape: Dragonwilds Wiki (https://dragonwilds.runescape.wiki).

Exports clean, structured content optimized for LLM contexts, RAG pipelines,
and offline knowledge bases.

Zero external dependencies required (uses standard library urllib, json, re).

Usage:
    python3 scripts/download_wiki.py [options]

Options:
    --output-dir DIR      Directory to save output (default: ./wiki_data)
    --format FORMAT       Output format: all, markdown, jsonl, combined, xml (default: all)
    --batch-size N        Number of pages per API request (default: 50, max: 50)
    --delay SEC           Delay in seconds between requests (default: 0.1)
    --limit N             Max pages to download (for testing, default: all)
    --include-redirects   Include redirect pages (default: False)
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import re
import argparse
from typing import Dict, List, Optional, Tuple

WIKI_API = "https://dragonwilds.runescape.wiki/api.php"
WIKI_EXPORT = "https://dragonwilds.runescape.wiki/w/Special:Export"
USER_AGENT = "DragonwildsWikiDownloader/1.0 (contact: arham; LLM-context-extractor)"

# Relevant namespaces:
# 0: Main content (Monsters, Items, Bosses, Quests, Areas, Recipes, Mechanics)
# 100: Updates (Patch notes, changelogs)
# 120: Transcripts (In-game dialogue, quest text)
# 3004: Guides (Community strategy guides)
TARGET_NAMESPACES = [0, 100, 120, 3004]


def api_request(params: Dict[str, str], retry_count: int = 4) -> dict:
    """Send a GET request to the MediaWiki API with rate limit handling and retries."""
    query_string = urllib.parse.urlencode(params)
    url = f"{WIKI_API}?{query_string}"
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(retry_count):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == retry_count - 1:
                print(f"\n[ERROR] Request failed after {retry_count} attempts: {e}", file=sys.stderr)
                raise
            sleep_time = (attempt + 1) * 2
            print(f"\n[WARN] API request failed ({e}), retrying in {sleep_time}s...", file=sys.stderr)
            time.sleep(sleep_time)


def get_all_page_titles(namespaces: List[int], include_redirects: bool = False) -> List[Tuple[int, int, str]]:
    """Enumerate all pages in the specified namespaces.
    Returns list of (pageid, ns, title).
    """
    pages = []
    print(f"[*] Enumerating pages from namespaces: {namespaces}...")

    for ns in namespaces:
        url_params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": str(ns),
            "aplimit": "500",
            "format": "json",
        }
        if not include_redirects:
            url_params["apfilterredir"] = "nonredirects"

        while True:
            data = api_request(url_params)
            allpages = data.get("query", {}).get("allpages", [])
            for p in allpages:
                pages.append((p["pageid"], p.get("ns", ns), p["title"]))

            if "continue" in data:
                url_params["apcontinue"] = data["continue"]["apcontinue"]
            else:
                break

    print(f"[+] Total pages enumerated: {len(pages)}")
    return pages


def convert_wikitable_to_markdown(table_text: str) -> str:
    """Convert a MediaWiki table {| ... |} to GitHub-Flavored Markdown table."""
    lines = [l.strip() for l in table_text.strip().splitlines() if l.strip()]
    if lines and lines[0].startswith("{"):
        lines = lines[1:]
    if lines and lines[-1].startswith("|}"):
        lines = lines[:-1]

    rows = []
    current_row = []
    is_header = False

    for line in lines:
        if line.startswith("|-"):
            if current_row:
                rows.append((current_row, is_header))
                current_row = []
            is_header = False
        elif line.startswith("!"):
            is_header = True
            cells = [c.strip() for c in line.lstrip("!").split("!!")]
            current_row.extend(cells)
        elif line.startswith("|"):
            cells = [c.strip() for c in line.lstrip("|").split("||")]
            current_row.extend(cells)
        else:
            if current_row:
                current_row[-1] += " " + line

    if current_row:
        rows.append((current_row, is_header))

    if not rows:
        return ""

    out = []
    header_row = None
    data_rows = []
    for r, h in rows:
        if h and header_row is None:
            header_row = r
        else:
            data_rows.append(r)

    if not header_row and data_rows:
        header_row = data_rows.pop(0)

    if not header_row:
        return ""

    num_cols = len(header_row)
    # Clean cells
    cleaned_header = [re.sub(r"\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]", r"\1", c).strip() for c in header_row]
    out.append("| " + " | ".join(cleaned_header) + " |")
    out.append("| " + " | ".join(["---"] * num_cols) + " |")

    for dr in data_rows:
        cleaned_cells = [re.sub(r"\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]", r"\1", c).strip() for c in dr]
        while len(cleaned_cells) < num_cols:
            cleaned_cells.append("")
        out.append("| " + " | ".join(cleaned_cells[:num_cols]) + " |")

    return "\n" + "\n".join(out) + "\n"


def clean_wikitext_to_markdown(title: str, wikitext: str, categories: List[str] = None) -> str:
    """Convert raw wikitext into clean, dense, token-efficient Markdown for LLMs."""
    text = wikitext

    # Remove HTML comments <!-- ... -->
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Clean file/image transclusions [[File:...]]
    text = re.sub(r"\[\[(?:File|Image):[^\]]+\]\]", "", text, flags=re.IGNORECASE)

    # Convert headings
    text = re.sub(r"^====\s*(.*?)\s*====\s*$", r"#### \1", text, flags=re.MULTILINE)
    text = re.sub(r"^===\s*(.*?)\s*===\s*$", r"### \1", text, flags=re.MULTILINE)
    text = re.sub(r"^==\s*(.*?)\s*==\s*$", r"## \1", text, flags=re.MULTILINE)

    # Bold and italics
    text = re.sub(r"'''(.*?)'''", r"**\1**", text)
    text = re.sub(r"''(.*?)''", r"*\1*", text)

    # Drop tables: {{DropsLine|name=...|quantity=...|rarity=...}}
    def format_dropsline(match):
        content = match.group(1)
        params = {}
        for part in content.split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip().lower()] = v.strip()
        name = params.get("name", "Unknown Item")
        qty = params.get("quantity", "1")
        rarity = params.get("rarity", "")
        notes = params.get("raritynotes", "")
        res = f"- **Drop:** {name} (Qty: {qty}"
        if rarity:
            res += f", Rarity: {rarity}"
        if notes:
            clean_notes = re.sub(r"\{\{[^}]+\}\}", "", notes).strip()
            clean_notes = re.sub(r"\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]", r"\1", clean_notes)
            if clean_notes:
                res += f", Notes: {clean_notes}"
        res += ")"
        return res

    text = re.sub(r"\{\{DropsLine\|([^{}\n]+)\}\}", format_dropsline, text, flags=re.IGNORECASE)

    # Recipe template: {{Recipe|facility=...|mat1=...}}
    def format_recipe(match):
        content = match.group(1)
        params = {}
        for part in content.split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip().lower()] = v.strip()
        facility = params.get("facility", "Crafting")
        skill = params.get("skill", "")
        output = params.get("output1", "")
        qty = params.get("output1qty", "1")
        mats = []
        for i in range(1, 10):
            mat = params.get(f"mat{i}")
            mqty = params.get(f"mat{i}qty", "1")
            if mat:
                mats.append(f"{mqty}x {mat}")
        res = [f"**Recipe:** {output} (Qty: {qty})"]
        if facility:
            res.append(f"- **Facility:** {facility}")
        if skill:
            res.append(f"- **Skill:** {skill}")
        if mats:
            res.append(f"- **Materials:** {', '.join(mats)}")
        return "\n" + "\n".join(res) + "\n"

    text = re.sub(r"\{\{Recipe\s*\|(.*?)\}\}", format_recipe, text, flags=re.IGNORECASE | re.DOTALL)

    # Journal entry template: {{Journal entry|...}}
    def format_journal(match):
        body = match.group(1).strip()
        return f"\n### Journal Lore Entry\n\n{body}\n"

    text = re.sub(r"\{\{Journal entry\|(.*?)\}\}", format_journal, text, flags=re.IGNORECASE | re.DOTALL)

    # Infoboxes: convert infobox key-values into structured markdown list
    def format_infobox(match):
        box_type = match.group(1).strip()
        body = match.group(2)
        out = [f"### Infobox: {box_type}"]
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith("|") and "=" in line:
                k, v = line[1:].split("=", 1)
                k = k.strip()
                v = v.strip()
                if v and not v.startswith("{{") and k.lower() not in ("image", "map"):
                    v_clean = re.sub(r"\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]", r"\1", v)
                    out.append(f"- **{k.capitalize()}**: {v_clean}")
        return "\n" + "\n".join(out) + "\n"

    text = re.sub(r"\{\{Infobox\s+([A-Za-z0-9_ ]+)\n(.*?)\}\}", format_infobox, text, flags=re.IGNORECASE | re.DOTALL)

    # MediaWiki tables: {| ... |} -> Markdown table
    text = re.sub(r"\{\|.*?\n\|\}", lambda m: convert_wikitable_to_markdown(m.group(0)), text, flags=re.DOTALL)

    # Wikilinks: [[Target|Label]] -> Label, [[Target]] -> Target
    text = re.sub(r"\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]", r"\1", text)

    # External links: [http://url label] -> [label](http://url)
    text = re.sub(r"\[(https?://[^\s]+)\s+([^\]]+)\]", r"[\2](\1)", text)

    # Remove category tags from bottom
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text, flags=re.IGNORECASE)

    # Remove citations / reflists / navbars / UI templates
    text = re.sub(
        r"\{\{(?:Reflist|Refn|CiteJournal|DropsTableHead|DropsTableBottom|UH|UL|Weapons|Special Effects|Crafting Tree|Calendar|Date page|HasStrategy|Otheruses)[^}]*\}\}",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Compress multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Build final markdown with header
    lines = [f"# {title}\n"]
    if categories:
        clean_cats = [c for c in categories if not c.startswith("Pages ")]
        if clean_cats:
            lines.append(f"**Categories:** {', '.join(clean_cats)}\n")

    lines.append(text.strip())
    return "\n".join(lines)


def sanitize_filename(title: str) -> str:
    """Turn page title into safe filesystem filename."""
    s = re.sub(r'[\\/*?:"<>|]', "_", title)
    s = s.strip().rstrip(". ")
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if s.upper() in reserved:
        s = f"_{s}_"
    return s if s else "untitled"


def export_xml_dump(titles: List[str], output_path: str):
    """Download full MediaWiki XML dump via Special:Export in batches of 300."""
    print(f"[*] Downloading full MediaWiki XML dump ({len(titles)} pages)...")
    batch_size = 300
    headers = {"User-Agent": USER_AGENT}

    # Open XML output file
    with open(output_path, "w", encoding="utf-8") as out_f:
        out_f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        out_f.write('<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">\n')

        for i in range(0, len(titles), batch_size):
            batch_titles = titles[i : i + batch_size]
            body_data = urllib.parse.urlencode({
                "pages": "\n".join(batch_titles),
                "curonly": "1",
            }).encode("utf-8")

            req = urllib.request.Request(WIKI_EXPORT, data=body_data, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    xml_content = resp.read().decode("utf-8", errors="replace")
                    # Extract <page>...</page> blocks
                    page_blocks = re.findall(r"(<page>.*?</page>)", xml_content, flags=re.DOTALL)
                    for block in page_blocks:
                        out_f.write(block + "\n")
                print(f"    XML: Exported {min(i + batch_size, len(titles))}/{len(titles)} pages...")
            except Exception as e:
                print(f"    [WARN] Failed exporting XML batch {i}: {e}", file=sys.stderr)
            time.sleep(0.2)

        out_f.write("</mediawiki>\n")
    print(f"[+] Full XML dump saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Download RuneScape: Dragonwilds Wiki for LLM Context")
    parser.add_argument("--output-dir", default="./wiki_data", help="Output directory")
    parser.add_argument("--format", choices=["all", "markdown", "jsonl", "combined", "xml"], default="all")
    parser.add_argument("--batch-size", type=int, default=50, help="Pages per API batch (max 50)")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between requests in seconds")
    parser.add_argument("--limit", type=int, default=None, help="Max pages to download (for testing)")
    parser.add_argument("--include-redirects", action="store_true", help="Include redirect pages")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    md_pages_dir = os.path.join(args.output_dir, "markdown_pages")
    if args.format in ("all", "markdown"):
        os.makedirs(md_pages_dir, exist_ok=True)

    # 1. Enumerate pages
    pages = get_all_page_titles(TARGET_NAMESPACES, include_redirects=args.include_redirects)
    if args.limit:
        pages = pages[: args.limit]
        print(f"[*] Limiting download to {len(pages)} pages as requested.")

    all_titles = [p[2] for p in pages]

    # If XML only requested
    if args.format == "xml":
        xml_path = os.path.join(args.output_dir, "dragonwilds_wiki_dump.xml")
        export_xml_dump(all_titles, xml_path)
        return

    # 2. Fetch page contents in batches of 50
    jsonl_path = os.path.join(args.output_dir, "dragonwilds_wiki.jsonl")
    combined_path = os.path.join(args.output_dir, "dragonwilds_full_context.txt")

    jsonl_file = open(jsonl_path, "w", encoding="utf-8") if args.format in ("all", "jsonl") else None
    combined_file = open(combined_path, "w", encoding="utf-8") if args.format in ("all", "combined") else None

    total_pages = len(pages)
    processed = 0
    total_words = 0

    print(f"[*] Downloading and converting {total_pages} pages into LLM format...")
    start_time = time.time()

    for i in range(0, total_pages, args.batch_size):
        batch = pages[i : i + args.batch_size]
        page_ids_str = "|".join(str(p[0]) for p in batch)

        params = {
            "action": "query",
            "pageids": page_ids_str,
            "prop": "revisions|categories",
            "rvslots": "*",
            "rvprop": "content",
            "cllimit": "50",
            "format": "json",
        }

        try:
            res = api_request(params)
            query_pages = res.get("query", {}).get("pages", {})

            for pid_str, pdata in query_pages.items():
                title = pdata.get("title", "")
                pid = pdata.get("pageid", 0)
                revisions = pdata.get("revisions", [])
                if not revisions:
                    continue

                wikitext = revisions[0].get("slots", {}).get("main", {}).get("*", "")
                cats = [c["title"].replace("Category:", "") for c in pdata.get("categories", [])]

                # Convert to clean Markdown
                markdown = clean_wikitext_to_markdown(title, wikitext, cats)
                word_count = len(markdown.split())
                total_words += word_count

                page_url = f"https://dragonwilds.runescape.wiki/w/{urllib.parse.quote(title.replace(' ', '_'))}"

                # Write JSONL
                if jsonl_file:
                    entry = {
                        "id": pid,
                        "title": title,
                        "url": page_url,
                        "categories": cats,
                        "markdown": markdown,
                        "wikitext": wikitext,
                        "word_count": word_count,
                    }
                    jsonl_file.write(json.dumps(entry, ensure_ascii=False) + "\n")

                # Write individual markdown file
                if args.format in ("all", "markdown"):
                    filename = sanitize_filename(title) + ".md"
                    filepath = os.path.join(md_pages_dir, filename)
                    with open(filepath, "w", encoding="utf-8") as pf:
                        pf.write(f"---\ntitle: \"{title}\"\nurl: \"{page_url}\"\ncategories: {cats}\n---\n\n")
                        pf.write(markdown)

                # Write to combined single context file
                if combined_file:
                    combined_file.write(f"\n{'='*70}\n")
                    combined_file.write(f"PAGE: {title} ({page_url})\n")
                    combined_file.write(f"{'='*70}\n\n")
                    combined_file.write(markdown)
                    combined_file.write("\n\n")

                processed += 1

        except Exception as e:
            print(f"\n[ERROR] Batch {i}-{i+args.batch_size} failed: {e}", file=sys.stderr)

        elapsed = time.time() - start_time
        pct = (processed / total_pages) * 100
        pages_per_sec = processed / elapsed if elapsed > 0 else 0
        sys.stdout.write(
            f"\r    [{processed}/{total_pages}] {pct:5.1f}% | {pages_per_sec:4.1f} pages/s | Words: {total_words:,}"
        )
        sys.stdout.flush()

        time.sleep(args.delay)

    if jsonl_file:
        jsonl_file.close()
    if combined_file:
        combined_file.close()

    print(f"\n[+] Completed in {time.time() - start_time:.1f}s!")
    print(f"[+] Downloaded: {processed} pages (~{total_words:,} words / ~{int(total_words * 1.3):,} tokens)")

    # 3. Export XML dump if format is 'all'
    if args.format == "all":
        xml_path = os.path.join(args.output_dir, "dragonwilds_wiki_dump.xml")
        export_xml_dump(all_titles, xml_path)

    # 4. Write metadata manifest
    manifest = {
        "source": "https://dragonwilds.runescape.wiki",
        "wiki_name": "RuneScape: Dragonwilds Wiki",
        "download_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_pages": processed,
        "total_words": total_words,
        "estimated_tokens": int(total_words * 1.3),
        "namespaces_included": TARGET_NAMESPACES,
        "files_generated": {
            "jsonl": "dragonwilds_wiki.jsonl",
            "combined_txt": "dragonwilds_full_context.txt",
            "markdown_pages_dir": "markdown_pages/",
            "xml_dump": "dragonwilds_wiki_dump.xml" if args.format == "all" else None,
        },
    }
    with open(os.path.join(args.output_dir, "manifest.json"), "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"[+] Manifest saved to {os.path.join(args.output_dir, 'manifest.json')}")
    print("\nAll files ready for LLM consumption!")


if __name__ == "__main__":
    main()
