# RuneScape: Dragonwilds Wiki LLM Context Extractor

This guide explains how the wiki was analyzed and how to download and convert the entire **RuneScape: Dragonwilds Wiki** ([dragonwilds.runescape.wiki](https://dragonwilds.runescape.wiki)) into optimized context for Large Language Models (LLMs).

---

## 1. Wiki Overview & Scope

The wiki is powered by **MediaWiki 1.45** and hosted by **Weird Gloop**.

* **Main Articles (Namespace 0):** 3,769 non-redirect pages (Monsters, Items, Bosses, Quests, Areas, Recipes, Combat Mechanics, Crafting, Materials)
* **Game Updates & Patch Notes (Namespace 100):** 122 pages
* **Transcripts & Lore Dialogues (Namespace 120):** 38 pages
* **Guides (Namespace 3004):** Player strategy guides
* **Total Content Pages:** **~3,930 pages**
* **Total Word Count:** **~734,000 words** (~950,000 – 1,000,000 tokens)
* **Full Download Time:** **~15–30 seconds** (via batched MediaWiki API requests)

---

## 2. Quick Start: Download the Wiki

Two standalone scripts are provided with **zero external dependencies**:

### Option A: Native Windows PowerShell (No Python or WSL needed)

Run directly in PowerShell from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_wiki.ps1 -OutputDir .\wiki_data
```

### Option B: Python 3 (Cross-platform: Windows, WSL, Linux, macOS, Docker)

Run using standard Python 3 (uses standard library `urllib`, `json`, `re`):

```bash
python3 scripts/download_wiki.py --output-dir ./wiki_data
```

*(You can also run inside WSL: `bash -c "python3 scripts/download_wiki.py --output-dir ./wiki_data"`)*

---

## 3. CLI Options & Formats

| Argument | Description | Default |
|---|---|---|
| `--output-dir` / `-OutputDir` | Directory to save all output files | `./wiki_data` |
| `--format` / `-Format` | `all`, `markdown`, `jsonl`, `combined`, `xml` | `all` |
| `--batch-size` / `-BatchSize` | Articles per API request batch (up to 50) | `50` |
| `--delay` / `-DelaySeconds` | Polite delay between batches | `0.1s` |
| `--limit` / `-Limit` | Download first N pages (useful for testing) | None (all) |

---

## 4. Generated Output Formats

When running with `--format all` (the default), the downloader produces four complementary formats in the output directory:

### 1. `dragonwilds_full_context.txt` (Single File Long-Context)
* **Best for:** Direct upload to long-context LLMs (**Gemini 1.5 Pro / 2.0 / 3.x Flash**, **Claude 3.5 Sonnet**, **NotebookLM**).
* **Details:** Every page is clearly separated with `# PAGE: <Title> (<URL>)`. Because the entire wiki is ~1M tokens, it fits into modern 1M–2M context windows in a single file!

### 2. `markdown_pages/` (Folder of Individual `.md` Files)
* **Best for:** **Claude Projects**, **Cursor / Windsurf** `@codebase` context, **Obsidian**, or file-based knowledge bases.
* **Details:** Each article is saved as `<Title>.md` with clean YAML frontmatter:
  ```markdown
  ---
  title: "Abysmal Whip"
  url: "https://dragonwilds.runescape.wiki/w/Abysmal_Whip"
  categories: ['Masterwork', 'Melee Weapons', 'One-Handed Melee Weapons']
  ---

  # Abysmal Whip
  ...
  ```

### 3. `dragonwilds_wiki.jsonl` (Structured JSON Lines)
* **Best for:** **RAG pipelines** (LangChain, LlamaIndex, ChromaDB, FAISS, Pinecone) and fine-tuning datasets.
* **Schema per line:**
  ```json
  {
    "id": 19246,
    "title": "Abysmal Whip",
    "url": "https://dragonwilds.runescape.wiki/w/Abysmal_Whip",
    "categories": ["Masterwork", "Melee Weapons"],
    "markdown": "# Abysmal Whip\n...",
    "wikitext": "{{Infobox Item...",
    "word_count": 482
  }
  ```

### 4. `dragonwilds_wiki_dump.xml` (Full MediaWiki XML Dump)
* **Best for:** Offline archives, backup, or tools that parse standard MediaWiki XML dumps (`mwparserfromhell`, Kiwix, etc.).

---

## 5. How Wikitext is Optimized for LLMs

Raw MediaWiki markup contains noisy templates, parser functions, and image syntax that waste tokens and confuse LLMs. The cleaner transforms:

1. **Infoboxes (`{{Infobox Item}}`, `{{Infobox Monster}}`, `{{Infobox Weapon}}`):**
   * Transformed into clean, structured key-value bullet points:
     ```markdown
     ### Infobox: Weapon
     - **Power**: 4
     - **Specialeffect**: ATTACKS build up BLEED on enemies (25)
     - **Damagetype**: Slash
     - **Basedmg**: 44 - 76
     - **Durability**: 1,300
     ```
2. **Drop Tables (`{{DropsLine}}`):**
   * Extracted into readable drop listings:
     ```markdown
     - **Drop:** Kuldra's Head (Qty: 1, Rarity: Always, Notes: Raid inventory)
     ```
3. **Crafting & Recipes (`{{Recipe}}`):**
   * Transformed into facility, skill, and material requirements:
     ```markdown
     **Recipe:** Abysmal Whip (Qty: 1)
     - **Facility:** Blacksmith's Bench
     - **Skill:** Artisan
     - **Materials:** 1x Abyssal Spine, 3x Shrapnel, 3x Swamp Thread, 4x Vault Shard
     ```
4. **MediaWiki Tables (`{| ... |}`):**
   * Automatically converted into standard GitHub-Flavored Markdown tables (`| Col | Col |`).
5. **Wikilinks & Formatting:**
   * Unwraps `[[Page|Anchor]]` $\rightarrow$ `Anchor` and `[[Page]]` $\rightarrow$ `Page`.
   * Preserves lore from `{{Journal entry}}`.
   * Strips file embeds `[[File:...]]`, navbars, citation tags `{{Refn}}`, and comment blocks `<!-- ... -->`.
