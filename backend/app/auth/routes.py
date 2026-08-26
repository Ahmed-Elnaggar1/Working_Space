from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.controllers import AuthController
from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.repositories import UserRepository
from app.auth.schemas import TokenResponse, UserLogin, UserRegister, UserResponse
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    return AuthController.register(db, payload)


# Alias signup for API.md / Sprint 2 contract compatibility
@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: UserRegister, db: Session = Depends(get_db)):
    return AuthController.register(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    return AuthController.login(db, payload, response)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    return AuthController.refresh(db, request, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    AuthController.logout(db, request, response)
    # Return 204 No Content response
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def get_me(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = UserRepository.get_by_id(db, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {"user": UserResponse.model_validate(user)}
