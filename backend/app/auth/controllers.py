from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import TokenResponse, UserLogin, UserRegister, UserResponse
from app.auth.services import AuthService
from app.core.config import settings


class AuthController:
    COOKIE_NAME = "refresh_token"

    @classmethod
    def _set_refresh_cookie(cls, response: Response, refresh_token: str) -> None:
        is_prod = settings.ENV == "production"
        # 7 days max age
        max_age = 7 * 24 * 60 * 60
        response.set_cookie(
            key=cls.COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            secure=is_prod,
            samesite="lax",
            max_age=max_age,
        )

    @classmethod
    def _clear_refresh_cookie(cls, response: Response) -> None:
        is_prod = settings.ENV == "production"
        response.delete_cookie(
            key=cls.COOKIE_NAME,
            httponly=True,
            secure=is_prod,
            samesite="lax",
        )

    @classmethod
    async def register(cls, db: AsyncSession, payload: UserRegister) -> dict:
        user = await AuthService.register(db, payload)
        # Returns response matching API contract: {"user": {"id": "uuid", "email": "email"}}
        return {"user": UserResponse.model_validate(user)}

    @classmethod
    async def login(cls, db: AsyncSession, payload: UserLogin, response: Response) -> TokenResponse:
        user, access_token, refresh_token = await AuthService.login(db, payload)
        cls._set_refresh_cookie(response, refresh_token)
        return TokenResponse(access_token=access_token)

    @classmethod
    async def refresh(cls, db: AsyncSession, request: Request, response: Response) -> TokenResponse:
        refresh_token = request.cookies.get(cls.COOKIE_NAME)
        new_access_token, new_refresh_token = await AuthService.refresh(db, refresh_token)
        cls._set_refresh_cookie(response, new_refresh_token)
        return TokenResponse(access_token=new_access_token)

    @classmethod
    async def logout(cls, db: AsyncSession, request: Request, response: Response) -> None:
        refresh_token = request.cookies.get(cls.COOKIE_NAME)
        await AuthService.logout(db, refresh_token)
        cls._clear_refresh_cookie(response)
