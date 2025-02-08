from urllib.request import Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import psutil
import logging

from app.api.api_router import api_router, auth_router
from app.core.config import get_settings
from app.api.endpoints import chat, visualization, news  # Add news import

app = FastAPI(
    title="minimal fastapi postgres template",
    version="6.1.0",
    description="https://github.com/rafsaf/minimal-fastapi-postgres-template",
    openapi_url="/openapi.json",
    docs_url="/",
)

app.include_router(auth_router)
app.include_router(api_router)
app.include_router(news.router, prefix="/news", tags=["news"])

# Sets all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        str(origin).rstrip("/")
        for origin in get_settings().security.backend_cors_origins
    ] + ["https://your-vercel-app.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Guards against HTTP Host Header attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=get_settings().security.allowed_hosts,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)

@app.middleware("http")
async def monitor_memory(request: Request, call_next):
    process = psutil.Process()
    before_mem = process.memory_info().rss / 1024 / 1024  # MB
    
    response = await call_next(request)
    
    after_mem = process.memory_info().rss / 1024 / 1024  # MB
    mem_used = after_mem - before_mem
    
    if mem_used > 50:  # Log if single request uses more than 50MB
        logger.warning(f"High memory usage: {mem_used:.2f}MB for {request.url.path}")
    
    return response
