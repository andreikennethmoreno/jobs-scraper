from flask import Flask, render_template, request, jsonify
from jobspy import scrape_jobs
from jobspy.model import Country
from flasgger import Swagger

app = Flask(__name__)

# Setup Swagger UI
swagger = Swagger(app)

@app.route("/", methods=["GET", "POST"])
def home():
    jobs = None
    countries = [c.name for c in Country]  # pass country names to template 

    if request.method == "POST":
        # get values from the form
        search_term = request.form.get("search_term")
        location = request.form.get("location")
        results_wanted = int(request.form.get("results_wanted", 10))
        country = request.form.get("country", "USA")

        jobs_df = scrape_jobs(
            site_name=["linkedin"],
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            country_indeed=country,
            linkedin_fetch_description=True 
        )

        jobs_df.to_csv("jobs.csv", index=False)
        jobs = jobs_df.to_dict(orient="records")

    return render_template("home.html", jobs=jobs, countries=countries)


@app.route("/api/countries", methods=["GET"])
def get_countries():
    """
    Get Supported Countries
    ---
    responses:
      200:
        description: List of available countries
        schema:
          type: object
          properties:
            countries:
              type: array
              items:
                type: string
    """
    countries = [c.name for c in Country]
    return jsonify({"countries": countries})


@app.route("/api/jobs", methods=["POST"])
def get_jobs():
    """
    Scrape Jobs
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
              example: "Software Engineer"
            location:
              type: string
              example: "New York"
            results_wanted:
              type: integer
              example: 5
            country:
              type: string
              example: "USA"
    responses:
      200:
        description: Job results
        schema:
          type: object
          properties:
            count:
              type: integer
            jobs:
              type: array
              items:
                type: object
                properties:
                  site:
                    type: string
                  title:
                    type: string
                  company:
                    type: string
                  location:
                    type: string
                  date_posted:
                    type: string
                  job_type:
                    type: string
                  description:
                    type: string
                  job_url:
                    type: string
    """
    data = request.get_json()

    search_term = data.get("search_term")
    location = data.get("location")
    results_wanted = int(data.get("results_wanted", 10))
    country = data.get("country", "USA")

    if not search_term or not location:
        return jsonify({"error": "search_term and location are required"}), 400

    try:
        jobs_df = scrape_jobs(
            site_name=["linkedin"],
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            country_indeed=country,
            linkedin_fetch_description=True
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    jobs = jobs_df.to_dict(orient="records")
    return jsonify({"jobs": jobs, "count": len(jobs)})


if __name__ == "__main__":
    app.run(debug=True)
