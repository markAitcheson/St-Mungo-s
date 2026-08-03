"""
One-off diagnostic script (v3): closes the three remaining gaps from v1/v2 -
room type names for Student Roost & Prestige (the price container itself
matched the "card" heuristic too early), and where Collegiate's booking flow
actually leads (no price text or iframe was found on the page itself).

This is NOT part of the production pipeline - it exists purely so we can see
real page structure and write accurate selectors for scrape.py. Safe to
delete once scrape.py has been built and verified.
"""
import json
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

JS_LISTING_CONTEXT = """
(selector) => {
  const els = Array.from(document.querySelectorAll(selector));
  return els.slice(0, 8).map(priceEl => {
    // walk up, skipping ancestors whose own class mentions price/offer/cashback,
    // looking for a repeated card/listing container
    let cur = priceEl.parentElement;
    let containerEl = null;
    for (let i = 0; i < 8 && cur; i++) {
      const cls = cur.className ? String(cur.className) : '';
      if (/(card|listing-item|listingitem|room-type|roomtype|product-item|tariff-item)/i.test(cls) && !/price/i.test(cls)) {
        containerEl = cur;
        break;
      }
      cur = cur.parentElement;
    }
    if (!containerEl) {
      containerEl = priceEl.parentElement;
      for (let i = 0; i < 4 && containerEl.parentElement; i++) containerEl = containerEl.parentElement;
    }
    return {
      priceText: priceEl.innerText ? priceEl.innerText.trim().slice(0,80) : '',
      containerTag: containerEl.tagName,
      containerCls: containerEl.className ? String(containerEl.className).slice(0,150) : '',
      containerText: containerEl.innerText ? containerEl.innerText.replace(/\\s+/g,' ').slice(0,500) : '',
      // list child elements' class names to see what holds the room-type name
      childClasses: Array.from(containerEl.children).map(c => c.className ? String(c.className).slice(0,80) : c.tagName)
    };
  });
}
"""

JS_LINK_HREFS = """
(labels) => {
  const results = [];
  const all = Array.from(document.querySelectorAll('a,button'));
  for (const el of all) {
    const t = (el.innerText || '').trim();
    if (labels.some(l => t.toLowerCase().includes(l.toLowerCase()))) {
      results.push({ text: t, href: el.href || el.getAttribute('data-href') || '', tag: el.tagName });
    }
  }
  return results;
}
"""


def run():
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Student Roost: room type name alongside atom-listingPrice
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto("https://www.studentroost.co.uk/locations/glasgow/st-mungos", timeout=60000, wait_until="load")
        page.wait_for_timeout(6000)
        out["student_roost"] = page.evaluate(JS_LISTING_CONTEXT, ".atom-listingPrice")
        page.close()

        # Prestige: room type name alongside RoomCard__price
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto("https://prestigestudentliving.com/student-accommodation/glasgow/foundry-courtyard", timeout=60000, wait_until="load")
        page.wait_for_timeout(6000)
        out["prestige"] = page.evaluate(JS_LISTING_CONTEXT, ".RoomCard__price")
        page.close()

        # Collegiate: where does "BOOK NOW" / "Book my stay" actually go?
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto("https://www.collegiate-ac.com/uk-student-accommodation/glasgow/bridleworks/", timeout=60000, wait_until="load")
        page.wait_for_timeout(6000)
        out["collegiate_links"] = page.evaluate(JS_LINK_HREFS, ["book now", "book my stay", "check availability", "rooms"])
        page.close()

        browser.close()
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2), flush=True)
