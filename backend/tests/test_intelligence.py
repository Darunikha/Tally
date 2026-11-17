"""UPI extraction, merchant normalization, payment methods, categorization, duplicate fingerprints."""
from datetime import datetime

import pytest
from bson import ObjectId

from app.categorization.defaults import DEFAULT_RULES
from app.categorization.engine import CategorizationEngine, InvalidRuleError, validate_pattern
from app.parsers.adapters.banks import ICICIParser
from app.parsers.base import ParsedTransaction
from app.services.normalization import fingerprints
from app.utils.merchant import clean_name, normalize_merchant
from app.utils.payment import detect_payment_method, extract_merchant
from app.utils.upi import extract_upi, is_upi


@pytest.mark.parametrize("desc,merchant,vpa,ref,flow", [
    ("UPI-SWIGGY-swiggy@icici-ICIC0000103-529012345678-UPI Intent", "Swiggy", "swiggy@icici", "529012345678", "P2M"),
    ("TO TRANSFER-UPI/DR/529012345678/SWIGGY/YESB/swiggy.in@ybl/Pay--", "Swiggy", "swiggy.in@ybl", "529012345678", "P2M"),
    ("UPI/P2M/529012345678/Swiggy Limited/UPI/ICICI Bank", "Swiggy", None, "529012345678", "P2M"),
    ("UPI/P2A/529012345678/RAHUL KUMAR/UPI/HDFC BANK", "Rahul Kumar", None, "529012345678", "P2A"),
    ("UPI/SWIGGY/529012345678/Payment from Phone", "Swiggy", None, "529012345678", "P2M"),
    ("UPI-RAHUL KUMAR-rahulk@okaxis-UTIB0000123-529011112222-Rent", "Rahul Kumar", "rahulk@okaxis", "529011112222", "P2A"),
    ("UPI-RAMESH TEA STALL-ramesh.tea99@paytm-PYTM0123456-529011112299-Pay", "Ramesh Tea Stall", "ramesh.tea99@paytm", "529011112299", None),
])
def test_upi_extraction(desc, merchant, vpa, ref, flow):
    u = extract_upi(desc)
    assert u.is_upi
    assert u.merchant == merchant
    assert u.upi_id == vpa
    assert u.reference == ref
    assert u.flow == flow


def test_upi_direction_markers():
    assert extract_upi("BY TRANSFER-UPI/CR/529012345678/PRIYA S/SBIN/priya@oksbi/Payment--").direction == "credit"
    assert extract_upi("TO TRANSFER-UPI/DR/529012345678/X/YESB/x@ybl/Pay--").direction == "debit"


def test_icici_adapter_prefers_vpa_over_remark():
    # In ICICI narrations the slot before the VPA is the user's remark ("Dinner"), not the payee
    u = ICICIParser().extract_upi("UPI/529012345699/Dinner/zomato@hdfcbank/HDFC Bank")
    assert u.merchant == "Zomato"
    u2 = ICICIParser().extract_upi("UPI/529012345699/Payment/ramesh.tea99@paytm/Paytm Payments Bank")
    assert u2.merchant == "Ramesh Tea"


def test_non_upi_not_detected():
    assert not is_upi("NEFT CR-HDFC0000001-ACME TECHNOLOGIES PVT LTD-SALARY")
    assert not is_upi("POS 4111XXXXXXXX1234 AMAZON PAY INDIA")
    assert not extract_upi("ATW-512345XXXXXX1234-S1ANBG12-BANGALORE").is_upi


@pytest.mark.parametrize("variant", ["SWIGGY*ORDER123", "UPI-SWIGGY", "SWIGGY INDIA", "swiggy@icici", "Bundl Technologies"])
def test_merchant_variants_group_together(variant):
    assert normalize_merchant(variant) == "Swiggy"


def test_specific_aliases_win():
    assert normalize_merchant("SWIGGY INSTAMART") == "Swiggy Instamart"
    assert normalize_merchant("AMAZON PRIME VIDEO") == "Amazon Prime"
    assert normalize_merchant("AMZN MKTP IN") == "Amazon"


def test_clean_name_for_unknown_merchants():
    assert clean_name("SHARMA GENERAL STORES PVT LTD") == "Sharma General Stores"
    assert clean_name("12345") is None


@pytest.mark.parametrize("desc,method", [
    ("UPI/P2M/529012345678/Swiggy", "UPI"), ("NEFT CR-HDFC0000001-ACME", "NEFT"), ("IMPS-529012345678-RAHUL", "IMPS"),
    ("POS 4111XXXXXXXX1234 AMAZON", "Card"), ("ACH D- NETFLIX-123", "Auto Debit"), ("ATW-512345XXXXXX1234-S1", "ATM/Cash"),
    ("CHQ DEP 000123", "Cheque"), ("SB INTEREST CREDIT", "Interest"), ("SMS ALERT CHARGES", "Bank Charges"), ("RANDOM", "Other"),
])
def test_payment_method(desc, method):
    assert detect_payment_method(desc) == method


def test_non_upi_merchant_extraction():
    assert extract_merchant("POS 4111XXXXXXXX1234 AMAZON PAY INDIA") == "Amazon"
    assert extract_merchant("NEFT CR-HDFC0000001-ACME TECHNOLOGIES PVT LTD-SALARY OCT-N123456789") == "Acme"
    assert extract_merchant("ATW-512345XXXXXX1234", "ATM/Cash") == "ATM Withdrawal"
    assert extract_merchant("BY TRANSFER-NEFT*HDFC0000001*N530801000*ACME TECHNOLOGIES PVT LTD--") == "Acme"


