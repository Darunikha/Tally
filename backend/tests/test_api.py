"""End-to-end API tests against an in-memory MongoDB."""
from tests.conftest import register


async def upload(client, auth, content, name="hdfc_statement.csv", ctype="text/csv"):
    return await client.post("/api/statements/preview", headers=auth, files={"file": (name, content, ctype)})


async def import_file(client, auth, content, name="hdfc_statement.csv"):
    r = await upload(client, auth, content, name)
    assert r.status_code == 201, r.text
    up = r.json()["upload"]
    r = await client.post(f"/api/statements/{up['id']}/confirm", headers=auth, json={})
    assert r.status_code == 200, r.text
    return r.json()


async def test_auth_flow(client):
    r = await client.post("/api/auth/register", json={"email": "a@b.com", "password": "short", "full_name": "A",
                                                       "accept_terms": True})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    headers = await register(client, "a@b.com")
    r = await client.post("/api/auth/register", json={"email": "a@b.com", "password": "secret123", "full_name": "A",
                                                       "accept_terms": True})
    assert r.status_code == 409
    assert (await client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong123"})).status_code == 401
    r = await client.post("/api/auth/login", json={"email": "A@B.com", "password": "secret123"})
    assert r.status_code == 200
    me = (await client.get("/api/auth/me", headers=headers)).json()
    assert me["email"] == "a@b.com" and "password_hash" not in me
    assert (await client.get("/api/transactions")).status_code == 401
    assert (await client.get("/api/transactions", headers={"Authorization": "Bearer junk"})).status_code == 401


async def test_seeded_categories_and_rules(client, auth):
    cats = (await client.get("/api/categories", headers=auth)).json()
    assert len(cats) == 17 and {"Food & Dining", "Other", "Income", "Credit Card Payments"} <= {c["name"] for c in cats}
    rules = (await client.get("/api/rules", headers=auth)).json()
    assert len(rules) > 15 and rules[0]["priority"] >= rules[-1]["priority"]


async def test_upload_preview_confirm_and_duplicate_detection(client, auth, sample):
    content = sample("hdfc_statement.csv")
    r = await upload(client, auth, content)
    assert r.status_code == 201
    body = r.json()
    assert body["upload"]["bank_name"] == "HDFC Bank" and body["upload"]["processing_status"] == "pending_review"
    assert body["upload"]["parsed_count"] == 133 and body["new_count"] == 133
    t0 = body["transactions"][0]
    assert t0["category_name"] and "fingerprint" not in t0

    # nothing imported until confirmation
    assert (await client.get("/api/transactions", headers=auth)).json()["total"] == 0
    up = (await client.post(f"/api/statements/{body['upload']['id']}/confirm", headers=auth, json={})).json()
    assert up["processing_status"] == "completed" and up["transaction_count"] == 133

    # same file again -> rejected as already imported
    r = await upload(client, auth, content)
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_statement"

    # overlapping file (same rows, different bytes) -> rows detected as duplicates
    overlapping = content.replace(b"Account Holder: DEMO USER", b"Account Holder: DEMO USER (copy)")
    r = await upload(client, auth, overlapping, "hdfc_copy.csv")
    assert r.status_code == 201 and r.json()["new_count"] == 0 and r.json()["upload"]["duplicate_count"] == 133
    up2 = (await client.post(f"/api/statements/{r.json()['upload']['id']}/confirm", headers=auth, json={})).json()
    assert up2["transaction_count"] == 0
    assert (await client.get("/api/transactions", headers=auth)).json()["total"] == 133


async def test_upload_validation(client, auth):
    r = await upload(client, auth, b"not,a,statement", "evil.exe", "application/octet-stream")
    assert r.status_code == 415
    r = await upload(client, auth, b"hello", "fake.pdf", "application/pdf")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_file"
    r = await upload(client, auth, b"PK\x03\x04zipdata", "x.csv")
    assert r.status_code == 400
    r = await upload(client, auth, b"a,b\n1,2\n", "random.csv")
    assert r.status_code == 422 and r.json()["error"]["code"] == "parse_error"
    hist = (await client.get("/api/statements", headers=auth)).json()
    assert hist[0]["processing_status"] == "failed"


async def test_pdf_upload(client, auth, sample):
    r = await upload(client, auth, sample("sbi_statement.pdf"), "sbi.pdf", "application/pdf")
    assert r.status_code == 201 and r.json()["upload"]["bank_name"] == "State Bank of India"


async def test_cancel_preview(client, auth, sample):
    r = await upload(client, auth, sample("axis_statement.csv"), "axis.csv")
    uid = r.json()["upload"]["id"]
    assert (await client.delete(f"/api/statements/{uid}/preview", headers=auth)).status_code == 204
    assert (await client.get(f"/api/statements/{uid}", headers=auth)).status_code == 404


async def test_transactions_filters_sort_edit(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    cats = {c["name"]: c["id"] for c in (await client.get("/api/categories", headers=auth)).json()}

    r = (await client.get("/api/transactions", headers=auth, params={"search": "swiggy", "page_size": 200})).json()
    assert r["total"] > 0 and all(t["normalized_merchant"] == "Swiggy" for t in r["items"])
    r = (await client.get("/api/transactions", headers=auth, params={"type": "credit", "page_size": 200})).json()
    assert all(t["transaction_type"] == "credit" for t in r["items"])
    r = (await client.get("/api/transactions", headers=auth, params={"category_id": cats["Food & Dining"]})).json()
    assert r["total"] > 0 and all(t["category_name"] == "Food & Dining" for t in r["items"])
    r = (await client.get("/api/transactions", headers=auth, params={"sort": "amount", "order": "desc"})).json()
    amounts = [t["amount"] for t in r["items"]]
    assert amounts == sorted(amounts, reverse=True) and amounts[0] == 85000
    r = (await client.get("/api/transactions", headers=auth, params={"start": "2025-10-01", "end": "2025-10-31", "page_size": 200})).json()
    assert all(t["transaction_date"].startswith("2025-10") for t in r["items"])
    r = (await client.get("/api/transactions", headers=auth, params={"payment_method": "UPI", "page": 2, "page_size": 10})).json()
    assert r["page"] == 2 and len(r["items"]) == 10 and all(t["payment_method"] == "UPI" for t in r["items"])

    # manual override + notes
    swiggy = (await client.get("/api/transactions", headers=auth, params={"search": "swiggy"})).json()["items"][0]
    r = await client.patch(f"/api/transactions/{swiggy['id']}", headers=auth,
                           json={"category_id": cats["Entertainment"], "notes": "team treat"})
    assert r.json()["category_name"] == "Entertainment" and r.json()["manual_override"] and r.json()["notes"] == "team treat"
    # re-applying rules must not override manual choices
    await client.post("/api/rules/apply", headers=auth)
    t = (await client.get(f"/api/transactions/{swiggy['id']}", headers=auth)).json()
    assert t["category_name"] == "Entertainment"
    # reset -> rules decide again
    t = (await client.patch(f"/api/transactions/{swiggy['id']}", headers=auth, json={"reset_category": True})).json()
    assert t["category_name"] == "Food & Dining" and not t["manual_override"]

    export = await client.get("/api/transactions/export", headers=auth, params={"type": "credit"})
    assert export.status_code == 200 and export.text.startswith("Date,Merchant")


async def test_custom_rules_and_categories(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    r = await client.post("/api/categories", headers=auth, json={"name": "Chai", "color": "#AA5500"})
    chai = r.json()["id"]
    assert (await client.post("/api/categories", headers=auth, json={"name": "Chai"})).status_code == 409
    assert (await client.post("/api/rules", headers=auth, json={"rule_name": "bad", "regex_pattern": "(a+)+",
                                                               "category_id": chai})).status_code == 400
    test = (await client.post("/api/rules/test", headers=auth, json={"regex_pattern": "RAMESH"})).json()
    assert test["match_count"] > 0
    r = await client.post("/api/rules", headers=auth, json={"rule_name": "Tea stall", "regex_pattern": "RAMESH TEA",
                                                            "category_id": chai, "priority": 200, "applies_to": "debit"})
    assert r.status_code == 201
    applied = (await client.post("/api/rules/apply", headers=auth)).json()
    assert applied["recategorized"] == test["match_count"]
    txns = (await client.get("/api/transactions", headers=auth, params={"category_id": chai, "page_size": 200})).json()
    assert txns["total"] == test["match_count"]

    # disable rule -> back to defaults after re-apply
    await client.patch(f"/api/rules/{r.json()['id']}", headers=auth, json={"enabled": False})
    await client.post("/api/rules/apply", headers=auth)
    assert (await client.get("/api/transactions", headers=auth, params={"category_id": chai})).json()["total"] == 0

    # rename / recolor / delete category
    assert (await client.patch(f"/api/categories/{chai}", headers=auth, json={"name": "Tea", "color": "#000000"})).json()["name"] == "Tea"
    other = next(c for c in (await client.get("/api/categories", headers=auth)).json() if c["name"] == "Other")
    assert (await client.delete(f"/api/categories/{other['id']}", headers=auth)).status_code == 400
    assert (await client.delete(f"/api/categories/{chai}", headers=auth)).status_code == 200


async def test_dashboard_analytics_upi(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    d = (await client.get("/api/analytics/dashboard", headers=auth, params={"month": 10, "year": 2025})).json()
    tx = (await client.get("/api/transactions", headers=auth, params={"month": 10, "year": 2025, "page_size": 200})).json()
    assert d["totals"]["transaction_count"] == tx["total"]
    assert d["totals"]["total_income"] == round(sum(t["credit_amount"] for t in tx["items"]), 2)
    assert d["totals"]["total_expenses"] == round(sum(t["debit_amount"] for t in tx["items"]), 2)
    assert d["changes"]["total_expenses"] is not None  # compared with September
    assert len(d["daily_trend"]) == 31 and len(d["monthly"]) == 6
    assert round(sum(c["amount"] for c in d["category_breakdown"]), 2) == d["totals"]["total_expenses"]
    assert d["insights"] and d["recent_transactions"]

    a = (await client.get("/api/analytics/overview", headers=auth, params={"start": "2025-08-01", "end": "2025-10-31"})).json()
    assert len(a["monthly"]) == 3 and a["granularity"] == "week" and len(a["weekday"]) == 7

    periods = (await client.get("/api/analytics/periods", headers=auth)).json()
    assert periods["latest"]["label"] == "October 2025" and len(periods["months"]) == 3

    u = (await client.get("/api/upi/summary", headers=auth, params={"month": 10, "year": 2025})).json()
    names = [m["merchant"] for m in u["merchants"]]
    assert "Swiggy" in names and len(names) == len(set(names))  # merchant variants grouped
    sw = next(m for m in u["merchants"] if m["merchant"] == "Swiggy")
    assert sw["upi_ids"] == ["swiggy@icici"] and sw["average"] == round(sw["total"] / sw["count"], 2)


async def test_anomalies_and_review(client, auth, sample):
    await import_file(client, auth, sample("hdfc_statement.csv"))
    r = (await client.get("/api/anomalies", headers=auth)).json()
    types = {a["type"] for a in r["items"]}
    assert {"high_amount", "rapid_repeat", "duplicate_like"} <= types and "fraud" not in r["disclaimer"].split()[0]
    flip = next(a for a in r["items"] if a["type"] == "high_amount")
    assert flip["transactions"][0]["merchant"] == "Flipkart" and flip["severity"] in ("medium", "high")
    await client.put(f"/api/anomalies/{flip['key']}/review", headers=auth, json={"status": "dismissed"})
    r2 = (await client.get("/api/anomalies", headers=auth, params={"status": "open"})).json()
    assert flip["key"] not in {a["key"] for a in r2["items"]}


async def test_statement_delete_removes_everything(client, auth, sample):
    up = await import_file(client, auth, sample("hdfc_statement.csv"))
    await import_file(client, auth, sample("sbi_statement.csv"), "sbi.csv")
    total = (await client.get("/api/transactions", headers=auth)).json()["total"]
    r = (await client.delete(f"/api/statements/{up['id']}", headers=auth)).json()
    assert r["deleted_transactions"] == 133
    assert (await client.get("/api/transactions", headers=auth)).json()["total"] == total - 133
    assert (await client.get("/api/transactions", headers=auth, params={"upload_id": up["id"]})).json()["total"] == 0
    assert len((await client.get("/api/statements", headers=auth)).json()) == 1
    # the deleted file can now be imported again
    assert (await upload(client, auth, sample("hdfc_statement.csv"))).status_code == 201


async def test_user_isolation(client, sample):
    a = await register(client, "alice@example.com")
    b = await register(client, "bob@example.com")
    up = await import_file(client, a, sample("hdfc_statement.csv"))
    assert (await client.get("/api/transactions", headers=b)).json()["total"] == 0
    assert (await client.get(f"/api/statements/{up['id']}", headers=b)).status_code == 404
    assert (await client.delete(f"/api/statements/{up['id']}", headers=b)).status_code == 404
    tid = (await client.get("/api/transactions", headers=a)).json()["items"][0]["id"]
    assert (await client.patch(f"/api/transactions/{tid}", headers=b, json={"notes": "x"})).status_code == 404
    # bob can import the same file independently
    assert (await upload(client, b, sample("hdfc_statement.csv"))).status_code == 201


async def test_settings_demo_and_wipe(client, auth):
    r = (await client.post("/api/settings/demo-data", headers=auth)).json()
    assert len(r["imported"]) == 1
    s = (await client.get("/api/settings/data-summary", headers=auth)).json()
    assert s["demo_statements"] == 1 and s["transactions"] == 133
    prof = (await client.patch("/api/settings/profile", headers=auth, json={"anomaly_sensitivity": "high", "full_name": "Dee"})).json()
    assert prof["settings"]["anomaly_sensitivity"] == "high" and prof["full_name"] == "Dee"
    assert (await client.post("/api/settings/password", headers=auth,
                              json={"current_password": "nope", "new_password": "newpass123"})).status_code == 400
    r = await client.post("/api/settings/password", headers=auth,
                          json={"current_password": "secret123", "new_password": "newpass123"})
    assert r.status_code == 200
    assert (await client.get("/api/transactions", headers=auth)).status_code == 401  # old session revoked
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}  # this device stays signed in
    await client.delete("/api/settings/demo-data", headers=auth)
    assert (await client.get("/api/transactions", headers=auth)).json()["total"] == 0


async def test_invalid_ids_and_dates(client, auth):
    assert (await client.get("/api/transactions/not-an-id", headers=auth)).status_code == 400
    assert (await client.get("/api/transactions", headers=auth, params={"start": "2025-13-01"})).status_code == 400
    assert (await client.get("/api/transactions", headers=auth, params={"start": "2025-10-10", "end": "2025-10-01"})).status_code == 400


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def test_excel_upload_and_cross_format_duplicates(client, auth, sample):
    r = await upload(client, auth, sample("hdfc_statement.xlsx"), "hdfc.xlsx", XLSX)
    assert r.status_code == 201, r.text
    assert r.json()["upload"]["bank_name"] == "HDFC Bank" and r.json()["upload"]["file_type"] == "xlsx"
    await client.post(f"/api/statements/{r.json()['upload']['id']}/confirm", headers=auth, json={})
    # the same statement downloaded as CSV is recognised as already imported, row by row
    r = await upload(client, auth, sample("hdfc_statement.csv"))
    assert r.status_code == 201 and r.json()["new_count"] == 0 and r.json()["upload"]["duplicate_count"] == 133
    r = await upload(client, auth, sample("icici_statement.xls"), "icici.xls", "application/vnd.ms-excel")
    assert r.status_code == 201 and r.json()["upload"]["bank_name"] == "ICICI Bank"
    r = await upload(client, auth, sample("axis_statement_html.xls"), "axis.xls", "application/vnd.ms-excel")
    assert r.status_code == 201 and r.json()["upload"]["parser_used"] == "axis:xls-html"


async def test_excel_validation(client, auth):
    r = await upload(client, auth, b"%PDF-1.4 not excel", "x.xlsx", XLSX)
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_file"
    r = await upload(client, auth, b"%PDF-1.4 not excel", "x.xls", "application/vnd.ms-excel")
    assert r.status_code == 400


async def test_password_protected_pdf_flow(client, auth, sample):
    data = sample("sbi_statement_locked.pdf")
    r = await upload(client, auth, data, "sbi_locked.pdf", "application/pdf")
    assert r.status_code == 422 and r.json()["error"]["code"] == "pdf_password_required"
    r = await client.post("/api/statements/preview", headers=auth, data={"password": "wrong"},
                          files={"file": ("sbi_locked.pdf", data, "application/pdf")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "pdf_password_incorrect"
    assert "wrong" not in r.text  # the password is never echoed back
    # password attempts leave no failed records in history
    assert (await client.get("/api/statements", headers=auth)).json() == []
    r = await client.post("/api/statements/preview", headers=auth, data={"password": "DEMO1234"},
                          files={"file": ("sbi_locked.pdf", data, "application/pdf")})
    assert r.status_code == 201 and r.json()["upload"]["parsed_count"] == 45
    r = await client.post("/api/statements/preview", headers=auth, data={"password": "x" * 129},
                          files={"file": ("sbi_locked.pdf", data, "application/pdf")})
    assert r.status_code == 422 and "x" * 20 not in r.text
