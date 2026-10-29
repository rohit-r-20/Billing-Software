#!/bin/bash
# Anti Matrix Billing ERP Launcher
cd "$(dirname "$0")"

if [ -f ".venv/bin/python" ]; then
    exec .venv/bin/python app.py "$@"
else
    exec python3 app.py "$@"
fi
