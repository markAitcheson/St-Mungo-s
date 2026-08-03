# Glasgow comp set report

Twice a day, this repo automatically:

1. Visits St Mungo's own pricing page and three local competitors
2. Records every room type's price and any live offer
3. Builds an Excel report comparing today's prices side by side, with the
   % change since the last report and since the very first time each room
   type was recorded, plus how each competitor compares to our own price
4. Emails that report to you

It runs on **GitHub Actions** - GitHub's free "run this code on a schedule"
service - so it works even if your laptop is off. Nothing needs to run
locally.

You don't need to know how to code to set this up. Follow the steps below in
order. It should take about 15 minutes.

---

## Step 1: Create a Gmail account to send the reports from

Reports are sent from a dedicated Gmail account (not your personal one) so
its password never touches your main account.

1. Go to [accounts.google.com/signup](https://accounts.google.com/signup)
   and create a new Gmail account, e.g. `stmungoscompset@gmail.com`.
2. Once it's created and you're logged in, turn on **2-Step Verification**
   (required before Google will let you create an "app password"):
   - Go to [myaccount.google.com/security](https://myaccount.google.com/security)
   - Under "How you sign in to Google", click **2-Step Verification** and
     follow the prompts (you'll verify with your phone number).
3. Now create an **app password** - a special password just for this
   script, separate from your login password:
   - Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Under "App name", type something like `Comp set report` and click
     **Create**.
   - Google will show you a **16-character password** (like `abcd efgh
     ijkl mnop`). Copy it somewhere safe - you'll paste it into GitHub in
     Step 3. You won't be able to see it again after you close this screen.

---

## Step 2: Find this repository on GitHub

1. Go to [github.com/markAitcheson/St-Mungo-s](https://github.com/markAitcheson/St-Mungo-s)
   and sign in if you're not already.
2. You should see the files this session created: `scraper/`,
   `run_pipeline.py`, `.github/workflows/comp-set-report.yml`, etc.

---

## Step 3: Add your email details as "secrets"

Secrets are private values (like passwords) that GitHub Actions can use
without ever showing them in logs or to anyone browsing the repo.

1. On the repository page, click **Settings** (top menu bar).
2. In the left sidebar, click **Secrets and variables** → **Actions**.
3. Click the green **New repository secret** button. Create each of these
   three, one at a time (click **New repository secret** again for each):

   | Secret name | Value |
   |---|---|
   | `REPORT_EMAIL_FROM` | The Gmail address you created in Step 1, e.g. `stmungoscompset@gmail.com` |
   | `REPORT_EMAIL_APP_PASSWORD` | The 16-character app password from Step 1 (remove the spaces) |
   | `REPORT_EMAIL_TO` | The inbox that should receive reports, e.g. `markaitcheson@icloud.com` |

   For each one: type the **Name** exactly as shown (case-sensitive), paste
   the **Value**, then click **Add secret**.

---

## Step 4: Run it once manually to check it works

Don't wait for the schedule - test it now:

1. On the repository page, click the **Actions** tab (top menu bar).
2. In the left sidebar, click **Glasgow comp set report**.
3. Click the **Run workflow** dropdown button (top right of the run list),
   make sure the branch shown is correct, then click the green **Run
   workflow** button.
4. Refresh the page after a few seconds - you'll see a new run appear with a
   yellow dot (in progress). Click it to watch the steps run live. It takes
   roughly 2-3 minutes (installing a browser, visiting each site, building
   the spreadsheet, sending the email).
5. When it finishes with a green tick, check the inbox from
   `REPORT_EMAIL_TO` - the report email should have arrived, with the
   `.xlsx` file attached.
6. If it fails (red cross), click into the run, click the `run-report` job,
   and read the red-highlighted step - see **Troubleshooting** below.

Once step 4 succeeds, you're done - it will now run automatically at 08:00
and 14:00 GMT every day without you doing anything.

---

## What you'll receive

- **Email**: a short summary of the biggest price movers since the last
  report, with the full spreadsheet attached.
- **Spreadsheet** (`data/latest_comp_set.xlsx`, also committed into the
  repo's `data/` folder each run so you always have the latest version
  there too):
  - **"Latest comp set" sheet** - every room type at every property, its
    current price, current offer, % change vs the last report (red = went
    up, green = went down), % change vs the very first price ever recorded,
    which St Mungo's room it's closest to in price (e.g. a competitor's
    "Premium En-suite" might line up with our "En-suite Silver"), and % vs
    that equivalent room.
  - **"History" sheet** - every price ever recorded, for building your own
    charts/pivot tables (this is the sheet to open with the Claude for Excel
    extension for trend analysis).

---

## Known limitations (please read)

- **Canvas (Boyce House) en-suite rooms**: Silver and Platinum en-suite are
  currently sold out on Canvas's own site (their page shows "SOLD OUT"
  instead of a price) - the report now shows them with an empty price and
  a "SOLD OUT" note instead of leaving them off entirely, so you can see
  they exist without them affecting the price comparisons. They'll pick up
  real prices again automatically once back in stock.
- Any competitor can redesign their website at any time, which may break
  its scraper. When that happens the report will show a "SCRAPE ERROR" row
  for that property instead of a wrong price - if you see one, let me know
  and I'll fix the selector.

---

## Changing things later

- **Add or remove a competitor**: edit `scraper/config.py` (the `PROPERTIES`
  list) and add a matching parser function to `scraper/scrape.py`. Easiest
  to just ask me to do it with the new URL.
- **Change the schedule**: edit the two `cron:` lines in
  `.github/workflows/comp-set-report.yml`. Times are UTC - use
  [crontab.guru](https://crontab.guru) to build a schedule, format is
  `minute hour * * *`.
- **Change who receives the report**: update the `REPORT_EMAIL_TO` secret in
  Step 3.

---

## Troubleshooting

- **Run failed at "Install dependencies"**: usually a temporary network
  blip - click **Re-run all jobs** on the failed run.
- **Run failed at "Run pipeline" with a KeyError about REPORT_EMAIL_...**:
  a secret name was typed slightly wrong in Step 3 - secret names are
  case-sensitive and must match exactly (`REPORT_EMAIL_FROM`,
  `REPORT_EMAIL_APP_PASSWORD`, `REPORT_EMAIL_TO`).
- **Run failed at "Run pipeline" with an SMTP authentication error**: the
  app password wasn't copied correctly (remove any spaces), or 2-Step
  Verification isn't actually turned on for the sending Gmail account.
- **Run succeeded but no email arrived**: check the sending Gmail account's
  Sent folder to confirm it left, and check spam in the receiving inbox.
- **A specific property always shows "SCRAPE ERROR"**: that site likely
  changed its page layout. Come back and ask me to fix the selector for
  that property - I'll re-inspect the live page and update
  `scraper/scrape.py`.
