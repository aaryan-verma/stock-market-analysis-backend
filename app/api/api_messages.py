from app.api.logger import get_logger

# Set up logger for this module
logger = get_logger(__name__)

# API Error Messages
JWT_ERROR_USER_REMOVED = "User removed"
PASSWORD_INVALID = "Incorrect email or password"
REFRESH_TOKEN_NOT_FOUND = "Refresh token not found"
REFRESH_TOKEN_EXPIRED = "Refresh token expired"
REFRESH_TOKEN_ALREADY_USED = "Refresh token already used"
EMAIL_ADDRESS_ALREADY_USED = "Cannot use this email address"

# Log that this module was imported (will help identify where messages originate)
logger.debug("API messages module loaded")
