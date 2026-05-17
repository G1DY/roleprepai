const form = document.getElementById("question-form");
const jobInput = document.getElementById("job-title");
const submitBtn = document.getElementById("submit-btn");
const resultsSection = document.getElementById("results");
const resultsRole = document.getElementById("results-role");
const questionsList = document.getElementById("questions-list");
const errorBanner = document.getElementById("error-banner");
const tryAgainBtn = document.getElementById("try-again");

const API_BASE = window.location.origin;

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  jobInput.disabled = isLoading;
  submitBtn.classList.toggle("loading", isLoading);
  submitBtn.querySelector(".btn-spinner").hidden = !isLoading;
}

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.hidden = false;
}

function clearError() {
  errorBanner.hidden = true;
  errorBanner.textContent = "";
}

function renderQuestions(jobTitle, questions) {
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
  const response = await fetch(`${API_BASE}/api/questions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jobTitle }),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.error || "Something went wrong. Please try again.");
  }

  return data;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();

  const jobTitle = jobInput.value.trim();
  if (!jobTitle) {
    showError("Please enter a job title.");
    jobInput.focus();
    return;
  }

  setLoading(true);

  try {
    const data = await fetchQuestions(jobTitle);
    renderQuestions(data.jobTitle || jobTitle, data.questions);
  } catch (err) {
    showError(err.message);
    resultsSection.hidden = true;
  } finally {
    setLoading(false);
  }
});

tryAgainBtn.addEventListener("click", () => {
  resultsSection.hidden = true;
  clearError();
  jobInput.value = "";
  jobInput.focus();
});
