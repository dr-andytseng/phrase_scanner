# PhraseScanner

A Python tool that crawls websites and scans every accessible page for a custom list of keywords or phrases, then reports where and how often each one appears.

Useful for content audits, SEO tracking, compliance checks, competitive research, or finding where specific terms or phrases live across a site.

## Features

- Crawls multiple websites from a simple text file of URLs
- Searches for any number of keywords or multi-word phrases, defined in a text file
- Respects `robots.txt`
- Detects and handles both HTML and XML/sitemap content
- Configurable crawl depth and max pages per site
- Skips binary files (PDFs, images, archives) and sensitive paths (`/admin`, `/login`, etc.)
- Exports results to both CSV and JSON
- Prints a live progress log and a summary report with top matches

## Requirements

- Python 3.7+
- Dependencies:
```bash
  pip install requests beautifulsoup4
```
  (Optional but recommended for XML parsing: `pip install lxml`)

## Setup

1. Clone this repository:
```bash
   git clone https://github.com/yourusername/phrase-scanner.git
   cd phrase-scanner
```
2. Install dependencies:
```bash
   pip install requests beautifulsoup4 lxml
```
3. Run the script once to auto-generate sample input files:
```bash
   python phrase_scanner.py
```
   This creates `urls.txt` and `phrases.txt` if they don't already exist.

## Usage

### 1. Configure your target URLs

Edit `urls.txt` — one URL per line, lines starting with `#` are ignored.

> **Note:** Each URL is a starting point, not a single page. The script crawls
> outward from it — following internal links within the same domain — up to
> `MAX_CRAWL_DEPTH` link-hops and `MAX_PAGES_PER_SITE` pages. It will never
> cross onto external domains, even if it encounters outbound links to them.