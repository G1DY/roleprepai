import json
import os
import re
from pathlib import Path

import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

load_dotenv()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def _parse_questions(text: str) -> list[str]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        lines = [line.strip(" \t-•0123456789.") for line in text.splitlines() if line.strip()]
        return [line for line in lines if len(line) > 10][:3]

    if isinstance(data, dict):
        data = data.get("questions", data.get("interview_questions", []))
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of questions")

    questions = [str(q).strip() for q in data if str(q).strip()]
    if len(questions) < 3:
        raise ValueError("Model returned fewer than 3 questions")
    return questions[:3]


def _generate_questions(job_title: str) -> list[str]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured on the server")

    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = f"""You are an expert technical interviewer and hiring manager.

Generate exactly 3 thoughtful, role-specific interview questions for this job title: "{job_title}"

Requirements:
- Each question should probe real skills, judgment, or experience relevant to the role
- Avoid generic questions like "tell me about yourself" or "what are your strengths"
- Vary the focus (e.g. technical depth, collaboration, trade-offs, past impact)
- Questions should be answerable in a 3–5 minute response

Return ONLY valid JSON in this exact shape, with no markdown or extra text:
{{"questions": ["question 1", "question 2", "question 3"]}}"""

    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.7, "max_output_tokens": 1024},
    )
    return _parse_questions(response.text)


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    if filename.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(FRONTEND_DIR, filename)


@app.post("/api/questions")
def questions():
    payload = request.get_json(silent=True) or {}
    job_title = (payload.get("jobTitle") or payload.get("job_title") or "").strip()

    if not job_title:
        return jsonify({"error": "Job title is required"}), 400
    if len(job_title) > 120:
        return jsonify({"error": "Job title must be 120 characters or fewer"}), 400

    try:
        generated = _generate_questions(job_title)
        return jsonify({"jobTitle": job_title, "questions": generated})
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        app.logger.exception("Failed to generate questions")
        return jsonify({"error": "Could not generate questions. Please try again."}), 502


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "geminiConfigured": bool(GEMINI_API_KEY)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
