"""
One-off diagnostic script (v2): renders each target page in a real browser
(via GitHub Actions, which has normal internet access) and prints every
element containing a '£' price, along with the full text of its nearest
"card-like" ancestor container (so room type name + price + offer text stay
together), plus any iframes found on the page.

This is NOT part of the production pipeline - it exists purely so we can see
real page structure and write accurate selectors for scrape.py. Safe to
delete once scrape.py has been built and verified.
"""
import json
from playwright.sync_api import sync_playwright

URLS = {
    "student_roost_st_mungos": "https://www.studentroost.co.uk/locations/glasgow/st-mungos",
    "prestige_foundry_courtyard": "https://prestigestudentliving.com/student-accommodation/glasgow/foundry-courtyard",
    "collegiate_bridleworks": "https://www.collegiate-ac.com/uk-student-accommodation/glasgow/bridleworks/",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

JS_EXTRACT = """
() => {
  const results = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  let count = 0;
  while ((node = walker.nextNode()) && count < 60) {
    const text = node.nodeValue;
    if (text && text.includes('£')) {
      let el = node.parentElement;
      if (!el) continue;
      // walk up to find a "card-like" container: has a class hinting at
      // room/plan/rate/card, or is simply 3-5 levels up with substantial text
      let cur = el;
      let cardEl = null;
      for (let i = 0; i < 6 && cur; i++) {
        const cls = cur.className ? String(cur.className) : '';
        if (/card|room|unit|plan|rate|tariff|product|listing/i.test(cls)) {
          cardEl = cur;
          break;
        }
        cur = cur.parentElement;
      }
      if (!cardEl) {
        // fallback: go up 3 levels
        cardEl = el;
        for (let i = 0; i < 3 && cardEl.parentElement; i++) cardEl = cardEl.parentElement;
      }
      results.push({
        priceText: text.trim().slice(0, 100),
        cardTag: cardEl.tagName,
        cardCls: cardEl.className ? String(cardEl.className).slice(0, 150) : '',
        cardText: cardEl.innerText ? cardEl.innerText.replace(/\\s+/g, ' ').slice(0, 400) : ''
      });
      count++;
    }
  }
  // also report any iframes (booking widgets often live in a separate domain)
  const iframes = Array.from(document.querySelectorAll('iframe')).map(f => ({
    src: f.src, id: f.id, cls: f.className ? String(f.className).slice(0,100) : ''
  }));
  // also report clickable tab/nav labels that might reveal a "Rooms" section
  const tabLike = Array.from(document.querySelectorAll('a,button,[role=tab]'))
    .map(el => el.innerText && el.innerText.trim())
    .filter(t => t && /room|price|book|rate|availability/i.test(t))
    .slice(0, 20);
  return { matches: results, iframes, tabLike };
}
"""


def inspect(name, url):
    out = {"name": name, "url": url}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, timeout=60000, wait_until="load")
            page.wait_for_timeout(6000)
            data = page.evaluate(JS_EXTRACT)
            out["status"] = "ok"
            out["title"] = page.title()
            out["price_matches_count"] = len(data["matches"])
            out["matches"] = data["matches"]
            out["iframes"] = data["iframes"]
            out["tabLike"] = data["tabLike"]
            browser.close()
    except Exception as e:
        out["status"] = "error"
        out["error"] = str(e)
    return out


if __name__ == "__main__":
    for name, url in URLS.items():
        print(f"=== {name} ===", flush=True)
        res = inspect(name, url)
        print(json.dumps(res, indent=2), flush=True)
