"""Throwaway diagnostic v2: use the confirmed real card structure
(h4[data-automation="Floor-Room-Card-Title"] for room name,
span[data-automation="Floor-Room-Card-Description"] for the "Prices from
£X per week" text) instead of a generic price-leaf-element scan, to get an
exact, unambiguous count of room cards on both toggle states. v1's generic
scan snagged a giant non-price HTML blob and was unusable. Not part of the
pipeline - delete after use."""
import json

from playwright.sync_api import sync_playwright

from scraper.scrape import USER_AGENT

URL = "https://www.canvas-world.com/en/locations/united-kingdom/glasgow/boyce-house#rooms"

CARD_DUMP_JS = """
() => {
  const titles = Array.from(document.querySelectorAll('[data-automation="Floor-Room-Card-Title"]'));
  return titles.map(t => {
    const card = t.closest('[data-automation="Floor-Room-Card-Content"]') || t.parentElement;
    const desc = card ? card.querySelector('[data-automation="Floor-Room-Card-Description"]') : null;
    const visible = !!(t.offsetWidth || t.offsetHeight || t.getClientRects().length);
    return {
      name: t.innerText.trim(),
      price_text: desc ? desc.innerText.trim() : null,
      visible,
    };
  });
}
"""

TOGGLE_STATE_JS = """
() => {
  const clickable = Array.from(document.querySelectorAll('button, a, [role="tab"], [role="button"]'))
    .filter(el => /^\\s*(en.?suite|studio)\\s*$/i.test((el.innerText || '').trim()));
  return clickable.map(el => ({
    text: el.innerText.trim(),
    aria_selected: el.getAttribute('aria-selected'),
    aria_pressed: el.getAttribute('aria-pressed'),
    cls: (el.className || '').toString().slice(0, 100),
  }));
}
"""


def dump(page, label):
    print(f"\n--- {label} ---")
    print("toggle state:", json.dumps(page.evaluate(TOGGLE_STATE_JS)))
    cards = page.evaluate(CARD_DUMP_JS)
    print(f"card_count={len(cards)}")
    print(json.dumps(cards, indent=2))


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(user_agent=USER_AGENT)
    page.goto(URL, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)
    dump(page, "initial load")

    clicked_studio = page.evaluate("""
    () => {
      const clickable = Array.from(document.querySelectorAll('button, a, [role="tab"], [role="button"]'));
      const t = clickable.find(el => /studio/i.test(el.innerText || ''));
      if (t) { t.click(); return true; }
      return false;
    }
    """)
    if clicked_studio:
        page.wait_for_timeout(3000)
        dump(page, "after clicking STUDIO toggle")

    clicked_ensuite = page.evaluate("""
    () => {
      const clickable = Array.from(document.querySelectorAll('button, a, [role="tab"], [role="button"]'));
      const t = clickable.find(el => /^\\s*en.?suite\\s*$/i.test((el.innerText || '').trim()));
      if (t) { t.click(); return true; }
      return false;
    }
    """)
    if clicked_ensuite:
        page.wait_for_timeout(3000)
        dump(page, "after clicking back to EN SUITE toggle")

    browser.close()
