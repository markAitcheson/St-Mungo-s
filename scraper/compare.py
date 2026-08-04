"""
History storage (a flat CSV, one row per room type per run) and the
comparison engine that turns it into %/£ deltas vs the last report and vs
the first-ever recorded price, plus how each competitor's price compares to
our own latest price in the same room category.
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

HISTORY_COLUMNS = [
    "run_ts", "property_id", "property_name", "is_own", "room_type",
    "category", "price_pw", "offer_text", "raw_text", "source_url",
]


def _normalize(name: str) -> str:
    """Lowercase, alphanumeric-only form of a room name, so matching survives
    the exact spacing/hyphenation/casing quirks between sites (e.g. Canvas's
    "BRONZE EN SUITE" vs Abodus's "Classic En-suite")."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# Ground-truth room equivalences, as specified directly by Mark (2026-08-04) -
# which competitor room is the same tier as which St Mungo's room, for the
# "vs St Mungo's" comparison column. Deliberately not derived from a tier-name
# or hierarchy-position heuristic: Mark knows which rooms actually compete
# with each other, and that's authoritative over any guess. A competitor room
# not listed here has no specified equivalent and won't get a "vs St Mungo's"
# figure - add a row here (competitor room name, St Mungo's room name) to
# define one.
#
# Keyed by (property_id, normalized competitor room name) -> St Mungo's room
# name (as it appears in scraper/scrape.py's student_roost output).
ROOM_EQUIVALENCE = {}


def _add_equivalence(property_id, competitor_room_names, own_room_name):
    for name in competitor_room_names:
        ROOM_EQUIVALENCE[(property_id, _normalize(name))] = own_room_name


# St Mungo's En-suite bronze
_add_equivalence("canvas_boyce_house", ["Bronze En-suite"], "En-suite bronze")
_add_equivalence("prestige_foundry_courtyard", ["Bronze Plus Ensuite"], "En-suite bronze")
_add_equivalence("abodus_st_james", ["Classic En-suite"], "En-suite bronze")

# St Mungo's En-suite silver
_add_equivalence("canvas_boyce_house", ["Silver En-suite"], "En-suite silver")
_add_equivalence("prestige_foundry_courtyard", ["Silver Ensuite"], "En-suite silver")
_add_equivalence("abodus_st_james", ["Premium En-suite"], "En-suite silver")

# St Mungo's En-suite gold
_add_equivalence("canvas_boyce_house", ["Gold En-suite"], "En-suite gold")
_add_equivalence("prestige_foundry_courtyard", ["Gold Ensuite"], "En-suite gold")
_add_equivalence("abodus_st_james", ["Superior En-suite"], "En-suite gold")

# St Mungo's bronze studio
_add_equivalence("abodus_st_james", ["Classic Studio"], "Studio bronze")

# St Mungo's silver studio
_add_equivalence("canvas_boyce_house", ["Silver Studio"], "Studio silver")
_add_equivalence("prestige_foundry_courtyard", ["Silver Studio"], "Studio silver")
_add_equivalence("abodus_st_james", ["Premium Studio"], "Studio silver")

# St Mungo's gold studio
_add_equivalence("canvas_boyce_house", ["Gold Studio"], "Studio gold")
_add_equivalence("prestige_foundry_courtyard", ["Gold Studio"], "Studio gold")
_add_equivalence("abodus_st_james", ["Deluxe Studio"], "Studio gold")

# St Mungo's platinum studio
_add_equivalence("canvas_boyce_house", ["Platinum Studio"], "Studio platinum")
_add_equivalence("abodus_st_james", ["Superior Studio"], "Studio platinum")


def categorize(room_type: str) -> str:
    """Best-effort room category from a free-text room type name, so prices
    across differently-named competitor room types can still be compared."""
    t = room_type.lower()
    if "studio" in t:
        return "studio"
    if "ensuite" in t or "en-suite" in t or "en suite" in t:
        return "ensuite"
    if "twin" in t or "flat" in t or "apartment" in t or "bed" in t:
        return "shared"
    return "other"


def load_history(path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_history(path, new_rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        if not exists:
            writer.writeheader()
        for row in new_rows:
            writer.writerow(row)


def build_comparison(history_rows: list[dict]) -> list[dict]:
    """One row per (property, room type) as of the latest run, with deltas
    vs the previous run, vs the first-ever run, and vs whichever St Mungo's
    room is its specified equivalent tier (the room a prospective tenant
    would actually be weighing this one against, rather than a
    same-category average that blurs bronze/gold/platinum together).

    The equivalent room comes solely from ROOM_EQUIVALENCE above - Mark's
    explicit ground truth of which competitor room matches which St Mungo's
    room - never guessed from a shared tier name or listing position. A
    competitor room with no entry in ROOM_EQUIVALENCE simply gets no
    "vs St Mungo's" figure."""
    series = defaultdict(list)
    for r in history_rows:
        if r.get("price_pw"):
            series[(r["property_id"], r["room_type"])].append(r)
    for rows in series.values():
        rows.sort(key=lambda r: r["run_ts"])

    all_ts = sorted({r["run_ts"] for r in history_rows})
    if not all_ts:
        return []
    latest_ts = all_ts[-1]

    # Our own latest room prices, keyed by normalized room name, to resolve
    # ROOM_EQUIVALENCE's target names against whatever price we actually
    # have on record for them this run.
    own_prices_by_name = {}
    for rows in series.values():
        last = rows[-1]
        if last.get("is_own") == "True" and last["run_ts"] == latest_ts:
            own_prices_by_name[_normalize(last["room_type"])] = (
                last["room_type"], float(last["price_pw"])
            )

    def find_equivalent(property_id, room_type):
        own_room_name = ROOM_EQUIVALENCE.get((property_id, _normalize(room_type)))
        if own_room_name is None:
            return None
        return own_prices_by_name.get(_normalize(own_room_name))

    comparison = []
    for (property_id, room_type), rows in series.items():
        last = rows[-1]
        if last["run_ts"] != latest_ts:
            continue  # room type wasn't found this run - skip rather than show stale data
        price = float(last["price_pw"])
        category = last["category"]

        pct_vs_prev = delta_vs_prev = None
        if len(rows) >= 2:
            prev_price = float(rows[-2]["price_pw"])
            delta_vs_prev = price - prev_price
            pct_vs_prev = (delta_vs_prev / prev_price) * 100 if prev_price else None

        baseline_price = float(rows[0]["price_pw"])
        delta_vs_baseline = price - baseline_price
        pct_vs_baseline = (delta_vs_baseline / baseline_price) * 100 if baseline_price else None

        vs_own_pct = None
        equivalent_room = None
        is_own = last.get("is_own") == "True"
        if not is_own:
            match = find_equivalent(property_id, room_type)
            if match:
                equivalent_room, own_price = match
                vs_own_pct = ((price - own_price) / own_price) * 100 if own_price else None

        comparison.append({
            "property_id": property_id,
            "property_name": last["property_name"],
            "is_own": is_own,
            "room_type": room_type,
            "category": category,
            "price_pw": price,
            "offer_text": last.get("offer_text", ""),
            "delta_vs_prev": delta_vs_prev,
            "pct_vs_prev": pct_vs_prev,
            "delta_vs_baseline": delta_vs_baseline,
            "pct_vs_baseline": pct_vs_baseline,
            "equivalent_room": equivalent_room,
            "vs_own_pct": vs_own_pct,
            "run_ts": last["run_ts"],
        })

    # Rooms present in the latest run but with no price (e.g. Canvas tiers
    # that show "SOLD OUT" instead of a price) would otherwise disappear
    # entirely, which reads as a scraper miss rather than what it is - still
    # surface them, just with no price/deltas to show.
    seen_keys = {(r["property_id"], r["room_type"]) for r in comparison}
    for r in history_rows:
        if r["run_ts"] != latest_ts or r.get("price_pw"):
            continue
        key = (r["property_id"], r["room_type"])
        if key in seen_keys or r["room_type"] == "SCRAPE ERROR":
            continue
        seen_keys.add(key)
        comparison.append({
            "property_id": r["property_id"],
            "property_name": r["property_name"],
            "is_own": r.get("is_own") == "True",
            "room_type": r["room_type"],
            "category": r["category"],
            "price_pw": None,
            "offer_text": r.get("offer_text", ""),
            "delta_vs_prev": None,
            "pct_vs_prev": None,
            "delta_vs_baseline": None,
            "pct_vs_baseline": None,
            "equivalent_room": None,
            "vs_own_pct": None,
            "run_ts": r["run_ts"],
        })
    return comparison
