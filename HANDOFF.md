# Handoff notes: Glasgow comp set report project

Written so a fresh Claude session (no memory of the conversation that built
this) can pick up exactly where things left off. Read this whole file before
changing anything.

## Who / what this is for

Mark Aitcheson manages **St Mungo's**, a Student Roost accommodation
building in Glasgow. He wants an automated competitive-set price tracker:
twice a day, scrape local competitors' room pricing, compare it to St
Mungo's own pricing, and get a report showing side-by-side prices, % change
since the last report, and % change since the first-ever recorded price.

Repo: **markAitcheson/St-Mungo-s**. Default branch is
`claude/student-accommodation-access-5v5j44` (this matters - GitHub Actions
`schedule` triggers, and `workflow_dispatch` *registration* (see below),
only ever work from whatever branch is set as default).

A prior session's work happened on a different branch,
`claude/script-scheduling-gmt-cyjouw`, and had not been merged into the
default branch - see "Branch mismatch (resolved)" below for what that was
and how it was fixed.

## Decisions already made (don't re-litigate these without reason)

- **Automation engine: GitHub Actions**, not a Claude Code Routine/session.
  Reasoning: an unattended twice-daily job needs to run whether or not this
  session/environment exists at the time; GitHub Actions runners have full
  internet access (this Claude Code sandbox's own network is locked to an
  allowlist - see "Environment quirk" below) and cost nothing at this
  volume.
- **Output format: a real .xlsx file** ("Option A" - not yet the "Option B"
  live OneDrive-via-Graph-API upgrade that was discussed and deferred).
  Mark has the Claude for Excel add-in and will open the workbook there for
  trend analysis using the "History" sheet.
- **Delivery: email**, sent via Gmail SMTP using a dedicated sending Gmail
  account + an app password stored as a GitHub Actions secret (the Gmail
  MCP tool only supports creating drafts, not actually sending, which is
  why this goes through smtplib directly instead).
- **Data storage: a flat CSV** (`data/history.csv`, append-only, one row per
  room type per run) committed back into the repo by the workflow itself
  after each run. No external database.

## Environment quirk worth knowing

This Claude Code session's own outbound network is policy-restricted to an
allowlist (npm, PyPI, GitHub API, etc.) - it **cannot** directly fetch
arbitrary competitor websites (`curl`/WebFetch both get blocked/403'd).
GitHub Actions runners have no such restriction. The workaround used
throughout this build: push a small throwaway diagnostic workflow, trigger
it via `mcp__github__actions_run_trigger` (method `run_workflow`), poll
`https://api.github.com/repos/.../actions/runs/<id>` until `status:
completed`, then pull logs via `mcp__github__get_job_logs`. This is also how
every real scraper selector below was confirmed against live pages rather
than guessed. Re-use this pattern for any future site inspection.

Also: raw.githubusercontent.com is CDN-cached for a few minutes - when
checking freshly-pushed file contents, fetch via
`api.github.com/repos/.../contents/<path>?ref=<commit-sha>` (base64-decoded)
instead, or you'll read stale data.

## Repo structure

```
scraper/
  config.py        PROPERTIES list: each competitor's id/name/url/parser key
  scrape.py         One parser function per site (Playwright), scrape_all() orchestrates
  compare.py        History CSV read/write + build_comparison() (the %Δ math)
  report_excel.py   Builds the .xlsx (Latest comp set + History sheets)
  send_email.py     smtplib SMTP_SSL send via Gmail app password
run_pipeline.py      Entry point: scrape -> append history -> build xlsx -> email
requirements.txt     playwright, openpyxl
.github/workflows/comp-set-report.yml   The real scheduled workflow
data/history.csv, data/latest_comp_set.xlsx   Committed by the workflow each run
README.md            Beginner-friendly GitHub setup instructions for Mark
```

## Branch mismatch (resolved)

A prior session's changes (new room-type-specific URLs, Bridle Works
removal, schedule change to 08:00/14:00 GMT) were committed to
`claude/script-scheduling-gmt-cyjouw` instead of the default branch
(`claude/student-accommodation-access-5v5j44`), so none of it took effect
on scheduled/dispatched runs - the default branch kept running the *old*
code: old single overview URL for St Mungo's, Bridle Works still present,
old 07:00/18:00 UTC schedule.

