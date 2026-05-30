import re
import urllib.parse
import random
from playwright.sync_api import sync_playwright

def extract_google_maps(category, location, page_num=1):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        query = urllib.parse.quote(f"{category} in {location}")
        url = f"https://www.google.com/maps/search/{query}"
        
        print(f"[GoogleMaps-Python] Navigating to: {url}")
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)
        
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
            print(f"[GoogleMaps-Python] Feed selector not found: {e}")
            
        results = []
        cards = page.locator('.Nv2PK').all()
        for card in cards:
            name, phone, address, rating, website = '', '', '', '', ''
            
            name_el = card.locator('.qBF1Pd')
            if name_el.count() > 0:
                name = name_el.first.inner_text().strip()
                
            rating_el = card.locator('.MW4etd')
            if rating_el.count() > 0:
                rating = rating_el.first.inner_text().strip()
                
            web_el = card.locator('a.lcr4fd, a[data-value="Website"]')
            if web_el.count() > 0:
                website = web_el.first.get_attribute('href')
                
            card_text = card.inner_text()
            
            # Phone regex
            phone_match = re.search(r'(\+91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}|0\d{2,4}[\-\s]?\d{6,8}', card_text)
            if phone_match:
                phone = phone_match.group(0)
                
            lines = card_text.split('\n')
            for line in lines:
                if 'Kerala' in line or 'India' in line or len(line) > 10:
                    if 'Open' not in line and 'Closed' not in line and not re.match(r'^\d+\.\d+', line):
                        address = line
                        break
                        
            if name and len(name) > 2:
                results.append({
                    'business_name': name,
                    'phone': re.sub(r'[^0-9+]', '', phone),
                    'address': address,
                    'url': website,
                    'rating': rating
                })
                
        unique_leads = []
        seen = set()
        for lead in results:
            if lead['business_name'] not in seen:
                seen.add(lead['business_name'])
                unique_leads.append({
                    'name': lead['business_name'],
                    'phone': lead['phone'],
                    'address': lead['address'],
                    'rating': lead['rating'],
                    'url': lead['url'],
                    'place_id': str(random.randint(1000000, 9999999))
                })
                
        browser.close()
        
        return {
            'leads': unique_leads,
            'page': page_num,
            'has_next': False,
            'total': len(unique_leads),
            'source_url': url
        }
