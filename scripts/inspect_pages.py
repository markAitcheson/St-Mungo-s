"""One-off diagnostic: does scrolling / a longer wait change how many price
elements Abodus's St James page renders? Tests the lazy-load hypothesis
after scrape_abodus() returned 0 rows on two consecutive real runs despite
matching 7 in the original inspection. Safe to delete afterwards."""
import json
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

COUNT_JS = """
() => Array.from(document.querySelectorAll('b'))
  .map(b => b.innerText.trim())
  .filter(t => /£\\d.*P\\/W/i.test(t))
"""


def run():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(
            "https://abodusstudents.com/accommodation/st-james-glasgow",
            timeout=60000, wait_until="load",
        )
        page.wait_for_timeout(3000)
        results["after_3s_no_scroll"] = page.evaluate(COUNT_JS)

        page.wait_for_timeout(5000)
        results["after_8s_no_scroll"] = page.evaluate(COUNT_JS)

        # scroll through the whole page to trigger any lazy-loaded sections
        page.evaluate("""
        async () => {
          const step = 400;
          const delay = ms => new Promise(r => setTimeout(r, ms));
          let y = 0;
          while (y < document.body.scrollHeight) {
            window.scrollTo(0, y);
            await delay(150);
            y += step;
          }
          window.scrollTo(0, 0);
        }
        """)
        page.wait_for_timeout(2000)
        results["after_full_scroll"] = page.evaluate(COUNT_JS)

        results["body_text_length"] = page.evaluate("() => document.body.innerText.length")
        results["contains_bot_check_wording"] = page.evaluate(
            "() => /verify you are human|checking your browser|cloudflare/i.test(document.body.innerText)"
        )
        browser.close()
    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2), flush=True)
