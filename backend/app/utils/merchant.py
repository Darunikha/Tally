"""Merchant identification & normalization.

Variations such as "SWIGGY*ORDER123", "UPI-SWIGGY", "SWIGGY INDIA" and "swiggy@icici" all
normalize to the canonical merchant "Swiggy". Order matters: more specific aliases first
(e.g. "Swiggy Instamart" before "Swiggy", "Amazon Prime" before "Amazon").
"""
import re

# (canonical name, regex). Matched against an UPPERCASE string.
MERCHANT_ALIASES: list[tuple[str, str]] = [
    ("Swiggy Instamart", r"INSTAMART"),
    ("Swiggy", r"SWIGGY|BUNDL\s*TECH"),
    ("Zomato", r"ZOMATO|BLINKIT\s*FOOD"),
    ("Blinkit", r"BLINKIT|GROFERS"),
    ("Zepto", r"\bZEPTO|KIRANAKART"),
    ("BigBasket", r"BIG\s*BASKET|BBNOW|SUPERMARKET\s*GROCERY\s*SUPPLIES"),
    ("DMart", r"\bD\s*MART\b|AVENUE\s*SUPERMARTS"),
    ("JioMart", r"JIO\s*MART"),
    ("Domino's", r"DOMINO"),
    ("McDonald's", r"MC\s*DONALD"),
    ("KFC", r"\bKFC\b"),
    ("Starbucks", r"STARBUCKS|TATA\s*STARBUCKS"),
    ("Pizza Hut", r"PIZZA\s*HUT"),
    ("Amazon Prime", r"PRIME\s*VIDEO|AMAZON\s*PRIME|PRIMEVIDEO"),
    ("Amazon", r"AMAZON|AMZN|\bAPAY\b"),
    ("Flipkart", r"FLIPKART|\bFKRT\b"),
    ("Myntra", r"MYNTRA"),
    ("Ajio", r"\bAJIO\b"),
    ("Meesho", r"MEESHO"),
    ("Nykaa", r"NYKAA"),
    ("Uber", r"\bUBER"),
    ("Ola", r"\bOLA\s*(CABS|MONEY|ELECTRIC)?\b|ANI\s*TECHNOLOGIES"),
    ("Rapido", r"RAPIDO|ROPPEN"),
    ("Namma Metro", r"NAMMA\s*METRO|BMRCL"),
    ("IRCTC", r"IRCTC"),
    ("MakeMyTrip", r"MAKE\s*MY\s*TRIP|\bMMT\b"),
    ("Goibibo", r"GOIBIBO"),
    ("IndiGo", r"INDIGO|INTERGLOBE"),
    ("Air India", r"AIR\s*INDIA"),
    ("redBus", r"RED\s*BUS"),
    ("Indian Oil", r"INDIAN\s*OIL|\bIOCL?\b"),
    ("HP Petrol", r"HPCL|HINDUSTAN\s*PETROLEUM|HP\s*PETROL"),
    ("Bharat Petroleum", r"BPCL|BHARAT\s*PETROLEUM"),
    ("Shell", r"\bSHELL\b"),
    ("Netflix", r"NETFLIX"),
    ("Spotify", r"SPOTIFY"),
    ("Disney+ Hotstar", r"HOTSTAR|NOVI\s*DIGITAL"),
    ("YouTube Premium", r"YOUTUBE"),
    ("Google Play", r"GOOGLE\s*PLAY|GOOGLEPLAY"),
    ("Apple", r"APPLE\s*(MEDIA|SERVICES|\.COM)|ITUNES"),
    ("BookMyShow", r"BOOK\s*MY\s*SHOW|BIGTREE"),
    ("PVR INOX", r"\bPVR\b|\bINOX\b"),
    ("Apollo Pharmacy", r"APOLLO"),
    ("PharmEasy", r"PHARMEASY"),
    ("Tata 1mg", r"\b1\s*MG\b"),
    ("Practo", r"PRACTO"),
    ("BESCOM", r"BESCOM"),
    ("TNEB", r"TNEB|TANGEDCO"),
    ("MSEDCL", r"MSEDCL|MAHAVITARAN"),
    ("BSES", r"\bBSES\b"),
    ("Airtel", r"AIRTEL"),
    ("Jio", r"\bJIO\b|RELIANCE\s*JIO"),
    ("Vi", r"VODAFONE|\bVI\s*(PREPAID|POSTPAID)"),
    ("ACT Fibernet", r"ACT\s*FIBERNET|ATRIA\s*CONVERGENCE"),
    ("Zerodha", r"ZERODHA"),
    ("Groww", r"GROWW|NEXTBILLION"),
    ("Upstox", r"UPSTOX|RKSV"),
    ("Coursera", r"COURSERA"),
    ("Udemy", r"UDEMY"),
    ("LIC", r"\bLIC\b|LIFE\s*INSURANCE\s*CORP"),
    ("CRED", r"\bCRED\b|DREAMPLUG"),
]

