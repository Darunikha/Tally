# Tally – Smart Bank Statement & UPI Spend Analyzer

Upload bank and credit card statements (CSV, Excel or PDF, including password-protected e-statements) from
different Indian banks. Tally parses them with bank-specific
adapters, recognises UPI merchants, categorises spending with a regex rule engine you control, flags
unusual activity, and turns everything into a dashboard.

It is **read-only**: it never connects to a bank, never stores bank credentials, never initiates payments,
and never sends statement data to external AI services.

| Layer    | Stack |
|----------|-------|
| Frontend | React 18 + Vite 5, Tailwind CSS 3, Recharts, Lucide icons, Axios |
| Backend  | FastAPI, Pydantic v2, Pandas, pdfplumber, openpyxl/xlrd, Motor (async MongoDB) |
| Database | MongoDB |
| Auth     | bcrypt password hashing + JWT bearer tokens |

---

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt      # or requirements.txt for runtime only
cp .env.example .env                     # then edit .env
```

In `.env`, set:

* `JWT_SECRET`: generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. The app refuses to start without a secret of at least 32 characters.
* `MONGODB_URL`: `mongodb://localhost:27017` or a MongoDB Atlas `mongodb+srv://…` URL.
  For a quick look without MongoDB, use `mongomock://`. That is an in-memory database and **all data is lost on restart**.

```bash
uvicorn app.main:app --reload --port 8000
```

