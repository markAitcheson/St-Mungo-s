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
`schedule` triggers, and `workflow_dispatch` *registration*, only ever work
from whatever branch is set as default - see "Environment quirk" below).

**Current status: working and validated.** Two PRs landed this session
(#1: branch mismatch + ground-truth room type fixes, #2: Canvas sold-out
handling), both merged to default, both confirmed against real scheduled
runs. See "Outstanding / not yet done" for what's actually still open -
it's short.

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
  why this goes through smtplib directly instead). Confirmed working
  end-to-end (real email received with .xlsx attached).
- **Data storage: a flat CSV** (`data/history.csv`, append-only, one row per
  room type per run) committed back into the repo by the workflow itself
  after each run. No external database.
- **Bridle Works (Collegiate) is out of the comp set entirely** - Mark
  decided it's too hard to scrape reliably ("Book my stay" redirects to a
  StarRez third-party booking portal that only reveals prices after a
  date-range search) and asked for it to be dropped rather than kept as a
  placeholder row.

## Environment quirk worth knowing

This Claude Code session's own outbound network is policy-restricted to an
allowlist (npm, PyPI, GitHub API, etc.) - it **cannot** directly fetch
arbitrary competitor websites (`curl`/WebFetch both get blocked/403'd).
GitHub Actions runners have no such restriction. The workaround used
throughout this project: push a small throwaway diagnostic
workflow+script, trigger it via `mcp__github__actions_run_trigger` (method
`run_workflow`), poll `https://api.github.com/repos/.../actions/runs/<id>`
until `status: completed`, then pull logs via `mcp__github__get_job_logs`.
This is how every real scraper selector in this repo was confirmed against
live pages rather than guessed. Re-use this pattern for any future site
inspection or debugging - it's reliable and fast (~1-2 min per run).

Important: `workflow_dispatch` **registration** only works for a workflow
file that exists on the **default branch** - pushing a diagnostic workflow
to a feature branch and trying to dispatch it will 404. This means
diagnostic pushes go directly to the default branch temporarily, then get
reverted with a follow-up commit once the finding is confirmed and applied
properly via a PR - don't leave throwaway `_diag_*` files sitting on
default. This repo has no branch protection, so direct pushes to default
are technically possible, but should stay strictly to this
push-diagnose-revert pattern; real changes always go through a PR.

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
.github/workflows/comp-set-report.yml   The real scheduled workflow (0 8,14 * * * UTC)
data/history.csv, data/latest_comp_set.xlsx   Committed by the workflow each run
README.md            Beginner-friendly GitHub setup instructions for Mark
```

## The comp set

| Property | URL | is_own | parser key |
|---|---|---|---|
| St Mungo's (Student Roost) - En-suite | https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-ensuite-st-mungos | True | `student_roost` |
| St Mungo's (Student Roost) - Studio | https://www.studentroost.co.uk/locations/glasgow/st-mungos?modal=rooms-studio-st-mungos | True | `student_roost` |
| St James (Abodus) | https://abodusstudents.com/accommodation/st-james-glasgow#the-rooms | False | `abodus` |
| Foundry Courtyard (Prestige) | https://prestigestudentliving.com/student-accommodation/glasgow/foundry-courtyard | False | `prestige` |
| Boyce House (Canvas) | https://www.canvas-world.com/en/locations/united-kingdom/glasgow/boyce-house#rooms | False | `canvas` |

Every parser has been validated against Mark's manually-supplied
ground-truth room type list, via real GitHub Actions diagnostic runs (not
guessed) - see below.

## Validation status per site

- **St Mungo's (own)**: reliable. The `?modal=...` URLs each open a modal
  (`[class*="modal" i], [role="dialog"]`) containing one price per room
  tier - a real per-tier breakdown, not a blended category price.
  En-suite: Bronze/Silver/Gold (3 tiers, matches Mark's list exactly - the
  modal also contains "upper floor" variants of each tier, which are
  deliberately filtered out in `scrape_student_roost()` since Mark's list
  doesn't want those tracked separately). Studio: Bronze/plain
  "Studio"/Silver/Gold/Platinum (5 tiers, exact match).
- **Prestige Foundry Courtyard**: reliable, untouched - Mark confirmed this
  one already looked accurate before any parser changes this session.
  `.RoomCard__inner` containers, 8-9 room types e.g. Bronze Plus Ensuite
  £175, Silver Ensuite £190, Gold Studio £285. Text pattern:
  `"Limited Availability {room name} {n} wks from £{price} pp/pw"`.
- **Canvas Boyce House**: reliable. En-suite and studio tiers sit behind a
  two-way toggle (buttons literally labelled "EN SUITE" / "STUDIO") rather
  than both being in the DOM at once - `scrape_canvas()` scrapes the
  default view, clicks "STUDIO", and scrapes again. Room cards use
  `data-automation="Floor-Room-Card-Title"` / `"...-Description"`. Returns
  all 4 en-suite tiers (Bronze/Silver/Gold/Platinum) and all 3 studio tiers
  (Silver/Gold/Platinum), matching Mark's list exactly. **Silver and
  Platinum en-suite are currently sold out** - Canvas's own page shows
  `"SOLD OUT"` instead of a price for those two, which `scrape_canvas()`
  now records as `price_pw=None, offer_text="SOLD OUT"` (rather than
  dropping the room, which previously made it look like a scraper bug -
  Mark flagged exactly this after the first fix). `build_comparison()`
  surfaces any latest-run room with no price as a status-only row (blank
  price/deltas, no equivalent-room match). Confirmed in a real scheduled
  run's `data/history.csv`: both rows present with empty `price_pw` and
  `offer_text=SOLD OUT`. They'll pick up real prices again automatically
  once back in stock.
- **St James (Abodus)**: reliable, with real room-tier names. Each price's
  surrounding text is matched against the real card copy pattern
  `"Available | {Room Name} | {description} | Prices from: £{price} P/W |
  View Room"` (or `"Limited Availability | ..."` for low-stock rooms) -
  this is class-name-independent, which matters because the page is built
  with Bricks page-builder, whose auto-generated class names (e.g.
  `brxe-tmqjgv`) regenerate between page loads/builds and previously made
  class-based or pure-DOM-structure selectors unreliable. Also cleanly
  excludes the page's hero teaser price and "similar properties" carousel
  (which repeat the same `£X P/W` format but end in "View Property"
  instead of "View Room"). Returns all 7 tiers matching Mark's list exactly
  (Classic/Premium/Superior En-suite, Classic/Premium/Deluxe/Superior
  Studio). If this ever goes flaky again, that would point to a genuine
  server-side issue on Abodus's end rather than the selector, since this
  approach doesn't share the old approaches' failure modes (class-name
  churn, ambiguous DOM structure).
- **Bridle Works (Collegiate)**: not scraped - removed from `PROPERTIES`
  entirely, see "Decisions already made" above.

## How the comparison math works (scraper/compare.py)

- `categorize(room_type)` - keyword heuristic (`studio`/`ensuite`/`twin`
  etc. in the name) mapping free-text room type names to a small set of
  broad categories, used to group comparable rooms across competitors.
- `build_comparison(history_rows)` - for the latest run, per (property,
  room_type): % vs the immediately preceding run, % vs the very first run
  ever recorded (baseline), and % vs **whichever St Mungo's room in the
  same broad category is the equivalent tier**, matched by name or
  hierarchy position - **never by price** (not a blended average across
  all our own tiers either - every property has multiple price/quality
  tiers within "en-suite" and "studio", e.g. Bronze/Silver/Gold/Platinum or
  Classic/Premium/Superior/Deluxe depending on the site, and averaging them
  together was misleading when comparing a specific competitor tier).
  `find_equivalent()` first tries a shared tier keyword (bronze/silver/
  gold/platinum - used by St Mungo's, Canvas and Prestige) so e.g. a
  competitor's "Silver Ensuite" matches our "En-suite silver" directly.
  When the competitor's tier names don't overlap with ours (e.g. Abodus's
  Classic/Premium/Superior/Deluxe), it falls back to the room's ordinal
  position within that competitor's own category, in the order their tiers
  appear in the source data, mapped proportionally onto our own tier
  ladder for that category - position in the hierarchy, not the price
  itself, decides the match. Price is only used afterwards, to compute the
  displayed % difference between the two now-matched rooms. The matched St
  Mungo's room is surfaced in the report as an "Equivalent St Mungo's room"
  column (`report_excel.py`), so it's visible which of our tiers each
  competitor room is actually being weighed against. That column is
  colour-coded red/green in `report_excel.py` too - red when the
  competitor is priced *below* St Mungo's, green when *above* (the
  opposite sense to the "vs last report"/"vs baseline" trend columns,
  which are red-up/green-down on our own price history, not a competitor
  comparison).
- Rooms present in the latest run with **no price** (e.g. sold out, like
  Canvas Silver/Platinum en-suite above) still get a row in the comparison
  output - price/deltas/equivalent-room are all blank, but the room stays
  visible with its `offer_text` (e.g. "SOLD OUT") rather than disappearing,
  which previously read as a scraper failure.
- Room types that stop appearing in a run **entirely** (not even a
  no-price row - the parser found nothing at all for that tier) still just
  drop out of that run's comparison, since there's nothing to show.

## Outstanding / not yet done

Everything major from this session is resolved and confirmed via real
scheduled runs, not just diagnostics. What's left:

1. **Full emailed report visual check**: the scrape/compare pipeline is
   confirmed correct via `data/history.csv` from real runs, but nobody has
   eyeballed the actual emailed `.xlsx` since the Canvas sold-out fix
   merged, to confirm "SOLD OUT" rows and the "Equivalent St Mungo's room"
   column render as expected in Excel (not just in the underlying data).
   Quick to check: trigger the workflow manually and open the attachment.
2. **Not started**: "Option B" from earlier discussion - a live workbook in
   OneDrive updated in place via Microsoft Graph API, instead of a
   committed file per run. Only worth revisiting if Mark asks for it later;
   requires an Azure app registration, more setup than the current
   approach.
3. **Watch for recurring sold-out swings**: if Canvas Silver/Platinum
   en-suite (or any other room) stays sold out indefinitely or flickers
   in/out a lot, that's just real-world inventory - no code change needed
   unless Mark asks for different handling (e.g. a "days sold out" stat).

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

For diagnosing a live site (the pattern used to confirm every selector
above): write a throwaway `scraper/_diag_<name>.py` script plus a matching
`.github/workflows/_diag-<name>.yml` (`workflow_dispatch` only), push both
**directly to the default branch** (feature branches can't register
`workflow_dispatch`), trigger via `run_workflow`, poll, read logs, then
revert the diagnostic push with a follow-up commit once you've confirmed
what you needed - real fixes land via a normal PR afterward, never by
leaving the diagnostic commits on default.
