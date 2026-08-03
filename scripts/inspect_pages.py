"""
One-off diagnostic script: renders each target page in a real browser (via
GitHub Actions, which has normal internet access) and prints every element
containing a '£' price, its tag/class chain, and the nearest heading text.

This is NOT part of the production pipeline - it exists purely so we can see
real page structure and write accurate selectors for scrape.py. Safe to
delete once scrape.py has been built and verified.
"""
import json
from playwright.sync_api import sync_playwright

URLS = {
    "student_roost_st_mungos": "https://www.studentroost.co.uk/locations/glasgow/st-mungos",
    "abodus_st_james": "https://abodusstudents.com/accommodation/st-james-glasgow",
    "prestige_foundry_courtyard": "https://prestigestudentliving.com/student-accommodation/glasgow/foundry-courtyard",
    "canvas_boyce_house": "https://www.canvas-world.com/en/locations/united-kingdom/glasgow/boyce-house",
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
      const el = node.parentElement;
      if (!el) continue;
      const chain = [];
      let cur = el;
      for (let i = 0; i < 4 && cur; i++) {
        chain.push({
          tag: cur.tagName,
          cls: cur.className ? String(cur.className).slice(0, 100) : '',
          id: cur.id || ''
        });
        cur = cur.parentElement;
      }
      let heading = '';
      let node2 = el;
      outer:
      for (let up = 0; up < 6 && node2; up++) {
        let sib = node2.previousElementSibling;
        while (sib) {
          if (/^H[1-6]$/.test(sib.tagName)) { heading = sib.innerText.slice(0, 120); break outer; }
          const h = sib.querySelector && sib.querySelector('h1,h2,h3,h4,h5');
          if (h) { heading = h.innerText.slice(0, 120); break outer; }
          sib = sib.previousElementSibling;
        }
        node2 = node2.parentElement;
      }
      results.push({ text: text.trim().slice(0, 200), tag: el.tagName, cls: el.className ? String(el.className).slice(0, 120) : '', chain, heading });
      count++;
    }
  }
  return results;
}
"""


def inspect(name, url):
    out = {"name": name, "url": url}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, timeout=45000, wait_until="networkidle")
            page.wait_for_timeout(3000)
            matches = page.evaluate(JS_EXTRACT)
            out["status"] = "ok"
            out["title"] = page.title()
            out["price_matches_count"] = len(matches)
            out["matches"] = matches
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
