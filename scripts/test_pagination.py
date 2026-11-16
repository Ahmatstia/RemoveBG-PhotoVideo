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
                cookie_list.append({"name": k, "value": v, "domain": ".shopee.co.id", "path": "/"})
    context.add_cookies(cookie_list)

    page = context.new_page()

    intercepted = []
    def on_res(response):
        if 'get_ratings' in response.url and response.status == 200:
            try:
                data = response.json()
                rats = data.get('data', {}).get('ratings') or []
                print(f"[PAGE INTERCEPT] Got {len(rats)} ratings from URL: {response.url[:90]}...", flush=True)
                intercepted.extend(rats)
            except Exception:
                pass

    page.on('response', on_res)

    print("Navigating...", flush=True)
    page.goto('https://shopee.co.id/product/617908491/12077537305', wait_until='commit')
    page.wait_for_timeout(3000)

    # Scroll down to reviews
    for y in range(800, 5200, 600):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(1000)

    print(f"Captured on initial scroll: {len(intercepted)} reviews", flush=True)

    # Now look for page controller buttons
    buttons = page.locator(".shopee-page-controller button").all()
    print(f"Found {len(buttons)} pagination buttons", flush=True)
    for b in buttons:
        print("Button text/class:", b.inner_text(), b.get_attribute("class"), flush=True)

    # Try clicking next page button or page 2
    if len(buttons) > 1:
        print("Clicking next button or page 2...", flush=True)
        # Click the right arrow button
        right_btn = page.locator(".shopee-page-controller button.shopee-icon-button--right")
        if right_btn.count() > 0:
            right_btn.click()
            page.wait_for_timeout(3000)
            print(f"After page 2 click, total captured: {len(intercepted)} reviews", flush=True)

    browser.close()
