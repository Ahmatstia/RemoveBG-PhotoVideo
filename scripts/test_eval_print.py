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
    page.goto('https://shopee.co.id/product/617908491/12077537305', wait_until='commit')
    page.wait_for_timeout(3000)

    url = '/api/v2/item/get_ratings?filter=0&flag=1&limit=6&offset=0&type=0&exclude_filter=1&filter_size=0&fold_filter=0&relevant_reviews=false&request_source=2&tag_filter=&variation_filters=&need_translation=1&shopid=617908491&itemid=12077537305&fe_toggle=%5B2%2C3%5D'
    res = page.evaluate("""async (u) => {
        const r = await fetch(u, { headers: { 'x-api-source': 'rweb', 'Accept': 'application/json' } });
        return { status: r.status, text: await r.text() };
    }""", url)
    print('Status:', res['status'])
    print('Text:', res['text'][:500])
    browser.close()
