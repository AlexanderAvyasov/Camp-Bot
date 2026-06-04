from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import Duty, DutyCheckpoint, DutyStatus, DutyType, Staff

router = APIRouter(prefix="/api/duties", tags=["duties"])


class CheckpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    duty_id: int
    label: str
    confirmed_at: Optional[datetime]


class StaffBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str


class DutyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: DutyType
    staff_id: int
    date: date
    status: DutyStatus
    session_id: int
    created_at: datetime
    staff: Optional[StaffBriefOut]
    checkpoints: list[CheckpointOut]


class DutyStatusUpdate(BaseModel):
    status: DutyStatus


class CheckpointCreate(BaseModel):
    label: str


@router.get("", response_model=list[DutyOut])
async def list_duties(
    staff_id: Optional[int] = Query(None),
    date_filter: Optional[str] = Query(None, alias="date"),
    week: bool = Query(False),
    session_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    q = select(Duty)
    if staff_id is not None:
        q = q.where(Duty.staff_id == staff_id)
    if session_id is not None:
        q = q.where(Duty.session_id == session_id)
    if date_filter is not None:
        try:
            parsed_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            q = q.where(Duty.date == parsed_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="Формат даты: YYYY-MM-DD")
    elif week:
        today = datetime.now(tz=timezone.utc).date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        q = q.where(Duty.date >= week_start, Duty.date <= week_end)
    q = q.order_by(Duty.date, Duty.type)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.patch("/{duty_id}", response_model=DutyOut)
async def update_duty_status(
    duty_id: int,
    body: DutyStatusUpdate,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Duty).where(Duty.id == duty_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Дежурство не найдено")
    await db.execute(update(Duty).where(Duty.id == duty_id).values(status=body.status))
    await db.commit()
    updated = (await db.execute(select(Duty).where(Duty.id == duty_id))).scalar_one()
    return updated


@router.post("/{duty_id}/checkpoint", response_model=CheckpointOut, status_code=201)
async def add_checkpoint(
    duty_id: int,
    body: CheckpointCreate,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Duty).where(Duty.id == duty_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Дежурство не найдено")
    cp = DutyCheckpoint(
        duty_id=duty_id,
        label=body.label,
        confirmed_at=datetime.now(tz=timezone.utc),
    )
    db.add(cp)
    await db.commit()
    await db.refresh(cp)
    return cp
