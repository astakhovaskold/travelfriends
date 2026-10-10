from app.schemas.auth import EmailLogin, EmailRegister, TelegramLogin
from app.services import auth_service as service
from fastapi import APIRouter, Depends, Header

router = APIRouter()


def get_current_user(authorization: str = Header(""), x_init_data: str = Header("")) -> dict:
    return service.get_current_user(authorization, x_init_data)


@router.post("/api/auth/telegram")
def exchange_telegram(body: TelegramLogin):
    return service.exchange_telegram(body)


@router.post("/api/auth/logout")
def logout(user: dict = Depends(get_current_user), authorization: str = Header("")):
    return service.logout(user, authorization)


@router.post("/api/auth/register", status_code=201)
def email_register(body: EmailRegister):
    return service.email_register(body)


@router.post("/api/auth/login")
def email_login(body: EmailLogin):
    return service.email_login(body)


@router.post("/api/auth/link/telegram")
def link_telegram(body: TelegramLogin, user: dict = Depends(get_current_user)):
    return service.link_telegram(body, user)
