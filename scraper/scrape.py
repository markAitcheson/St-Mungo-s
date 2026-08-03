"""
Per-site parsers. Selectors below were confirmed against real rendered pages
(see git history for the diagnostic scripts used to find them) - not
guessed. Each parser returns a list of {room_type, price_pw, offer_text,
raw_text} dicts for one property.

If a site redesigns its page, its parser will start returning nothing (or
throw) rather than silently returning wrong prices - scrape_all() catches
that per-property and records a "SCRAPE ERROR" row so it's visible in the
report rather than silently missing.
"""
import re

from playwright.sync_api import sync_playwright

from scraper.config import PROPERTIES
from scraper.compare import categorize

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _price_from_text(text: str):
    m = re.search(r"£\s?([\d,]+(?:\.\d{2})?)", text)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def scrape_student_roost(page, url):
    """Room type cards: div.roomGroup-card (excludes the "other Student
    Roost properties nearby" cards, which use a different class)."""
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)
    out = []
    for card in page.query_selector_all(".roomGroup-card"):
        text = card.inner_text().replace("\n", " ")
        m = re.match(r"(.*?)\s+from\s*£", text)
        room_type = m.group(1).strip() if m else "Unknown room type"
        price = _price_from_text(text)
        if price is None:
            continue
        out.append({"room_type": room_type, "price_pw": price, "offer_text": "", "raw_text": text[:300]})
    return out


def scrape_prestige(page, url):
    """Room cards: div.RoomCard__inner, text like
    'Limited Availability Bronze Plus Ensuite 1 wks from £175 pp/pw'."""
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)
    out = []
    for card in page.query_selector_all(".RoomCard__inner"):
        text = card.inner_text().replace("\n", " ")
        m = re.search(r"Availability\s+(.*?)\s+\d+\s*wks?\s*from\s*£([\d.]+)", text)
        price = _price_from_text(text)
        if price is None:
            continue
        room_type = m.group(1).strip() if m else "Unknown room type"
        out.append({"room_type": room_type, "price_pw": price, "offer_text": "", "raw_text": text[:300]})
    return out


def scrape_canvas(page, url):
    """No stable class names (Tailwind-generated); prices are leaf <span>s
    containing '£', room type is the nearest preceding heading."""
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)
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
    out = []
    seen = set()
    for item in data:
        price = _price_from_text(item["price"])
        if price is None:
            continue
        room_type = item["heading"] or "Unknown room type"
        key = (room_type, price)
        if key in seen:
            continue
        seen.add(key)
        out.append({"room_type": room_type, "price_pw": price, "offer_text": "", "raw_text": item["price"]})
    return out


def scrape_abodus(page, url):
    """Bricks-builder page: the room price ladder is <b> tags formatted
    '£175.00 P/W'. Bricks regenerates its hashed class names (e.g.
    'brxe-tmqjgv') between page loads, so scoping by class is unreliable -
    confirmed by two real runs where the same selector matched 7 elements
    once and 0 the next. Instead this filters structurally: real ladder
    items have no heading directly above them, while both the page's hero
    teaser price and its "similar properties" carousel (which repeats
    prices for St James itself and other Abodus properties like Martha
    Street Apartments in the same '£X P/W' format) always sit right under a
    property-name heading. Room-type labels for each price couldn't be
    reliably matched (see README.md "Known limitations") - rooms are
    numbered by price rank instead until someone checks the page and
    confirms real names."""
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)
    texts = page.evaluate("""
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
      return Array.from(document.querySelectorAll('b'))
        .filter(b => isPrice(b.innerText.trim()) && !hasNearbyHeading(b))
        .map(b => b.innerText.trim());
    }
    """)
    out = []
    for i, t in enumerate(texts, start=1):
        price = _price_from_text(t)
        if price is None:
            continue
        out.append({
            "room_type": f"Room tier {i} (label unconfirmed - see README)",
            "price_pw": price,
            "offer_text": "",
            "raw_text": t,
        })
    return out


def scrape_collegiate_unavailable(page, url):
    """Bridle Works shows no static pricing - "Book my stay" redirects to a
    StarRez booking portal that needs a date-range search to reveal prices,
    which isn't reliably scrapeable with a plain page visit. Returns a
    placeholder row so the gap is visible in the report instead of the
    property silently vanishing."""
    return [{
        "room_type": "N/A",
        "price_pw": None,
        "offer_text": "Pricing lives behind a separate booking portal (StarRez) - check manually.",
        "raw_text": "",
    }]


PARSERS = {
    "student_roost": scrape_student_roost,
    "prestige": scrape_prestige,
    "canvas": scrape_canvas,
    "abodus": scrape_abodus,
    "collegiate_unavailable": scrape_collegiate_unavailable,
}


def scrape_all() -> list[dict]:
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for prop in PROPERTIES:
            page = browser.new_page(user_agent=USER_AGENT)
            parser = PARSERS[prop["parser"]]
            try:
                rooms = parser(page, prop["url"])
                error = None
            except Exception as e:
                rooms = []
                error = str(e)
            for r in rooms:
                r.update({
                    "property_id": prop["id"],
                    "property_name": prop["name"],
                    "is_own": prop["is_own"],
                    "source_url": prop["url"],
                    "category": categorize(r["room_type"]),
                })
                results.append(r)
            if error:
                results.append({
                    "property_id": prop["id"], "property_name": prop["name"], "is_own": prop["is_own"],
                    "room_type": "SCRAPE ERROR", "price_pw": None, "offer_text": error[:300],
                    "raw_text": "", "source_url": prop["url"], "category": "error",
                })
            page.close()
        browser.close()
    return results
