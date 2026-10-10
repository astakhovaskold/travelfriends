from app.api.auth import get_current_user
from app.schemas import Review
from app.services import review_service as service
from fastapi import APIRouter, Depends

router = APIRouter()


@router.post("/api/reviews")
async def add_review(r: Review, u: dict = Depends(get_current_user)):
    return await service.add_review(r, u)