Interactive API docs are at http://localhost:8000/api/docs.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api to http://127.0.0.1:8000)
```

Create an account. Then either upload a statement, or go to **Settings → Demo mode → Load demo data**
to import a bundled synthetic statement.

Production build: `npm run build`, which outputs `frontend/dist`. Serve it behind the same origin as the API, or
set `VITE_API_URL` at build time and add that origin to `CORS_ORIGINS` in the backend.

### 3. Tests

```bash
cd backend && python -m pytest        # 392 backend tests
cd frontend && npm test               # 229 frontend tests (Vitest + React Testing Library)
cd frontend && npm run coverage       # frontend coverage report → frontend/coverage/
```

**Backend.** These tests cover:
* CSV, Excel (.xlsx, .xls, HTML-.xls) and PDF parsing, including RC4/AES password-protected PDFs, and bank recognition
* Running-balance reconciliation for each bank
* UPI and merchant normalization, regex categorization, duplicate detection, anomaly rules and analytics math
* The full API: uploads, filters, rules, deletion and per-user isolation
* Budgets: status thresholds, projections, suggestions, validation and per-user isolation
* Credit cards: every issuer layout, purchase vs payment direction, detection that never claims a bank statement, and not double counting card payments
* Recurring payments: cadence and amount rules (including what must *not* be flagged), price changes, status, summary and the API
* Exports: CSV and Excel contents, formula-injection safety, filters, limits, privacy, and the PDF report (checked against the dashboard's numbers)
* Accounts: creating and filing statements, balances, per-account filtering that adds up to the combined totals, moving statements, automatic setup
* Onboarding: the checklist's steps follow real data, welcome and dismissal are remembered, and nothing is shown to people who already have data
* Learning: rule patterns that can't be widened or fooled, when a rule is (and isn't) offered, manual choices never overridden, and suggestions from repeated corrections
* Auth security: password reset, email verification, session revocation, rate limits and data export

**Frontend.** These tests cover:
* Formatting: Indian rupee grouping, IST greetings and dates
* API error handling
* UI components
* The sign-in, signup (consent), forgot/reset password and email verification pages
* The upload flow: file checks, the locked-PDF password prompt, duplicates and import
* Budgets: progress states, creating, editing and deleting, month navigation and the dashboard card
* Credit cards: the grouped format list, the card badge and note, and the dashboard note
* Recurring payments: summary, upcoming list, group and status filters, hiding and restoring
* Downloads: the export menu, the report button, filenames and readable errors
* Accounts: the Accounts page, choosing or creating an account while importing, moving statements, and the account filter
* Theme: light, dark and match-device, remembered in the browser; the chart colours that change with it
* First run: the welcome tour, the getting-started checklist, and the same "add your first statement" prompt on every analysis page
* Learning: the "remember this?" prompt, suggested rules, and sorting a whole merchant at once

The API is mocked, so frontend tests need no running server.

### 4. Continuous integration (GitHub Actions)

`.github/workflows/ci.yml` runs automatically on every push and pull request. It has two parallel jobs:

| Job | Steps |
|-----|-------|
| Backend (Python 3.12) | install `requirements-dev.txt` → regenerate the synthetic samples → `pytest` |
| Frontend (Node 22) | `npm ci` (exact lockfile versions) → `npm test` → `npm run build` |

No secrets are needed: tests use the in-memory database and an in-memory email outbox. Results appear in the repo's **Actions** tab and as ✅/❌ next to each commit.

To make CI actually block broken code:
* **Protect `main`:** go to GitHub → Settings → Branches → Add rule for `main` → tick *Require status checks to pass*, then select both CI jobs. Pull requests can then only be merged when CI is green.
* **Render:** in your service's settings, set Auto-Deploy to **"After CI checks pass"** so failing commits are never deployed.
* **Vercel:** it builds every push itself, and a failing build is never promoted. For a stricter gate, turn off auto-deploys and let CI trigger them.

### Windows note

Windows Smart App Control can block native binaries that have no reputation yet. This project already
works around the two blocks it hit:
* `numpy` is pinned to 2.1.3 in `requirements.txt`.
* Rollup is overridden to its WebAssembly build (`@rollup/wasm-node`) in `frontend/package.json`.

---

## Project structure

```
backend/
  app/
    main.py                 app factory: CORS, security headers, error handlers, routers
    core/                   settings (.env), bcrypt/JWT, redacting logger, error format
    database/mongo.py       Motor client, collection names, indexes
    models/documents.py     shape of every MongoDB document
    schemas/requests.py     Pydantic request validation
    parsers/
      base.py               BaseBankParser interface, StatementTable, ParsedTransaction
      readers.py            CSV/PDF → table (header detection, pdfplumber, PDF passwords, OCR, text-line fallback)
      excel.py              .xlsx / .xls / HTML-.xls / text-.xls → table (zip-bomb + row limits)
      adapters/banks.py     HDFC, ICICI, SBI, Axis, Kotak adapters + generic fallback
      adapters/cards.py     credit card adapters: HDFC, ICICI, SBI Card, Axis + generic card
      registry.py           bank identification and dispatch
    categorization/         default categories/rules + regex rule engine
    analytics/              pure calculation functions + insight generator
    anomaly_detection/      rule-based detectors
    (analytics/budgets.py   budget progress, projections and suggested limits)
    (analytics/recurring.py recurring payment detection)
    (services/exports.py    CSV and Excel export, services/report_pdf.py PDF report)
    (services/accounts.py   accounts: filing statements, balances, setup)
    (api/onboarding.py      first-run checklist progress)
    (services/learning.py   rules learned from your corrections)
    services/               file validation, normalization/dedupe, import pipeline, summaries, queries
    utils/                  UPI extraction, merchant normalization, payment methods, IST dates, money
    api/                    auth, statements, transactions, categories+rules, accounts, budgets, recurring, reports, analytics+UPI, anomalies, settings
  sample_data/              SYNTHETIC statements: 5 bank CSV layouts, unknown layout, .xlsx, .xls,
                            HTML-.xls, 2 PDFs, a password-locked PDF (password DEMO1234), 4 credit card
                            CSV layouts, an unknown-issuer card CSV and a card PDF + generator
  tests/
frontend/src/
  api/client.js             axios instance, auth header, error messages
  context/                  auth, global period/statement filter, toasts
  components/               layout (sidebar, top bar, period picker), UI kit, charts, transaction detail
  pages/                    Dashboard, Upload, Transactions, UPI, Analytics, Anomalies, Categories & Rules,
                            Accounts, Budgets, Recurring, Statement History, Settings, Login/Register
  context/ThemeContext.jsx  light / dark / match-device
  components/onboarding/    welcome tour, getting-started checklist, no-data prompt, demo-data button
  components/learning/      the "remember this?" prompt and the suggested-rules / needs-a-category lists
```

---

## How it works

### Import pipeline
```
upload → validate (extension, size, magic bytes) → read table (CSV / PDF tables / PDF text / OCR)
       → identify bank (adapters score headers + header text) → adapter maps columns & parses rows
       → normalize (payment method, UPI ID/ref/flow, merchant) → categorize (rules)
       → fingerprint & flag duplicates → STAGED preview
