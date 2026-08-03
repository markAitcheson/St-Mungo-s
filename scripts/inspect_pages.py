"""
One-off diagnostic script (v4): find Abodus St James's room-type name for
each price in its Bricks-builder price ladder.

This is NOT part of the production pipeline - safe to delete once scrape.py
has been built and verified.
"""
import json
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

JS = """
() => {
  const results = [];
  const bolds = Array.from(document.querySelectorAll('div.brxe-tmqjgv b, div.brxe-tmqjgv.brxe-shortcode b'));
  for (const priceEl of bolds) {
    let cur = priceEl.parentElement;
    let containerEl = null;
    for (let i = 0; i < 8 && cur; i++) {
      if (cur.children && cur.children.length >= 2) { containerEl = cur; break; }
      cur = cur.parentElement;
    }
    if (!containerEl) containerEl = priceEl.parentElement;
    results.push({
      priceText: priceEl.innerText.trim(),
      containerText: containerEl.innerText ? containerEl.innerText.replace(/\\s+/g,' ').slice(0,300) : '',
      containerCls: containerEl.className ? String(containerEl.className).slice(0,150) : '',
      grandparentText: containerEl.parentElement && containerEl.parentElement.innerText ? containerEl.parentElement.innerText.replace(/\\s+/g,' ').slice(0,400) : ''
    });
  }
  return results;
}
"""


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto("https://abodusstudents.com/accommodation/st-james-glasgow", timeout=60000, wait_until="load")
        page.wait_for_timeout(6000)
        data = page.evaluate(JS)
        browser.close()
    return data


if __name__ == "__main__":
    print(json.dumps(run(), indent=2), flush=True)
