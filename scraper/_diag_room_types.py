"""Throwaway diagnostic script v2: Canvas and Abodus are confirmed - this
pass focuses on St Mungo's modal URLs, which returned only the same 2
generic 'En-suite Rooms'/'Studio Rooms' cards as the plain overview page in
v1 (not a Bronze/Silver/Gold breakdown), even though a modal element was
present and visible. Dumps the modal's full text plus every price-bearing
leaf element and its nearest heading, scoped to inside the modal, to find
the real selector for per-tier pricing. Not part of the pipeline - delete
after use."""
import json

from playwright.sync_api import sync_playwright

from scraper.scrape import USER_AGENT


def dump_st_mungos(page, url, label):
    print(f"\n=== St Mungo's - {label} ===")
    print(f"URL: {url}")
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)
    data = page.evaluate("""
    () => {
      const modal = document.querySelector('[class*="modal" i], [role="dialog"]');
      if (!modal) return { modal_present: false };

      const priceEls = Array.from(modal.querySelectorAll('*'))
        .filter(el => el.children.length === 0 && /£\\d/.test(el.innerText || ''));
      const priceItems = priceEls.map(el => {
        let heading = '';
        let node = el;
        outer:
        for (let up = 0; up < 8 && node; up++) {
          let sib = node.previousElementSibling;
          while (sib) {
            const h = sib.matches('h1,h2,h3,h4,h5,h6') ? sib : sib.querySelector('h1,h2,h3,h4,h5,h6');
            if (h) { heading = h.innerText.trim(); break outer; }
            sib = sib.previousElementSibling;
          }
          node = node.parentElement;
        }
        return { price_text: el.innerText.trim().slice(0, 80), tag: el.tagName, class: (el.className || '').toString().slice(0, 80), heading };
      });

      return {
        modal_present: true,
        modal_class: (modal.className || '').toString().slice(0, 150),
        modal_full_text: modal.innerText.replace(/\\n+/g, ' | ').slice(0, 3000),
        price_item_count: priceItems.length,
        price_items: priceItems.slice(0, 40),
      };
    }
    """)
    print(json.dumps(data, indent=2)[:8000])


with sync_playwright() as p:
    browser = p.chromium.launch()

    page = browser.new_page(user_agent=USER_AGENT)
    dump_st_mungos(page, "https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-ensuite-st-mungos", "En-suite modal")
    page.close()

    page = browser.new_page(user_agent=USER_AGENT)
    dump_st_mungos(page, "https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-studio-st-mungos", "Studio modal")
    page.close()

    browser.close()
