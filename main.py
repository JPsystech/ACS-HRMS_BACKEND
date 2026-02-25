# FastAPI Application Redirect
# This file redirects to the actual app in the app package

from app.main import app

# This allows uvicorn to find the app when running from root directory
# Render deployment command: uvicorn main:app --host 0.0.0.0 --port 8001