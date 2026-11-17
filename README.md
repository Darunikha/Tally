# Tally – Smart Bank Statement & UPI Spend Analyzer

Upload bank statements (CSV, Excel or PDF, including password-protected e-statements) from different
Indian banks. Tally parses them with bank-specific
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
cd backend
python -m pytest
```

There are 135 tests covering:
* CSV, Excel (.xlsx, .xls, HTML-.xls) and PDF parsing, incl. RC4/AES password-protected PDFs, and bank recognition
* Running-balance reconciliation for each bank
* Transaction, UPI and merchant normalization
* Regex categorization, priorities and manual overrides
* Duplicate detection, anomaly rules and analytics math
* The full API: auth, uploads, filters, rules, deletion and per-user isolation

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
      registry.py           bank identification and dispatch
    categorization/         default categories/rules + regex rule engine
    analytics/              pure calculation functions + insight generator
    anomaly_detection/      rule-based detectors
    services/               file validation, normalization/dedupe, import pipeline, summaries, queries
    utils/                  UPI extraction, merchant normalization, payment methods, IST dates, money
    api/                    auth, statements, transactions, categories+rules, analytics+UPI, anomalies, settings
  sample_data/              SYNTHETIC statements: 5 bank CSV layouts, unknown layout, .xlsx, .xls,
                            HTML-.xls, 2 PDFs, a password-locked PDF (password DEMO1234) + generator
  tests/
frontend/src/
  api/client.js             axios instance, auth header, error messages
  context/                  auth, global period/statement filter, toasts
  components/               layout (sidebar, top bar, period picker), UI kit, charts, transaction detail
  pages/                    Dashboard, Upload, Transactions, UPI, Analytics, Anomalies, Categories & Rules,
                            Statement History, Settings, Login/Register
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
* Files are processed **in memory** and never written to disk or the database (`file_retained: false`).
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

### Adding a bank
Create a subclass of `BaseBankParser` in `parsers/adapters/banks.py`, declaring:
* `column_aliases`: canonical field → that bank's header names
* `signature_headers` and `text_markers`: used for detection
* optionally, a custom `extract_upi`

Add it to `BANK_PARSERS`. Nothing else changes. The adapters already cover the main layout styles:
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

### Data model (MongoDB)
`users`, `statement_uploads`, `raw_transactions`, `staged_transactions` (preview area), `categories`,
`categorization_rules`, `spending_summaries` (cached monthly roll-ups, always rebuildable) and `anomaly_reviews`.
Every document carries `user_id`. Indexes cover date, upload, merchant, category, reference, and a
unique `(user_id, fingerprint)`.

Dates are statement calendar dates in Asia/Kolkata, stored as midnight with no UTC shift. Amounts are shown
in ₹ with Indian digit grouping.

---

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
* Secrets and the database URL come only from environment variables.
* The session token is kept in `sessionStorage`, so it is cleared when the tab closes.

## Scanned PDFs
Text PDFs and CSVs work out of the box. For scanned (image-only) PDFs, install the Tesseract binary and
`pip install pytesseract`, and Tally will OCR them automatically. Without it, users get a clear message
suggesting a CSV or text PDF instead.

## Sample data
Everything in `backend/sample_data/` is **synthetic** and generated by `generate_samples.py`. It contains no
real customer information. To regenerate it, run `python sample_data/generate_samples.py` (this needs `reportlab`, from the dev requirements).
