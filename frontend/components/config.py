# config.py
import os

# Get backend URL (default to local FastAPI instance)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")