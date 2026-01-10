#!/usr/bin/env python3
"""
Run the Humboldt Jobs web server
"""
import uvicorn
from config import API_HOST, API_PORT

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  HUMBOLDT JOBS WEB SERVER")
    print("=" * 50)
    print(f"\n  Starting server at http://{API_HOST}:{API_PORT}")
    print(f"  API docs at http://{API_HOST}:{API_PORT}/api/docs")
    print("\n  Press Ctrl+C to stop\n")
    
    uvicorn.run(
        "api.app:app",
        host=API_HOST,
        port=API_PORT,
        reload=True
    )
