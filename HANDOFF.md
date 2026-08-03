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

Mark has since supplied **room/type-specific URLs** (modal deep-links or
in-page anchors) in place of the plain overview pages the parsers were
originally built against:

| Property | URL | is_own | parser key |
|---|---|---|---|
| St Mungo's (Student Roost) - En-suite | https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-ensuite-st-mungos | True | `student_roost` |
| St Mungo's (Student Roost) - Studio | https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-studio-st-mungos | True | `student_roost` |
| St James (Abodus) | https://abodusstudents.com/accommodation/st-james-glasgow#the-rooms | False | `abodus` |
| Foundry Courtyard (Prestige) | https://prestigestudentliving.com/student-accommodation/glasgow/foundry-courtyard | False | `prestige` |
| Boyce House (Canvas) | https://www.canvas-world.com/en/locations/united-kingdom/glasgow/boyce-house#rooms | False | `canvas` |

**Important - not yet re-validated against these exact URLs.** Only the
URLs/config were updated so far (config.py + scrape.py + README), per Mark's
explicit instruction to pause there. The parsers (`scrape_student_roost`,
`scrape_canvas`) were built and confirmed against the old overview pages, not
these new ones. Before trusting real output:
- **St Mungo's**: the `?modal=rooms-ensuite-st-mungos` / `?modal=rooms-studio-st-mungos`
  query params presumably auto-open a modal for that specific room type on
  page load. Need to confirm (a) the modal actually opens from a fresh page
  load with no click needed (Playwright won't click anything), and (b)
  whether `.roomGroup-card` still matches inside the modal, or whether the
  background page's cards are still present underneath and would cause
  double-counting across the two new config rows.
- **Canvas**: Mark says the en-suite/studio toggle lives on this one page and
  the `#rooms` anchor doesn't switch it - it likely defaults to one type on
  load. The current parser walks *all* `£`-containing `<span>` leaves
  regardless of which toggle state is active, so it may only be capturing
  whichever type renders by default, silently missing the other. Needs a
  fresh diagnostic-workflow inspection to check whether both room types are
  in the DOM at once (hidden via CSS, in which case current parser is fine)
  or only one is rendered at a time (in which case the scraper needs to
  trigger the toggle click, which Playwright can do but the current code
  doesn't).
- **Abodus**: only the URL gained a `#the-rooms` fragment (same overview
  page, just a same-page anchor) - the existing flakiness described below is
  unrelated and still applies.

Use the diagnostic-workflow pattern above to re-inspect before assuming
anything changed/didn't change.

## Validation status per site (confirmed via real GitHub Actions runs, not guesses)

- **Student Roost (own)**: reliable. `.roomGroup-card` containers, e.g. "En-suite
  Rooms" £179/pw, "Studio Rooms" £209/pw. (A different card class,
  `.propertySmall-card`, links to *other* Student Roost buildings nearby -
  correctly excluded.)
- **Prestige Foundry Courtyard**: reliable. `.RoomCard__inner` containers, 8-9
  room types e.g. Bronze Plus Ensuite £175, Silver Ensuite £190, Gold Studio
  £285.
  Text pattern: `"Limited Availability {room name} {n} wks from £{price} pp/pw"`.
- **Canvas Boyce House**: reliable. No stable class names (Tailwind-generated
  hashes) - selector finds price-bearing `<span>` leaves and walks up to the
  nearest preceding heading (`h1-h5`) for the room type name, e.g. "BRONZE EN
  SUITE" £162, "GOLD EN SUITE" £188.
- **St James (Abodus)**: unreliable, and *not currently fixed* - see below.
- **Bridle Works (Collegiate)**: no longer scraped - removed from
  `PROPERTIES` entirely at Mark's request (was previously kept as a
  placeholder "N/A - check manually" row because "Book my stay" redirects to
  a StarRez third-party booking portal that only reveals prices after a
  date-range search; Mark decided that wasn't worth carrying).

### Open problem: Abodus St James is flaky

Across 4 real fetches in this session:
1. First diagnostic fetch: found the genuine 7-item price ladder (£175-£280,
   ascending) in `<b>` tags inside a `div.brxe-tmqjgv` (Bricks page-builder
   auto-generated class).
2. Production run: same unscoped selector also picked up **cross-sell
   carousel prices** for other Abodus properties (e.g. Martha Street
   Apartments' £199) mixed into the results - a real bug, fixed by scoping
   to `div.brxe-tmqjgv`.
3. Next run: the scoped selector matched **zero** elements (Bricks
   apparently regenerates its hashed class names between page loads/builds
   - not a stable selector).
4. Rewrote to a class-independent structural heuristic (real ladder items
   have no heading directly above them; both the hero teaser price and the
   cross-sell carousel do). Re-tested 3 more times (with/without scrolling,
   3s/8s waits): **all three found the same 5 cross-sell-only values, never
   the true ladder again.** No bot-check page text was detected
   (`contains_bot_check_wording: false`), and scrolling/waiting longer made
   no difference - so it isn't a lazy-load timing issue on our end.

Current best guess: Abodus's own pricing widget makes an async call that is
itself flaky/rate-limited server-side (possibly from repeated automated
requests off the same GitHub Actions IP range during this session's
testing). This is documented as a known limitation in README.md rather than
silently hidden. **Do not spend more effort tuning selectors on the
overview page** - if Mark supplies a specific St James room-type URL, try
that fresh instead; it may hit a different, more stable endpoint.

When Abodus *does* return data, room types are labelled "Room tier 1"
onward (price rank order) rather than real names, since names couldn't be
tied to prices confidently - price/% tracking is still accurate even with
placeholder labels.

## How the comparison math works (scraper/compare.py)

- `categorize(room_type)` - keyword heuristic (`studio`/`ensuite`/`twin`
  etc. in the name) mapping free-text room type names to a small set of
  categories, used to compare unlike room names across competitors.
- `build_comparison(history_rows)` - for the latest run, per (property,
  room_type): % vs the immediately preceding run, % vs the very first run
  ever recorded (baseline), and % vs St Mungo's own latest average price in
  the same category.
- Room types that stop appearing in a run (e.g. sold out) simply drop out of
  that run's comparison rather than showing stale data.

## Outstanding / not yet done

1. **Branch mismatch: resolved** - see "Branch mismatch (resolved)" section
   above. Once the merge PR lands on `claude/student-accommodation-access-5v5j44`,
   the default branch runs the new URLs/config on schedule/dispatch.
2. **Mark is providing ground-truth room type data manually** in the next
   session (his words: "I will provide all room types manually in the next
   chat context") - wait for that rather than guessing. Use it to check
   against real scrape output once running on the correct (merged) branch.
3. **Canvas parser needs fixing**: confirmed (not just theoretical) to be
   missing Studio rooms - only En-suite came back in the real run above.
   Needs a fresh diagnostic-workflow inspection of the live page to see
   whether Studio cards are in the DOM but hidden (fixable by adjusting the
   selector) or only rendered after a toggle click (needs Playwright to
   click it).
4. **Abodus still flaky**: missing entirely in the latest real run, matching
   prior sessions' findings. Not yet fixed - see "Open problem" section
   above. Now that the branch mismatch is resolved, worth trying the new
   `#the-rooms`-anchored URL fresh in case Mark's supplied ground truth
   suggests a different endpoint/approach.
5. **St Mungo's new modal URLs** (`?modal=rooms-ensuite-st-mungos` /
   `?modal=rooms-studio-st-mungos`): still completely untested (old run
   above used the old single overview URL, which happened to work fine).
   Re-validate now that the merge PR lands them on the default branch - see
   risks noted in "The comp set" section above (modal may not auto-open
   without a click; background page cards could cause double-counting
   across the two new config rows).
6. **Schedule times**: done. `.github/workflows/comp-set-report.yml` runs
   at `0 8 * * *` and `0 14 * * *` UTC (08:00/14:00 GMT) - now merged onto
   the default branch, so this takes effect once the merge PR lands.
7. **Gmail/secrets setup**: done and confirmed working end-to-end (real
   email received with .xlsx attached), on the default branch's old code.
8. **Not started**: "Option B" from earlier discussion - a live workbook in
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
