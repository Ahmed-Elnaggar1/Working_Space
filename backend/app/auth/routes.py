from fastapi import APIRouter, Depends, Request, Response, status

from app.auth.controllers import AuthController
from app.auth.dependencies import CurrentUser, get_auth_service, get_current_user
from app.auth.schemas import (
    LogoutRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from app.auth.services import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    service: AuthService = Depends(get_auth_service),
):
    return await AuthController.register(service, payload)


# Alias signup for API.md / Sprint 2 contract compatibility
@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    payload: UserRegister,
    service: AuthService = Depends(get_auth_service),
):
    return await AuthController.register(service, payload)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    return await AuthController.login(service, payload, response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    payload: TokenRefreshRequest | None = None,
    service: AuthService = Depends(get_auth_service),
):
    return await AuthController.refresh(service, request, response, payload=payload)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    payload: LogoutRequest | None = None,
    service: AuthService = Depends(get_auth_service),
):
    await AuthController.logout(service, request, response, payload=payload)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me")
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    return await AuthController.get_me(service, current_user.id)
