#!/bin/sh
set -e

exec gunicorn --bind 0.0.0.0:5000 --workers 4 --access-logfile - web.webapp:app
