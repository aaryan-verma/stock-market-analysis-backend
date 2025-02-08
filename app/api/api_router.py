from fastapi import APIRouter

from app.api import api_messages
from app.api.endpoints import auth, users, stock_data, analysis, visualization

# Router for routes that need full database authentication
auth_router = APIRouter(
    responses={
        401: {
            "description": "No `Authorization` access token header, token is invalid or user removed",
            "content": {
                "application/json": {
                    "examples": {
                        "not authenticated": {
                            "summary": "No authorization token header",
                            "value": {"detail": "Not authenticated"},
                        },
                        "invalid token": {
                            "summary": "Token validation failed, decode failed, it may be expired or malformed",
                            "value": {"detail": "Token invalid: {detailed error msg}"},
                        },
                        "removed user": {
                            "summary": api_messages.JWT_ERROR_USER_REMOVED,
                            "value": {"detail": api_messages.JWT_ERROR_USER_REMOVED},
                        },
                    }
                }
            },
        },
    }
)

# Add routes that need database authentication
auth_router.include_router(auth.router, prefix="/auth", tags=["auth"])
auth_router.include_router(users.router, prefix="/users", tags=["users"])

# Router for routes that only need token verification
api_router = APIRouter()

# Add routes that only need token verification
api_router.include_router(stock_data.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(visualization.router, prefix="/visualization", tags=["visualization"])
