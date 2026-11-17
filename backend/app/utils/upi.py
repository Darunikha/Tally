"""UPI transaction detection and detail extraction.

Handles common narration shapes, e.g.
  HDFC : UPI-SWIGGY-swiggy@icici-ICIC0000103-529012345678-UPI Intent
  ICICI: UPI/529012345678/Payment from Ph/swiggy@icici/ICICI Bank
  SBI  : TO TRANSFER-UPI/DR/529012345678/SWIGGY/YESB/swiggy.in@ybl/Pay--
  Axis : UPI/P2M/529012345678/Swiggy Limited/UPI/ICICI Bank
  Kotak: UPI/SWIGGY/529012345678/Payment from Phone
"""
import re
from dataclasses import dataclass

from app.utils.merchant import match_alias, name_tokens, normalize_merchant

# Hyphen is excluded from the local part: several banks use "-" as the narration delimiter.
VPA_RE = re.compile(r"(?<![A-Za-z0-9._])([A-Za-z0-9][A-Za-z0-9._]{1,255}@[A-Za-z][A-Za-z0-9]{1,63})")
_UPI_WORD = re.compile(r"(^|[^A-Z])UPI([^A-Z]|$)|\bVPA\b|\bBHIM\b")
_RRN = re.compile(r"(?<!\d)(\d{12})(?!\d)")
_REF_FALLBACK = re.compile(r"(?<!\d)(\d{10,16})(?!\d)")
_PERSONAL_HANDLE = re.compile(r"@ok(axis|hdfcbank|icici|sbi)$")


@dataclass
class UpiDetails:
    is_upi: bool
    upi_id: str | None = None
    reference: str | None = None
    flow: str | None = None        # "P2M" (to merchant) | "P2A" (to person/account) | None
    direction: str | None = None   # "debit" | "credit" | None (from narration DR/CR markers)
    payee_name: str | None = None  # raw name as found in the narration
    merchant: str | None = None    # normalized merchant


def is_upi(description: str | None) -> bool:
    if not description:
        return False
    up = description.upper()
    return bool(_UPI_WORD.search(up)) or (bool(VPA_RE.search(description)) and "@" in description)


def extract_upi(description: str | None, prefer_vpa: bool = False) -> UpiDetails:
    """Extract UPI id, reference, flow and merchant from a narration.

    prefer_vpa: for formats where the free-text slot before the VPA is a user remark rather than
    the payee name (e.g. ICICI), derive the merchant from the VPA first.
    """
    if not is_upi(description):
        return UpiDetails(is_upi=False)
    desc = description.strip()
    up = desc.upper()

    vpa_match = VPA_RE.search(desc)
    upi_id = vpa_match.group(1).lower() if vpa_match else None

    ref_match = _RRN.search(desc) or _REF_FALLBACK.search(desc)
    reference = ref_match.group(1) if ref_match else None

    tokens_upper = set(re.split(r"[/\-\s:]+", up))
    flow = "P2M" if "P2M" in tokens_upper else "P2A" if "P2A" in tokens_upper or "P2P" in tokens_upper else None
    direction = "debit" if "DR" in tokens_upper else "credit" if "CR" in tokens_upper else None

    names = name_tokens(desc)
    vpa_local = upi_id.split("@")[0] if upi_id else None
    vpa_name = re.sub(r"[._\-\d]+", " ", vpa_local).strip() if vpa_local else None

    payee = names[0] if names else None
    if prefer_vpa and vpa_name:
        merchant = normalize_merchant(vpa_name, *names)
        payee = payee if match_alias(payee or "") == merchant else (vpa_name or payee)
    else:
        merchant = normalize_merchant(*names, vpa_name)

    if flow is None and merchant and match_alias(merchant):
        flow = "P2M"
    elif flow is None and upi_id and _PERSONAL_HANDLE.search(upi_id):
        flow = "P2A"  # Google Pay personal handles (@okaxis, @okhdfcbank, ...) are issued to individuals

    return UpiDetails(
        is_upi=True,
        upi_id=upi_id,
        reference=reference,
        flow=flow,
        direction=direction,
        payee_name=payee,
        merchant=merchant,
    )