# ---------------------------------------------------------------- categorization
def _engine(extra_rules=()):
    names = {n for _, _, n, _, _ in DEFAULT_RULES} | {"Other", "Custom"}
    cat_ids = {n: str(ObjectId()) for n in names}
    rules = [{"_id": ObjectId(), "rule_name": n, "regex_pattern": rx, "category_id": cat_ids[c], "priority": p,
              "applies_to": a, "enabled": True, "is_default": True} for n, rx, c, p, a in DEFAULT_RULES]
    rules += list(extra_rules)
    return CategorizationEngine(rules, cat_ids["Other"]), cat_ids


@pytest.mark.parametrize("merchant,desc,ttype,expected", [
    ("Swiggy", "UPI-SWIGGY", "debit", "Food & Dining"), ("Zomato", "", "debit", "Food & Dining"),
    ("BigBasket", "", "debit", "Groceries"), ("Blinkit", "", "debit", "Groceries"),
    ("Amazon", "", "debit", "Shopping"), ("Flipkart", "", "debit", "Shopping"),
    ("Uber", "", "debit", "Transportation"), ("Ola", "", "debit", "Transportation"), ("Rapido", "", "debit", "Transportation"),
    ("Netflix", "", "debit", "Subscriptions"), ("Spotify", "", "debit", "Subscriptions"),
    ("BESCOM", "", "debit", "Bills & Utilities"), ("TNEB", "", "debit", "Bills & Utilities"),
    ("Acme", "NEFT CR-ACME-SALARY OCT", "credit", "Income"), ("Groww", "UPI SIP", "debit", "Investments"),
    ("Suresh Nair", "UPI-SURESH NAIR-x@okhdfc-RENT", "debit", "Rent"),
    ("Indian Oil", "", "debit", "Fuel"), ("Apollo Pharmacy", "", "debit", "Healthcare"),
    ("Priya S", "UPI/P2A/123/PRIYA S", "credit", "Transfers"),
])
def test_default_categorization(merchant, desc, ttype, expected):
    engine, ids = _engine()
    m = engine.categorize(merchant, desc, ttype)
    assert m.category_id == ids[expected]


def test_unrecognized_goes_to_other_for_review():
    engine, ids = _engine()
    m = engine.categorize("Mystery Vendor", "XYZ123", "debit")
    assert m.category_id == ids["Other"] and m.source == "default"
    assert engine.apply({"normalized_merchant": "Mystery", "raw_description": "", "transaction_type": "debit"})["needs_review"]


def test_priority_and_custom_rules():
    custom_cat = str(ObjectId())
    custom = {"_id": ObjectId(), "rule_name": "Office lunch", "regex_pattern": r"SWIGGY", "category_id": custom_cat,
              "priority": 80, "applies_to": "debit", "enabled": True, "is_default": False}
    engine, ids = _engine([custom])
    m = engine.categorize("Swiggy", "", "debit")
    assert m.category_id == custom_cat and m.source == "custom_rule"  # same priority: user rule wins


def test_disabled_rules_and_applies_to():
    custom = str(ObjectId())
    engine, ids = _engine([{"_id": ObjectId(), "rule_name": "x", "regex_pattern": "MYSTERY", "category_id": custom,
                            "priority": 999, "applies_to": "credit", "enabled": True}])
    ids["Custom"] = custom
    assert engine.categorize("Mystery", "", "debit").category_id == ids["Other"]
    assert engine.categorize("Mystery", "", "credit").category_id == ids["Custom"]
    engine2, _ = _engine([{"_id": ObjectId(), "rule_name": "x", "regex_pattern": "MYSTERY", "category_id": custom,
                           "priority": 999, "applies_to": "any", "enabled": False}])
    assert engine2.categorize("Mystery", "", "debit").category_id != ids["Custom"]


def test_manual_override_untouched():
    engine, _ = _engine()
    assert engine.apply({"manual_override": True, "normalized_merchant": "Swiggy", "transaction_type": "debit"}) == {}


@pytest.mark.parametrize("bad", ["", "(", "(a+)+", "(\\w*)*$", "x" * 301])
def test_invalid_patterns_rejected(bad):
    with pytest.raises(InvalidRuleError):
        validate_pattern(bad)


# ---------------------------------------------------------------- duplicates
def _pt(day, amt, desc="UPI/SWIGGY", bal=None):
    return ParsedTransaction(transaction_date=datetime(2025, 10, day), description=desc, debit_amount=amt, balance=bal)


def test_fingerprints_stable_and_occurrence_aware():
    uid = ObjectId()
    a = [_pt(1, 100), _pt(1, 100), _pt(2, 50)]
    fa, fb = fingerprints(uid, a), fingerprints(uid, list(a))
    assert fa == fb                      # same statement re-uploaded -> identical fingerprints
    assert len(set(fa)) == 3             # two identical coffees in one statement stay distinct
    assert fingerprints(ObjectId(), a)[0] != fa[0]  # per-user


def test_fingerprint_ignores_whitespace_but_not_amount():
    uid = ObjectId()
    assert fingerprints(uid, [_pt(1, 100, "UPI / SWIGGY")]) == fingerprints(uid, [_pt(1, 100, "UPI/SWIGGY")])
    assert fingerprints(uid, [_pt(1, 100)]) != fingerprints(uid, [_pt(1, 101)])
