from urllib.request import Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import psutil
import logging
import os
from starlette.config import Config

from app.api.api_router import api_router, auth_router
from app.core.config import get_settings
from app.api.endpoints import chat, visualization, news  # Add news import

config = Config(".env")

app = FastAPI(
    title="Stock Market Analysis API",
    version="1.0.0",
    description="Stock Market Analysis Backend API",
    openapi_url="/openapi.json",
    docs_url="/",
)

app.include_router(auth_router)
app.include_router(api_router)
app.include_router(news.router, prefix="/news", tags=["news"])

# Sets all CORS enabled origins
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.security.backend_cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Guards against HTTP Host Header attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.security.allowed_hosts,
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))  # Changed default to 10000
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, workers=4)
