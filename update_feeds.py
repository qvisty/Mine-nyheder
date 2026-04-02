#!/usr/bin/env python3
"""
Scheduled task script for PythonAnywhere.

Set this up as a scheduled task on PythonAnywhere to refresh the feed cache.
It calls the /api/refresh endpoint on your deployed app.

PythonAnywhere setup:
  1. Go to the "Tasks" tab
  2. Add a new scheduled task (hourly on free tier, or daily)
  3. Command: python3 /home/<username>/mine-nyheder/update_feeds.py

Alternatively, for free accounts that only support daily tasks,
the app will lazy-load feeds on the first request after a restart.
"""

import requests
import sys

# Update this to your PythonAnywhere URL
APP_URL = "https://<username>.pythonanywhere.com"

try:
    resp = requests.post(f"{APP_URL}/api/refresh", timeout=60)
    resp.raise_for_status()
    data = resp.json()
    print(f"Feed refresh successful: {data['articleCount']} articles")
except Exception as e:
    print(f"Feed refresh failed: {e}", file=sys.stderr)
    sys.exit(1)
