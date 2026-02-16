"""Localization and locale-related constants."""

# Turkish month name to number mapping for date parsing
TURKISH_MONTHS = {
    "Ocak": "01",
    "Şubat": "02",
    "Mart": "03",
    "Nisan": "04",
    "Mayıs": "05",
    "Haziran": "06",
    "Temmuz": "07",
    "Ağustos": "08",
    "Eylül": "09",
    "Ekim": "10",
    "Kasım": "11",
    "Aralık": "12",
}

# Double match patterns for different languages (used in booking slot parsing)
DOUBLE_MATCH_PATTERNS = [
    r"(\d+)\s*Başvuru sahipleri.*?:\s*(\d{2}-\d{2}-\d{4})",  # Turkish
    r"(\d+)\s*[Aa]pplicants?.*?:\s*(\d{2}-\d{2}-\d{4})",  # English
]
