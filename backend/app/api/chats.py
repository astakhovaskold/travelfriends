from fastapi import APIRouter, Depends
from app.api.auth import get_current_user
from app.schemas import Msg, React
from app.services import chat_service as service

router = APIRouter()

@router.get('/api/trips/{trip_id}/people')
def trip_people(trip_id: int, u: dict = Depends(get_current_user)):
    return service.trip_people(trip_id, u)

@router.get('/api/trips/{trip_id}/chat')
def get_chat(trip_id: int, since: int = 0, u: dict = Depends(get_current_user)):
    return service.get_chat(trip_id, since, u)

@router.post('/api/trips/{trip_id}/messages')
async def post_message(trip_id: int, m: Msg, u: dict = Depends(get_current_user)):
    return await service.post_message(trip_id, m, u)

@router.post('/api/messages/{msg_id}/react')
def react(msg_id: int, r: React, u: dict = Depends(get_current_user)):
    return service.react(msg_id, r, u)

@router.post('/api/messages/{msg_id}/report', tags=['Модерация'])
async def report(msg_id: int, u: dict = Depends(get_current_user)):
    return await service.report(msg_id, u)

