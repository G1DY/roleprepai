# RolePrep AI

Generate three thoughtful, role-specific interview questions for any job title using Gemini.

## Stack

- **Backend:** Flask + Google Generative AI (Gemini)
- **Frontend:** HTML5, CSS3, vanilla JavaScript
- **Deploy:** [Render](https://render.com) (see `render.yaml`)

## Local development

1. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).

2. Create a virtualenv **in a normal terminal** (not inside a broken `myenv` that points at Cursor’s Python):

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
python app.py
```

3. Open [http://localhost:5000](http://localhost:5000), enter a job title, and click **Generate**.

## Deploy to Render

1. Push this repo to GitHub (do **not** commit `.env` or `myenv/` / `.venv/`).

2. In Render: **New → Blueprint** and connect the repo, or **New Web Service** with:
   - **Root directory:** `backend`
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `gunicorn --bind 0.0.0.0:$PORT app:app`

3. Add environment variable `GEMINI_API_KEY` in the Render dashboard.

4. Deploy. The Flask app serves the frontend and API from one URL.

## API

`POST /api/questions`

```json
{ "jobTitle": "Senior Backend Engineer" }
```

Response:

```json
{
  "jobTitle": "Senior Backend Engineer",
  "questions": ["...", "...", "..."]
}
```