_COMPILED = [(name, re.compile(p)) for name, p in MERCHANT_ALIASES]

# Words that carry no merchant identity.
_NOISE_WORDS = {
    "PVT", "PRIVATE", "LTD", "LIMITED", "LLP", "INC", "CORP", "CO", "INDIA", "IND", "TECHNOLOGIES",
    "TECHNOLOGY", "TECH", "SERVICES", "SERVICE", "ONLINE", "PAYMENTS", "PAYMENT", "RETAIL", "INTERNET",
    "COM", "WWW", "IN", "THE", "AND", "ORDER", "PAY", "MERCHANT", "STORE", "PG", "RAZORPAY",
    "PAYU", "CCAVENUE", "BILLDESK", "CASHFREE",
}

# Tokens in descriptions that are channel/bank boilerplate, not names.
_BOILERPLATE = re.compile(
    r"^(UPI|DR|CR|P2A|P2M|P2P|NEFT|IMPS|RTGS|NACH|ACH|ECS|POS|ECOM|ATW|ATM|NWD|MB|IB|INB|BIL|ONL|"
    r"TO TRANSFER|BY TRANSFER|TRANSFER|TRF|TO|BY|FROM|VIA|REF|NO|NA|N A|PAYMENT|PAY|PAYMENT FROM PH|"
    r"PAYMENT FROM PHONE|PAID VIA|UPI INTENT|COLLECT|COLLECT REQUEST|SENT USING PAYTM|NO REMARKS|"
    r"UPIINTENT|PAYTM|PHONEPE|GPAY|GOOGLE PAY|BHIM|D|C|CHQ|CHEQUE|CLG|SI|ACH D|ACH C|NEFT CR|"
    r"NEFT DR|IMPS P2A|INTERNET BANKING|NET BANKING|DEBIT CARD|CREDIT CARD|VISA|MASTERCARD|RUPAY)$"
)
_IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_BANK_CODE = re.compile(r"^(SBIN|HDFC|ICIC|UTIB|KKBK|YESB|PUNB|BARB|CNRB|IDIB|IOBA|INDB|FDRL|AIRP|PYTM|IDFB|AUBL|UBIN|CBIN|BKID|MAHB|KARB|SIBL|RATN)$")
_BANK_NAME = re.compile(r"\bBANK\b|\bBK\b")
_MASKED_CARD = re.compile(r"\b[0-9X\*]{4,}X{2,}[0-9X\*]*\b|\bXX+\d+\b")


def match_alias(text: str | None) -> str | None:
    if not text:
        return None
    up = text.upper()
    for name, rx in _COMPILED:
        if rx.search(up):
            return name
    return None


def is_boilerplate(token: str) -> bool:
    t = re.sub(r"\s+", " ", token.strip().upper())
    if not t or not re.search(r"[A-Z]", t):
        return True
    if _BOILERPLATE.match(t) or _IFSC.match(t) or _BANK_CODE.match(t) or _BANK_NAME.search(t):
        return True
    if re.fullmatch(r"[A-Z]?\d[\dA-Z]*", t) and sum(c.isdigit() for c in t) >= len(t) / 2:
        return True  # reference-like tokens e.g. N123456789, 529012345678
    if _MASKED_CARD.search(t) and len(t.split()) == 1:
        return True
    return False


def clean_name(text: str | None, max_words: int = 3) -> str | None:
    """Strip order ids, digits, legal suffixes; title-case. 'SWIGGY*ORDER123' -> 'Swiggy'."""
    if not text:
        return None
    s = text.upper()
    s = s.split("*")[0] if "*" in s and s.split("*")[0].strip() else s
    s = s.split("@")[0] if "@" in s else s
    s = _MASKED_CARD.sub(" ", s)
    s = re.sub(r"ORDER\s*\w*", " ", s)
    s = re.sub(r"[^A-Z&' ]+", " ", s)
    words = [w for w in s.split() if w not in _NOISE_WORDS]
    words = [w for i, w in enumerate(words) if len(w) > 1 or i > 0]  # keep initials like "Priya S"
    if not words:
        return None
    name = " ".join(words[:max_words])
    return name.title().replace("'S", "'s")


def normalize_merchant(*candidates: str | None) -> str | None:
    """Return the canonical merchant for the first candidate that matches a known alias,
    otherwise a cleaned version of the first usable candidate."""
    for c in candidates:
        alias = match_alias(c)
        if alias:
            return alias
    for c in candidates:
        cleaned = clean_name(c)
        if cleaned:
            return cleaned
    return None


def name_tokens(description: str) -> list[str]:
    """Split a bank narration into candidate name tokens (boilerplate removed)."""
    s = re.sub(r"[A-Za-z0-9._]{2,}@[A-Za-z][A-Za-z0-9]{1,}", " ", description)  # drop VPAs
    parts = re.split(r"\s*(?:/|--|-|:|\*|\||\\)\s*", s)  # SBI uses '*' in NEFT narrations
    return [p.strip() for p in parts if p and not is_boilerplate(p)]
