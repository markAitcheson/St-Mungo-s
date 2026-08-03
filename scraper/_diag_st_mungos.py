"""Throwaway diagnostic script: scrape only the two St Mungo's config
entries and print results, to confirm the new modal URLs work as expected
before trusting a real scheduled run. Not part of the pipeline - delete
after use."""
from playwright.sync_api import sync_playwright

from scraper.config import PROPERTIES
from scraper.scrape import scrape_student_roost, USER_AGENT

targets = [p for p in PROPERTIES if p["id"].startswith("student_roost_st_mungos")]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for prop in targets:
        page = browser.new_page(user_agent=USER_AGENT)
        print(f"\n=== {prop['name']} ===")
        print(f"URL: {prop['url']}")
        try:
            rooms = scrape_student_roost(page, prop["url"])
            for r in rooms:
                print(f"  room_type={r['room_type']!r} price_pw={r['price_pw']}")
            if not rooms:
                print("  (no rooms found)")
        except Exception as e:
            print(f"  ERROR: {e}")
        page.close()
    browser.close()
