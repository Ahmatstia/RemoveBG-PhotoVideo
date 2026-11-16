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

    def on_req(request):
        if 'get_ratings' in request.url:
            print("=== GET_RATINGS REQUEST DETECTED ===", flush=True)
            print("URL:", request.url, flush=True)
            print("Method:", request.method, flush=True)
            print("Headers:", json.dumps(request.headers, indent=2), flush=True)

    def on_res(response):
        if 'get_ratings' in response.url:
            print(f"RESPONSE STATUS: {response.status}", flush=True)

    page.on('request', on_req)
    page.on('response', on_res)

    page.goto('https://shopee.co.id/product/617908491/12077537305', wait_until='commit')
    page.wait_for_timeout(3000)

    # Scroll down to trigger the request
    for y in range(800, 3600, 600):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(800)

    browser.close()
