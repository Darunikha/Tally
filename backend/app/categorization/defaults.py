"""Default categories and categorization rules seeded for each new user (all editable)."""

# name, color, description
# The 8 main spending categories use a CVD-validated categorical palette (validate_palette.js);
# the rest use calmer tones and fold into "Others" in charts beyond the top 5.
DEFAULT_CATEGORIES: list[tuple[str, str, str]] = [
    ("Food & Dining", "#1BAF7A", "Restaurants, cafes and food delivery"),
    ("Groceries", "#008300", "Supermarkets and grocery delivery"),
    ("Shopping", "#EB6834", "Online and retail shopping"),
    ("Transportation", "#2A78D6", "Cabs, autos, metro and local transport"),
    ("Fuel", "#8A6D3B", "Petrol, diesel and EV charging"),
    ("Entertainment", "#E87BA4", "Movies, events and games"),
    ("Healthcare", "#E34948", "Pharmacy, doctors and hospitals"),
    ("Education", "#4B7F87", "Courses, fees and books"),
    ("Bills & Utilities", "#6250D6", "Electricity, phone, internet and gas"),
    ("Rent", "#EDA100", "House rent and maintenance"),
    ("Travel", "#7D8FB3", "Flights, trains, buses and hotels"),
    ("Subscriptions", "#A07AA8", "Streaming and recurring digital services"),
    ("Transfers", "#94A3B8", "Transfers to people and own accounts"),
    ("Investments", "#3F6F8F", "Mutual funds, stocks, SIPs and insurance"),
    ("Income", "#2F7D55", "Salary, interest and other income"),
    ("Other", "#B8B2A7", "Uncategorized - needs review"),
]

OTHER_CATEGORY = "Other"

# rule_name, regex (matched against "MERCHANT | DESCRIPTION" uppercased), category, priority, applies_to
# Higher priority wins. Merchant-specific rules sit above generic keyword rules.
DEFAULT_RULES: list[tuple[str, str, str, int, str]] = [
    ("Salary", r"SALARY|\bSAL\b|PAYROLL", "Income", 100, "credit"),
    ("Interest", r"INTEREST|\bINT\.?\s*(PD|CR)\b|BANK INTEREST", "Income", 95, "credit"),
    ("Dividends", r"DIVIDEND|\bDIV\b", "Income", 95, "credit"),
    ("Subscriptions - streaming", r"NETFLIX|SPOTIFY|HOTSTAR|AMAZON PRIME|PRIME VIDEO|YOUTUBE|APPLE|GOOGLE PLAY|SONYLIV|ZEE5|JIOCINEMA", "Subscriptions", 90, "debit"),
    ("Grocery delivery", r"INSTAMART|BLINKIT|ZEPTO|BIGBASKET|DMART|JIOMART|MORE RETAIL|RATNADEEP|NATURE'?S BASKET|SUPERMARKET|GROCER|KIRANA", "Groceries", 85, "debit"),
    ("Food delivery & restaurants", r"SWIGGY|ZOMATO|DOMINO|MCDONALD|KFC|STARBUCKS|PIZZA|BURGER|EATSURE|RESTAURANT|CAFE|BAKERY|BIRYANI|\bTEA\b|CHAI|COFFEE|HOTEL\s+\w+\s+(VEG|FOODS?)|DHABA|FOODS?\b", "Food & Dining", 80, "debit"),
    ("Online shopping", r"AMAZON|FLIPKART|MYNTRA|AJIO|MEESHO|NYKAA|TATA CLIQ|CROMA|RELIANCE DIGITAL|DECATHLON|IKEA|LIFESTYLE|SHOPPERS STOP|WESTSIDE", "Shopping", 75, "debit"),
    ("Ride hailing & transit", r"\bUBER|\bOLA\b|RAPIDO|NAMMA METRO|METRO RAIL|BMTC|BEST BUS|FASTAG|PARKING|AUTO RICKSHAW", "Transportation", 75, "debit"),
    ("Fuel", r"PETROL|DIESEL|FUEL|INDIAN OIL|\bIOCL?\b|HPCL|HP PETROL|BPCL|BHARAT PETROLEUM|\bSHELL\b|NAYARA", "Fuel", 75, "debit"),
    ("Travel", r"IRCTC|MAKEMYTRIP|GOIBIBO|INDIGO|AIR INDIA|VISTARA|AKASA|SPICEJET|REDBUS|CLEARTRIP|YATRA|OYO|AIRBNB|BOOKING\.COM", "Travel", 75, "debit"),
    ("Entertainment", r"BOOKMYSHOW|PVR|INOX|CINEPOLIS|STEAM|PLAYSTATION|DREAM11|GAMING", "Entertainment", 70, "debit"),
    ("Healthcare", r"APOLLO|PHARMEASY|1MG|NETMEDS|PRACTO|PHARMACY|MEDICAL|HOSPITAL|CLINIC|DIAGNOSTIC|LAB\b|CHEMIST", "Healthcare", 70, "debit"),
    ("Education", r"COURSERA|UDEMY|BYJU|UNACADEMY|SCHOOL|COLLEGE|UNIVERSITY|TUITION|EXAM FEE", "Education", 70, "debit"),
    ("Utilities - power, phone, internet", r"BESCOM|TNEB|TANGEDCO|MSEDCL|BSES|TATA POWER|ADANI ELEC|ELECTRICITY|AIRTEL|\bJIO\b|VODAFONE|\bVI\b|BSNL|BROADBAND|FIBERNET|ACT FIBER|\bGAS\b|MAHANAGAR GAS|INDANE|WATER BOARD|BWSSB|DTH|TATA PLAY|RECHARGE", "Bills & Utilities", 70, "debit"),
    ("Credit card bill", r"\bCRED\b|CREDIT CARD (BILL|PAYMENT)|CC PAYMENT|BILLDESK.*CARD", "Bills & Utilities", 65, "debit"),
    ("Investments", r"ZERODHA|GROWW|UPSTOX|KUVERA|COIN BY|MUTUAL FUND|\bMF\b|\bSIP\b|\bNSE\b|\bBSE\b|\bPPF\b|\bNPS\b|\bLIC\b|ICCL|INDIAN CLEARING", "Investments", 65, "debit"),
    ("Rent", r"\bRENT\b|HOUSE RENT|NOBROKER|MAINTENANCE CHARGES|SOCIETY MAINT", "Rent", 60, "debit"),
    ("Bank charges", r"BANK CHARGES|SMS ALERT|\bAMC\b|ANNUAL FEE|CHRG|DEBIT CARD FEE|\bGST\b", "Bills & Utilities", 40, "debit"),
    ("Refunds & cashback", r"REFUND|REVERSAL|CASHBACK|REV-", "Income", 40, "credit"),
    ("Cash withdrawal", r"ATM WITHDRAWAL|\bATW\b|\bATM\b|CASH WDL|\bNWD\b", "Transfers", 30, "debit"),
    ("Person-to-person transfers", r"P2A|\bIMPS\b|\bNEFT\b|\bRTGS\b|SELF TRANSFER|\bTO SELF\b|FUND TRANSFER", "Transfers", 10, "any"),
    ("Incoming UPI transfers", r"\bUPI\b", "Transfers", 5, "credit"),
]
