"""Bank-specific adapters. Each declares its own column names, identification markers and quirks."""
from app.parsers.base import BaseBankParser


class HDFCParser(BaseBankParser):
    key = "hdfc"
    bank_name = "HDFC Bank"
    column_aliases = {
        "date": ["Date"],
        "description": ["Narration"],
        "reference": ["Chq./Ref.No.", "Chq/Ref No"],
        "value_date": ["Value Dt", "Value Date"],
        "debit": ["Withdrawal Amt.", "Withdrawal Amt"],
        "credit": ["Deposit Amt.", "Deposit Amt"],
        "balance": ["Closing Balance"],
    }
    signature_headers = ["Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]
    text_markers = [r"HDFC\s*BANK", r"IFS\w*\s*(?:CODE)?\s*[:-]?\s*HDFC0\d{6}"]


class ICICIParser(BaseBankParser):
    key = "icici"
    bank_name = "ICICI Bank"
    column_aliases = {
        "date": ["Transaction Date", "Txn Date"],
        "value_date": ["Value Date"],
        "reference": ["Cheque Number", "Cheque No"],
        "description": ["Transaction Remarks", "Remarks"],
        "debit": ["Withdrawal Amount (INR )", "Withdrawal Amount (INR)", "Withdrawal Amount"],
        "credit": ["Deposit Amount (INR )", "Deposit Amount (INR)", "Deposit Amount"],
        "balance": ["Balance (INR )", "Balance (INR)", "Balance"],
    }
    signature_headers = ["Transaction Remarks", "Withdrawal Amount (INR )", "Deposit Amount (INR )", "Balance (INR )", "Cheque Number"]
    text_markers = [r"ICICI\s*BANK", r"IFS\w*\s*(?:CODE)?\s*[:-]?\s*ICIC0\d{6}"]
    # ICICI: UPI/<ref>/<user remark>/<vpa>/<bank> - the free text is a remark, so trust the VPA.
    upi_prefer_vpa = True


class SBIParser(BaseBankParser):
    key = "sbi"
    bank_name = "State Bank of India"
    column_aliases = {
        "date": ["Txn Date", "Transaction Date"],
        "value_date": ["Value Date"],
        "description": ["Description"],
        "reference": ["Ref No./Cheque No.", "Ref No/Cheque No", "Ref No./Cheque No"],
        "debit": ["Debit"],
        "credit": ["Credit"],
        "balance": ["Balance"],
    }
    signature_headers = ["Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"]
    text_markers = [r"STATE\s*BANK\s*OF\s*INDIA", r"IFS\w*\s*(?:CODE)?\s*[:-]?\s*SBIN0\d{6}"]


class AxisParser(BaseBankParser):
    key = "axis"
    bank_name = "Axis Bank"
    column_aliases = {
        "date": ["Tran Date", "Transaction Date"],
        "reference": ["CHQNO", "Chq No"],
        "description": ["PARTICULARS", "Particulars"],
        "debit": ["DR", "Debit"],
        "credit": ["CR", "Credit"],
        "balance": ["BAL", "Balance"],
    }
    signature_headers = ["Tran Date", "CHQNO", "PARTICULARS", "DR", "CR", "BAL", "SOL"]
    text_markers = [r"AXIS\s*BANK", r"IFS\w*\s*(?:CODE)?\s*[:-]?\s*UTIB0\d{6}"]


class KotakParser(BaseBankParser):
    """Kotak uses a single Amount column with a separate Dr/Cr indicator."""

    key = "kotak"
    bank_name = "Kotak Mahindra Bank"
    column_aliases = {
        "date": ["Transaction Date", "Date"],
        "value_date": ["Value Date"],
        "description": ["Description", "Narration"],
        "reference": ["Chq / Ref No.", "Chq/Ref No."],
        "amount": ["Amount"],
        "dr_cr": ["Dr / Cr", "Dr/Cr"],
        "balance": ["Balance"],
    }
    signature_headers = ["Sl. No.", "Transaction Date", "Value Date", "Description", "Chq / Ref No.", "Amount", "Dr / Cr", "Balance"]
    text_markers = [r"KOTAK\s*MAHINDRA", r"IFS\w*\s*(?:CODE)?\s*[:-]?\s*KKBK0\d{6}"]


class GenericParser(BaseBankParser):
    """Fallback for unfamiliar layouts: broad alias lists + fuzzy (contains) header matching."""

    key = "generic"
    bank_name = "Unknown Bank"
    fuzzy_columns = True
    column_aliases = {
        "date": ["Transaction Date", "Txn Date", "Tran Date", "Posting Date", "Date", "Txn Dt", "Trans Date"],
        "value_date": ["Value Date", "Value Dt"],
        "description": ["Description", "Narration", "Particulars", "Transaction Remarks", "Remarks",
                        "Transaction Details", "Details", "Memo", "Payee"],
        "debit": ["Withdrawal Amount", "Withdrawal Amt", "Withdrawals", "Withdrawal", "Debit Amount", "Debit",
                  "Paid Out", "Money Out", "DR"],
        "credit": ["Deposit Amount", "Deposit Amt", "Deposits", "Deposit", "Credit Amount", "Credit",
                   "Paid In", "Money In", "CR"],
        "amount": ["Transaction Amount", "Amount", "Amt"],
        "dr_cr": ["Dr / Cr", "DrCr", "CrDr", "Debit/Credit", "Transaction Type", "Type"],
        "balance": ["Closing Balance", "Running Balance", "Available Balance", "Balance", "Bal"],
        "reference": ["Chq./Ref.No.", "Ref No./Cheque No.", "Reference No", "Reference", "Ref No", "Cheque Number",
                      "Cheque No", "Chq No", "UTR", "Ref"],
    }

    def detect(self, table) -> float:
        return 0.0  # never auto-selected; registry falls back to it explicitly


BANK_PARSERS: list[BaseBankParser] = [HDFCParser(), ICICIParser(), SBIParser(), AxisParser(), KotakParser()]
GENERIC_PARSER = GenericParser()
