from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.crud import (
    check_location_conflict,
    check_responsible_conflict,
    copy_event,
    create_event,
    delete_event,
    get_event_by_id,
    get_events,
    update_event,
)
from app.db.models import EVENT_TYPE_COLORS, EVENT_TYPE_LABELS, EventType, StaffRole

router = APIRouter(prefix="/api/events", tags=["events"])


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    staff_id: int


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    type: EventType
    color: str = ""
    location: Optional[str]
    responsible_id: Optional[int]
    start_time: datetime
    end_time: datetime
    session_id: Optional[int]
    copied_from: Optional[int]
    created_at: datetime
    members: list[MemberOut]

    @classmethod
    def from_orm_with_color(cls, obj):
        data = cls.model_validate(obj)
        data.color = EVENT_TYPE_COLORS.get(obj.type, "#888")
        return data


class EventCreate(BaseModel):
    title: str
    type: EventType
    location: Optional[str] = None
    responsible_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    session_id: Optional[int] = None
    member_ids: list[int] = []


class EventUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[EventType] = None
    location: Optional[str] = None
    responsible_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    member_ids: Optional[list[int]] = None


class ConflictWarning(BaseModel):
    type: str
    events: list[str]


@router.get("", response_model=list[EventOut])
async def list_events(
    date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    session_id: Optional[int] = Query(None),
    staff_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    date_from = None
    date_to = None
    if date:
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            date_from = d
            date_to = d.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
    events = await get_events(db, date_from=date_from, date_to=date_to, session_id=session_id, staff_id=staff_id)
    return [EventOut.from_orm_with_color(e) for e in events]


@router.post("", response_model=dict, status_code=201)
async def create_event_endpoint(body: EventCreate, db: AsyncSession = Depends(get_session)):
    if body.end_time <= body.start_time:
        raise HTTPException(status_code=422, detail="Время окончания должно быть позже начала")

    warnings = []
    if body.location:
        conflicts = await check_location_conflict(db, body.location, body.start_time, body.end_time, body.session_id)
        if conflicts:
            warnings.append({"type": "location", "events": [e.title for e in conflicts]})
    if body.responsible_id:
        rconflicts = await check_responsible_conflict(db, body.responsible_id, body.start_time, body.end_time)
        if rconflicts:
            warnings.append({"type": "responsible", "events": [e.title for e in rconflicts]})

    event = await create_event(
        db, title=body.title, event_type=body.type,
        start_time=body.start_time, end_time=body.end_time,
        location=body.location, responsible_id=body.responsible_id,
        session_id=body.session_id, member_ids=body.member_ids,
    )
    return {"event": EventOut.from_orm_with_color(event).model_dump(), "warnings": warnings}


@router.patch("/{event_id}", response_model=EventOut)
async def update_event_endpoint(event_id: int, body: EventUpdate, db: AsyncSession = Depends(get_session)):
    event = await get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    updates = body.model_dump(exclude_none=True)
    updated = await update_event(db, event_id, **updates)
    return EventOut.from_orm_with_color(updated)


@router.delete("/{event_id}", status_code=204)
async def delete_event_endpoint(event_id: int, db: AsyncSession = Depends(get_session)):
    ok = await delete_event(db, event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")


@router.post("/{event_id}/copy", response_model=EventOut, status_code=201)
async def copy_event_endpoint(event_id: int, new_date: str, db: AsyncSession = Depends(get_session)):
    try:
        d = datetime.strptime(new_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Формат даты: YYYY-MM-DD")
    new_event = await copy_event(db, event_id, d)
    if not new_event:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    return EventOut.from_orm_with_color(new_event)


@router.get("/{event_id}/members", response_model=list[MemberOut])
async def get_members(event_id: int, db: AsyncSession = Depends(get_session)):
    event = await get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Мероприятие не найдено")
    return event.members
