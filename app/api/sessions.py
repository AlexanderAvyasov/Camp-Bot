from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import DayScheduleCreate, DayScheduleOut, SessionCreate, SessionOut
from app.db.base import get_session
from app.db.crud import (
    activate_session,
    add_schedule_item,
    copy_schedule,
    create_session,
    get_all_sessions,
    get_schedule,
    get_session_by_id,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
async def list_sessions(session: AsyncSession = Depends(get_session)):
    return await get_all_sessions(session)


@router.post("", response_model=SessionOut, status_code=201)
async def create_session_endpoint(body: SessionCreate, session: AsyncSession = Depends(get_session)):
    if body.end_date <= body.start_date:
        raise HTTPException(status_code=422, detail="Дата окончания должна быть позже даты начала")
    return await create_session(session, body.name, body.start_date, body.end_date)


@router.patch("/{session_id}/activate", response_model=SessionOut)
async def activate_session_endpoint(session_id: int, session: AsyncSession = Depends(get_session)):
    obj = await activate_session(session, session_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Смена не найдена")
    return obj


@router.get("/{session_id}/schedule", response_model=list[DayScheduleOut])
async def get_schedule_endpoint(session_id: int, session: AsyncSession = Depends(get_session)):
    obj = await get_session_by_id(session, session_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Смена не найдена")
    return await get_schedule(session, session_id)


@router.post("/{session_id}/schedule", response_model=DayScheduleOut, status_code=201)
async def add_schedule_endpoint(
    session_id: int, body: DayScheduleCreate, session: AsyncSession = Depends(get_session)
):
    obj = await get_session_by_id(session, session_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Смена не найдена")
    return await add_schedule_item(session, session_id, body.day_type, body.time, body.label)


@router.post("/{session_id}/schedule/copy/{from_session_id}", response_model=dict)
async def copy_schedule_endpoint(
    session_id: int, from_session_id: int, session: AsyncSession = Depends(get_session)
):
    to_obj = await get_session_by_id(session, session_id)
    if not to_obj:
        raise HTTPException(status_code=404, detail="Целевая смена не найдена")
    from_obj = await get_session_by_id(session, from_session_id)
    if not from_obj:
        raise HTTPException(status_code=404, detail="Смена-источник не найдена")
    count = await copy_schedule(session, session_id, from_session_id)
    return {"copied": count}
