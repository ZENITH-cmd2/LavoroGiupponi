"""
Vercel Serverless Entry Point
Wraps the Flask app for Vercel's Python runtime.
"""
import sys
import os

# Add backend directory to Python path so imports work
backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, os.path.abspath(backend_dir))

# Import the Flask app
from server import app

# Vercel expects the WSGI app to be named 'app'
# (already exported as 'app' from server.py)
