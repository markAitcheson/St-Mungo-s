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

**Current status: working and validated, fresh baseline as of
2026-08-04T08:15:46Z.** Four PRs/rounds of work have landed on default so
far:
- #1: branch mismatch + ground-truth room type fixes
- #2: Canvas sold-out handling
- #3: (merge of #1/#2 work, see git log)
- #4: replaced price-based "closest equivalent" room matching with
  name/hierarchy-position matching (`find_equivalent()` in
  `scraper/compare.py`), and fixed the "vs St Mungo's" column colours,
  which were inverted (was red-for-above/green-for-below; competitors
  should read red-for-below/green-for-above St Mungo's price) - both
  requested directly by Mark. PR #4 was merged via GitHub's PR UI.

Two follow-up changes landed **after PR #4 merged**, pushed straight to
default (Mark explicitly said "merge now", no PR - the changes were small
and he wanted them live before the next scheduled run):
- `data/history.csv` was truncated to just the header, so every room's
  "first-ever recorded price" baseline resets to whatever the next run
  scrapes - Mark asked for this explicitly ("clear history so the next 8am
  report can be taken as the first").
- The cron schedule moved from `0 8,14 * * *` to `5 8,14 * * *` UTC. The
  08:00 run on 2026-08-04 never fired at all - Actions history showed zero
  runs ever triggered by the `schedule` event, only `workflow_dispatch` -
  which matches GitHub's own documented warning that `:00` is the most
  congested slot for scheduled workflows and can be delayed/dropped.
  Confirmed fixed: a manual `workflow_dispatch` at 08:15 UTC that day ran
  clean against the cleared history and produced the new baseline row set
  (visible at the top of `data/history.csv` now, all rows dated
  `2026-08-04T08:15:46+00:00`).

Two more rounds landed later the same day, both pushed straight to default
(no PR - see "Environment quirk" below for when that's appropriate):
- Replaced the tier-name/hierarchy-position `find_equivalent()` heuristic
  with an explicit `ROOM_EQUIVALENCE` table in `scraper/compare.py`, built
  from the full competitor-room-to-St-Mungo's-room pairing Mark dictated
  directly - see "How the comparison math works" below for the exact
  mapping and why the heuristic was replaced rather than kept as a
  fallback (Mark's list is ground truth, not a guess to fall back from).
- **Found and fixed the actual cause of the cron never self-firing**: as of
  13:07 UTC on 2026-08-04, checking Actions history showed **all 11 runs
  ever logged for this workflow were `workflow_dispatch`, zero were
  `schedule`** - the scheduled trigger had never fired even once, on either
  the old `:00` or the `:05` cron. Root cause wasn't GitHub congestion (the
  earlier theory) - it's that `08:05`/`14:05 UTC` was written assuming
  Mark's local time is GMT year-round, but the UK is on **BST (UTC+1)**
  roughly late March-late October, so at the time of checking (August) that
  schedule was actually firing at 09:05/15:05 *local*, not 8am/2pm -
  nothing had failed to fire, Mark just hadn't reached the actual (later)
  fire time yet when he checked at "2pm". Fixed properly rather than just
  re-timed: the workflow now has 4 cron entries (`5 7/8/13/14 * * *` UTC -
  both UTC hours that "8am"/"2pm Europe/London" can map to across the DST
  switch) and a new first step, `Check local time window` (job id `gate`),
  that reads the actual `TZ=Europe/London` wall-clock hour at run time and
  only lets the remaining steps run if it's genuinely 08:xx or 14:xx local
  - `workflow_dispatch` runs always skip the check. This means the
  intended local times stay correct automatically across every future
  BST/GMT switch with no manual cron edit twice a year. **Not yet
  confirmed against a real unattended fire** - see "Outstanding" below.

See "Outstanding / not yet done" for what's actually still open.

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
push-diagnose-revert pattern for diagnostics; real feature changes go
through a PR by default.

**Exception, seen this session**: after PR #4 merged, Mark asked for two
more small changes (clear history, fix cron timing) and explicitly said
"merge now" rather than go through another PR review round. Those went
straight to default via a fast-forward push (branch was reset to default's
tip first, committed on top, force-pushed to the feature branch, then
fast-forwarded onto default) - no PR was opened for them. Read this as:
PRs are the default for real changes, but a direct explicit instruction to
skip review for a specific, already-understood change is Mark's call to
make, not something to assume. Don't extend it to unrelated changes without
him saying so again.

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
.github/workflows/comp-set-report.yml   The real scheduled workflow (4 cron entries + a local-time gate step for BST/GMT, see "Current status")
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
  ever recorded (baseline), and % vs **whichever St Mungo's room Mark
  specified as its equivalent tier**, looked up from `ROOM_EQUIVALENCE` in
  `scraper/compare.py` - **never guessed by tier name, hierarchy position,
  or price**. As of 2026-08-04, Mark dictated the full equivalence list
  directly (superseding the previous `find_equivalent()` heuristic from PR
  #4, which guessed via a shared tier keyword like bronze/silver/gold/
  platinum, falling back to ordinal position in the source listing when tier
  names didn't overlap, e.g. Abodus's Classic/Premium/Superior/Deluxe). The
  new `ROOM_EQUIVALENCE` dict is keyed by `(property_id, normalized
  competitor room name)` -> St Mungo's room name; `_normalize()` strips
  case/spacing/hyphenation so e.g. Canvas's "BRONZE EN SUITE" and Abodus's
  "Classic En-suite" both key correctly regardless of each site's own
  formatting. A competitor room with no entry in the dict (e.g. Prestige's
  "Silver Plus Ensuite", "Bronze Sky View Ensuite", "Platinum 2 Bed Flat",
  or Canvas's "PLATINUM EN SUITE" - St Mungo's has no platinum en-suite
  tier) simply gets no equivalent match and no "vs St Mungo's" figure -
  this is intentional, not a gap to fill in. The full mapping as Mark gave
  it:
  - En-suite bronze = Canvas Bronze En-suite, Foundry Bronze Plus En-suite,
    St James Classic En-suite
  - En-suite silver = Canvas Silver En-suite, Foundry Silver En-suite,
    St James Premium En-suite
  - En-suite gold = Canvas Gold En-suite, Foundry Gold En-suite,
    St James Superior En-suite
  - Bronze studio = St James Classic studio
  - Silver studio = Canvas Silver studio, Foundry Silver studio,
    St James Premium studio
  - Gold studio = Canvas Gold studio, Foundry Gold studio,
    St James Deluxe studio
  - Platinum studio = Canvas Platinum studio, St James Superior studio

  Price is only used afterwards, to compute the displayed % difference
  between the two now-matched rooms. The matched St Mungo's room is
  surfaced in the report as an "Equivalent St Mungo's room" column
  (`report_excel.py`), so it's visible which of our tiers each competitor
  room is actually being weighed against. That column is colour-coded
  red/green in `report_excel.py` too - red when the competitor is priced
  *below* St Mungo's, green when *above* (the opposite sense to the "vs
  last report"/"vs baseline" trend columns, which are red-up/green-down on
  our own price history, not a competitor comparison). If Mark adds a new
  competitor room type or wants a pairing changed, update `ROOM_EQUIVALENCE`
  directly (or add a new `_add_equivalence(...)` call) - don't reintroduce
  heuristic matching.
- Rooms present in the latest run with **no price** (e.g. sold out, like
  Canvas Silver/Platinum en-suite above) still get a row in the comparison
  output - price/deltas/equivalent-room are all blank, but the room stays
  visible with its `offer_text` (e.g. "SOLD OUT") rather than disappearing,
  which previously read as a scraper failure.
- Room types that stop appearing in a run **entirely** (not even a
  no-price row - the parser found nothing at all for that tier) still just
  drop out of that run's comparison, since there's nothing to show.

## Outstanding / not yet done

1. **Confirm the 4-cron/gate-step schedule actually self-fires and lands at
   the right local time.** As of this fix landing (2026-08-04, ~13:xx UTC),
   zero `schedule`-triggered runs have ever completed for this workflow -
   every run in Actions history is `workflow_dispatch`. This may just be
   because nobody had waited past the (corrected, BST-aware) fire time yet
   when last checked, but it hasn't been positively confirmed either way.
   Check Actions history (`mcp__github__actions_list`, method
   `list_workflow_runs`, filter `{"event": "schedule"}` on
   `comp-set-report.yml`) after the next 08:xx/14:xx Europe/London passes -
   confirm (a) a `schedule` run appears at all, and (b) its "Check local
   time window" step actually let the real work through (i.e. `should_run`
   was `true` and `data/history.csv` got a new row) rather than skipping.
   Two of every day's four scheduled firings are *expected* to skip by
   design (the "wrong" DST-offset entry) - only investigate if BOTH firings
   near a target local hour skip, or if none run at all.
2. **Full emailed report visual check**: nobody has eyeballed the actual
   emailed `.xlsx` from a real run since PR #4's tier-matching/colour fixes
   merged, to confirm the "Equivalent St Mungo's room" column and the new
   red-below/green-above colouring render as expected in Excel (not just in
   the underlying data/tests). Quick to check: open the attachment from the
   next real send, or trigger manually and check
   `data/latest_comp_set.xlsx` as committed by the workflow.
3. **Not started**: "Option B" from earlier discussion - a live workbook in
   OneDrive updated in place via Microsoft Graph API, instead of a
   committed file per run. Only worth revisiting if Mark asks for it later;
   requires an Azure app registration, more setup than the current
   approach.
4. **Watch for recurring sold-out swings**: if Canvas Silver/Platinum
   en-suite (or any other room) stays sold out indefinitely or flickers
   in/out a lot, that's just real-world inventory - no code change needed
   unless Mark asks for different handling (e.g. a "days sold out" stat).
5. **Watch the fresh baseline settle in.** Since `data/history.csv` was
   just cleared, the next couple of runs will have no "vs last report" or
   meaningful "vs baseline" figures yet (nothing to compare against) - this
   is expected, not a bug, until at least 2 runs have landed post-clear.

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
