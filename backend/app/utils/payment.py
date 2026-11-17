"""Payment method detection & non-UPI merchant extraction from narrations."""
import re

from app.utils.merchant import name_tokens, normalize_merchant
from app.utils.upi import is_upi

PAYMENT_METHODS = [
    "UPI", "Card", "NEFT", "IMPS", "RTGS", "Net Banking", "Auto Debit", "ATM/Cash", "Cheque",
    "Interest", "Bank Charges", "Other",
]

_RULES: list[tuple[str, re.Pattern]] = [
    ("IMPS", re.compile(r"\bIMPS\b")),
    ("NEFT", re.compile(r"\bNEFT\b")),
    ("RTGS", re.compile(r"\bRTGS\b")),
    ("Auto Debit", re.compile(r"\b(NACH|ACH|ECS|SI|AUTOPAY|AUTO\s*DEBIT|MANDATE)\b")),
    ("ATM/Cash", re.compile(r"\b(ATM|ATW|NWD|CASH\s*(WDL|WITHDRAWAL|DEP|DEPOSIT)|CDM)\b")),
    ("Card", re.compile(r"\b(POS|ECOM|DEBIT\s*CARD|CREDIT\s*CARD|VISA|MASTERCARD|RUPAY|VPS|IPS|PCD)\b|X{4}\d{4}")),
    ("Cheque", re.compile(r"\b(CHQ|CHEQUE|CLG|CLEARING|INWARD\s*CLG)\b")),
    ("Interest", re.compile(r"\b(INT\.?\s*(PD|PAID|CR)|INTEREST|SB\s*INT)\b")),
    ("Bank Charges", re.compile(r"\b(CHARGES?|CHRG|FEE|GST|SMS\s*ALERT|AMC|PENALTY)\b")),
    ("Net Banking", re.compile(r"\b(NET\s*BANKING|INB|IB\s*BILL|BIL/ONL|BILLPAY|ONLINE\s*TRANSFER|MB\s*TRF)\b")),
]


def detect_payment_method(description: str | None) -> str:
    if not description:
        return "Other"
    if is_upi(description):
        return "UPI"
    up = description.upper()
    for name, rx in _RULES:
        if rx.search(up):
            return name
    return "Other"


FIXED_MERCHANTS = {"ATM/Cash": "ATM Withdrawal", "Interest": "Bank Interest", "Bank Charges": "Bank Charges"}


def extract_merchant(description: str | None, payment_method: str | None = None) -> str | None:
    """Merchant for non-UPI narrations, e.g. 'POS 4111XXXXXXXX1234 AMAZON PAY INDIA' -> 'Amazon'."""
    if not description:
        return None
    if payment_method in FIXED_MERCHANTS:
        return FIXED_MERCHANTS[payment_method]
    up = description.upper()
    # strip leading channel tags like "POS 4111XXXX1234", "ACH D-", "NEFT CR-"
    up = re.sub(r"^(POS|ECOM|ATW|NWD|VPS|IPS|PCD)\s+[0-9X\*]+\s*", "", up)
    tokens = name_tokens(up)
    # tokens first so cleaning picks the payee slot; full string last as alias-only safety net
    return normalize_merchant(*tokens, up) if tokens else normalize_merchant(up)
