"""
run_api.py
==========
Entry point to start the Verity FastAPI server.

Run:
    python run_api.py
    OR
    uvicorn api.app:app --reload --port 8000
"""

import uvicorn
from api.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
