# jobspy/jobstreet/util.py
import re

def parse_salary_string(salary_text: str):
    """
    Parses JobStreet salary strings (e.g., "IDR 10,000,000 – IDR 25,000,000 per month")
    Returns: (min_amount, max_amount, currency, interval)
    """
    if not salary_text or salary_text == "N/A":
        return None, None, None, None

    # Determine Interval
    interval = "monthly"  # Default for JobStreet usually
    if "year" in salary_text.lower():
        interval = "yearly"
    elif "hour" in salary_text.lower():
        interval = "hourly"

    # Remove commas and extract numbers
    clean_text = salary_text.replace(",", "").replace(".", "") # Removing thousands separators
    
    # Extract currency (First 3 letters usually, e.g. IDR, SGD)
    currency_match = re.search(r"[A-Z]{3}", salary_text)
    currency = currency_match.group(0) if currency_match else "USD"

    # Extract numbers
    numbers = re.findall(r'\d+', clean_text)
    
    min_amount = None
    max_amount = None

    if len(numbers) >= 2:
        min_amount = int(numbers[0])
        max_amount = int(numbers[1])
    elif len(numbers) == 1:
        min_amount = int(numbers[0])
    
    return min_amount, max_amount, currency, interval