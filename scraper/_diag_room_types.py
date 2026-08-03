"""Throwaway diagnostic script: inspect the real DOM for St Mungo's modal
URLs, Canvas's en-suite/studio toggle, and Abodus's #the-rooms ladder, now
that Mark has supplied the ground-truth room type names for each. Prints
raw structured findings so parsers can be corrected against real names
instead of assumptions. Not part of the pipeline - delete after use."""
import json

from playwright.sync_api import sync_playwright

from scraper.scrape import USER_AGENT, _price_from_text


def dump_st_mungos(page, url, label):
    print(f"\n=== St Mungo's - {label} ===")
    print(f"URL: {url}")
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)
    data = page.evaluate("""
    () => {
      const cards = Array.from(document.querySelectorAll('.roomGroup-card')).map(c => ({
        text: c.innerText.replace(/\\n/g, ' | ').slice(0, 400),
        visible: !!(c.offsetWidth || c.offsetHeight || c.getClientRects().length),
      }));
      const modal = document.querySelector('[class*="modal" i], [role="dialog"]');
      return {
        card_count: cards.length,
        cards,
        modal_present: !!modal,
        modal_visible: modal ? !!(modal.offsetWidth || modal.offsetHeight) : null,
        title: document.title,
      };
    }
    """)
    print(json.dumps(data, indent=2)[:4000])


def dump_canvas(page, url):
    print(f"\n=== Canvas Boyce House ===")
    print(f"URL: {url}")
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)

    def snapshot(label):
        data = page.evaluate("""
        () => {
          const results = [];
          const priceEls = Array.from(document.querySelectorAll('span'))
            .filter(el => /£\\d/.test(el.innerText || '') && el.children.length === 0);
          for (const el of priceEls) {
            let heading = '';
            let node = el;
            outer:
            for (let up = 0; up < 8 && node; up++) {
              let sib = node.previousElementSibling;
              while (sib) {
                const h = sib.matches('h1,h2,h3,h4,h5') ? sib : sib.querySelector('h1,h2,h3,h4,h5');
                if (h) { heading = h.innerText.trim(); break outer; }
                sib = sib.previousElementSibling;
              }
              node = node.parentElement;
            }
            results.push({ price: el.innerText.trim(), heading });
          }
          return results;
        }
        """)
        print(f"--- snapshot: {label} ({len(data)} price els) ---")
        print(json.dumps(data, indent=2)[:3000])

    snapshot("initial load")

    toggles = page.evaluate("""
    () => {
      const clickable = Array.from(document.querySelectorAll('button, a, [role="tab"], [role="button"]'));
      return clickable
        .filter(el => /studio|en.?suite|ensuite/i.test(el.innerText || ''))
        .map(el => ({ tag: el.tagName, text: (el.innerText || '').trim().slice(0, 60) }));
    }
    """)
    print(f"--- candidate toggle elements ---")
    print(json.dumps(toggles, indent=2)[:2000])

    clicked = page.evaluate("""
    () => {
      const clickable = Array.from(document.querySelectorAll('button, a, [role="tab"], [role="button"]'));
      const studioToggle = clickable.find(el => /studio/i.test(el.innerText || ''));
      if (studioToggle) { studioToggle.click(); return true; }
      return false;
    }
    """)
    if clicked:
        page.wait_for_timeout(3000)
        snapshot("after clicking a 'studio' toggle")
    else:
        print("(no clickable studio toggle found)")


def dump_abodus(page, url):
    print(f"\n=== Abodus St James ===")
    print(f"URL: {url}")
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(8000)
    data = page.evaluate("""
    () => {
      const isPrice = t => /£\\d.*P\\/W/i.test(t);
      const hasNearbyHeading = el => {
        let node = el;
        for (let up = 0; up < 6 && node; up++) {
          let sib = node.previousElementSibling;
          while (sib) {
            if (sib.matches('h1,h2,h3,h4,h5') || sib.querySelector('h1,h2,h3,h4,h5')) return true;
            sib = sib.previousElementSibling;
          }
          node = node.parentElement;
        }
        return false;
      };
      const nearbyText = el => {
        // walk up to a reasonable container and grab its full text for context
        let node = el;
        for (let up = 0; up < 4 && node.parentElement; up++) node = node.parentElement;
        return node.innerText.replace(/\\n/g, ' | ').slice(0, 300);
      };
      return Array.from(document.querySelectorAll('b'))
        .filter(b => isPrice(b.innerText.trim()))
        .map(b => ({
          price_text: b.innerText.trim(),
          has_nearby_heading: hasNearbyHeading(b),
          container_text: nearbyText(b),
        }));
    }
    """)
    print(json.dumps(data, indent=2)[:6000])


with sync_playwright() as p:
    browser = p.chromium.launch()

    page = browser.new_page(user_agent=USER_AGENT)
    dump_st_mungos(page, "https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-ensuite-st-mungos", "En-suite modal")
    page.close()

    page = browser.new_page(user_agent=USER_AGENT)
    dump_st_mungos(page, "https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-studio-st-mungos", "Studio modal")
    page.close()

    page = browser.new_page(user_agent=USER_AGENT)
    dump_canvas(page, "https://www.canvas-world.com/en/locations/united-kingdom/glasgow/boyce-house#rooms")
    page.close()

    page = browser.new_page(user_agent=USER_AGENT)
    dump_abodus(page, "https://abodusstudents.com/accommodation/st-james-glasgow#the-rooms")
    page.close()

    browser.close()