Before the fix, Mark manually triggered the real "Glasgow comp set report"
workflow to verify end-to-end delivery (Gmail secrets are now configured
and working - he received a real email with the .xlsx attached). That run
executed on the **default branch**, i.e. against the **old** code, not the
new URLs from the other session. Concretely, confirmed from
`data/history.csv` on the default branch (run at `2026-08-03T17:44:22+00:00`):
- St Mungo's (own): both En-suite (£179) and Studio (£209) captured fine.
- Foundry Courtyard (Prestige): 8 room types captured, looks complete.
- **St James (Abodus): missing entirely from this run** (zero rows) -
  consistent with the pre-existing documented flakiness below, not a new
  issue.
- **Canvas (Boyce House): only 2 rows, both En-suite** ("BRONZE EN SUITE"
  £162, "GOLD EN SUITE" £188) - **no Studio rooms at all**. This confirms
  the toggle-hiding risk flagged in this file previously: the old overview
  page apparently only exposes one room type (En-suite) in the DOM by
  default, and Studio isn't being captured.
- Bridle Works: still present as a placeholder row (old code never removed
  it - that removal only existed on the other branch).

So: **the "missing room types" Mark observed were from the OLD
scraper/URLs**, not a verdict on the new modal/anchor URLs, which were
still untested at the time. Mark said he would manually supply the
complete, correct list of room types per property, to use as ground truth.

**Fix applied**: `claude/script-scheduling-gmt-cyjouw` was merged into a
branch based on the current default branch (bringing in the new URLs,
Bridle Works removal, and 08:00/14:00 GMT schedule), and the throwaway
`_diag-st-mungos` diagnostic workflow/script from that branch was deleted
before merging (it was only needed for one-off inspection, not for
production). That merge is the PR this HANDOFF update ships with - once
it's merged into `claude/student-accommodation-access-5v5j44`, the default
branch will actually run the new code on schedule/dispatch.

**Next session still needs to**: re-run and compare against Mark's
manually-supplied ground-truth room type list, fixing the Canvas parser
(confirmed missing Studio) and revisiting Abodus and the new St Mungo's
modal URLs per the notes below - none of that behavioral validation was
in scope for the branch-mismatch fix itself.

## The comp set (as of this session)

Bridle Works (Collegiate) has been **removed** - Mark decided it's too hard
to scrape reliably (see below) and asked for it to be dropped rather than
kept as a placeholder row.

Mark supplied **room/type-specific URLs** (modal deep-links or in-page
anchors) in place of the plain overview pages the parsers were originally
built against, then supplied the **ground-truth room type list per
property** in this session. Every parser below has been rewritten and
re-validated against that ground truth via real GitHub Actions diagnostic
runs (see "Environment quirk" for the pattern) - not guessed:

| Property | URL | is_own | parser key |
|---|---|---|---|
| St Mungo's (Student Roost) - En-suite | https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-ensuite-st-mungos | True | `student_roost` |
| St Mungo's (Student Roost) - Studio | https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-studio-st-mungos | True | `student_roost` |
| St James (Abodus) | https://abodusstudents.com/accommodation/st-james-glasgow#the-rooms | False | `abodus` |
| Foundry Courtyard (Prestige) | https://prestigestudentliving.com/student-accommodation/glasgow/foundry-courtyard | False | `prestige` |
| Boyce House (Canvas) | https://www.canvas-world.com/en/locations/united-kingdom/glasgow/boyce-house#rooms | False | `canvas` |

## Validation status per site (confirmed via real GitHub Actions runs against Mark's ground truth)

