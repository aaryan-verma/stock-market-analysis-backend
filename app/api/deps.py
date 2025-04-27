from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status, APIRouter # type: ignore
from fastapi.security import OAuth2PasswordBearer # type: ignore
from sqlalchemy import select # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore

from app.api import api_messages
from app.api.logger import get_logger
from app.core import database_session
from app.core.security.jwt import verify_jwt_token
from app.models import User

# Set up logger for this module
logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/access-token")


async def get_session() -> AsyncGenerator[AsyncSession]:
    logger.debug("Getting database session")
    async with database_session.get_async_session() as session:
        logger.debug("Database session obtained")
        yield session


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_session),
) -> User:
    logger.debug("Verifying token and getting current user")
    try:
        token_payload = verify_jwt_token(token)
        
        logger.debug(f"Token verified for user ID: {token_payload.sub}")
        user = await session.scalar(select(User).where(User.user_id == token_payload.sub))

        if user is None:
            logger.warning(f"User with ID {token_payload.sub} not found in database")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=api_messages.JWT_ERROR_USER_REMOVED,
            )
        logger.debug(f"User {user.user_id} authenticated successfully")
        return user
    except HTTPException:
        # Re-raise HTTP exceptions
        logger.warning("Authentication failed due to HTTP exception", exc_info=True)
        raise
    except Exception as e:
        # Log other unexpected errors
        logger.error(f"Unexpected error in get_current_user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )


def create_token_auth_router() -> APIRouter:
    """Create a router that requires only token authentication without database checks"""
    logger.debug("Creating token-auth router")
    return APIRouter()


async def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    """Verify JWT token without database check"""
    logger.debug("Verifying token without database check")
    try:
        token_payload = verify_jwt_token(token)
        if not token_payload:
            logger.warning("Token validation failed - no payload")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        logger.debug(f"Token verified successfully for user ID: {token_payload.sub}")
        return token_payload.sub
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
