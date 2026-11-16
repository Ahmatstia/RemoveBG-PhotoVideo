import json
from playwright.sync_api import sync_playwright

with open('data/shopee_cookies.json') as f:
    cookie_str = json.load(f)['cookie_string']

shop_id = 617908491
item_id = 12077537305

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

    captured_reviews = []
    seen_ids = set()

    def on_res(response):
        url = response.url
        if 'get_ratings' in url and response.status == 200:
            try:
                data = response.json()
                ratings = data.get('data', {}).get('ratings') or []
                for r in ratings:
                    cid = r.get('cmmtid')
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        captured_reviews.append({
                            'id': cid,
                            'user': r.get('author_username'),
                            'star': r.get('rating_star'),
                            'comment': (r.get('comment') or '').strip(),
                            'model': r.get('product_items', [{}])[0].get('model_name') if r.get('product_items') else '',
                            'images': len(r.get('images') or []),
                        })
                print(f'Captured so far: {len(captured_reviews)} reviews', flush=True)
            except Exception as e:
                pass

    page.on('response', on_res)

    page.goto(f'https://shopee.co.id/product/{shop_id}/{item_id}', wait_until='commit')
    page.wait_for_timeout(3000)

    # Scroll to reviews
    for y in range(800, 3600, 600):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(800)

    # Now test relative evaluate fetch with the exact query parameters!
    for offset in range(6, 60, 6):
        endpoint = (
            f"/api/v2/item/get_ratings?filter=0&flag=1&limit=6&offset={offset}&type=0"
            f"&exclude_filter=1&filter_size=0&fold_filter=0&relevant_reviews=false"
            f"&request_source=2&tag_filter=&variation_filters=&need_translation=1"
            f"&shopid={shop_id}&itemid={item_id}&fe_toggle=%5B2%2C3%5D"
        )
        res = page.evaluate("""async (url) => {
            try {
                const r = await fetch(url, { headers: { 'x-api-source': 'rweb', 'Accept': 'application/json' } });
                return { status: r.status, text: await r.text() };
            } catch(e) {
                return { status: 0, text: String(e) };
            }
        }""", endpoint)
        print(f"Offset {offset} fetch status:", res['status'])
        if res['status'] == 200:
            try:
                d = json.loads(res['text'])
                rats = d.get('data', {}).get('ratings') or []
                for r in rats:
                    cid = r.get('cmmtid')
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        captured_reviews.append({
                            'id': cid,
                            'user': r.get('author_username'),
                            'star': r.get('rating_star'),
                            'comment': (r.get('comment') or '').strip(),
                            'model': r.get('product_items', [{}])[0].get('model_name') if r.get('product_items') else '',
                            'images': len(r.get('images') or []),
                        })
            except Exception:
                pass
        page.wait_for_timeout(500)

    print(f"\nTOTAL REVIEWS CAPTURED: {len(captured_reviews)}")
    for i, rev in enumerate(captured_reviews[:5]):
        print(f"[{i+1}] {rev['user']} (⭐{rev['star']}) - Varian: {rev['model']}")
        print(f"     \"{rev['comment'][:80]}...\" (Foto: {rev['images']})")

    browser.close()
