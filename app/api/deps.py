from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status, APIRouter # type: ignore
from fastapi.security import OAuth2PasswordBearer # type: ignore
from sqlalchemy import select # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession # type: ignore

from app.api import api_messages
from app.core import database_session
from app.core.security.jwt import verify_jwt_token
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/access-token")


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with database_session.get_async_session() as session:
        yield session


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_session),
) -> User:
    token_payload = verify_jwt_token(token)

    user = await session.scalar(select(User).where(User.user_id == token_payload.sub))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=api_messages.JWT_ERROR_USER_REMOVED,
        )
    return user


def create_token_auth_router() -> APIRouter:
    """Create a router that requires only token authentication without database checks"""
    return APIRouter()


async def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    """Verify JWT token without database check"""
    token_payload = verify_jwt_token(token)
    if not token_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return token_payload.sub
