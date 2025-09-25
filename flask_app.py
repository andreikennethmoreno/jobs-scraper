from flask import Flask, render_template, request
import pandas as pd
from jobspy import scrape_jobs

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    jobs = None
    if request.method == "POST":
        # get values from the form
        search_term = request.form.get("search_term")
        location = request.form.get("location")

        # run the scraper dynamically
        jobs_df = scrape_jobs(
            site_name=["indeed", "linkedin"],  # choose which sites
            search_term=search_term,
            location=location,
            results_wanted=10,
            country_indeed="USA"
        )

        # save to CSV (optional)
        jobs_df.to_csv("jobs.csv", index=False)

        # convert to dict for template
        jobs = jobs_df.to_dict(orient="records")

    return render_template("home.html", jobs=jobs)

if __name__ == "__main__":
    app.run(debug=True)
