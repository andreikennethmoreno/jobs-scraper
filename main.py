from flask import Flask, request, jsonify, redirect
from jobspy import scrape_jobs
from jobspy.model import Country
from flasgger import Swagger
from jobspy.util import get_next_client
import json
import pandas as pd
from datetime import datetime
import re
import ast


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
    Generate a custom course roadmap where each Major Tech gets its own course.
    ---
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            job_id:
              type: string
            extracted_salary:
              type: string
            tech_mentioned:
              type: object
              properties:
                major:
                  type: array
                  items:
                    type: string
                minor:
                  type: array
                  items:
                    type: string
          example:
            extracted_salary: "$60,000 - $80,000"
            job_id: "li-1234567890"
            tech_mentioned:
              major:
                - "Python"
                - "Django"
                - "React"
                - "PostgreSQL"
              minor:
                - "Docker"
                - "AWS"
                - "Git"
    responses:
      200:
        description: Suggested course roadmap
        schema:
          type: object
          properties:
            title: { type: string }
            description: { type: string }
            difficulty_level: { type: string }
            course_roadmap:
              type: object
              properties:
                major:
                  type: array
                  items:
                    type: object
                minor:
                  type: array
                  items:
                    type: object
          example:
            title: "Backend Developer Roadmap"
            description: "Curated path for Backend Developer"
            difficulty_level: "Intermediate"
            course_roadmap:
              major:
                - course_title: "Python Mastery"
                  course_tech: "Python"
                  course_objective: "Enhance backend logic capabilities."
                  course_description: "about Python Mastery"
              minor:
                - course_title: "Docker Basics"
                  course_tech: "Docker"
                  course_objective: "Improve deployment workflow."
                  course_description: "about Docker Basics"
    """
    import json
    import re
    import ast

    try:
        data = request.get_json(force=True)
        job_title = data.get("title", "Unknown Job")
        description = data.get("description", "")
        
        # 🟢 FIX START: Better Input Handling -----------------------
        tech_data = data.get("tech_mentioned", [])
        
        # 1. Handle String input (legacy/swagger test)
        if isinstance(tech_data, str):
            try:
                tech_data = json.loads(tech_data)
            except:
                tech_data = [tech_data]
        
        # 2. 🟢 CRITICAL FIX: Allow both List AND Dict
        if not isinstance(tech_data, (list, dict)):
            tech_data = [] # Only wipe if it's junk data
        
        # 3. Create string representation for the prompt
        # This preserves the { major: [], minor: [] } structure string
        tech_string = json.dumps(tech_data, indent=2)
        # 🟢 FIX END -----------------------------------------------

        client = get_next_client()

        # 🟢 UPDATED PROMPT to understand the structure
        prompt = f"""
You are an expert Technical Curriculum Developer.

**CONTEXT:**
Job Title: {job_title}
Job Description: {description}

**REQUIRED TECHNOLOGIES (Input):**
{tech_string}

**INSTRUCTIONS:**
1. **Analyze Input:** - If "REQUIRED TECHNOLOGIES" is a simple list, generate courses for every item.
   - If "REQUIRED TECHNOLOGIES" is an object with "major" and "minor" lists, READ BOTH LISTS.
   - **CRITICAL:** You must generate a course for EVERY item found in the input.

2. **Categorize & Output:**
   - Organize the output courses into "major" and "minor" arrays.
   - Use the input's categorization as a guide, but ensure every tech is covered.

3. **Difficulty:** - If job title contains "Senior" -> Advanced.
   - If "Junior" -> Beginner.
   - Otherwise -> Intermediate.

