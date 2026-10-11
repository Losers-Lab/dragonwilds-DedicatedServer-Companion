<#
.SYNOPSIS
    Downloads all articles, guides, updates, and transcripts from the RuneScape: Dragonwilds Wiki
    (https://dragonwilds.runescape.wiki) and converts them into LLM-ready context.

.DESCRIPTION
    Runs natively on Windows PowerShell (5.1+) or PowerShell 7+ with zero external dependencies.
    Outputs:
      - dragonwilds_wiki.jsonl (for vector databases / RAG pipelines)
      - dragonwilds_full_context.txt (single file for long-context LLMs)
      - markdown_pages/*.md (folder of individual markdown files)
      - dragonwilds_wiki_dump.xml (full standard MediaWiki XML export)

.PARAMETER OutputDir
    Directory to save output files (default: .\wiki_data)

.PARAMETER Format
    Output format: 'all', 'markdown', 'jsonl', 'combined', 'xml' (default: 'all')

.PARAMETER BatchSize
    Pages per API request batch (default: 50, max: 50)

.PARAMETER DelaySeconds
    Delay between API batch requests in seconds (default: 0.1)

.PARAMETER Limit
    Optional maximum number of pages to download (useful for testing)
#>

[CmdletBinding()]
param (
    [string]$OutputDir = ".\wiki_data",
    [ValidateSet("all", "markdown", "jsonl", "combined", "xml")]
    [string]$Format = "all",
    [int]$BatchSize = 50,
    [double]$DelaySeconds = 0.1,
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"

$WikiApi = "https://dragonwilds.runescape.wiki/api.php"
$WikiExport = "https://dragonwilds.runescape.wiki/w/Special:Export"
$UserAgent = "DragonwildsWikiDownloader/1.0 (contact: arham; LLM-context-extractor)"
$Headers = @{ "User-Agent" = $UserAgent }

# Relevant namespaces:
# 0: Main (monsters, items, bosses, crafting, lore)
# 100: Updates (patch notes)
# 120: Transcripts (dialogues)
# 3004: Guides
$TargetNamespaces = @(0, 100, 120, 3004)

if (!(Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$MdPagesDir = Join-Path $OutputDir "markdown_pages"
if ($Format -in @("all", "markdown") -and !(Test-Path $MdPagesDir)) {
    New-Item -ItemType Directory -Path $MdPagesDir -Force | Out-Null
}

function Clean-WikitextToMarkdown {
    param (
        [string]$Title,
        [string]$Wikitext,
        [string[]]$Categories
    )

    $text = $Wikitext

    # Remove HTML comments
    $text = [regex]::Replace($text, '<!--.*?-->', '', 'Singleline')

    # Remove file/image transclusions
    $text = [regex]::Replace($text, '\[\[(?:File|Image):[^\]]+\]\]', '', 'IgnoreCase')

    # Convert headings
    $text = [regex]::Replace($text, '(?m)^====\s*(.*?)\s*====\s*$', '#### $1')
    $text = [regex]::Replace($text, '(?m)^===\s*(.*?)\s*===\s*$', '### $1')
    $text = [regex]::Replace($text, '(?m)^==\s*(.*?)\s*==\s*$', '## $1')

    # Bold & Italics
    $text = [regex]::Replace($text, "'''(.*?)'''", '**$1**')
    $text = [regex]::Replace($text, "''(.*?)''", '*$1*')

    # DropsLine
    $text = [regex]::Replace($text, '(?i)\{\{DropsLine\|([^{}\n]+)\}\}', {
        param($m)
        $parts = $m.Groups[1].Value -split '\|'
        $dict = @{}
        foreach ($p in $parts) {
            if ($p -match '^\s*([^=]+?)\s*=\s*(.*?)\s*$') {
                $dict[$Matches[1].ToLower()] = $Matches[2]
            }
        }
        $name = if ($dict.ContainsKey('name')) { $dict['name'] } else { 'Unknown Item' }
        $qty = if ($dict.ContainsKey('quantity')) { $dict['quantity'] } else { '1' }
        $rarity = if ($dict.ContainsKey('rarity')) { $dict['rarity'] } else { '' }
        $res = "- **Drop:** $name (Qty: $qty"
        if ($rarity) { $res += ", Rarity: $rarity" }
        $res += ")"
        return $res
    })

    # Recipe
    $text = [regex]::Replace($text, '(?is)\{\{Recipe\s*\|(.*?)\}\}', {
        param($m)
        $parts = $m.Groups[1].Value -split '\|'
        $dict = @{}
        foreach ($p in $parts) {
            if ($p -match '^\s*([^=]+?)\s*=\s*(.*?)\s*$') {
                $dict[$Matches[1].ToLower()] = $Matches[2]
            }
        }
        $facility = if ($dict.ContainsKey('facility')) { $dict['facility'] } else { 'Crafting' }
        $skill = if ($dict.ContainsKey('skill')) { $dict['skill'] } else { '' }
        $output = if ($dict.ContainsKey('output1')) { $dict['output1'] } else { '' }
        $qty = if ($dict.ContainsKey('output1qty')) { $dict['output1qty'] } else { '1' }
        $mats = [System.Collections.Generic.List[string]]::new()
        for ($i = 1; $i -le 10; $i++) {
            $mKey = "mat$i"
            $qKey = "mat${i}qty"
            if ($dict.ContainsKey($mKey) -and $dict[$mKey]) {
                $mq = if ($dict.ContainsKey($qKey)) { $dict[$qKey] } else { '1' }
                $mats.Add("$mq" + "x " + $dict[$mKey])
            }
        }
        $sb = [System.Text.StringBuilder]::new()
        [void]$sb.AppendLine("`n**Recipe:** $output (Qty: $qty)")
        if ($facility) { [void]$sb.AppendLine("- **Facility:** $facility") }
        if ($skill) { [void]$sb.AppendLine("- **Skill:** $skill") }
        if ($mats.Count -gt 0) { [void]$sb.AppendLine("- **Materials:** $($mats -join ', ')") }
        return $sb.ToString()
    })

    # Journal entry
    $text = [regex]::Replace($text, '(?is)\{\{Journal entry\|(.*?)\}\}', {
        param($m)
        return "`n### Journal Lore Entry`n`n" + $m.Groups[1].Value.Trim() + "`n"
    })

    # Infoboxes
    $text = [regex]::Replace($text, '(?is)\{\{Infobox\s+([A-Za-z0-9_ ]+)\n(.*?)\}\}', {
        param($m)
        $boxType = $m.Groups[1].Value.Trim()
        $body = $m.Groups[2].Value
        $lines = [System.Collections.Generic.List[string]]::new()
        $lines.Add("### Infobox: $boxType")
        foreach ($line in ($body -split "`n")) {
            $line = $line.Trim()
            if ($line.StartsWith('|') -and ($line -match '^\s*\|\s*([^=]+?)\s*=\s*(.*?)\s*$')) {
                $k = $Matches[1].Trim()
                $v = $Matches[2].Trim()
                if ($v -and !$v.StartsWith('{{') -and ($k.ToLower() -notin @('image', 'map'))) {
                    $vClean = [regex]::Replace($v, '\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]', '$1')
                    $lines.Add("- **$([cultureinfo]::CurrentCulture.TextInfo.ToTitleCase($k))**: $vClean")
                }
            }
        }
        return "`n" + ($lines -join "`n") + "`n"
    })

    # Wikilinks: [[Target|Label]] -> Label, [[Target]] -> Target
    $text = [regex]::Replace($text, '\[\[(?:[^\]\|]+\|)?([^\]]+)\]\]', '$1')

    # External links
    $text = [regex]::Replace($text, '\[(https?://[^\s]+)\s+([^\]]+)\]', '[$2]($1)')

    # Categories bottom
    $text = [regex]::Replace($text, '(?i)\[\[Category:[^\]]+\]\]', '')

    # UI / Citations
    $text = [regex]::Replace($text, '(?i)\{\{(?:Reflist|Refn|CiteJournal|DropsTableHead|DropsTableBottom|UH|UL|Weapons|Special Effects|Crafting Tree|Calendar|Date page|HasStrategy|Otheruses)[^}]*\}\}', '')

    # Compress multiple newlines
    $text = [regex]::Replace($text, '\n{3,}', "`n`n")

    $header = "# $Title`n"
    if ($Categories -and $Categories.Count -gt 0) {
        $cleanCats = $Categories | Where-Object { $_ -notlike "Pages *" }
        if ($cleanCats) {
            $header += "`n**Categories:** " + ($cleanCats -join ", ") + "`n"
        }
    }

    return $header + "`n" + $text.Trim()
}

function Sanitize-Filename([string]$name) {
    return [regex]::Replace($name, '[\\/*?:"<>|]', '_').Trim()
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " RuneScape: Dragonwilds Wiki Downloader (LLM Context)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Enumerate pages
Write-Host "[*] Enumerating pages from namespaces: $($TargetNamespaces -join ', ')..."
$pages = [System.Collections.Generic.List[PSObject]]::new()

foreach ($ns in $TargetNamespaces) {
    $url = "${WikiApi}?action=query&list=allpages&apnamespace=$ns&apfilterredir=nonredirects&aplimit=500&format=json"
    while ($true) {
        $res = Invoke-RestMethod -Uri $url -Headers $Headers
        if ($res.query.allpages) {
            foreach ($p in $res.query.allpages) {
                $pages.Add($p)
            }
        }
        if ($res.continue) {
            $apc = [System.Web.HttpUtility]::UrlEncode($res.continue.apcontinue)
            $url = "${WikiApi}?action=query&list=allpages&apnamespace=$ns&apfilterredir=nonredirects&aplimit=500&apcontinue=$apc&format=json"
        } else {
            break
        }
    }
}

Write-Host "[+] Total non-redirect pages found: $($pages.Count)" -ForegroundColor Green

if ($Limit -gt 0 -and $Limit -lt $pages.Count) {
    $pages = $pages.GetRange(0, $Limit)
    Write-Host "[*] Limiting download to $($pages.Count) pages as requested." -ForegroundColor Yellow
}

$allTitles = $pages | ForEach-Object { $_.title }

# Export XML if requested
if ($Format -eq "xml" -or $Format -eq "all") {
    $xmlPath = Join-Path $OutputDir "dragonwilds_wiki_dump.xml"
    Write-Host "[*] Exporting MediaWiki XML dump to $xmlPath..." -ForegroundColor Cyan
    $xmlWriter = [System.IO.StreamWriter]::new($xmlPath, $false, [System.Text.Encoding]::UTF8)
    $xmlWriter.WriteLine('<?xml version="1.0" encoding="utf-8"?>')
    $xmlWriter.WriteLine('<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11">')

    $batchXmlSize = 300
    for ($i = 0; $i -lt $allTitles.Count; $i += $batchXmlSize) {
        $chunk = $allTitles | Select-Object -Skip $i -First $batchXmlSize
        $body = @{
            pages = ($chunk -join "`n")
            curonly = "1"
        }
        try {
            $xmlDoc = Invoke-RestMethod -Uri $WikiExport -Method Post -Body $body -Headers $Headers -TimeoutSec 60
            $pageNodes = $xmlDoc.DocumentElement.GetElementsByTagName("page")
            foreach ($pNode in $pageNodes) {
                $xmlWriter.WriteLine($pNode.OuterXml)
            }
            Write-Host "    XML: Exported $([Math]::Min($i + $batchXmlSize, $allTitles.Count))/$($allTitles.Count) pages..."
        } catch {
            Write-Warning "Failed XML batch: $_"
        }
        Start-Sleep -Milliseconds 150
    }
    $xmlWriter.WriteLine('</mediawiki>')
    $xmlWriter.Close()
    Write-Host "[+] XML dump saved: $xmlPath" -ForegroundColor Green

    if ($Format -eq "xml") {
        Write-Host "[+] Done." -ForegroundColor Green
        return
    }
}

# 2. Download page contents in batches of 50
$jsonlPath = Join-Path $OutputDir "dragonwilds_wiki.jsonl"
$combinedPath = Join-Path $OutputDir "dragonwilds_full_context.txt"

$jsonlWriter = if ($Format -in @("all", "jsonl")) { [System.IO.StreamWriter]::new($jsonlPath, $false, [System.Text.Encoding]::UTF8) } else { $null }
$combinedWriter = if ($Format -in @("all", "combined")) { [System.IO.StreamWriter]::new($combinedPath, $false, [System.Text.Encoding]::UTF8) } else { $null }

$total = $pages.Count
$processed = 0
$totalWords = 0
$startTime = [System.DateTime]::UtcNow

Write-Host "[*] Fetching and formatting $total pages..." -ForegroundColor Cyan

for ($i = 0; $i -lt $total; $i += $BatchSize) {
    $batch = $pages | Select-Object -Skip $i -First $BatchSize
    $ids = ($batch | ForEach-Object { $_.pageid }) -join '|'

    $batchUrl = "${WikiApi}?action=query&pageids=$ids&prop=revisions|categories&rvslots=*&rvprop=content&cllimit=50&format=json"

    try {
        $batchRes = Invoke-RestMethod -Uri $batchUrl -Headers $Headers -TimeoutSec 30
        $pageProps = $batchRes.query.pages.PSObject.Properties

        foreach ($pProp in $pageProps) {
            $pData = $pProp.Value
            $title = $pData.title
            $pageId = $pData.pageid
            $revisions = $pData.revisions
            if (!$revisions) { continue }

            $wikitext = $revisions[0].slots.main.'*'
            $cats = @()
            if ($pData.categories) {
                $cats = $pData.categories | ForEach-Object { $_.title -replace '^Category:', '' }
            }

            # Markdown conversion
            $markdown = Clean-WikitextToMarkdown -Title $title -Wikitext $wikitext -Categories $cats
            $words = ($markdown -split '\s+').Count
            $totalWords += $words

            $pageUrl = "https://dragonwilds.runescape.wiki/w/" + [System.Uri]::EscapeDataString($title.Replace(' ', '_'))

            # JSONL
            if ($jsonlWriter) {
                $obj = [ordered]@{
                    id = $pageId
                    title = $title
                    url = $pageUrl
                    categories = $cats
                    markdown = $markdown
                    wikitext = $wikitext
                    word_count = $words
                }
                $jsonlWriter.WriteLine((ConvertTo-Json $obj -Compress))
            }

            # Individual markdown
            if ($Format -in @("all", "markdown")) {
                $fileName = (Sanitize-Filename $title) + ".md"
                $filePath = Join-Path $MdPagesDir $fileName
                $catsYaml = ($cats | ForEach-Object { "'$_'" }) -join ', '
                $frontmatter = "---`ntitle: `"$title`"`nurl: `"$pageUrl`"`ncategories: [$catsYaml]`n---`n`n"
                [System.IO.File]::WriteAllText($filePath, $frontmatter + $markdown, [System.Text.Encoding]::UTF8)
            }

            # Combined context file
            if ($combinedWriter) {
                $combinedWriter.WriteLine("`n" + ("=" * 70))
                $combinedWriter.WriteLine("PAGE: $title ($pageUrl)")
                $combinedWriter.WriteLine(("=" * 70) + "`n")
                $combinedWriter.WriteLine($markdown)
                $combinedWriter.WriteLine("`n")
            }

            $processed++
        }
    } catch {
        Write-Warning "Batch $i failed: $_"
    }

    $elapsed = ([System.DateTime]::UtcNow - $startTime).TotalSeconds
    $rate = if ($elapsed -gt 0) { [Math]::Round($processed / $elapsed, 1) } else { 0 }
    $pct = [Math]::Round(($processed / $total) * 100, 1)
    Write-Progress -Activity "Downloading Wiki Pages" -Status "$processed / $total ($pct%) @ $rate pages/s" -PercentComplete $pct

    Start-Sleep -Seconds $DelaySeconds
}

Write-Progress -Activity "Downloading Wiki Pages" -Completed

if ($jsonlWriter) { $jsonlWriter.Close() }
if ($combinedWriter) { $combinedWriter.Close() }

$totalSeconds = [Math]::Round(([System.DateTime]::UtcNow - $startTime).TotalSeconds, 1)
Write-Host "`n[+] Completed in ${totalSeconds}s!" -ForegroundColor Green
Write-Host "[+] Downloaded $processed pages (~$($totalWords.ToString('N0')) words / ~$([Math]::Round($totalWords * 1.3).ToString('N0')) tokens)" -ForegroundColor Green
Write-Host "[+] Output files in $OutputDir" -ForegroundColor Cyan
