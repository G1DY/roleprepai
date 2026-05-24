#!/usr/bin/env bash
# Run the API with system Python (avoids broken venv symlinks in some IDE terminals).
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-/usr/bin/python3.12}"
VENV_DIR=".venv"

if [[ ! -x "$PYTHON" ]]; then
  echo "error: $PYTHON not found. Install Python 3.12 or set PYTHON=..." >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]] || [[ ! -f "$VENV_DIR/bin/python" ]] || ! "$VENV_DIR/bin/python" -c "import flask" 2>/dev/null; then
  echo "Creating virtualenv at $VENV_DIR ..."
  PATH="/usr/bin:/bin" "$PYTHON" -m venv "$VENV_DIR"
  PATH="/usr/bin:/bin" "$VENV_DIR/bin/pip" install -r requirements.txt
fi

if [[ ! -f .env ]]; then
  echo "warning: .env missing — copy .env.example and set GEMINI_API_KEY" >&2
fi

exec "$VENV_DIR/bin/python" app.py
