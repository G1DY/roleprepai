const form = document.getElementById("question-form");
const jobInput = document.getElementById("job-title");
const submitBtn = document.getElementById("submit-btn");
const resultsSection = document.getElementById("results");
const resultsRole = document.getElementById("results-role");
const questionsList = document.getElementById("questions-list");
const errorBanner = document.getElementById("error-banner");
const errorTitle = document.getElementById("error-title");
const errorMessage = document.getElementById("error-message");
const errorHint = document.getElementById("error-hint");
const tryAgainBtn = document.getElementById("try-again");
const charCount = document.getElementById("char-count");

const API_BASE = window.location.origin;
const REQUEST_TIMEOUT_MS = 60_000;

const CLIENT_ERRORS = {
  NETWORK: {
    code: "NETWORK_ERROR",
    message: "Could not reach the server.",
    hint: "Make sure the backend is running (python app.py in backend/) and you are on http://localhost:5000.",
  },
  TIMEOUT: {
    code: "CLIENT_TIMEOUT",
    message: "The request timed out.",
    hint: "Generation can take up to a minute. Check your connection and try again.",
  },
  INVALID_RESPONSE: {
    code: "INVALID_RESPONSE",
    message: "Received an invalid response from the server.",
    hint: "Refresh the page and try again.",
  },
  EMPTY_QUESTIONS: {
    code: "EMPTY_QUESTIONS",
    message: "No questions were returned.",
    hint: "Try a different job title or generate again.",
  },
};

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  jobInput.readOnly = isLoading;
  submitBtn.classList.toggle("loading", isLoading);
  submitBtn.querySelector(".btn-spinner").hidden = !isLoading;
  submitBtn.setAttribute("aria-busy", String(isLoading));
}

function normalizeError(raw) {
  if (!raw) return CLIENT_ERRORS.INVALID_RESPONSE;

  if (typeof raw === "string") {
    return { code: "UNKNOWN", message: raw, hint: null };
  }

  if (typeof raw === "object" && raw.message) {
    return {
      code: raw.code || "UNKNOWN",
      message: raw.message,
      hint: raw.hint || null,
    };
  }

  return CLIENT_ERRORS.INVALID_RESPONSE;
}

function showError(error) {
  const { code, message, hint } = normalizeError(error);

  errorTitle.textContent = friendlyTitle(code);
  errorMessage.textContent = message;
  errorHint.textContent = hint || "";
  errorHint.hidden = !hint;

  errorBanner.hidden = false;
  errorBanner.dataset.code = code;
  jobInput.setAttribute("aria-invalid", "true");
  jobInput.classList.add("input-invalid");
  errorBanner.focus({ preventScroll: true });
}

function clearError() {
  errorBanner.hidden = true;
  errorBanner.removeAttribute("data-code");
  errorTitle.textContent = "";
  errorMessage.textContent = "";
  errorHint.textContent = "";
  errorHint.hidden = true;
  jobInput.removeAttribute("aria-invalid");
  jobInput.classList.remove("input-invalid");
}

function friendlyTitle(code) {
  const titles = {
    MISSING_JOB_TITLE: "Job title required",
    JOB_TITLE_TOO_LONG: "Title too long",
    MISSING_API_KEY: "Service not configured",
    INVALID_API_KEY: "Invalid API key",
    QUOTA_EXCEEDED: "Rate limit reached",
    RATE_LIMITED: "Please wait before trying again",
    MODEL_UNAVAILABLE: "Model unavailable",
    CONTENT_BLOCKED: "Input not accepted",
    UPSTREAM_TIMEOUT: "Request timed out",
    PARSE_FAILED: "Unexpected AI response",
    GENERATION_FAILED: "Generation failed",
    NETWORK_ERROR: "Connection problem",
    CLIENT_TIMEOUT: "Timed out",
    INVALID_JSON_BODY: "Invalid request",
  };
  return titles[code] || "Something went wrong";
}

function renderQuestions(jobTitle, questions) {
  if (!Array.isArray(questions) || questions.length === 0) {
    showError(CLIENT_ERRORS.EMPTY_QUESTIONS);
    return;
  }

  resultsRole.textContent = jobTitle;
  questionsList.replaceChildren(
    ...questions.map((q) => {
      const li = document.createElement("li");
      li.textContent = q;
      return li;
    })
  );
  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function fetchQuestions(jobTitle) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response;
  try {
    response = await fetch(`${API_BASE}/api/questions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ jobTitle }),
      signal: controller.signal,
    });
  } catch (err) {
    if (err.name === "AbortError") {
      throw normalizeError(CLIENT_ERRORS.TIMEOUT);
    }
    throw normalizeError(CLIENT_ERRORS.NETWORK);
  } finally {
    clearTimeout(timeoutId);
  }

  let data = {};
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await response.json().catch(() => ({}));
  }

  if (!response.ok) {
    throw normalizeError(data.error);
  }

  if (!data.questions?.length) {
    throw normalizeError(CLIENT_ERRORS.EMPTY_QUESTIONS);
  }

  return data;
}

function updateCharCount() {
  const len = jobInput.value.length;
  const max = jobInput.maxLength;
  charCount.textContent = `${len} / ${max}`;
  charCount.classList.toggle("char-count-warn", len > max * 0.9);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  // One Gemini call per click — ignore double-submit while loading.
  if (submitBtn.disabled) {
    return;
  }

  clearError();

  const jobTitle = jobInput.value.trim();
  if (!jobTitle) {
    showError({
      code: "MISSING_JOB_TITLE",
      message: "Enter a job title to generate questions.",
      hint: "Examples: Senior Backend Engineer, UX Researcher, DevOps Engineer.",
    });
    jobInput.focus();
    return;
  }

  if (jobTitle.length > jobInput.maxLength) {
    showError({
      code: "JOB_TITLE_TOO_LONG",
      message: "Job title is too long.",
      hint: `Use at most ${jobInput.maxLength} characters.`,
    });
    return;
  }

  setLoading(true); // disable button before any async work
  resultsSection.hidden = true;

  try {
    const data = await fetchQuestions(jobTitle);
    renderQuestions(data.jobTitle || jobTitle, data.questions);
  } catch (err) {
    showError(err.code ? err : { message: err.message || String(err) });
    resultsSection.hidden = true;
  } finally {
    setLoading(false);
  }
});

jobInput.addEventListener("input", () => {
  if (jobInput.hasAttribute("aria-invalid")) {
    clearError();
  }
  updateCharCount();
});

tryAgainBtn.addEventListener("click", () => {
  resultsSection.hidden = true;
  clearError();
  jobInput.value = "";
  updateCharCount();
  jobInput.focus();
});

updateCharCount();
