"""
AllowED API server entry point

Run with:
  python3 server.py
  OR
  uvicorn api.main:app --reload --port 8000
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
