from flask import Flask, request, jsonify, redirect
from jobspy import scrape_jobs
from jobspy.model import Country
from flasgger import Swagger
import json
import pandas as pd

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
          properties:
            search_term: { type: string, example: React Developer }
            location: { type: string, example: Manila }
            site_name:
              type: array
              items: { type: string }
              example: ["linkedin", "indeed"]
            results_wanted: { type: integer, example: 10 }
            country: { type: string, example: PHILIPPINES }
    responses:
      200:
        description: Job results
    """
    try:
        data = request.get_json(force=True)
        search_term = data.get("search_term")
        location = data.get("location")
        results_wanted = int(data.get("results_wanted", 10))
        country = data.get("country", "USA")
        site_name = data.get("site_name", ["linkedin", "indeed"])

        if not search_term or not location:
            return jsonify({"error": "search_term and location are required"}), 400

        # Normalize site_name for Vercel JSON weirdness
        if isinstance(site_name, str):
            try:
                site_name = json.loads(site_name)
            except Exception:
                site_name = [s.strip() for s in site_name.split(",") if s.strip()]

        # Ensure it's a list
        if not isinstance(site_name, list):
            site_name = [str(site_name)]

        jobs_df = scrape_jobs(
            site_name=site_name,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            country_indeed=country,
            linkedin_fetch_description=True,
        )

        if jobs_df is None or not isinstance(jobs_df, pd.DataFrame):
            return jsonify({"error": "No job data returned."}), 500

        jobs = jobs_df.to_dict(orient="records")
        return jsonify({"jobs": jobs, "count": len(jobs)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    #return jsonify({"message": "Sanity CHECK"})
    return redirect("/apidocs")


if __name__ == "__main__":
    app.run(debug=True)
