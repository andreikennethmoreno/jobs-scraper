from flask import Flask, request, jsonify, redirect
from jobspy import scrape_jobs
from jobspy.model import Country
from flasgger import Swagger
from jobspy.util import get_next_client
import json
import pandas as pd
from datetime import datetime

app = Flask(__name__)
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Job Scraper API 👔",
        "description": "An API for scraping jobs from Linked and Indeed sites using JobSpy.",
        "version": "1.0.0",
    },
    "basePath": "/api"
}

swagger = Swagger(app, template=swagger_template)


@app.route("/api/generate", methods=["POST"])
def generate_text():
    """
    Generate text using Google Gemini API
    ---
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            prompt:
              type: string
              example: "Explain how AI works in a few words"
    responses:
      200:
        description: Generated text response
        examples:
          application/json:
            prompt: "Explain how AI works in a few words"
            date_generated: "2025-11-04T12:00:00.000000"
            response: "AI mimics human learning using data and algorithms."
    """
    data = request.get_json(silent=True)
    if not data or "prompt" not in data:
        return jsonify({"error": "Missing 'prompt' field in JSON body"}), 400

    prompt = data["prompt"]

    try:
        client = get_next_client()  # rotate keys each request
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )

        return jsonify({
            "prompt": prompt,
            "date_generated": datetime.utcnow().isoformat(),
            "response": getattr(response, "text", "").strip(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        results_wanted = int(data.get("results_wanted", 5))
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


@app.route("/api/generate-course-roadmap", methods=["POST"])
def generate_course_roadmap():
    """
    Generate a custom course roadmap based on a job description.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          example:
            job_id: "li-1234567890"
            title: "Full Stack Developer"
            description: "We are looking for a Full Stack Developer proficient in Python, Django, React, and PostgreSQL. Responsibilities include building APIs, developing front-end applications, and integrating with cloud services. Experience with Docker, AWS, and Git is required. Salary: $60,000 - $80,000 per year."
            location: "Manila, Philippines"
            country: "PHILIPPINES"
    responses:
      200:
        description: Suggested course roadmap
        schema:
          type: object
          example:
            title: "Full Stack Developer Roadmap"
            description: "Custom roadmap to acquire skills for Full Stack Development"
            course_roadmap:
              - course_title: "Python Fundamentals"
                course_objective: "Learn core Python programming skills"
                course_description: "Covers Python syntax, data structures, and best practices."
              - course_title: "Django Web Development"
                course_objective: "Build web apps with Django"
                course_description: "Covers models, views, templates, REST API, and deployment."
              - course_title: "Frontend with React"
                course_objective: "Learn React and front-end development"
                course_description: "Covers components, state, hooks, and connecting to APIs."
    """
    import json
    import re

    data = request.get_json(force=True)
    job_title = data.get("title", "Unknown")
    description = data.get("description", "")

    client = get_next_client()

    prompt = f"""
You are an expert career coach. Given this job description:

{description}

Generate a course roadmap for someone who wants to qualify for this job. 
Focus on the actual technologies, programming languages, frameworks, and tools mentioned. 
Each course should cover a fundamental or beginner-friendly approach to that technology.

Requirements:
- Include at least 3 courses, but add more if there are extra relevant technologies/tools.
- Each course must have:
  - course_title
  - course_objective
  - course_description
- Each course should focus on practical, hands-on fundamentals.

Return strictly JSON ONLY, no markdown, no explanations.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    raw_text = getattr(response, "text", "{}").strip()
    print("Raw AI response:", repr(raw_text))

    # CLEAN AI OUTPUT: remove markdown code fences if present
    cleaned_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.IGNORECASE).strip()

    try:
        roadmap_json = json.loads(cleaned_text)
    except json.JSONDecodeError:
        # fallback: try safe eval in case AI used single quotes
        try:
            import ast
            roadmap_json = ast.literal_eval(cleaned_text)
        except Exception:
            roadmap_json = {
                "title": f"{job_title} Roadmap",
                "description": "Custom roadmap could not be generated",
                "course_roadmap": []
            }

    return jsonify(roadmap_json)




@app.route("/api/extract-job-info", methods=["POST"])
def extract_job_info():
    """
    Extract tech stack and salary from a single job description.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          example:
            job_id: "li-1234567890"
            title: "Full Stack Developer"
            description: "We are looking for a Full Stack Developer proficient in Python, Django, React, and PostgreSQL. Responsibilities include building APIs, developing front-end applications, and integrating with cloud services. Experience with Docker, AWS, and Git is required. Salary: $60,000 - $80,000 per year."
            location: "Manila, Philippines"
            country: "PHILIPPINES"
    responses:
      200:
        description: Tech stack array and salary
        schema:
          type: object
          example:
            job_id: "li-1234567890"
            tech_mentioned: ["Python", "Django", "React", "PostgreSQL", "Docker", "AWS", "Git"]
            extracted_salary: "$60,000 - $80,000"
    """
    import re

    try:
        data = request.get_json(force=True)
        job_id = data.get("job_id", "unknown")
        description = data.get("description", "")
        location = data.get("location", "Unknown")
        country = data.get("country", "USA")

        if not description:
            return jsonify({
                "job_id": job_id,
                "tech_mentioned": [],
                "extracted_salary": "Not specified"
            })

        client = get_next_client()

        # Combined prompt with strict JSON enforcement
        combined_prompt = f"""
You are an assistant that extracts tech stack and salary from a job description.
Respond with JSON only. Do not add explanations or markdown.

Job description:
{description}

Location: {location}
Country: {country}

Return JSON in the format:
{{
  "tech_mentioned": ["Python", "Django", "React"],
  "extracted_salary": "$60,000 - $80,000"
}}
If no technologies are mentioned, return an empty array for tech_mentioned.
If no salary is mentioned, return "Not specified" for extracted_salary.
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=combined_prompt
        )

        result_text = getattr(response, "text", "{}").strip()

        # Debug print to see raw AI output
        print("Raw AI response:", repr(result_text))

        # Try to parse AI output
        try:
            result_json = json.loads(result_text)
            tech_mentioned = result_json.get("tech_mentioned", [])
            if not isinstance(tech_mentioned, list):
                tech_mentioned = []
            extracted_salary = result_json.get("extracted_salary", "Not specified")
        except Exception:
            tech_mentioned = []

            # Fallback regex for salary extraction
            salary_match = re.search(
                r"[\$₱¥]\s?\d{1,3}(?:,\d{3})*(?:\s?-\s?[\$₱¥]?\d{1,3}(?:,\d{3})*)?",
                description
            )
            extracted_salary = salary_match.group(0) if salary_match else "Not specified"

        return jsonify({
            "job_id": job_id,
            "tech_mentioned": tech_mentioned,
            "extracted_salary": extracted_salary
        })

    except Exception as e:
        return jsonify({
            "job_id": data.get("job_id", "unknown"),
            "tech_mentioned": [],
            "extracted_salary": "Not specified",
            "error": str(e)
        })


@app.route("/")
def index():
    #return jsonify({"message": "Sanity CHECK"})
    return redirect("/apidocs")


if __name__ == "__main__":
    app.run(debug=True)
