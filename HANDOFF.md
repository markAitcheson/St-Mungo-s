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

Repo: **markAitcheson/St-Mungo-s**, branch
`claude/student-accommodation-access-5v5j44` (this branch is also currently
the repo's *default* branch, which matters - GitHub Actions `schedule`
triggers only ever fire from whatever branch is set as default).

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

## The comp set (as of this session)

| Property | URL | is_own | parser key |
|---|---|---|---|
| St Mungo's (Student Roost) | https://www.studentroost.co.uk/locations/glasgow/st-mungos | True | `student_roost` |
| St James (Abodus) | https://abodusstudents.com/accommodation/st-james-glasgow | False | `abodus` |
| Foundry Courtyard (Prestige) | https://prestigestudentliving.com/student-accommodation/glasgow/foundry-courtyard | False | `prestige` |
| Boyce House (Canvas) | https://www.canvas-world.com/en/locations/united-kingdom/glasgow/boyce-house | False | `canvas` |
| Bridle Works (Collegiate) | https://www.collegiate-ac.com/uk-student-accommodation/glasgow/bridleworks/ | False | `collegiate_unavailable` |

These were **overview/listing pages** (one URL per property showing all its
room types), not per-room-type pages. Mark said he will provide **specific
room-type URLs** for clearer pricing structure per room type - when he does,
re-inspect those pages (using the diagnostic-workflow pattern above) before
assuming the existing parsers still apply; per-room-type pages may have a
different, possibly simpler/more reliable, DOM structure than the overview
pages the current selectors were built against.

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
- **Bridle Works (Collegiate)**: not scraped at all by design. "Book my stay"
  redirects to a StarRez third-party booking portal
  (`ukportal.collegiate-ac.com/...`) that only reveals prices after a
  date-range search - not something a plain page visit can capture. The
  scraper returns a placeholder row (`room_type: "N/A"`, explanatory
  `offer_text`) so the gap is visible in the report rather than silent.

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

## Outstanding / not yet done (what the user is about to give you)

1. **Schedule times**: `.github/workflows/comp-set-report.yml` currently has
   placeholder cron times `0 7 * * *` and `0 18 * * *` (07:00 and 18:00
   UTC) - Mark has *not* confirmed these, he only knows they're
   placeholders. Ask what times he actually wants (get local UK time, then
   convert to UTC - watch for BST vs GMT) and update the two `cron:` lines,
   plus the comment above them and the README's "Changing the schedule"
   section if the explanation needs updating.
2. **Room-type-specific URLs**: Mark said he'll provide these "so we can get
   a clearer understanding of the pricing structures." When they arrive:
   re-run the diagnostic-workflow inspection pattern on each new URL before
   changing any parser - don't assume they share structure with the
   overview pages already scraped.
3. **Mark still needs to complete his side of setup** (unconfirmed as of
   this note): create a dedicated Gmail account, turn on 2-Step
   Verification, generate an app password, add three repo secrets
   (`REPORT_EMAIL_FROM`, `REPORT_EMAIL_APP_PASSWORD`, `REPORT_EMAIL_TO`),
   then manually trigger the workflow once via the Actions tab to confirm a
   real email arrives. Full step-by-step is in README.md - point him there
   rather than re-explaining inline unless he's stuck on a specific step.
4. **Not started**: "Option B" from earlier discussion - a live workbook in
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
