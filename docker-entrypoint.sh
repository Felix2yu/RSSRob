#!/bin/sh
set -e

python -m rssrob serve &
python web/webapp.py --host 0.0.0.0 --port 5000

wait
