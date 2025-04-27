"""Endpoints package for the API.

This package contains all the endpoint modules for the API.
"""

from app.api.logger import get_logger

# Set up package-level logger
logger = get_logger("app.api.endpoints")
logger.info("API endpoints module initialized")
