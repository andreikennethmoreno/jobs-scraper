# jobspy/jobstreet/constant.py

# Based on your working script's "special_urls"
DOMAIN_MAP = {
    # Special cases (JobsDB & Seek)
    "th": "https://th.jobsdb.com/th/{work}-jobs/in-{location}",
    "hk": "https://hk.jobsdb.com/hk/{work}-jobs/in-{location}",
    "nz": "https://www.seek.co.nz/{work}-jobs/in-{location}",
    "au": "https://www.seek.com.au/{work}-jobs/in-{location}",
    
    # Standard JobStreet pattern (no /id/, /ph/ in the path)
    "id": "https://id.jobstreet.com/{work}-jobs/in-{location}",
    "my": "https://my.jobstreet.com/{work}-jobs/in-{location}",
    "sg": "https://sg.jobstreet.com/{work}-jobs/in-{location}",
    "ph": "https://ph.jobstreet.com/{work}-jobs/in-{location}",
    "vn": "https://vn.jobstreet.com/{work}-jobs/in-{location}",
}

# Fallback template
DEFAULT_URL_TEMPLATE = "https://{country}.jobstreet.com/{work}-jobs/in-{location}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
}