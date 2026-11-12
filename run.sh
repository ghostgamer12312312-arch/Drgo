#!/data/data/com.termux/files/usr/bin/bash
# Start the bot from Termux. Creates a virtualenv on first run.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    python -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt
exec python main.py
