from flask import Flask, render_template, request
import pandas as pd
from jobspy import scrape_jobs
from jobspy.model import Country  # import Country enum

app = Flask(__name__)

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

        # run the scraper dynamically
        jobs_df = scrape_jobs(
            site_name=["indeed", "linkedin"],  # choose which sites
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            country_indeed=country
        )

        # save to CSV (optional)
        jobs_df.to_csv("jobs.csv", index=False)

        # convert to dict for template
        jobs = jobs_df.to_dict(orient="records")

    return render_template("home.html", jobs=jobs, countries=countries)

    

if __name__ == "__main__":
    app.run(debug=True)
