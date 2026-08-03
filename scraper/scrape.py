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
    """Each config URL opens a specific room-category modal via a
    ?modal=rooms-{ensuite,studio}-st-mungos query param. The modal (found
    via a generic [class*="modal"]/[role="dialog"] selector, confirmed
    present and populated in a real diagnostic run) contains one price-per
    price-bearing leaf element per room tier, e.g. "En-suite bronze" £179,
    "Studio gold" £237 - a real per-tier breakdown, unlike the plain page's
    .roomGroup-card summary which only shows one blended "from" price per
    broad category. "Upper floor" en-suite variants (a premium sub-tier of
    each of bronze/silver/gold) are dropped: Mark's ground-truth room list
    only wants the 3 base en-suite tiers tracked, not those variants."""
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)
    data = page.evaluate("""
    () => {
      const modal = document.querySelector('[class*="modal" i], [role="dialog"]');
      if (!modal) return [];
      const priceEls = Array.from(modal.querySelectorAll('*'))
        .filter(el => el.children.length === 0 && /£\\d/.test(el.innerText || ''));
      return priceEls.map(el => {
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
        return { price: el.innerText.trim(), heading };
      });
    }
    """)
    out = []
    seen = set()
    for item in data:
        room_type = item["heading"] or "Unknown room type"
        if "upper floor" in room_type.lower():
            continue
        price = _price_from_text(item["price"])
        if price is None:
            continue
        key = (room_type, price)
        if key in seen:
            continue
        seen.add(key)
        out.append({"room_type": room_type, "price_pw": price, "offer_text": "", "raw_text": item["price"]})
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


_CANVAS_PRICE_SNAPSHOT_JS = """
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
"""

_CANVAS_CLICK_STUDIO_TOGGLE_JS = """
() => {
  const clickable = Array.from(document.querySelectorAll('button, a, [role="tab"], [role="button"]'));
  const studioToggle = clickable.find(el => /studio/i.test(el.innerText || ''));
  if (studioToggle) { studioToggle.click(); return true; }
  return false;
}
"""


def scrape_canvas(page, url):
    """No stable class names (Tailwind-generated); prices are leaf <span>s
    containing '£', room type is the nearest preceding heading. The page
    shows en-suite and studio room tiers behind a two-way toggle (buttons
    labelled "EN SUITE" / "STUDIO") rather than both at once, so this
    scrapes the default (en-suite) view, clicks the "STUDIO" toggle, and
    scrapes again - confirmed via a real diagnostic run to reveal the
    studio tiers (Gold/Platinum/Silver) that were previously missing."""
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(6000)

    out = []
    seen = set()

    def collect():
        for item in page.evaluate(_CANVAS_PRICE_SNAPSHOT_JS):
            price = _price_from_text(item["price"])
            if price is None:
                continue
            room_type = item["heading"] or "Unknown room type"
            key = (room_type, price)
            if key in seen:
                continue
            seen.add(key)
            out.append({"room_type": room_type, "price_pw": price, "offer_text": "", "raw_text": item["price"]})

    collect()
    if page.evaluate(_CANVAS_CLICK_STUDIO_TOGGLE_JS):
        page.wait_for_timeout(3000)
        collect()
    return out


_ABODUS_ROOM_PATTERN = re.compile(
    r"(?:Available|Limited Availability)\s*\|\s*(.+?)\s*\|.*?"
    r"Prices from:\s*£([\d,]+(?:\.\d{2})?)\s*P/W.*?View Room",
    re.IGNORECASE,
)


def scrape_abodus(page, url):
    """Bricks-builder page: the room price ladder is <b> tags formatted
    '£175.00 P/W'. Bricks regenerates its hashed class names (e.g.
    'brxe-tmqjgv') between page loads, so scoping by class is unreliable -
    a class-based selector matched 7 elements once and 0 the next across
    real runs. This instead reads each price's surrounding text (walking up
    4 ancestor levels) and matches it against the real card copy pattern
    "Available | {Room Name} | {description} | Prices from: £{price} P/W |
    View Room" - confirmed via a real diagnostic run to return all 7 room
    tiers with their actual names (e.g. "Classic En-suite", "Deluxe
    Studio"). This also cleanly excludes the page's hero teaser price and
    its "similar properties" carousel (St James itself + other Abodus
    properties like Martha Street Apartments), which repeat the same
    '£X P/W' format but end in "View Property" instead of "View Room" and
    don't match the room-card pattern."""
    page.goto(url, timeout=60000, wait_until="load")
    page.wait_for_timeout(8000)
    texts = page.evaluate("""
    () => {
      const isPrice = t => /£\\d.*P\\/W/i.test(t);
      const containerText = el => {
        let node = el;
        for (let up = 0; up < 4 && node.parentElement; up++) node = node.parentElement;
        return node.innerText.replace(/\\n/g, ' | ');
      };
      return Array.from(document.querySelectorAll('b'))
        .filter(b => isPrice(b.innerText.trim()))
        .map(b => containerText(b));
    }
    """)
    out = []
    seen = set()
    for t in texts:
        m = _ABODUS_ROOM_PATTERN.search(t)
        if not m:
            continue
        room_type = m.group(1).strip()
        price = float(m.group(2).replace(",", ""))
        key = (room_type, price)
        if key in seen:
            continue
        seen.add(key)
        out.append({"room_type": room_type, "price_pw": price, "offer_text": "", "raw_text": t[:300]})
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
