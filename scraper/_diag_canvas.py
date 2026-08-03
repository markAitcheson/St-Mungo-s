"""Throwaway diagnostic: Canvas Boyce House keeps returning only 2 of 4
en-suite tiers (Bronze, Gold - never Silver, Platinum) across 3 independent
real runs, while the studio side (reached via clicking the "STUDIO" toggle)
returns all 3 tiers cleanly. Investigate whether Silver/Platinum en-suite
are: (a) genuinely absent from the page right now, (b) present but need a
second interaction beyond the EN SUITE/STUDIO toggle (e.g. a carousel/
pagination control), or (c) present in the DOM but filtered out by the
current selector for some reason. Not part of the pipeline - delete after
use."""
import json

from playwright.sync_api import sync_playwright

from scraper.scrape import USER_AGENT

URL = "https://www.canvas-world.com/en/locations/united-kingdom/glasgow/boyce-house#rooms"


def dump(page, label):
    data = page.evaluate("""
    () => {
      const bodyText = document.body.innerText;
      const mentionsSilver = /silver/i.test(bodyText);
      const mentionsPlatinum = /platinum/i.test(bodyText);

      const priceEls = Array.from(document.querySelectorAll('*'))
        .filter(el => el.children.length === 0 && /£\\d/.test(el.innerText || ''));
      const prices = priceEls.map(el => el.innerText.trim());

      // any element whose text mentions a tier name, visible or not
      const tierMentions = Array.from(document.querySelectorAll('*'))
        .filter(el => el.children.length === 0 && /silver|platinum|bronze|gold/i.test(el.innerText || ''))
        .map(el => ({
          text: el.innerText.trim().slice(0, 60),
          visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
        }));

      // clickable controls that might page/carousel through tiers
      const controls = Array.from(document.querySelectorAll('button, a, [role="tab"], [role="button"], [class*="arrow" i], [class*="next" i], [class*="prev" i], [class*="carousel" i], [aria-label]'))
        .map(el => ({
          tag: el.tagName,
          text: (el.innerText || '').trim().slice(0, 40),
          aria: el.getAttribute('aria-label'),
          cls: (el.className || '').toString().slice(0, 60),
        }))
        .filter(c => c.text || c.aria);

      return {
        mentionsSilver, mentionsPlatinum,
        price_count: prices.length,
        prices,
        tier_mention_count: tierMentions.length,
        tier_mentions: tierMentions.slice(0, 30),
        control_count: controls.length,
        controls: controls.slice(0, 40),
      };
    }
    """)
    print(f"\n--- {label} ---")
    print(json.dumps(data, indent=2)[:6000])


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(user_agent=USER_AGENT)
    page.goto(URL, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)
    dump(page, "initial load (en-suite default view)")

    # scroll fully to trigger any lazy-loaded cards
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(3000)
    dump(page, "after scrolling to bottom")

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(1000)

    # dump full raw HTML of whatever section contains the room cards, to eyeball structure
    html = page.evaluate("""
    () => {
      const priceEl = Array.from(document.querySelectorAll('*'))
        .find(el => el.children.length === 0 && /£\\d/.test(el.innerText || ''));
      if (!priceEl) return 'NO PRICE EL FOUND';
      let node = priceEl;
      for (let up = 0; up < 6 && node.parentElement; up++) node = node.parentElement;
      return node.outerHTML.slice(0, 4000);
    }
    """)
    print("\n--- surrounding HTML (6 levels up from first price element) ---")
    print(html)

    browser.close()
