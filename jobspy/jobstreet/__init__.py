# jobspy/jobstreet/__init__.py
from __future__ import annotations

import math
import os
import json
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import cloudscraper  # Using cloudscraper for WAF bypass

from jobspy.jobstreet.constant import DOMAIN_MAP, DEFAULT_URL_TEMPLATE, headers
from jobspy.jobstreet.util import parse_salary_string
from jobspy.model import (
    Scraper,
    ScraperInput,
    Site,
    JobPost,
    Location,
    JobResponse,
    Compensation,
    CompensationInterval,
)
from jobspy.util import create_logger

log = create_logger("JobStreet")

class JobStreet(Scraper):
    def __init__(self, proxies: list[str] | str | None = None, ca_cert: str | None = None, user_agent: str | None = None):
        print("DEBUG: JobStreet Class Initialized")
        super().__init__(Site.JOBSTREET, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        
        print("DEBUG: Creating CloudScraper Instance...")
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        if self.proxies:
            print(f"DEBUG: Setting Proxies: {self.proxies}")
            self.scraper.proxies = self.proxies
        else:
            print("DEBUG: No Proxies set.")

        # <--- NEW: LOAD COOKIES LOGIC --->
        self._load_cookies()
        
        self.country_code = None

    def _load_cookies(self):
        """
        Loads cookies from jobspy/config/jobstreet.json
        """
        try:
            # 1. Get the directory of THIS file (jobspy/jobstreet)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 2. Go up 1 level to 'jobspy' folder
            jobspy_dir = os.path.dirname(current_dir)
            
            # 3. Build path to config/jobstreet.json
            cookie_file = os.path.join(jobspy_dir, "config", "jobstreet.json")
            
            print(f"DEBUG: Looking for cookies at: {cookie_file}")

            if os.path.exists(cookie_file):
                with open(cookie_file, 'r') as f:
                    cookies_list = json.load(f)
                
                print(f"DEBUG: Found {len(cookies_list)} cookies.")
                
                # Load cookies into CloudScraper
                for cookie in cookies_list:
                    # CRITICAL: Ensure the domain matches the site you are scraping!
                    # If your JSON has ".glints.com", it won't work for ".jobstreet.com"
                    self.scraper.cookies.set(
                        cookie.get('name'), 
                        cookie.get('value'), 
                        domain=cookie.get('domain', ''),
                        path=cookie.get('path', '/')
                    )
                print("DEBUG: Cookies loaded successfully.")
            else:
                print(f"DEBUG: Cookie file NOT FOUND at {cookie_file}")
                
        except Exception as e:
            print(f"DEBUG: Error loading cookies: {e}")

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        print("DEBUG: >>> STARTING SCRAPE METHOD <<<")
        print(f"DEBUG: Search Term: {scraper_input.search_term}")
        print(f"DEBUG: Location: {scraper_input.location}")
        
        job_list = []
        
        # 1. Determine Country Code
        try:
            if isinstance(scraper_input.country.value, tuple):
                 self.country_code = scraper_input.country.value[1].split(":")[0].lower()
            else:
                 self.country_code = scraper_input.country.value.lower()
        except:
            self.country_code = "id"
        
        print(f"DEBUG: Resolved Country Code: {self.country_code}")

        # Pagination setup
        jobs_per_page = 30
        start_page = (scraper_input.offset // jobs_per_page) + 1
        total_needed = scraper_input.results_wanted
        max_pages = start_page + math.ceil(total_needed / jobs_per_page)
        
        current_count = 0
        print(f"DEBUG: Paging from {start_page} to {max_pages}")

        for page in range(start_page, max_pages + 1):
            if current_count >= total_needed:
                print("DEBUG: Reached total needed jobs. Stopping.")
                break
            
            # 2. Construct URL
            work_slug = scraper_input.search_term.replace(" ", "-") if scraper_input.search_term else "jobs"
            loc_slug = scraper_input.location.replace(" ", "-") if scraper_input.location else "anywhere"
            
            if self.country_code in DOMAIN_MAP:
                url_template = DOMAIN_MAP[self.country_code]
            else:
                url_template = DEFAULT_URL_TEMPLATE
            
            url = url_template.format(country=self.country_code, work=work_slug, location=loc_slug)
            url += f"?page={page}"
            
            print(f"DEBUG: ------------------------------------------------")
            print(f"DEBUG: TARGET URL: {url}")
            
            parsed_uri = urlparse(url)
            base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

            try:
                # 3. Perform Request
                print("DEBUG: Sending Request via CloudScraper...")
                response = self.scraper.get(url)
                
                print(f"DEBUG: Response Status Code: {response.status_code}")
                
                if response.status_code == 404:
                    print("DEBUG: ERROR - 404 Not Found. Check URL structure.")
                    log.error(f"404 Not Found: {url}")
                    break

                if not response.ok:
                    print(f"DEBUG: ERROR - Request failed with status {response.status_code}")
                    break
                
                # 4. Check HTML Content
                html_len = len(response.text)
                print(f"DEBUG: Received HTML content (Length: {html_len} chars)")
                
                soup = BeautifulSoup(response.text, "html.parser")

                # Cloudflare Check
                page_text = soup.get_text()
                if "Just a moment..." in page_text or "Verify you are human" in page_text:
                    print("DEBUG: !!! BLOCKED BY CLOUDFLARE CHALLENGE !!!")
                    log.error("Blocked by Cloudflare challenge.")
                    break
                
                # 5. Extract Job Cards
                job_cards = soup.find_all("article", attrs={"data-automation": "normalJob"})
                print(f"DEBUG: Found {len(job_cards)} job cards on page {page}")
                
                if not job_cards:
                    print("DEBUG: No job cards found. Dumping first 500 chars of HTML for inspection:")
                    print(soup.prettify()[:500])
                    break

                for i, card in enumerate(job_cards):
                    if current_count >= total_needed:
                        break

                    print(f"DEBUG: Processing card {i+1}...")
                    job = self._process_job_card(card, base_domain)
                    if job:
                        print(f"DEBUG:   -> Success: {job.title} at {job.company_name}")
                        job_list.append(job)
                        current_count += 1
                    else:
                        print("DEBUG:   -> Failed to parse card.")
                        
            except Exception as e:
                print(f"DEBUG: CRITICAL EXCEPTION on page {page}: {e}")
                log.error(f"Error scraping page {page}: {str(e)}")
                break

        print(f"DEBUG: >>> FINISHED SCRAPE. Total jobs found: {len(job_list)} <<<")
        return JobResponse(jobs=job_list)

    def _process_job_card(self, card, base_domain) -> JobPost | None:
        try:
            # Title
            title_tag = card.find("a", attrs={"data-automation": "jobTitle"})
            title = title_tag.get_text(strip=True) if title_tag else None
            
            # URL
            job_url = None
            if title_tag and title_tag.has_attr('href'):
                raw_link = title_tag['href']
                if raw_link.startswith("http"):
                    job_url = raw_link
                else:
                    job_url = f"{base_domain}{raw_link}"
            
            # ID
            job_id = None
            if job_url:
                clean_url = job_url.split("?")[0]
                parts = clean_url.split("-")
                if parts:
                    job_id = parts[-1]

            # Company
            company_tag = card.find("a", attrs={"data-automation": "jobCompany"})
            company_name = company_tag.get_text(strip=True) if company_tag else None
            
            # Location
            location_tags = card.find_all("a", attrs={"data-automation": "jobLocation"})
            location_text = ", ".join([tag.get_text(strip=True) for tag in location_tags]) if location_tags else None
            
            # Salary
            salary_tag = card.find("span", attrs={"data-automation": "jobSalary"})
            salary_text = salary_tag.get_text(strip=True) if salary_tag else None
            
            compensation = None
            if salary_text and salary_text != "N/A":
                min_amt, max_amt, curr, interval_str = parse_salary_string(salary_text)
                if min_amt or max_amt:
                    interval_enum = None
                    if interval_str == "monthly": interval_enum = CompensationInterval.MONTHLY
                    elif interval_str == "yearly": interval_enum = CompensationInterval.YEARLY
                    
                    compensation = Compensation(
                        interval=interval_enum,
                        min_amount=min_amt,
                        max_amount=max_amt,
                        currency=curr
                    )

            # Logo
            logo_container = card.find("div", attrs={"data-automation": "company-logo-container"})
            logo_img = logo_container.find("img") if logo_container else None
            company_logo = logo_img["src"] if logo_img and logo_img.has_attr("src") else None

            return JobPost(
                id=f"js-{job_id}" if job_id else None,
                title=title,
                company_name=company_name,
                job_url=job_url,
                location=Location(city=location_text, country=self.country_code),
                compensation=compensation,
                job_type=[],
                company_logo=company_logo,
                description=None,
                date_posted=None
            )

        except Exception as e:
            print(f"DEBUG: Error inside _process_job_card: {e}")
            return None