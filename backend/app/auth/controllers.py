from uuid import UUID

from fastapi import HTTPException, Request, Response, status

from app.auth.exceptions import (
    AuthError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.auth.schemas import TokenResponse, UserLogin, UserRegister, UserResponse
from app.auth.services import AuthService
from app.core.config import settings


class AuthController:
    COOKIE_NAME = "refresh_token"

    @classmethod
    def _set_refresh_cookie(
        cls,
        response: Response,
        refresh_token: str,
        max_age: int,
    ) -> None:
        response.set_cookie(
            key=cls.COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            secure=settings.ENV == "production",
            samesite="lax",
            max_age=max_age,
        )

    @classmethod
    def _clear_refresh_cookie(cls, response: Response) -> None:
        response.delete_cookie(
            key=cls.COOKIE_NAME,
            httponly=True,
            secure=settings.ENV == "production",
            samesite="lax",
        )

    @classmethod
    async def register(cls, service: AuthService, payload: UserRegister) -> dict:
        try:
            user = await service.register(payload)
        except UserAlreadyExistsError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

        return {"user": UserResponse.model_validate(user)}

    @classmethod
    async def login(
        cls,
        service: AuthService,
        payload: UserLogin,
        response: Response,
    ) -> TokenResponse:
        try:
            result = await service.login(payload)
        except InvalidCredentialsError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            ) from error

        cls._set_refresh_cookie(
            response,
            result.refresh_token,
            result.refresh_token_max_age,
        )
        return TokenResponse(access_token=result.access_token)

    @classmethod
    async def refresh(
        cls,
        service: AuthService,
        request: Request,
        response: Response,
    ) -> TokenResponse:
        try:
            result = await service.refresh(request.cookies.get(cls.COOKIE_NAME))
        except AuthError as error:
            cls._clear_refresh_cookie(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session.",
            ) from error

        cls._set_refresh_cookie(
            response,
            result.refresh_token,
            result.refresh_token_max_age,
        )
        return TokenResponse(access_token=result.access_token)

    @classmethod
    async def logout(
        cls,
        service: AuthService,
        request: Request,
        response: Response,
    ) -> None:
        try:
            await service.logout(request.cookies.get(cls.COOKIE_NAME))
        finally:
            cls._clear_refresh_cookie(response)

    @classmethod
    async def get_me(cls, service: AuthService, user_id: UUID) -> dict:
        try:
            user = await service.get_user(user_id)
        except UserNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            ) from error
        return {"user": UserResponse.model_validate(user)}
