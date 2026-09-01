# PhraseScanner

A Python tool that crawls websites and scans every accessible page for a custom list of keywords or phrases, then reports where and how often each one appears.

Useful for content audits, SEO tracking, compliance checks, competitive research, or finding where specific terms or phrases live across a site.

## Features

- Crawls multiple websites from a simple text file of URLs
- Searches for any number of keywords or multi-word phrases, defined in a text file
- Respects robots.txt
- Detects and handles both HTML and XML/sitemap content
- Configurable crawl depth and max pages per site
- Skips binary files (PDFs, images, archives) and sensitive paths (/admin, /login, etc.)
- Exports results to both CSV and JSON
- Prints a live progress log and a summary report with top matches

## Requirements

- Python 3.7+
- Dependencies are listed in requirements.txt (requests, beautifulsoup4, lxml)

## Setup

1. Clone this repository:
   git clone https://github.com/dr-andytseng/phrase-scanner.git
   cd phrase-scanner
2. Install dependencies:
   pip install -r requirements.txt
3. Run the script once to auto-generate sample input files:
   python phrase_scanner.py
   This creates urls.txt and phrases.txt if they don't already exist.

## Usage

### 1. Configure your target URLs

Edit urls.txt — one URL per line, lines starting with # are ignored.

Note: Each URL is a starting point, not a single page. The script crawls outward from it, following internal links within the same domain, up to MAX_CRAWL_DEPTH link-hops and MAX_PAGES_PER_SITE pages. It will never cross onto external domains, even if it encounters outbound links to them.

Example urls.txt:
```
https://example.com
https://blog.example.com
```
### 2. Configure your phrases

Edit phrases.txt — one term per line, single words or multi-word phrases both work.

Example phrases.txt:
```
privacy policy
data breach
subscription
free trial
```
### 3. Run the scanner

python phrase_scanner.py

The script will crawl each site, log progress in the terminal, and save results to:
- phrasescanner_results_CSV.csv
- phrasescanner_results_JSON.json

## Usage Examples

Example 1 — Compliance check across a company's site
urls.txt: your company domain. phrases.txt: gdpr, ccpa, cookie consent, data retention. Run the script to find which pages mention (or fail to mention) key compliance phrases.

Example 2 — Competitor content audit
urls.txt: a competitor's blog and docs site. phrases.txt: your product category terms, e.g. api, integration, pricing. See how often and where they discuss topics relevant to your market.

Example 3 — Marketing claim audit
urls.txt: your own marketing site. phrases.txt: free trial, no credit card, cancel anytime. Confirm these phrases still appear where you expect them to, after a site redesign.

## Configuration Options

Inside main(), you can adjust:

- DELAY_BETWEEN_REQUESTS — seconds to wait between page fetches. Default: 0.5
- MAX_PAGES_PER_SITE — max pages crawled per site before stopping. Default: 5000
- MAX_CRAWL_DEPTH — max link-hops from the starting URL. Default: 5

These three settings control both how thorough the scan is and how long it takes. A full run against a large site with the defaults can take a long time — for example, 5000 pages at a 0.5s delay is at least ~42 minutes of delay alone, before network latency per request.

### Tuning for speed vs. thoroughness

If you want a faster, lighter scan (e.g. checking a small marketing site, or doing a quick spot-check):
```
DELAY_BETWEEN_REQUESTS = 0.2
MAX_PAGES_PER_SITE = 100
MAX_CRAWL_DEPTH = 3
```
This is a good default for scanning a single landing page, blog, or small docs site where you don't need to crawl the entire domain.

If you want a deep, exhaustive scan (e.g. a full compliance audit of a large site):
```
DELAY_BETWEEN_REQUESTS = 1.0
MAX_PAGES_PER_SITE = 10000
MAX_CRAWL_DEPTH = 8
```
Expect this to take considerably longer — run it in the background or overnight for large domains.

General guidance: lower MAX_CRAWL_DEPTH first if you just want to check top-level and near-top-level pages, since depth has an exponential effect on pages discovered. Lower MAX_PAGES_PER_SITE as a hard ceiling/safety net regardless of depth, especially on sites you don't control. Only lower DELAY_BETWEEN_REQUESTS if you're scanning a site you own or have permission to hit harder, since reducing delay increases server load per unit time.

## Output Format

Both CSV and JSON outputs include, per page: URL, number of phrases found, list of matched phrases, per-phrase occurrence counts, scan timestamp, crawl depth, HTTP status code, and an error message if the fetch failed.

## Notes & Limitations

- This is a same-domain crawler — it won't follow external links.
- Respects robots.txt by default; it will skip disallowed pages.
- Large sites with high MAX_PAGES_PER_SITE values can take a long time to run — adjust DELAY_BETWEEN_REQUESTS and depth/page limits accordingly.

## Legal & Ethical Use

This tool is intended for scanning websites you own or have explicit permission to crawl. Before scanning any third-party site, review its Terms of Service and robots.txt, since some sites explicitly prohibit automated crawling regardless of what robots.txt allows. Aggressive crawl settings (high MAX_PAGES_PER_SITE, low DELAY_BETWEEN_REQUESTS) can place meaningful load on a target server — use conservative settings on any site you don't control. You are responsible for how you use this tool and for complying with applicable laws and site policies in your jurisdiction.

## License

MIT — see LICENSE for details.
