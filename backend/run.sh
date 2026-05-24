#!/usr/bin/env bash
# Run RolePrep AI with system Python (works when .venv points at Cursor AppImage).
set -euo pipefail
cd "$(dirname "$0")"

SYSTEM_PYTHON="${PYTHON:-/usr/bin/python3.12}"
export PATH="/usr/bin:/bin:${PATH}"

if [[ ! -x "$SYSTEM_PYTHON" ]]; then
  echo "error: $SYSTEM_PYTHON not found. Install Python 3.12 or set PYTHON=/usr/bin/python3.12" >&2
  exit 1
fi

venv_broken() {
  [[ ! -f .venv/bin/python ]] && return 0
  local resolved
  resolved="$(readlink -f .venv/bin/python 2>/dev/null || echo "")"
  [[ -z "$resolved" ]] && return 0
  [[ "$resolved" == *"AppImage"* || "$resolved" == *"Cursor"* ]] && return 0
  ! .venv/bin/python -c "import flask" 2>/dev/null
}

install_deps() {
  echo "Installing dependencies into deps/ ..."
  rm -rf deps
  "$SYSTEM_PYTHON" -m pip install -q -r requirements.txt -t deps
}

if venv_broken; then
  if [[ -d .venv ]]; then
    echo "note: removing broken .venv (was not using system Python)" >&2
    rm -rf .venv
  fi
  if [[ ! -d deps ]] || ! "$SYSTEM_PYTHON" -c "import sys; sys.path.insert(0,'deps'); import flask" 2>/dev/null; then
    install_deps
  fi
  export PYTHONPATH="${PWD}/deps${PYTHONPATH:+:$PYTHONPATH}"
  RUN_PYTHON="$SYSTEM_PYTHON"
else
  RUN_PYTHON=".venv/bin/python"
fi

if [[ ! -f .env ]]; then
  echo "warning: .env missing — copy .env.example and set GEMINI_API_KEY" >&2
elif ! grep -qE '^GEMINI_API_KEY=.+' .env 2>/dev/null; then
  echo "warning: GEMINI_API_KEY is empty in .env" >&2
fi

if ! grep -qE '^GEMINI_MODEL=gemini-2\.5-flash' .env 2>/dev/null; then
  echo "tip: set GEMINI_MODEL=gemini-2.5-flash in .env (1.5-flash is no longer available)" >&2
fi

echo "Starting server at http://localhost:5000 (Ctrl+C to stop)"
exec "$RUN_PYTHON" app.py
