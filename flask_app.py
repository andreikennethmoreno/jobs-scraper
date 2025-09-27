from flask import Flask, render_template, request, jsonify
from jobspy import scrape_jobs
from jobspy.model import Country
from flasgger import Swagger
import re

app = Flask(__name__)

# Setup Swagger UI
swagger = Swagger(app)

# --- Tech dictionary ---
TECH_LINKS = {
    "C#": "https://learn.microsoft.com/en-us/dotnet/csharp/",
    "Java": "https://docs.oracle.com/javase/tutorial/",
    "JavaScript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
    "React": "https://react.dev/",
    "Python": "https://docs.python.org/3/",
    "Go": "https://go.dev/doc/",
    "Ruby": "https://www.ruby-lang.org/en/documentation/",
    "Scala": "https://docs.scala-lang.org/"
}

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
    # --- First try JobSpy structured fields ---
    min_amt = job.get("compensation_min")
    max_amt = job.get("compensation_max")
    currency = job.get("compensation_currency")

    currency_map = {
        "USD": "$",
        "PHP": "₱",
        "EUR": "€",
        "GBP": "£",
    }

    symbol = currency_map.get(currency, currency or "")

    if min_amt and max_amt:
        return f"{symbol}{min_amt:,.0f} - {symbol}{max_amt:,.0f}"
    elif min_amt:
        return f"{symbol}{min_amt:,.0f}+"

    # --- Fallback: parse salary mention from description ---
    desc = job.get("description", "")
    if not desc:
        return None

    # Try PHP patterns (e.g. ₱20,000 - ₱40,000 or PHP 25,000/month)
    peso_match = re.search(r"(?:₱|PHP\s?)\s?[\d,]+(?:\s*-\s*(?:₱|PHP\s?)?[\d,]+)?", desc, re.I)
    if peso_match:
        return peso_match.group(0)

    # USD fallback (e.g. $122,100 - $134,400)
    usd_match = re.search(r"\$[\d,]+(?:\s*-\s*\$[\d,]+)?", desc)
    if usd_match:
        return usd_match.group(0)

    # Generic "salary/compensation/pay ... $/₱"
    generic_match = re.search(r"(salary|compensation|pay).{0,50}(?:₱|PHP\s?|\$)[\d,]+", desc, re.I)
    if generic_match:
        return generic_match.group(0)

    return None


@app.route("/", methods=["GET", "POST"])
def home():
    jobs = None
    countries = [c.name for c in Country]

    if request.method == "POST":
        search_term = request.form.get("search_term")
        location = request.form.get("location")
        results_wanted = int(request.form.get("results_wanted", 10))
        country = request.form.get("country", "USA")

        jobs_df = scrape_jobs(
            site_name=["linkedin", "indeed"],
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            country_indeed=country,
            linkedin_fetch_description=True
        )

        jobs = jobs_df.to_dict(orient="records")

        # annotate each job with tech stack + salary
        for job in jobs:
            job["tech_mentions"] = extract_tech(job.get("description", ""))
            job["salary_display"] = extract_salary(job)

    return render_template("home.html", jobs=jobs, countries=countries)

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

    # add tech + salary info
    for job in jobs:
        job["tech_mentions"] = extract_tech(job.get("description", ""))
        job["salary_display"] = extract_salary(job)

    return jsonify({"jobs": jobs, "count": len(jobs)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
