"""
VETRI Flask Application Entrypoint

Local Development:
    python run.py

Production WSGI Server (Linux/Unix):
    gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 run:app
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, use_reloader=False, port=5000, threaded=True)


