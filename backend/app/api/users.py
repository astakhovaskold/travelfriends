from app.api.auth import get_current_user
from app.schemas import BlockReq, Profile, Reg
from app.services import user_service as service
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/api/me")
def me(u: dict = Depends(get_current_user)):
    return service.me(u)


@router.post("/api/rules")
def accept_rules(u: dict = Depends(get_current_user)):
    return service.accept_rules(u)


@router.post("/api/register")
def register(r: Reg, u: dict = Depends(get_current_user)):
    return service.register(r, u)


@router.post("/api/profile")
def save_profile(p: Profile, u: dict = Depends(get_current_user)):
    return service.save_profile(p, u)


@router.get("/api/users/{user_id}")
def profile(user_id: int, u: dict = Depends(get_current_user)):
    return service.profile(user_id, u)


@router.post("/api/block", tags=["Модерация"])
def block(b: BlockReq, u: dict = Depends(get_current_user)):
    return service.block(b, u)


@router.post("/api/users/{user_id}/report", tags=["Модерация"])
async def report_user(user_id: int, u: dict = Depends(get_current_user)):
    return await service.report_user(user_id, u)