- **St Mungo's (own)**: reliable, and now returns real per-tier pricing
  instead of two blended category prices. The `?modal=...` query params
  open a modal (`[class*="modal" i], [role="dialog"]`) containing one price
  per tier - confirmed via a real run: En-suite modal returns Bronze £179,
  Silver £199, Gold £209 (3 rows, matching Mark's list exactly); Studio
  modal returns Bronze £211, plain "Studio" £209, Silver £209, Gold £237,
  Platinum £275 (5 rows, also an exact match). The en-suite modal also
  contains "upper floor" variants of each tier (e.g. "En-suite bronze -
  upper floor" £189) - these are deliberately filtered out in
  `scrape_student_roost()` since Mark's ground-truth list only wants the 3
  base en-suite tiers tracked.
- **Prestige Foundry Courtyard**: reliable, untouched this session (Mark
  confirmed the report already looks accurate for this property).
  `.RoomCard__inner` containers, 8-9 room types e.g. Bronze Plus Ensuite
  £175, Silver Ensuite £190, Gold Studio £285. Text pattern:
  `"Limited Availability {room name} {n} wks from £{price} pp/pw"`.
- **Canvas Boyce House**: en-suite and studio tiers sit behind a two-way
  toggle (buttons literally labelled "EN SUITE" / "STUDIO") rather than
  both being in the DOM at once - `scrape_canvas()` scrapes the default
  view, clicks the "STUDIO" toggle, and scrapes again. Room cards use
  `data-automation="Floor-Room-Card-Title"` / `"...-Description"`
  (confirmed via a real diagnostic run) - more precise than the earlier
  generic "any £-containing span" scan, which occasionally snagged
  unrelated page content. Studio always returns all 3 tiers (Silver £270,
  Gold £297, Platinum £314). En-suite returns all 4 card slots
  (Bronze/Silver/Gold/Platinum), but Silver and Platinum's price field
  reads literally `"SOLD OUT"` instead of a price - confirmed directly (not
  inferred) via a targeted diagnostic run that dumped the exact card
  structure: Mark first reported these two as "missing" from a real
  scheduled run, and this is genuinely why - not a scraper miss. Since
  showing nothing for a real, named room tier looks exactly like a broken
  scraper, `scrape_canvas()` now records those two rooms anyway
  (`price_pw=None`, `offer_text="SOLD OUT"`) and `build_comparison()`
  (`scraper/compare.py`) surfaces any latest-run room with no price as a
  status-only row (blank price/deltas, no equivalent-room match) instead of
  silently dropping it - so the report will show "SILVER EN SUITE - SOLD
  OUT" rather than nothing at all. If Silver/Platinum come back in stock,
  they'll pick up real prices automatically on the next run.
- **St James (Abodus)**: now reliable, with real room-tier names. Previous
  sessions could never get real tier labels and saw the scoped-selector
  flakiness described below; the fix that resolved both problems at once
  was to stop trying to identify ladder items via DOM structure (headings,
  class names) and instead match each price's surrounding text against the
  real card copy pattern `"Available | {Room Name} | {description} |
  Prices from: £{price} P/W | View Room"` (or `"Limited Availability | ..."`
  for low-stock rooms). This is class-name-independent (survives Bricks'
  hashed-class churn - see below) and returns genuine names like "Classic
  En-suite" / "Deluxe Studio" directly from the page copy. It also cleanly
  excludes the page's hero teaser price and "similar properties" carousel
  (St James itself + other Abodus properties like Martha Street
  Apartments), which repeat the same `£X P/W` format but end in "View
  Property" instead of "View Room" and so never match the pattern.
  Confirmed via a real run: all 7 of Mark's listed tiers came back exactly
  (Classic/Premium/Superior En-suite, Classic/Premium/Deluxe/Superior
  Studio), no cross-sell contamination, no missing rows.
- **Bridle Works (Collegiate)**: no longer scraped - removed from
  `PROPERTIES` entirely at Mark's request (was previously kept as a
  placeholder "N/A - check manually" row because "Book my stay" redirects to
  a StarRez third-party booking portal that only reveals prices after a
  date-range search; Mark decided that wasn't worth carrying).

Prior sessions saw Abodus's price ladder disappear intermittently
(`div.brxe-tmqjgv`, a Bricks-builder auto-generated class, regenerates
between page loads/builds, and a purely structural "no heading nearby"
heuristic sometimes matched 0 real items and sometimes matched only the
cross-sell carousel). The content-pattern approach above sidesteps both
problems since it never depends on class names or DOM position - only on
the price's own surrounding text, which is stable page copy. If it ever
goes flaky again, that would point to a genuine server-side issue on
Abodus's end rather than our selector, since the current approach doesn't
share the previous approaches' failure modes.

## How the comparison math works (scraper/compare.py)

- `categorize(room_type)` - keyword heuristic (`studio`/`ensuite`/`twin`
  etc. in the name) mapping free-text room type names to a small set of
  broad categories, used to group comparable rooms across competitors.
- `build_comparison(history_rows)` - for the latest run, per (property,
  room_type): % vs the immediately preceding run, % vs the very first run
  ever recorded (baseline), and % vs **whichever St Mungo's room in the
  same broad category is closest in price right now** (not a blended
  average across all our own tiers - Mark's ground-truth room list showed
  every property has multiple price/quality tiers within "en-suite" and
  "studio", e.g. Bronze/Silver/Gold/Platinum or Classic/Premium/Superior/
  Deluxe depending on the site, and averaging them together was misleading
  when comparing a specific competitor tier). The matched St Mungo's room
  is surfaced in the report as a new "Equivalent St Mungo's room" column
  (`report_excel.py`), so it's visible which of our tiers each competitor
  room is actually being weighed against.
- Room types that stop appearing in a run (e.g. sold out) simply drop out of
  that run's comparison rather than showing stale data.

## Outstanding / not yet done

1. **Branch mismatch: resolved.** Merged via PR #1 onto the default branch.
2. **Ground-truth room type validation: done.** Mark's room list for St
   Mungo's, Canvas, and Abodus has been checked against real scrape output
   (see "Validation status per site" above) and all three parsers rewritten
   to match. Foundry Courtyard (Prestige) was untouched - Mark confirmed it
   already looked accurate.
3. **Canvas en-suite Silver/Platinum: resolved.** Mark reported these as
   missing from a real scheduled run after PR #1 merged. Root cause
   confirmed directly (not inferred): both cards render with a literal
   "SOLD OUT" price field on Canvas's own page, which `_price_from_text()`
   correctly failed to parse as a price, so the room silently dropped
   instead of showing as sold out. Fixed in `scrape_canvas()` and
   `build_comparison()` - see "Validation status per site" above. Fixed in
   the follow-up PR after PR #1, not PR #1 itself.
4. **Gmail/secrets setup**: done and confirmed working end-to-end (real
   email received with .xlsx attached) in an earlier session, before this
   session's parser fixes - worth a fresh manual trigger to confirm the new
   per-tier rows and "SOLD OUT" status rows render correctly in the actual
   emailed spreadsheet (this session validated the scrape/compare logic
   directly, not the full emailed report).
5. **Not started**: "Option B" from earlier discussion - a live workbook in
   OneDrive updated in place via Microsoft Graph API, instead of a
   committed file per run. Only worth revisiting if Mark asks for it later;
   requires an Azure app registration, more setup than the current
   approach.

## Useful commands for resuming

```bash
git clone <repo-url> St-Mungo-s   # or it may already be checked out
cd St-Mungo-s
git checkout claude/student-accommodation-access-5v5j44
git pull
python3 -m py_compile scraper/*.py run_pipeline.py   # quick syntax check
```

To manually trigger the real workflow from a session for testing (needs the
`mcp__github__actions_run_trigger` tool):
```
method: run_workflow, owner: markAitcheson, repo: St-Mungo-s,
workflow_id: comp-set-report.yml, ref: claude/student-accommodation-access-5v5j44
```
Then poll `GET https://api.github.com/repos/markAitcheson/St-Mungo-s/actions/runs?branch=claude/student-accommodation-access-5v5j44&per_page=1`
until `status: completed`, and read logs via `mcp__github__get_job_logs`
(job logs are often too large for the tool's inline output - it saves to a
file and tells you to read that file in chunks).
