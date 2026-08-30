#!/usr/bin/env python3
"""
PhraseScanner
A Python script to crawl websites and search for predefined phrases across all accessible pages.
Reads URLs and phrases from external text files.
Compatible with macOS and other Unix-like systems.
"""

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import csv
import json
import time
import re
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
from datetime import datetime
import sys
import os
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

# Filter out the BeautifulSoup XML warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

class PhraseScanner:
    def __init__(self, urls_file='urls.txt', phrases_file='phrases.txt', delay=1, max_pages_per_site=400, max_depth=10):
        """
        Initialize the PhraseScanner.
        
        Args:
            urls_file (str): Path to file containing URLs to scan
            phrases_file (str): Path to file containing phrases to search for
            delay (int): Delay between requests in seconds
            max_pages_per_site (int): Maximum number of pages to crawl per site
            max_depth (int): Maximum crawl depth from the starting URL
        """
        self.urls_file = urls_file
        self.phrases_file = phrases_file
        self.delay = delay
        self.max_pages_per_site = max_pages_per_site
        self.max_depth = max_depth
        
        self.base_urls = []
        self.phrases = []
        self.results = []
        self.crawled_urls = set()
        self.robots_cache = {}
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Load URLs and phrases from files
        self.load_urls()
        self.load_phrases()
    
    def load_urls(self):
        """Load URLs from the specified text file."""
        if not os.path.exists(self.urls_file):
            print(f"❌ Error: {self.urls_file} not found!")
            print(f"Please create {self.urls_file} with one URL per line.")
            sys.exit(1)
        
        try:
            with open(self.urls_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                
            # Validate URLs
            for url in urls:
                if url.startswith('http://') or url.startswith('https://'):
                    self.base_urls.append(url)
                else:
                    print(f"⚠️  Warning: Skipping invalid URL: {url}")
            
            if not self.base_urls:
                print(f"❌ Error: No valid URLs found in {self.urls_file}")
                sys.exit(1)
                
            print(f"✅ Loaded {len(self.base_urls)} URLs from {self.urls_file}")
            
        except Exception as e:
            print(f"❌ Error reading {self.urls_file}: {e}")
            sys.exit(1)
    
    def load_phrases(self):
        """Load phrases from the specified text file."""
        if not os.path.exists(self.phrases_file):
            print(f"❌ Error: {self.phrases_file} not found!")
            print(f"Please create {self.phrases_file} with one phrase per line.")
            sys.exit(1)
        
        try:
            with open(self.phrases_file, 'r', encoding='utf-8') as f:
                phrases = [line.strip().lower() for line in f if line.strip() and not line.strip().startswith('#')]
                
            if not phrases:
                print(f"❌ Error: No phrases found in {self.phrases_file}")
                sys.exit(1)
                
            self.phrases = phrases
            print(f"✅ Loaded {len(self.phrases)} phrases from {self.phrases_file}")
            
        except Exception as e:
            print(f"❌ Error reading {self.phrases_file}: {e}")
            sys.exit(1)
    
    def can_fetch(self, url):
        """Check if we can fetch the URL according to robots.txt."""
        try:
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            if base_url not in self.robots_cache:
                robots_url = urljoin(base_url, '/robots.txt')
                rp = RobotFileParser()
                rp.set_url(robots_url)
                try:
                    rp.read()
                    self.robots_cache[base_url] = rp
                except:
                    # If robots.txt can't be read, assume we can crawl
                    self.robots_cache[base_url] = None
            
            rp = self.robots_cache[base_url]
            if rp is None:
                return True
                
            return rp.can_fetch(self.session.headers['User-Agent'], url)
            
        except Exception:
            return True
    
    def get_domain(self, url):
        """Extract domain from URL."""
        return urlparse(url).netloc
    
    def normalize_url(self, url):
        """Normalize URL by removing fragments and unnecessary parameters."""
        parsed = urlparse(url)
        # Remove fragment (part after #)
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized
    
    def is_valid_url(self, url, base_domain, allowed_scheme):
        """Check if URL is valid for crawling."""
        try:
            parsed = urlparse(url)
            
            # Must be same domain
            if parsed.netloc != base_domain:
                return False
            
            # Must use the same scheme (http/https) as the original URL
            if parsed.scheme != allowed_scheme:
                return False
            
            # Skip certain file types
            skip_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar', '.exe', '.dmg'}
            if any(parsed.path.lower().endswith(ext) for ext in skip_extensions):
                return False
                
            # Skip certain paths
            skip_paths = {'/admin', '/login', '/wp-admin', '/api/'}
            if any(skip_path in parsed.path.lower() for skip_path in skip_paths):
                return False
                
            return True
            
        except Exception:
            return False
    
    def detect_content_type(self, response):
        """Detect if content is XML, HTML, or other format."""
        content_type = response.headers.get('content-type', '').lower()
        content_preview = response.text[:200].strip().lower()
        
        # Check content type header
        if 'xml' in content_type:
            return 'xml'
        elif 'html' in content_type:
            return 'html'
        
        # Check content for XML declaration or root elements
        if (content_preview.startswith('<?xml') or 
            content_preview.startswith('<rss') or
            content_preview.startswith('<feed') or
            content_preview.startswith('<urlset') or
            content_preview.startswith('<sitemapindex')):
            return 'xml'
        
        # Default to HTML for web content
        return 'html'
    
    def create_soup(self, html_content, content_type='html'):
        """Create BeautifulSoup object with appropriate parser."""
        try:
            if content_type == 'xml':
                # Try to use lxml XML parser if available, otherwise use html.parser
                try:
                    return BeautifulSoup(html_content, 'xml')
                except Exception:
                    # Fall back to html.parser if lxml is not available
                    return BeautifulSoup(html_content, 'html.parser')
            else:
                return BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            print(f"  ⚠️  Error creating soup: {e}")
            return None
    
    def extract_links(self, html_content, base_url, content_type='html'):
        """Extract all links from HTML content."""
        links = set()
        try:
            soup = self.create_soup(html_content, content_type)
            if soup is None:
                return links
                
            base_domain = self.get_domain(base_url)
            base_scheme = urlparse(base_url).scheme  # Get the scheme from the original URL
            
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                if not href:
                    continue
                    
                # Convert relative URLs to absolute
                absolute_url = urljoin(base_url, href)
                normalized_url = self.normalize_url(absolute_url)
                
                # Only include links that match the same domain AND scheme as the original URL
                if self.is_valid_url(normalized_url, base_domain, base_scheme):
                    links.add(normalized_url)
                    
        except Exception as e:
            print(f"  ⚠️  Error extracting links: {e}")
            
        return links
    
    def fetch_webpage(self, url):
        """Fetch webpage content using requests."""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # Detect content type
            content_type = self.detect_content_type(response)
            
            return True, response.text, None, content_type, response.status_code
        except requests.RequestException as e:
            return False, None, str(e), 'html', None
    
    def extract_text(self, html_content, content_type='html'):
        """Extract main text content from HTML/XML using BeautifulSoup."""
        try:
            soup = self.create_soup(html_content, content_type)
            if soup is None:
                return ""
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text.lower()
            
        except Exception as e:
            print(f"  ⚠️  Error extracting text: {e}")
            return ""
    
    def search_phrases(self, text, url, depth, status_code, error=None):
        """Search for phrases in the extracted text."""
        found_phrases = []
        phrases_counts = {}
        
        for phrase in self.phrases:
            pattern = r'\b' + re.escape(phrase) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            if matches:
                found_phrases.append(phrase)
                phrases_counts[phrase] = len(matches)
        
        return {
            'url': url,
            'found_phrases': found_phrases,
            'phrases_counts': phrases_counts,
            'total_phrases_found': len(found_phrases),
            'scan_timestamp': datetime.now().isoformat(),
            'depth': depth,
            'status_code': status_code,
            'error': error or ''
        }
    
    def crawl_website(self, start_url):
        """Crawl a single website starting from the given URL."""
        print(f"\n🔍 Crawling: {start_url}")
        print(f"   Max pages: {self.max_pages_per_site}, Max depth: {self.max_depth}")
        
        base_domain = self.get_domain(start_url)
        to_visit = deque([(start_url, 0)])  # (url, depth)
        visited = set()
        site_results = []
        pages_crawled = 0
        
        while to_visit and pages_crawled < self.max_pages_per_site:
            current_url, depth = to_visit.popleft()
            
            if current_url in visited or depth > self.max_depth:
                continue
                
            if not self.can_fetch(current_url):
                print(f"  🚫 Robots.txt disallows: {current_url}")
                continue
            
            visited.add(current_url)
            pages_crawled += 1
            
            print(f"  [{pages_crawled}/{self.max_pages_per_site}] Scanning: {current_url}")
            
            # Fetch and process page
            success, html_content, error, content_type, status_code = self.fetch_webpage(current_url)
            
            if not success:
                print(f"    ❌ Error: {error}")
                site_results.append({
                    'url': current_url,
                    'found_phrases': [],
                    'phrases_counts': {},
                    'total_phrases_found': 0,
                    'scan_timestamp': datetime.now().isoformat(),
                    'depth': depth,
                    'status_code': '',
                    'error': error
                })
                continue
            
            # Log content type for debugging (optional)
            if content_type == 'xml':
                print(f"    📄 Detected XML content")
            
            # Extract text and search for phrases
            text_content = self.extract_text(html_content, content_type)
            result = self.search_phrases(text_content, current_url, depth, status_code)
            
            if result['found_phrases']:
                print(f"    ✅ Found: {', '.join(result['found_phrases'])}")
            else:
                print(f"    ⚪ No phrases found")
            
            site_results.append(result)
            
            # Extract links for further crawling (only if not at max depth and HTML content)
            if depth < self.max_depth and content_type == 'html':
                links = self.extract_links(html_content, current_url, content_type)
                for link in links:
                    if link not in visited:
                        to_visit.append((link, depth + 1))
            
            # Be respectful to servers
            time.sleep(self.delay)
        
        print(f"  ✅ Completed crawling {start_url}: {pages_crawled} pages processed")
        return site_results
    
    def scan_all_websites(self):
        """Main method to scan all websites."""
        print(f"🚀 Starting phrase scan of {len(self.base_urls)} websites")
        print(f"📋 Phrases: {', '.join(self.phrases[:10])}{'...' if len(self.phrases) > 10 else ''}")
        print("=" * 80)
        
        all_results = []
        
        for i, url in enumerate(self.base_urls, 1):
            print(f"\n[{i}/{len(self.base_urls)}] Processing website: {url}")
            site_results = self.crawl_website(url)
            all_results.extend(site_results)
        
        self.results = all_results
        print("\n" + "=" * 80)
        print(f"🎉 Scan complete! Processed {len(self.results)} total pages across {len(self.base_urls)} websites.")
    
    def save_to_csv(self, filename='phrasescanner_results_CSV.csv'):
        """Save results to CSV file with new column format."""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['URL', 'Phrases Found', 'Phrase List', 'Phrase Counts', 'Scan Time', 'Depth', 'Status Code', 'Error']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for result in self.results:
                csv_result = {
                    'URL': result['url'],
                    'Phrases Found': result['total_phrases_found'],
                    'Phrase List': ', '.join(result['found_phrases']) if result['found_phrases'] else '',
                    'Phrase Counts': ', '.join([f"{k}:{v}" for k, v in result['phrases_counts'].items()]) if result['phrases_counts'] else '',
                    'Scan Time': result['scan_timestamp'],
                    'Depth': result['depth'],
                    'Status Code': result['status_code'],
                    'Error': result.get('error', '')
                }
                writer.writerow(csv_result)
        
        print(f"📊 Results saved to: {filename}")
    
    def save_to_json(self, filename='phrasescanner_results_JSON.json'):
        """Save results to JSON file with new format."""
        # Transform results to match new column format
        formatted_results = []
        for result in self.results:
            formatted_result = {
                'URL': result['url'],
                'Phrases Found': result['total_phrases_found'],
                'Phrase List': ', '.join(result['found_phrases']) if result['found_phrases'] else '',
                'Phrase Counts': ', '.join([f"{k}:{v}" for k, v in result['phrases_counts'].items()]) if result['phrases_counts'] else '',
                'Scan Time': result['scan_timestamp'],
                'Depth': result['depth'],
                'Status Code': result['status_code'],
                'Error': result.get('error', '')
            }
            formatted_results.append(formatted_result)
        
        output_data = {
            'scan_info': {
                'total_websites': len(self.base_urls),
                'total_pages_scanned': len(self.results),
                'phrases_searched': self.phrases,
                'max_pages_per_site': self.max_pages_per_site,
                'max_depth': self.max_depth,
                'scan_date': datetime.now().isoformat()
            },
            'results': formatted_results
        }
        
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(output_data, jsonfile, indent=2, ensure_ascii=False)
        
        print(f"📋 Results saved to: {filename}")
    
    def print_summary(self):
        """Print a detailed summary of the scan results."""
        successful_scans = [r for r in self.results if 'error' not in r]
        failed_scans = [r for r in self.results if 'error' in r]
        pages_with_phrases = [r for r in successful_scans if r['total_phrases_found'] > 0]
        
        # Phrase statistics
        phrase_stats = {}
        for result in successful_scans:
            for phrase, count in result['phrases_counts'].items():
                if phrase not in phrase_stats:
                    phrase_stats[phrase] = {'pages': 0, 'total_occurrences': 0}
                phrase_stats[phrase]['pages'] += 1
                phrase_stats[phrase]['total_occurrences'] += count
        
        print("\n" + "=" * 80)
        print("📈 PhraseScanner Summary")
        print("=" * 80)
        print(f"🌐 Total websites: {len(self.base_urls)}")
        print(f"📄 Total pages scanned: {len(self.results)}")
        print(f"✅ Successful scans: {len(successful_scans)}")
        print(f"❌ Failed scans: {len(failed_scans)}")
        print(f"🎯 Pages with Phrases: {len(pages_with_phrases)}")
        
        if phrase_stats:
            print(f"\n🔍 Top phrases found:")
            sorted_phrases = sorted(phrase_stats.items(), 
                                   key=lambda x: x[1]['total_occurrences'], 
                                   reverse=True)[:10]
            
            for phrase, stats in sorted_phrases:
                print(f"  • '{phrase}': {stats['total_occurrences']} occurrences across {stats['pages']} pages")
        
        if pages_with_phrases:
            print(f"\n📋 Sample pages with phrases:")
            for result in pages_with_phrases[:10]:  # Show first 10
                phrases_found = ', '.join(result['found_phrases'][:5])  # Show first 5 phrases
                if len(result['found_phrases']) > 5:
                    phrases_found += '...'
                print(f"  • {result['url']}: {phrases_found}")
            
            if len(pages_with_phrases) > 10:
                print(f"  ... and {len(pages_with_phrases) - 10} more pages")


def create_sample_files():
    """Create sample input files if they don't exist."""
    
    # Create sample URLs file
    if not os.path.exists('urls.txt'):
        sample_urls = [
            "# Example websites — edit this file with your own URLs. Lines starting with # are ignored.",
            "https://www.python.org",
            "https://realpython.com",
            "https://docs.python.org/3/"
        ]
        
        with open('urls.txt', 'w') as f:
            f.write('\n'.join(sample_urls))
        print("📝 Created sample urls.txt file")
    
    # Create sample phrases file
    if not os.path.exists('phrases.txt'):
        sample_phrases = [
            "# Example phrases — edit this file with your own phrases. Lines starting with # are ignored.",
            "python",
            "programming",
            "development",
            "tutorial",
            "documentation",
            "machine learning",
            "data science",
            "artificial intelligence"
        ]
        
        with open('phrases.txt', 'w') as f:
            f.write('\n'.join(sample_phrases))
        print("📝 Created sample phrases.txt file")


def main():
    """Main function to run the PhraseScanner."""
    print("🔍 PhraseScanner")
    print("=" * 50)
    
    # Create sample files if they don't exist
    create_sample_files()
    
    # Configuration
    DELAY_BETWEEN_REQUESTS = 0.5  # seconds
    MAX_PAGES_PER_SITE = 5000    # Limit to prevent infinite crawling
    MAX_CRAWL_DEPTH = 5        # How deep to go from the starting URL
    
    try:
        # Create scanner instance
        scanner = PhraseScanner(
            urls_file='urls.txt',
            phrases_file='phrases.txt',
            delay=DELAY_BETWEEN_REQUESTS,
            max_pages_per_site=MAX_PAGES_PER_SITE,
            max_depth=MAX_CRAWL_DEPTH
        )
        
        # Debug: Print actual configuration being used
        print(f"🔧 Debug - Config Values: MAX_PAGES_PER_SITE={MAX_PAGES_PER_SITE}, MAX_CRAWL_DEPTH={MAX_CRAWL_DEPTH}")
        print(f"🔧 Debug - Scanner Values: max_pages_per_site={scanner.max_pages_per_site}, max_depth={scanner.max_depth}")
        
        # Run the PhraseScanner
        scanner.scan_all_websites()
        
        # Save results
        scanner.save_to_csv('phrasescanner_results_CSV.csv')
        scanner.save_to_json('phrasescanner_results_JSON.json')
        
        # Print summary
        scanner.print_summary()
        
    except KeyboardInterrupt:
        print("\n⏹️  Scan interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()