confirm → insert into raw_transactions (duplicates skipped) → refresh spending_summaries
```
* Uploaded files are **never kept** (`file_retained: false`). They are processed in memory; uploads over 1 MB are briefly spooled to an OS temp file by the web framework, which is deleted when the request ends.
* Nothing is imported until you confirm. Re-uploading an identical file is rejected. Overlapping
  statements are imported without double counting, using per-transaction fingerprints:
  date + amounts + normalized narration + balance, plus an occurrence counter for legitimately identical rows.
* Deleting a statement first marks it `deleting`, then removes its transactions, then the upload record, then refreshes
  summaries. Each step is idempotent, and interrupted deletions are finished automatically at startup.

### Supported file types
| File | How it's read |
|------|---------------|
| `.csv` | Any delimiter (`,` `;` tab `|`). Preamble lines before the header row are skipped automatically. |
| `.pdf` | Ruled tables via pdfplumber, with a plain-text line fallback. **Password-protected e-statements** (RC4 and AES-128/256) are supported: the upload page asks for the password, uses it once in memory, and never stores it. |
| `.xlsx` | openpyxl in read-only mode. Real date and number cells are handled, and every sheet is searched for the transaction table. |
| `.xls` | Real binary `.xls` files via xlrd. Many banks' "Excel" downloads are actually HTML tables or tab-separated text with an `.xls` extension, so those are detected by their content and handled too. |

Password-protected **Excel** files aren't supported. Users are told to save an unlocked copy, or to download a CSV or PDF instead.

### Credit card statements
Pick your card from the **Statement format** list, or leave it on auto-detect. HDFC, ICICI, SBI Card and Axis
statements are recognised automatically; any other issuer works through **Other credit card**.

A card statement reads differently from a bank statement, and Tally handles three things for you:

* **Direction.** A plain amount is a purchase (spending). A payment or refund is marked `Cr`/`C`, a `CR` flag column or a minus sign, and is read as a credit. There is no running balance on a card.
* **Detection is careful.** A file with only generic `Date / Details / Amount` headers and no issuer name is not guessed to be a card, because getting the sign wrong would turn every purchase into income. If a file looks like that, Tally warns you and asks you to pick the card from the list.
* **No double counting.** You pay your card from the bank, so that payment appears twice: as a debit in the bank statement and as a credit on the card. Both are filed under **Credit Card Payments**. Once you have imported a card statement, that category is left out of income and spending everywhere (dashboard, analytics, budgets, anomalies), because the card's own purchases are already counted. Until then, a card bill paid from the bank still counts as spending. They always remain visible on the Transactions page, and the dashboard says how many are left out.

Card merchants are cleaned of the trailing city and country (`SWIGGY BANGALORE IN` becomes **Swiggy**). Annual fees, finance charges and GST on a card are real charges and are filed under Bills & Utilities, not as card payments.

Accounts created before card support get the new category and rules added automatically on their next import (once, so changes you make later are never undone). Transactions you imported earlier keep their category until you run **Apply rules** on the Categories page.

### Adding a bank
Create a subclass of `BaseBankParser` in `parsers/adapters/banks.py`, declaring:
* `column_aliases`: canonical field → that bank's header names
* `signature_headers` and `text_markers`: used for detection
* optionally, a custom `extract_upi`

Add it to `BANK_PARSERS`. Nothing else changes. For a card issuer, subclass `CreditCardParser` in `adapters/cards.py` instead and add it to `CARD_PARSERS`. The adapters already cover the main layout styles:
* Separate debit and credit columns: HDFC, ICICI, SBI, Axis
* A single amount with a Dr/Cr flag: Kotak
* A signed single amount: generic

Unrecognized layouts fall back to the generic adapter, which uses fuzzy header matching. The original
row is always kept in `raw_bank_fields`.

### Categorization
Rules are regexes matched against `MERCHANT | DESCRIPTION`. They are evaluated in priority order (highest
first); on equal priority, your rules beat the defaults. A rule can apply to debits, credits or both.

* **Manual category changes are never overwritten.** "Apply rules" skips them, and "Let rules decide" on a
  transaction releases one.
* **Unmatched transactions go to "Other"** and are flagged for review.
* **Unsafe patterns are rejected.** User patterns are length-limited and nested quantifiers like `(a+)+` are refused.

### UPI intelligence
The parser handles these narration styles:
* `UPI-NAME-vpa@bank-IFSC-RRN-remark` (HDFC)
* `UPI/RRN/remark/vpa/bank` (ICICI; the VPA is trusted over the free-text remark)
* `TO TRANSFER-UPI/DR/RRN/NAME/BANK/vpa/…` (SBI)
* `UPI/P2M|P2A/RRN/Name/…` (Axis)
* `UPI/NAME/RRN/remark` (Kotak)

For each transaction it extracts the VPA, the 12-digit RRN, the flow (P2M/P2A) and the direction.
Merchant aliases group variants together, so `SWIGGY*ORDER123`, `UPI-SWIGGY`, `SWIGGY INDIA` and
`swiggy@icici` all become **Swiggy**.

### Learning from your corrections
Tally gets better at sorting your transactions as you correct it, but never silently: a rule is only created when you say yes, and it appears in **Categories & Rules** like any other rule, where you can edit, switch off or delete it.

* **Remember this?** When you move a transaction to another category, Tally offers to always file that merchant there. It says how many other transactions would move, and whether the rule applies to payments, money received, or both. Say yes and those transactions are re-sorted and future statements follow the rule.
* **Tally noticed a pattern.** If you keep moving the same merchant to the same category (twice or more), it shows up on the Categories page as a suggested rule. "Not now" hides that suggestion; moving the merchant somewhere else later is a new suggestion. Tally won't guess if you have moved a merchant to two places equally often.
* **Needs a category.** Merchants Tally could not place are grouped, so one choice sorts every transaction from that merchant and is remembered for the next statement.
* **Your word always wins.** A transaction you set by hand is never moved by a rule. A learned rule matches the merchant name exactly, so "Swiggy" doesn't catch "Swiggy Instamart" and a word in someone else's description never matches. Its priority is above every built-in rule, so what you teach beats the defaults.
* No rule is offered when the built-in rules already agree with you, or for a payee Tally could not read ("Unknown"), since that rule would catch unrelated payments.

### Anomalies
These are indicators for review, never fraud verdicts. Every baseline comes from your own history:

| Detector | Flags when… |
|----------|-------------|
| Unusually high amount | the amount is above Q3 + k·IQR of your debits (recurring payments like rent and SIPs are excluded), or above your own alert threshold |
| Higher than usual for the category | z-score against your earlier spending in that category |
| Repeated payments | 3 or more payments to the same merchant within 24 hours |
| Possible duplicate | same merchant, same amount, same day, same account |
| Unusual daily frequency | more transactions in a day than your mean + 3σ |
| Category spike | a month's category spend is more than 1.5× the average of the previous 3 months |

Sensitivity (low / medium / high) and the large-transaction alert are set in **Settings**. You can mark
anomalies as reviewed, dismiss them, or reopen them.

### Appearance
Choose **Light**, **Dark** or **Match device** from the moon/sun button in the top bar, or in Settings. The choice is kept in this browser only and applied before the page paints, so there is no flash of the wrong theme. Every colour comes from a small set of tokens defined in `src/index.css`, and the dark palette was checked for contrast (text at least 4.5:1, chart colours at least 3:1). Charts lighten their series colours on a dark background, and native controls such as date pickers follow the theme too.

### Getting started
A new account sees a short **welcome tour** once (three screens; skip it any time, and it never returns). Until the first statement is added, every analysis page shows the same prompt: upload a statement or try the demo data, so a new user is never shown an "all clear" for data that does not exist yet.

After the first statement, the Dashboard shows a **Get set up** checklist: add a statement, file it under an account, review uncategorised transactions, set a budget. The steps tick themselves from your real data, so there is nothing to mark by hand. Hide the checklist whenever you like; it also disappears once all four are done. Accounts that already have data are not shown the welcome tour.

### Accounts
An **account** is one bank account or credit card, such as "HDFC Savings", "SBI Salary" or "HDFC Card". Filing statements under accounts lets you see each account's balance and spending on its own, or everything together.

* **Filing a statement.** When you review an import, choose the account from the **Account** list or create one right there (named after the bank). If you have exactly one account of the same kind for that bank, Tally selects it for you. A card statement can only go into a credit card account, and a bank statement into a bank account.
* **Accounts page.** Each account shows its latest balance (and the date it is as of) and the money in and out in its most recent month with data. Credit cards show what was spent instead, since a card statement has no balance. The total across bank accounts adds each account's latest balance, so the dates can differ.
* **One account or all.** The account picker in the date selector narrows the Dashboard, Analytics, UPI, Anomalies, Transactions, exports and PDF report to one account. Per-account totals always add up to the combined total.
* **Moving and unfiling.** Change a statement's account any time in **Statement History**; its transactions move with it. Deleting an account never deletes data: its statements simply become unassigned.
* **Existing data.** Statements imported before accounts existed are unassigned. **Set up automatically** on the Accounts page creates one account per bank (and per credit card) and files them for you.
* **Budgets and recurring payments** always cover everything, since a budget applies to all your spending. Anomaly baselines come from the selected account's own history.
* Only the **last 4 digits** can be stored, to help you recognise an account. Never enter a full account or card number.

### Budgets
Set a monthly limit per category, plus an optional overall limit, on the **Budgets** page. Budgets are
per calendar month and compare against your debit transactions for that month:

| Status | Meaning |
|--------|---------|
| On track | below your alert level |
| Nearly there | at or above your alert level (50-100%, default 80%) |
| Over budget | spending is above the limit |

* The page opens on your latest month with data, and you can step back through earlier months.
* In the current month, once at least 7 days have passed, Tally projects where you'll finish and tells you if you're on pace to go over. It also shows roughly how much you can spend per day for the rest of the month.
* Suggested limits come from your average spending in the previous three months that had data.
* The dashboard shows the budgets that need the most attention for the month you're viewing.
* Deleting a category deletes its budget. Deleting your statements keeps your budgets.

### Recurring payments
The **Recurring** page lists subscriptions, bills, rent and SIPs that Tally finds in your own history, with what you
commit to each month and year, and what is due in the next 30 days.

A merchant is recurring when you pay it on a steady schedule **and** a steady amount:

| Pattern | Needs |
|---------|-------|
| Monthly | at least 3 payments, gaps of about a month (26-35 days, so weekends and short months don't matter) |
| Quarterly | at least 3 payments, about 3 months apart |
| Yearly | at least 2 payments, about a year apart |
| Weekly | at least 6 payments, a week apart |

* **Fixed amounts** (Netflix, rent) must match within 3%. **Varying bills** (electricity) are still found when the schedule is very regular and the amount stays within about 35%; they are shown with a `~`.
* **Price changes** are called out when the latest payment differs from the earlier ones (for example "Price up 23% (₹649 → ₹799)"), and the current price is the one shown.
* **Frequent but irregular spending is not reported.** Food delivery, cabs and shopping are paid often but not on a schedule, so they don't qualify. A fixed subscription hiding among a merchant's other purchases (an app store, say) is still found by its amount.
* **Not counted:** cash withdrawals and payments to your own credit cards.
* **Status** is judged as of your newest transaction, not today's date, so statements that are a few months old don't make everything look cancelled. A payment more than a short grace period overdue is shown as "Not seen lately" and left out of the totals.
* Anything that isn't really recurring can be hidden with **Not recurring**; hidden items leave the totals and can be restored from the **Hidden** list.

### Exports and reports
* **Transactions: CSV or Excel.** The **Export** menu on the Transactions page downloads *every* transaction that matches your current filters (not just the visible page), oldest first. Excel keeps real dates and numbers so you can sort and sum, and has an "About this export" sheet recording the filters used. Up to 50,000 rows per export; narrow the filters beyond that.
* **Spending report: PDF.** The **Report** button on the Dashboard and Analytics pages downloads a report for the chosen period (and statement): totals against the previous period, spending by category, top merchants, a month-by-month table for longer periods, and your budgets when a single month is selected. The numbers come from the same code as the dashboard, so they always agree. Amounts are written `Rs. 1,02,509` because the standard PDF fonts have no rupee sign.
* **Safe to open in a spreadsheet.** A payee can name themselves `=HYPERLINK(...)`, and a spreadsheet would run that as a formula (CSV injection). In CSV, any text starting with `=`, `+`, `-`, `@`, tab or carriage return is prefixed with an apostrophe; in Excel those cells are stored with an explicit text type. Nothing in an export can execute.
* Exports and reports are limited to 30 per hour per account. Files are generated on request and never stored.
* When the website and API are on different domains, the API exposes the `Content-Disposition` header so the browser can name the downloaded file.

### Data model (MongoDB)
`users`, `statement_uploads`, `raw_transactions`, `staged_transactions` (preview area), `categories`,
`categorization_rules`, `learning_dismissed` (suggested rules you said no to), `accounts` (your bank accounts and cards; statements and transactions carry the account they belong to),
`budgets` (one per user and category; no category means the overall budget),
`recurring_ignored` (merchants you marked as not recurring),
`spending_summaries` (cached monthly roll-ups, always rebuildable) and `anomaly_reviews`.
Every document carries `user_id`. Indexes cover date, upload, merchant, category, reference, and a
unique `(user_id, fingerprint)`.

Dates are statement calendar dates in Asia/Kolkata, stored as midnight with no UTC shift. Amounts are shown
in ₹ with Indian digit grouping.

---

## Accounts, email & legal

**Email** is used for verification links, password-reset links and "password changed" alerts. Set `EMAIL_PROVIDER` in `backend/.env`:

| Provider | Use for | Settings |
|----------|---------|----------|
| `console` | Local development. Emails, including their links, are printed in the backend terminal. Never sends in production. | none |
| `resend` | Production (resend.com has a free tier) | `RESEND_API_KEY`, and `EMAIL_FROM` on a domain you've verified with Resend |
| `smtp` | Any mail server (Gmail app password, Zoho, Amazon SES…) | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |

Also set `FRONTEND_URL` to your website's address so the links in emails point to the right place.

**How it works:**
* **Forgot password.** The user gets a one-time link that expires in 30 minutes. The response never reveals whether an email is registered.
  Only a SHA-256 hash of each link token is stored. Resetting the password signs the account out on every device.
* **Email verification.** A link is sent at signup, and the app shows a banner until the email is verified.
  Set `REQUIRE_EMAIL_VERIFICATION=true` to block uploads until the email is verified (recommended in production).
* **Sessions.** Changing your password signs out all other devices. Settings also has "Sign out everywhere".
* **Rate limits.** Counters are stored in MongoDB (hashed keys, auto-expiring), so they work across server instances:

  | Action | Limit |
  |---|---|
  | Login | 20 per 15 min per IP, and 8 per 15 min per email |
  | Signup | 5 per hour per IP |
  | Forgot password | 3 per hour per email |
  | Uploads | 60 per hour per user |
  | Exports and reports | 30 per hour per user |

  When a limit is hit, the API returns HTTP 429 with a `Retry-After` header. Behind a proxy (Render, Nginx), set `TRUST_PROXY_HEADERS=true` so the real client IP is used.

**Privacy Policy & Terms** are at `/privacy` and `/terms`. They're written around India's Digital Personal Data Protection Act, 2023:
notice, purpose, consent, user rights, a Grievance Officer, and the Data Protection Board.

* **Consent.** Signup requires ticking the consent box. The version accepted and the time are stored with the user.
* **Your rights in the app.** "Download my data" in Settings gives a full JSON export (right of access), and deleting your account covers erasure and withdrawal of consent.

⚠️ **Before going public:**
1. Fill in your details in `frontend/src/legal/config.js`. Until you do, the pages show a visible "template" notice.
2. Have the text reviewed by a lawyer.
3. When you change the text, bump `LEGAL_VERSION` in `backend/.env` and `version` in `config.js`.

## Security & privacy

* Uploads are treated as untrusted input:
  * Extension, MIME type and magic bytes are checked.
  * Size is limited (`MAX_UPLOAD_MB`) and the read itself is bounded.
  * PDFs are limited to 200 pages. Excel files get zip-bomb, sheet and row limits, and XML is parsed with defusedxml.
  * PDF passwords are used once in memory to unlock the file. They are never stored, logged or returned.
* Every query is scoped to the authenticated user. Search text is regex-escaped. IDs are validated.
* Passwords are hashed with bcrypt (12 rounds), and login responses take the same time whether or not an email exists.
* Logs never include descriptions, amounts or VPAs, and a redacting filter masks VPAs and long digit runs as a backstop.
* API responses send `Cache-Control: no-store`, `X-Frame-Options: DENY` and `nosniff`. CORS only allows the configured origins.
* Exported spreadsheets are safe to open: text that could run as a spreadsheet formula is neutralised (see Exports and reports).
* Secrets and the database URL come only from environment variables.
* The session token is kept in `sessionStorage`, so it is cleared when the tab closes.

## Scanned PDFs
Text PDFs and CSVs work out of the box. For scanned (image-only) PDFs, install the Tesseract binary and
`pip install pytesseract`, and Tally will OCR them automatically. Without it, users get a clear message
suggesting a CSV or text PDF instead.

## Sample data
Everything in `backend/sample_data/` is **synthetic** and generated by `generate_samples.py`. It contains no
real customer information. To regenerate it, run `python sample_data/generate_samples.py` (this needs `reportlab`, from the dev requirements).
