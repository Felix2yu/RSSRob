#!/bin/sh
set -e

exec /usr/local/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --access-logfile - rssrob.webapp:app