**Output Format (JSON Only):**
{{
  "title": "{job_title} Roadmap",
  "description": "Curated path for {job_title}",
  "difficulty_level": "Beginner | Intermediate | Advanced",
  "course_roadmap": {{
      "major": [
          {{ "course_title": "Title", "course_tech": "Tech Name", "course_objective": "Objective", "course_description": "about {{course_title}}" }}
      ],
      "minor": [
          {{ "course_title": "Title", "course_tech": "Tech Name", "course_objective": "Objective", "course_description": "about {{course_title}}" }}
      ]
  }}
}}
"""

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
        except Exception:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )

        raw_text = getattr(response, "text", "{}").strip()
        print("Raw AI response:", repr(raw_text))

        cleaned_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.IGNORECASE).strip()

        try:
            roadmap_json = json.loads(cleaned_text)
        except json.JSONDecodeError:
            try:
                roadmap_json = ast.literal_eval(cleaned_text)
            except Exception:
                roadmap_json = {
                    "title": f"{job_title} Roadmap",
                    "description": "Custom roadmap could not be generated",
                    "course_roadmap": {"major": [], "minor": []}
                }

        return jsonify(roadmap_json)

    except Exception as e:
        return jsonify({
            "title": "Error", 
            "description": str(e), 
            "course_roadmap": {"major": [], "minor": []}
        }), 500



@app.route("/api/extract-job-info", methods=["POST"])
def extract_job_info():
    """
    Extract major/minor tech stack and salary from a job description.
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
        description: Extracted major/minor tech stack and salary information
        schema:
          type: object
          example:
            job_id: "li-1234567890"
            tech_mentioned:
              major: ["Python", "Django", "React", "PostgreSQL"]
              minor: ["Docker", "AWS", "Git"]
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
                "tech_mentioned": {},
                "extracted_salary": "Not specified"
            })

        client = get_next_client()

        # ... (keep your existing combined_prompt) ...
        combined_prompt = f"""
You are an assistant that analyzes a job description and extracts:
1. Required (major) technologies
2. Optional (minor) or nice-to-have technologies
3. Salary information

Respond with JSON only. Do not include explanations or markdown.

Instructions:
- "major" technologies = core skills required for the role, essential to perform the job, often repeated or emphasized.
- "minor" technologies = optional tools, nice-to-have skills, supporting tools, or low-importance extras mentioned only briefly.
- Only include actual technologies, frameworks, tools, or programming languages.
- If none are found, return empty arrays.

Job description:
{description}

Location: {location}
Country: {country}

Return JSON in the following format:
{{
  "tech_mentioned": {{
    "major": ["Python", "React", "TypeScript"],
    "minor": ["Excel", "Confluence"]
  }},
  "extracted_salary": "$60,000 - $80,000"
}}

If salary is not mentioned, set extracted_salary to "Not specified".
"""
        
        # Use the safe generator if you added the helper function, otherwise use standard
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=combined_prompt
            )
        except Exception:
             # Fallback to stable model if 2.5 is overloaded
             response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=combined_prompt
            )

        result_text = getattr(response, "text", "{}").strip()
        
        # Clean Markdown Code Fences (Important step to avoid JSON errors)
        result_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", result_text, flags=re.IGNORECASE).strip()

        print("Raw AI response:", repr(result_text))

        try:
            result_json = json.loads(result_text)
            
            # Get the tech_mentioned object
            tech_mentioned = result_json.get("tech_mentioned", {})

            # --- THE FIX IS HERE ---
            # We now check if it is a DICT (Object), not a List
            if not isinstance(tech_mentioned, dict):
                # If AI returns a list (legacy format), try to wrap it, otherwise empty dict
                if isinstance(tech_mentioned, list):
                    tech_mentioned = {"major": tech_mentioned, "minor": []}
                else:
                    tech_mentioned = {"major": [], "minor": []}
            # -----------------------

            extracted_salary = result_json.get("extracted_salary", "Not specified")

        except Exception as e:
            print(f"JSON Parse Error: {e}")
            tech_mentioned = {"major": [], "minor": []}
            
            # Fallback regex for salary
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
            "tech_mentioned": {"major": [], "minor": []},
            "extracted_salary": "Not specified",
            "error": str(e)
        })


@app.route("/")
def index():
    #return jsonify({"message": "Sanity CHECK"})
    return redirect("/apidocs")


if __name__ == "__main__":
    app.run(debug=True)
