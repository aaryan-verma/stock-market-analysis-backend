from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.logger import get_logger
from app.core.security.password import get_password_hash
from app.models import User
from app.schemas.requests import UserUpdatePasswordRequest
from app.schemas.responses import UserResponse

# Set up logger for this module
logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    description="Get current authenticated user",
)
async def get_current_user(
    current_user: User = Depends(deps.get_current_user),
) -> User:
    logger.info(f"Fetching user profile for user: {current_user.user_id}")
    return current_user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Delete current authenticated user",
)
async def delete_current_user(
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> None:
    logger.info(f"Request to delete user account: {current_user.user_id}")
    try:
        await session.delete(current_user)
        await session.commit()
        logger.info(f"User account deleted successfully: {current_user.user_id}")
    except Exception as e:
        logger.error(f"Error deleting user account {current_user.user_id}: {str(e)}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user account",
        )


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Update current user password",
)
async def reset_current_user_password(
    user_update_password: UserUpdatePasswordRequest,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user),
) -> None:
    current_user.hashed_password = get_password_hash(user_update_password.password)
    session.add(current_user)
    await session.commit()
