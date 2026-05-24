import json
import logging
import os
import re
import time
from pathlib import Path
from threading import Lock

import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from google.api_core import exceptions as google_exceptions

from errors import (
    CONTENT_BLOCKED,
    GENERATION_FAILED,
    INVALID_API_KEY,
    INVALID_JSON_BODY,
    JOB_TITLE_TOO_LONG,
    MISSING_API_KEY,
    MISSING_JOB_TITLE,
    MODEL_UNAVAILABLE,
    PARSE_FAILED,
    QUOTA_EXCEEDED,
    RATE_LIMITED,
    RESPONSE_TRUNCATED,
    UPSTREAM_TIMEOUT,
    ApiError,
)

load_dotenv()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# One model = one Gemini call per click (free tier ~5 RPM).
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
FALLBACK_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash")
ENABLE_MODEL_FALLBACK = os.getenv("GEMINI_ENABLE_FALLBACK", "false").lower() in (
    "1",
    "true",
    "yes",
)
GEMINI_MIN_INTERVAL_SEC = float(os.getenv("GEMINI_MIN_INTERVAL_SEC", "12"))
_last_gemini_by_client: dict[str, float] = {}
_gemini_interval_lock = Lock()

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def _error_response(err: ApiError):
    return jsonify({"error": err.to_dict()}), err.http_status


def _parse_questions(text: str | None) -> list[str]:
    if not text or not text.strip():
        raise ValueError("Empty model response")

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text.strip())

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        lines = [
            line.strip(" \t-•0123456789.")
            for line in text.splitlines()
            if line.strip()
        ]
        questions = [line for line in lines if len(line) > 10]
        if len(questions) >= 3:
            return questions[:3]
        raise ValueError("Could not parse questions from plain text")

    if isinstance(data, dict):
        data = data.get("questions", data.get("interview_questions", []))
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of questions")

    questions = [str(q).strip() for q in data if str(q).strip()]
    if len(questions) < 3:
        raise ValueError(f"Expected 3 questions, got {len(questions)}")
    return questions[:3]


def _models_to_try() -> list[str]:
    """Return models to call. Default is a single model to respect free-tier RPM (5/min)."""
    primary = GEMINI_MODEL or "gemini-2.5-flash"
    if not ENABLE_MODEL_FALLBACK:
        return [primary]

    seen: set[str] = set()
    ordered: list[str] = []
    for name in (primary, *FALLBACK_MODELS):
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _map_gemini_exception(exc: Exception) -> ApiError:
    if isinstance(exc, google_exceptions.Unauthenticated):
        return INVALID_API_KEY
    if isinstance(exc, google_exceptions.PermissionDenied):
        return INVALID_API_KEY
    if isinstance(exc, google_exceptions.ResourceExhausted):
        return QUOTA_EXCEEDED
    if isinstance(exc, google_exceptions.NotFound):
        return MODEL_UNAVAILABLE
    if isinstance(exc, google_exceptions.InvalidArgument):
        msg = str(exc).lower()
        if "api key" in msg or "api_key" in msg:
            return INVALID_API_KEY
        if "model" in msg:
            return MODEL_UNAVAILABLE
        return GENERATION_FAILED
    if isinstance(exc, google_exceptions.DeadlineExceeded):
        return UPSTREAM_TIMEOUT
    if isinstance(exc, google_exceptions.GoogleAPIError):
        return GENERATION_FAILED
    return GENERATION_FAILED


def _generate_with_model(model_name: str, job_title: str) -> list[str]:
    model = genai.GenerativeModel(model_name)
    prompt = f"""You are an expert technical interviewer and hiring manager.

Generate exactly 3 thoughtful, role-specific interview questions for this job title: "{job_title}"

Requirements:
- Each question should probe real skills, judgment, or experience relevant to the role
- Avoid generic questions like "tell me about yourself" or "what are your strengths"
- Vary the focus (e.g. technical depth, collaboration, trade-offs, past impact)
- Each question must be under 220 characters (concise but specific)
- Questions should be answerable in a 3–5 minute response

Return JSON only in this exact shape:
{{"questions": ["question 1", "question 2", "question 3"]}}"""

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 2048,
            "response_mime_type": "application/json",
        },
    )

    if not response.candidates:
        feedback = getattr(response, "prompt_feedback", None)
        block_reason = getattr(feedback, "block_reason", None) if feedback else None
        if block_reason:
            raise ValueError(f"blocked:{block_reason}")
        raise ValueError("No response candidates")

    candidate = response.candidates[0]
    finish = getattr(candidate, "finish_reason", None)
    finish_name = finish.name if hasattr(finish, "name") else str(finish)
    if finish_name in ("SAFETY", "RECITATION", "BLOCKLIST"):
        raise ValueError(f"blocked:{finish_name}")
    if "MAX_TOKENS" in finish_name:
        raise ValueError("truncated:max_tokens")

    text = response.text
    return _parse_questions(text)


