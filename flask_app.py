from flask import Flask, request, jsonify, redirect  
from jobspy import scrape_jobs
from jobspy.model import Country
from flasgger import Swagger
from duckduckgo_search import DDGS
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
import re

app = Flask(__name__)
swagger = Swagger(app)

# Load .env variables
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("GOOGLE_CSE_ID")

# Start with just a list of technologies
TECH_LIST = [
    "HTML", "CSS", "JavaScript", "TypeScript", "PHP", "Python", "Ruby", "SQL", "Node.js",
    "React", "Vue.js", "Angular", "Svelte", "Bootstrap", "Tailwind CSS",
    "Express.js", "Django", "Flask", "Laravel", "Ruby on Rails", "ASP.NET Core",
    "MySQL", "PostgreSQL", "SQLite", "MongoDB", "Firebase",
    "Git", "npm", "Yarn", "Webpack", "Vite", "REST API", "GraphQL"
]

def get_doc_link_google(tech):
    """Fetch the first Google search result for <tech> documentation"""
    service = build("customsearch", "v1", developerKey=API_KEY)
    res = service.cse().list(q=f"{tech} documentation", cx=CSE_ID).execute()
    if "items" in res:
        return res["items"][0]["link"]
    return None

# Build the dictionary dynamically
TECH_LINKS = {}
for tech in TECH_LIST:
    link = get_doc_link_google(tech)
    TECH_LINKS[tech] = link
    print(f"{tech} -> {link}")


def extract_tech(desc: str):
    """Extract keywords and map them to links."""
    if not desc:
        return []
    found = []
    for tech, url in TECH_LINKS.items():
        pattern = r"\b" + re.escape(tech) + r"\b"
        if re.search(pattern, desc, flags=re.IGNORECASE):
            found.append({"tech": tech, "url": url})
    return found

def extract_salary(job: dict):
    """Pull salary info from structured fields or description text."""
    min_amt = job.get("compensation_min")
    max_amt = job.get("compensation_max")
    currency = job.get("compensation_currency")

    currency_map = {"USD": "$", "PHP": "₱", "EUR": "€", "GBP": "£"}
    symbol = currency_map.get(currency, currency or "")

    if min_amt and max_amt:
        return f"{symbol}{min_amt:,.0f} - {symbol}{max_amt:,.0f}"
    elif min_amt:
        return f"{symbol}{min_amt:,.0f}+"

    desc = job.get("description", "")
    if not desc:
        return None

    peso_match = re.search(r"(?:₱|PHP\s?)\s?[\d,]+(?:\s*-\s*(?:₱|PHP\s?)?[\d,]+)?", desc, re.I)
    if peso_match:
        return peso_match.group(0)

    usd_match = re.search(r"\$[\d,]+(?:\s*-\s*\$[\d,]+)?", desc)
    if usd_match:
        return usd_match.group(0)

    generic_match = re.search(r"(salary|compensation|pay).{0,50}(?:₱|PHP\s?|\$)[\d,]+", desc, re.I)
    if generic_match:
        return generic_match.group(0)

    return None

@app.route("/api/countries", methods=["GET"])
def get_countries():
    """Get Supported Countries
    ---
    responses:
      200:
        description: List of available countries
    """
    countries = [c.name for c in Country]
    return jsonify({"countries": countries})

@app.route("/api/jobs", methods=["POST"])
def get_jobs():
    """Scrape Jobs
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - search_term
            - location
          properties:
            search_term:
              type: string
            location:
              type: string
            results_wanted:
              type: integer
            country:
              type: string
    responses:
      200:
        description: Job results
    """
    data = request.get_json()
    search_term = data.get("search_term")
    location = data.get("location")
    results_wanted = int(data.get("results_wanted", 10))
    country = data.get("country", "USA")

    if not search_term or not location:
        return jsonify({"error": "search_term and location are required"}), 400

    jobs_df = scrape_jobs(
        site_name=["linkedin"],
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        country_indeed=country,
        linkedin_fetch_description=True
    )

    jobs = jobs_df.to_dict(orient="records")

    for job in jobs:
        job["tech_mentions"] = extract_tech(job.get("description", ""))
        job["salary_display"] = extract_salary(job)

    return jsonify({"jobs": jobs, "count": len(jobs)})

@app.route("/")
def index():
    return redirect("/apidocs")

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
