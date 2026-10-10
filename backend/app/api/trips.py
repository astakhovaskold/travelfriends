from app.api.auth import get_current_user
from app.schemas import KickReq, Trip
from app.services import trip_service as service
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/api/trips")
def trips(u: dict = Depends(get_current_user)):
    return service.trips(u)


@router.get("/api/trips/{trip_id}")
def one_trip(trip_id: int, u: dict = Depends(get_current_user)):
    return service.one_trip(trip_id, u)


@router.get("/api/my")
def my(u: dict = Depends(get_current_user)):
    return service.my(u)


@router.post("/api/trips")
def create_trip(t: Trip, u: dict = Depends(get_current_user)):
    return service.create_trip(t, u)


@router.post("/api/trips/{trip_id}/join")
async def join(trip_id: int, u: dict = Depends(get_current_user)):
    return await service.join(trip_id, u)


@router.get("/api/trips/{trip_id}/requests", tags=["Заявки"])
def list_requests(trip_id: int, u: dict = Depends(get_current_user)):
    return service.list_requests(trip_id, u)


@router.post("/api/trips/{trip_id}/requests/{uid}/{act}", tags=["Заявки"])
async def answer_request(trip_id: int, uid: int, act: str, u: dict = Depends(get_current_user)):
    return await service.answer_request(trip_id, uid, act, u)


@router.post("/api/trips/{trip_id}/leave")
def leave(trip_id: int, u: dict = Depends(get_current_user)):
    return service.leave(trip_id, u)


@router.post("/api/trips/{trip_id}/kick")
async def kick(trip_id: int, k: KickReq, u: dict = Depends(get_current_user)):
    return await service.kick(trip_id, k, u)


@router.post("/api/trips/{trip_id}/close")
def close_trip(trip_id: int, u: dict = Depends(get_current_user)):
    return service.close_trip(trip_id, u)
