"""API module for stock market analysis backend.

This module contains all the API endpoints and related functionality.
"""

from app.api.logger import get_logger

# Set up package-level logger
logger = get_logger("app.api")
logger.info("API module initialized")
