"""
WSGI configuration for PythonAnywhere.

Copy this file to your PythonAnywhere WSGI config location and update
the path to match your project directory.

Typical PythonAnywhere WSGI config path:
  /var/www/<username>_pythonanywhere_com_wsgi.py
"""

import sys
import os

# Update this path to your project directory on PythonAnywhere
# Example: '/home/yourusername/mine-nyheder'
project_path = '/home/<username>/mine-nyheder'

if project_path not in sys.path:
    sys.path.insert(0, project_path)

os.chdir(project_path)

from app import app as application  # noqa: E402
