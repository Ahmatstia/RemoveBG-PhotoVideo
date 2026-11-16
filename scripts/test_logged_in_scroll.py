import json
from playwright.sync_api import sync_playwright

with open('data/shopee_cookies.json') as f:
    cookie_str = json.load(f)['cookie_string']

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--disable-blink-features=AutomationControlled'])
    context = browser.new_context(
        viewport={'width': 1280, 'height': 850},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

    cookie_list = []
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            k = k.strip()
            v = v.strip()
            if k:
                cookie_list.append({
                    "name": k,
                    "value": v,
                    "domain": ".shopee.co.id",
                    "path": "/",
                })
    context.add_cookies(cookie_list)

    page = context.new_page()

    captured_ratings = []
    def on_res(response):
        url = response.url
        if 'rating' in url.lower() or 'comment' in url.lower():
            print(f'INTERCEPTED: {url} -> {response.status}', flush=True)
            if response.status == 200:
                try:
                    data = response.json()
                    ratings = data.get('data', {}).get('ratings') or []
                    print(f'>>> GOT {len(ratings)} RATINGS! <<<', flush=True)
                    captured_ratings.extend(ratings)
                except Exception as e:
                    print('JSON parse error:', e, flush=True)
            else:
                try:
                    print('Status not 200, text:', response.text()[:200], flush=True)
                except Exception:
                    pass

    page.on('response', on_res)

    print('Navigating to canonical URL as logged in user...', flush=True)
    page.goto('https://shopee.co.id/product/617908491/12077537305', wait_until='commit')
    page.wait_for_timeout(3000)

    # Scroll down to reviews
    print('Scrolling down...', flush=True)
    for y in range(800, 5000, 600):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(1000)

    print(f'Total captured ratings: {len(captured_ratings)}')
    if captured_ratings:
        print('Sample rating:', captured_ratings[0].get('comment'))
    
    browser.close()
