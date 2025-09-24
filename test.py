import csv
from jobspy import scrape_jobs

jobs = scrape_jobs(
    site_name=["indeed", "linkedin"],   # websites to scrape
    search_term="software engineer",    # job title / keyword
    location="San Francisco, CA",       # location
    results_wanted=10,                  # how many results to fetch
    country_indeed="USA"
)

print(jobs.head())  # print first few rows
jobs.to_csv("jobs.csv", quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
print("Saved jobs to jobs.csv ✅")
