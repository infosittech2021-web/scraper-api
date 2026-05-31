"""
Google Maps Lead Extractor v2

Uses Playwright (headless Chromium) to scrape Google Maps search results.
Falls back to HTTP-based extraction if Playwright is unavailable.

This is designed to run on Render.com (free tier) with build.sh setting up
the Chromium browser binary.
"""

import re
import json
import random
import urllib.parse
import os

# Phone number regex (Indian format)
PHONE_RE = re.compile(
    r'(\+91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}|0\d{2,4}[\-\s]?\d{6,8}'
)


def extract_google_maps(category, location, page_num=1):
    """
    Extract business leads from Google Maps search results.
    Returns dict with keys: leads, page, has_next, total, source_url
    """
    query = f"{category} in {location}"
    url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"

    print(f"[Scraper] Query  : {query}")
    print(f"[Scraper] Maps URL: {url}")

    leads = []
    debug_info = []

    # Strategy 1: Playwright (headless browser) — most reliable
    try:
        leads = _scrape_with_playwright(url)
        print(f"[Scraper] Playwright: {len(leads)} leads")
    except Exception as e:
        err_msg = f"Playwright error: {str(e)}"
        print(f"[Scraper] {err_msg}")
        debug_info.append(err_msg)
        # Strategy 2: HTTP fallback (works when Google serves SSR content)
        try:
            leads = _scrape_with_http(url, query)
            print(f"[Scraper] HTTP fallback: {len(leads)} leads")
        except Exception as e2:
            err_msg2 = f"HTTP fallback error: {str(e2)}"
            print(f"[Scraper] {err_msg2}")
            debug_info.append(err_msg2)

    # Deduplicate by name
    unique, seen = [], set()
    for lead in leads:
        key = lead['name'].strip().lower()
        if key and len(key) > 2 and key not in seen:
            seen.add(key)
            unique.append(lead)

    print(f"[Scraper] Final result: {len(unique)} unique leads")

    return {
        'leads': unique,
        'page': page_num,
        'has_next': False,
        'total': len(unique),
        'source_url': url,
        'debug': debug_info
    }


# ---------------------------------------------------------------------------
# Strategy 1: Playwright (Headless Browser)
# ---------------------------------------------------------------------------

def _scrape_with_playwright(url):
    """Scrape Google Maps using Playwright headless Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # Try different launch args for reliability on Render
        launch_args = [
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-gpu',
            '--single-process',
        ]

        browser = p.chromium.launch(
            headless=True,
            args=launch_args,
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
        )
        page = context.new_page()

        print(f"[Playwright] Navigating to: {url}")
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)

        # Wait for results feed and scroll to load more
        feed_selector = '.m6QErb[aria-label^="Results for"]'

        try:
            page.wait_for_selector(feed_selector, timeout=10000)
            for i in range(5):
                page.evaluate(f"""() => {{
                    const el = document.querySelector('{feed_selector}');
                    if (el) el.scrollTop = el.scrollHeight;
                }}""")
                page.wait_for_timeout(1500)
        except Exception as e:
            print(f"[Playwright] Feed selector not found: {e}")
            # Try a broader scroll approach
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
            except:
                pass

        results = []
        cards = page.locator('.Nv2PK').all()
        print(f"[Playwright] Found {len(cards)} business cards")

        for card in cards:
            name, phone, address, rating, website = '', '', '', '', ''

            # Business name
            name_el = card.locator('.qBF1Pd')
            if name_el.count() > 0:
                name = name_el.first.inner_text().strip()

            # Rating
            rating_el = card.locator('.MW4etd')
            if rating_el.count() > 0:
                rating = rating_el.first.inner_text().strip()

            # Website link
            web_el = card.locator('a.lcr4fd, a[data-value="Website"]')
            if web_el.count() > 0:
                website = web_el.first.get_attribute('href') or ''

            # Extract text content for phone and address parsing
            card_text = card.inner_text()

            # Phone
            phone_match = PHONE_RE.search(card_text)
            if phone_match:
                phone = phone_match.group(0)

            # Address
            lines = card_text.split('\n')
            for line in lines:
                line = line.strip()
                if any(kw in line for kw in ['Kerala', 'India', 'Tamil', 'Karnataka']):
                    if 'Open' not in line and 'Closed' not in line:
                        if not re.match(r'^\d+\.\d+', line):
                            address = line
                            break
                elif len(line) > 15 and ',' in line:
                    if 'Open' not in line and 'Closed' not in line:
                        if not re.match(r'^\d+\.\d+', line):
                            address = line
                            break

            if name and len(name) > 2:
                results.append({
                    'name': name,
                    'phone': re.sub(r'[^0-9+]', '', phone),
                    'address': address,
                    'url': website,
                    'rating': rating,
                    'place_id': str(random.randint(1000000, 9999999)),
                })

        browser.close()

    return results


# ---------------------------------------------------------------------------
# Strategy 2: HTTP Fallback (for when Playwright isn't available)
# ---------------------------------------------------------------------------

def _scrape_with_http(url, query):
    """
    HTTP-based fallback. Google Maps requires JS, so this only works
    if Google serves some data in the HTML (rare but possible).
    """
    import requests
    from bs4 import BeautifulSoup

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/131.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/',
    }

    results = []

    # Try Google Maps page
    resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    html = resp.text
    print(f"[HTTP] Maps page: {len(html)} chars, HTTP {resp.status_code}")

    # Parse JSON-LD structured data
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    name = item.get('name', '').strip()
                    if name and len(name) > 2:
                        phone = item.get('telephone', '')
                        addr_obj = item.get('address', {})
                        address = ''
                        if isinstance(addr_obj, dict):
                            parts = filter(None, [
                                addr_obj.get('streetAddress', ''),
                                addr_obj.get('addressLocality', ''),
                                addr_obj.get('addressRegion', ''),
                            ])
                            address = ', '.join(parts)
                        rating = ''
                        agg = item.get('aggregateRating', {})
                        if isinstance(agg, dict):
                            rating = str(agg.get('ratingValue', ''))
                        results.append({
                            'name': name,
                            'phone': re.sub(r'[^0-9+]', '', phone) if phone else '',
                            'address': address,
                            'rating': rating,
                            'url': item.get('url', ''),
                            'place_id': str(random.randint(1000000, 9999999)),
                        })
        except (json.JSONDecodeError, TypeError):
            continue

    return results
