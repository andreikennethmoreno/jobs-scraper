from flask import Flask, request, jsonify, redirect  
from jobspy import scrape_jobs
from jobspy.model import Country
from flasgger import Swagger
from duckduckgo_search import DDGS
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
import google.generativeai as genai
import json
import re

app = Flask(__name__)
swagger = Swagger(app)

# Load .env variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("GOOGLE_CSE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# Initialize Gemini client
genai.configure(api_key=GEMINI_API_KEY)
gemini_client = genai.GenerativeModel("gemini-2.5-flash")

def extract_tech_from_gemini(desc: str):
    """Use Gemini to extract technologies mentioned in a job description."""
    if not desc:
        return []

    prompt = (
        "Extract all programming languages, frameworks, databases, tools, and cloud services "
        "mentioned in the following job description. "
        "Output ONLY a valid JSON array of technology names, e.g. [\"Python\", \"AWS\", \"React\"]. "
        "No explanations, no code blocks, just the JSON array.\n\n"
        f"Job Description:\n{desc}"
    )

    try:
        response = gemini_client.generate_content(prompt)
        text = response.text.strip()

        # Clean any code fences or garbage
        text = re.sub(r"^```(json)?|```$", "", text).strip()

        try:
            tech_list = json.loads(text)
        except json.JSONDecodeError:
            # fallback if not JSON, split by comma/newline
            tech_list = [t.strip().strip('"') for t in re.split(r"[,\\n]+", text) if t.strip()]

        # Clean duplicates
        tech_list = list(dict.fromkeys(tech_list))
        return tech_list

    except Exception as e:
        print("Gemini error:", e)
        return []

def get_doc_link_google(tech):
    """Fetch the first Google search result for <tech> documentation."""
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(q=f"{tech} documentation", cx=CSE_ID, num=1).execute()
        if "items" in res:
            return res["items"][0]["link"]
    except Exception as e:
        print(f"Google search failed for {tech}: {e}")
    return None


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
        site_name=["linkedin", "indeed"],
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        country_indeed=country,
        linkedin_fetch_description=True
    )

    jobs = jobs_df.to_dict(orient="records")

    for job in jobs:
        desc = job.get("description", "")
        techs = extract_tech_from_gemini(desc)
        tech_mentions = [{"tech": t, "url": get_doc_link_google(t)} for t in techs]
        job["tech_mentions"] = tech_mentions
        job["salary_display"] = extract_salary(job)

    return jsonify({"jobs": jobs, "count": len(jobs)})

@app.route("/")
def index():
    return redirect("/apidocs")

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
