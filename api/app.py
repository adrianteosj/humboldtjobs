"""
FastAPI Application for Humboldt Jobs API
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import API_HOST, API_PORT
from db.database import init_db

# Initialize database on startup
init_db()

# Create FastAPI app
app = FastAPI(
    title="Humboldt Jobs API",
    description="API for browsing job listings in Humboldt County, CA",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Import and include routes
from .routes import router as api_router
from .web_routes import router as web_router

app.include_router(api_router, prefix="/api")
app.include_router(web_router)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "humboldt-jobs"}


def run_server():
    """Run the server with uvicorn"""
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    run_server()
