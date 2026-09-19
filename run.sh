#!/usr/bin/env bash
# Wrapper so the right interpreter is used (Homebrew python lacks some deps here).
set -euo pipefail
cd "$(dirname "$0")"
PY="${PY:-$HOME/anaconda3/bin/python3}"
exec "$PY" main.py "$@"
