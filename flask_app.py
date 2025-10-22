from flask import Flask, request, jsonify, redirect
from jobspy import scrape_jobs
from jobspy.model import Country
from flasgger import Swagger
import json

app = Flask(__name__)
swagger = Swagger(app)

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
              example: React Developer
            location:
              type: string
              example: Manila
            results_wanted:
              type: integer
              example: 10
            country:
              type: string
              example: PHILIPPINES
            site_name:
              type: array
              items:
                type: string
              example: ["linkedin", "indeed"]
    responses:
      200:
        description: Job results
    """
    data = request.get_json()

    search_term = data.get("search_term")
    location = data.get("location")
    results_wanted = int(data.get("results_wanted", 10))
    country = data.get("country", "USA")
    site_name = data.get("site_name", ["linkedin", "indeed"])

    # make sure site_name is a list (fix for production)
    if isinstance(site_name, str):
        try:
            site_name = json.loads(site_name)
        except:
            site_name = [site_name]

    if not search_term or not location:
        return jsonify({"error": "search_term and location are required"}), 400

    try:
        jobs_df = scrape_jobs(
            site_name=site_name,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            country_indeed=country,
            linkedin_fetch_description=True,
        )

        jobs = jobs_df.to_dict(orient="records")

        return jsonify({"jobs": jobs, "count": len(jobs)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return redirect("/apidocs")


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