def _enforce_client_interval() -> None:
    if GEMINI_MIN_INTERVAL_SEC <= 0:
        return
    client = (
        request.headers.get("X-Forwarded-For", request.remote_addr or "local")
        .split(",")[0]
        .strip()
    )
    now = time.monotonic()
    with _gemini_interval_lock:
        last = _last_gemini_by_client.get(client, 0.0)
        elapsed = now - last
        if elapsed < GEMINI_MIN_INTERVAL_SEC:
            wait = int(GEMINI_MIN_INTERVAL_SEC - elapsed) + 1
            raise ApiErrorException(
                ApiError(
                    code=RATE_LIMITED.code,
                    message=f"Please wait {wait} seconds before trying again.",
                    hint=RATE_LIMITED.hint,
                    http_status=RATE_LIMITED.http_status,
                )
            )
        _last_gemini_by_client[client] = now


def _generate_questions(job_title: str) -> list[str]:
    if not GEMINI_API_KEY:
        raise ApiErrorException(MISSING_API_KEY)

    _enforce_client_interval()
    models = _models_to_try()

    # Never burn multiple RPM on quota/auth errors — fail immediately.
    no_retry_codes = {
        QUOTA_EXCEEDED.code,
        INVALID_API_KEY.code,
        MISSING_API_KEY.code,
        CONTENT_BLOCKED.code,
    }

    for model_name in models:
        try:
            logger.info(
                "Gemini call 1/%d for %r (model=%s)",
                len(models),
                job_title,
                model_name,
            )
            return _generate_with_model(model_name, job_title)
        except ApiErrorException:
            raise
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("blocked:"):
                raise ApiErrorException(CONTENT_BLOCKED) from exc
            if msg.startswith("truncated:"):
                raise ApiErrorException(RESPONSE_TRUNCATED) from exc
            # Do not call another model on parse failure — that triples API usage.
            logger.warning("Parse failed for model %s: %s", model_name, exc)
            raise ApiErrorException(PARSE_FAILED) from exc
        except Exception as exc:
            mapped = _map_gemini_exception(exc)
            if mapped.code in no_retry_codes:
                raise ApiErrorException(mapped) from exc
            if (
                ENABLE_MODEL_FALLBACK
                and mapped.code == MODEL_UNAVAILABLE.code
                and model_name != models[-1]
            ):
                logger.warning("Model %s unavailable, trying fallback", model_name)
                continue
            raise ApiErrorException(mapped) from exc

    raise ApiErrorException(GENERATION_FAILED)


class ApiErrorException(Exception):
    def __init__(self, api_error: ApiError):
        self.api_error = api_error
        super().__init__(api_error.message)


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    if filename.startswith("api/"):
        return _error_response(
            ApiError(
                code="NOT_FOUND",
                message="That endpoint does not exist.",
                http_status=404,
            )
        )
    return send_from_directory(FRONTEND_DIR, filename)


@app.post("/api/questions")
def questions():
    if not request.is_json:
        return _error_response(INVALID_JSON_BODY)

    payload = request.get_json(silent=True)
    if payload is None:
        return _error_response(INVALID_JSON_BODY)

    job_title = (payload.get("jobTitle") or payload.get("job_title") or "").strip()

    if not job_title:
        return _error_response(MISSING_JOB_TITLE)
    if len(job_title) > 120:
        return _error_response(JOB_TITLE_TOO_LONG)

    try:
        generated = _generate_questions(job_title)
        return jsonify({"jobTitle": job_title, "questions": generated})
    except ApiErrorException as exc:
        return _error_response(exc.api_error)
    except Exception:
        logger.exception("Unhandled error generating questions for %r", job_title)
        return _error_response(GENERATION_FAILED)


@app.get("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "geminiConfigured": bool(GEMINI_API_KEY),
            "model": GEMINI_MODEL,
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
