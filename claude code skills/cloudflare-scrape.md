---
name: cloudflare-scrape
description: Scrape Cloudflare-protected websites (like Metal Archives) using nodriver. Handles CF bypass, DataTables pagination, review extraction.
---

# Cloudflare Scrape Skill

Use **nodriver** to access Cloudflare-protected websites that regular HTTP clients and Playwright/Puppeteer cannot reach. This skill covers the full pipeline: bypass CF, paginate DataTables, extract structured data, and batch-process in parallel.

## Why nodriver works when others don't

| Tool | Protocol | CF Detection |
|------|----------|--------------|
| Playwright / Puppeteer | CDP (Chrome DevTools Protocol) | Instantly detected |
| curl_cffi | HTTP with TLS spoofing | Fails (JS challenge needed) |
| **nodriver** | Native WebSocket (non-CDP) | **Bypasses CF** |

CF detects CDP debugging ports. nodriver communicates via the browser's own WebSocket protocol.

## Setup

```bash
pip install nodriver
```

## Core patterns

### 1. Launch and pass Cloudflare

```python
import asyncio, nodriver as uc

browser = await uc.start(headless=False)  # MUST be visible for CF
page = await browser.get("https://target-site.com/")

# Wait for CF JS challenge to auto-resolve
for i in range(10):
    await page.sleep(3)
    title = await page.evaluate("document.title")
    if "Just a moment" not in title and "安全验证" not in title:
        break  # CF passed
```

### 2. Evaluate JavaScript (CRITICAL: arrow function format)

nodriver only works with arrow functions wrapped in IIFE:

```python
# ✅ CORRECT
html = await page.evaluate("(() => { return document.body.innerHTML; })()")

# ❌ WRONG - returns None
html = await page.evaluate("document.body.innerHTML")
```

### 3. DataTables pagination — click, don't use URL params

DataTables ignores `?displayStart=` URL parameters. Must click "Next" via JS:

```python
# Get current page data
html = await page.evaluate("""
    (() => {
        const t = document.getElementById('searchResultsAlbum');
        return t ? t.innerHTML : '';
    })()
""")

# Click Next button
await page.evaluate("""
    (() => {
        const btn = document.getElementById('searchResultsAlbum_next');
        if (btn && !btn.classList.contains('paginate_button_disabled')) {
            btn.click();
        }
    })()
""")
await page.sleep(4)  # Wait for new page to render
```

### 4. Extract structured data from table HTML

Parse links with regex from innerHTML:

```python
import re

# Extract band name, album URL, album name from search results
pattern = r'<tr[^>]*>.*?<a href="[^"]+/bands/[^"]+"[^>]*>([^<]+)</a>.*?<a href="(https://www\.metal-archives\.com/albums/[^"]+)"[^>]*>([^<]+)</a>'
matches = re.findall(pattern, html)
albums = [{'url': m[1], 'band': m[0].strip(), 'album': m[2].strip()} for m in matches]
```

### 5. Extract review scores from album pages

```python
page = await browser.get(album_url)
await page.sleep(2.5)
text = await page.evaluate("document.body.innerText")

m = re.search(r'(\d+)\s*reviews?\s*\(avg\.?\s*(\d+)%\)', text)
if m:
    review_count = int(m.group(1))
    avg_percent = int(m.group(2))
```

### 6. Fix Windows GBK encoding crash

```python
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
```

### 7. Parallel batch processing

Split URLs into batches and run as background tasks:

```bash
# Launch 4 parallel batches
python script.py 1 &
python script.py 2 &
python script.py 3 &
python script.py 4 &
wait
```

Each batch reads from its own JSON file of URLs, opens its own nodriver browser, passes CF independently.

## Full pipeline example

See the working scripts at:
- `C:/Users/19269/AppData/Local/Temp/ma_page_click.py` — DataTables pagination collector
- `C:/Users/19269/AppData/Local/Temp/ma_collect_urls.py` — Full collect + check pipeline

## Common pitfalls

1. **Never use `headless=True`** — CF will detect it
2. **Don't close browser too fast** — nodriver temp profiles need time to clean up (the "closed pipe" warnings are harmless)
3. **Navigating to sub-pages may trigger new CF** — always wait and check title after each navigation
4. **Metal Archives search pagination** — there are 673 albums in Slam/Brutal Death Metal, 200 per page, last page has 73
5. **Most albums have 0 reviews** — niche genres like Slam/Brutal Death Metal are very underground. Only ~5-6% have any reviews
