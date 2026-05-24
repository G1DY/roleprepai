"""Structured API errors with stable codes and user-facing copy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiError:
    code: str
    message: str
    hint: str | None = None
    http_status: int = 400

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.hint:
            body["hint"] = self.hint
        return body


# --- Client / validation ---

MISSING_JOB_TITLE = ApiError(
    code="MISSING_JOB_TITLE",
    message="Enter a job title to generate questions.",
    hint="Examples: Senior Backend Engineer, Product Designer, Data Analyst.",
    http_status=400,
)

JOB_TITLE_TOO_LONG = ApiError(
    code="JOB_TITLE_TOO_LONG",
    message="Job title is too long.",
    hint="Keep it under 120 characters — a role name, not a full job description.",
    http_status=400,
)

INVALID_JSON_BODY = ApiError(
    code="INVALID_JSON_BODY",
    message="Request body must be valid JSON.",
    hint='Send {"jobTitle": "Your Role"} with Content-Type: application/json.',
    http_status=400,
)

# --- Server configuration ---

MISSING_API_KEY = ApiError(
    code="MISSING_API_KEY",
    message="The AI service is not configured on this server.",
    hint="Add GEMINI_API_KEY to backend/.env, then restart the application.",
    http_status=503,
)

# --- Upstream (Gemini) ---

INVALID_API_KEY = ApiError(
    code="INVALID_API_KEY",
    message="The Gemini API key was rejected.",
    hint="Check GEMINI_API_KEY in backend/.env — create or copy a key from Google AI Studio.",
    http_status=503,
)

QUOTA_EXCEEDED = ApiError(
    code="QUOTA_EXCEEDED",
    message="Gemini rate or usage limit reached.",
    hint="Free tier allows ~5 requests per minute. Wait 60 seconds, then try once.",
    http_status=429,
)

RATE_LIMITED = ApiError(
    code="RATE_LIMITED",
    message="Please wait before generating again.",
    hint="This app allows one Gemini request every 12 seconds to stay within free-tier limits.",
    http_status=429,
)

MODEL_UNAVAILABLE = ApiError(
    code="MODEL_UNAVAILABLE",
    message="The configured AI model is unavailable.",
    hint="Set GEMINI_MODEL to gemini-2.0-flash or gemini-1.5-flash in .env.",
    http_status=503,
)

CONTENT_BLOCKED = ApiError(
    code="CONTENT_BLOCKED",
    message="Could not generate questions for that input.",
    hint="Try a standard job title without special characters or sensitive terms.",
    http_status=422,
)

UPSTREAM_TIMEOUT = ApiError(
    code="UPSTREAM_TIMEOUT",
    message="The AI service took too long to respond.",
    hint="Try again in a moment — generation usually completes within a few seconds.",
    http_status=504,
)

# --- Application logic ---

PARSE_FAILED = ApiError(
    code="PARSE_FAILED",
    message="Received an unexpected response from the AI service.",
    hint="Try generating again. If this persists, set GEMINI_MODEL=gemini-2.5-flash in .env.",
    http_status=502,
)

RESPONSE_TRUNCATED = ApiError(
    code="RESPONSE_TRUNCATED",
    message="The AI response was cut off before it finished.",
    hint="Click Generate again — this is usually fixed automatically on retry.",
    http_status=502,
)

GENERATION_FAILED = ApiError(
    code="GENERATION_FAILED",
    message="We could not generate interview questions right now.",
    hint="Check your connection and try again in a moment.",
    http_status=502,
)
