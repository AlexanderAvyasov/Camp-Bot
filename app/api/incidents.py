from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import Child, Incident, Staff

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


class ReporterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str


class ChildBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    description: str
    reported_by: int
    child_id: Optional[int]
    photo_url: Optional[str]
    session_id: Optional[int]
    created_at: datetime
    reporter: Optional[ReporterOut]
    child: Optional[ChildBriefOut]


class IncidentCreate(BaseModel):
    type: str
    description: str
    reported_by: int
    child_id: Optional[int] = None
    photo_url: Optional[str] = None
    session_id: Optional[int] = None


@router.get("", response_model=list[IncidentOut])
async def list_incidents(
    type: Optional[str] = Query(None),
    today_only: bool = Query(False),
    session_id: Optional[int] = Query(None),
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    q = select(Incident)
    if type is not None:
        q = q.where(Incident.type == type)
    if session_id is not None:
        q = q.where(Incident.session_id == session_id)
    if today_only:
        today = date.today()
        day_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        q = q.where(Incident.created_at >= day_start)
    q = q.order_by(Incident.created_at.desc()).offset(page * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/{incident_id}", response_model=IncidentOut)
async def get_incident(
    incident_id: int,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Инцидент не найден")
    return incident


@router.post("", response_model=IncidentOut, status_code=201)
async def create_incident(
    body: IncidentCreate,
    db: AsyncSession = Depends(get_session),
):
    reporter_result = await db.execute(select(Staff).where(Staff.id == body.reported_by))
    if not reporter_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    if body.child_id is not None:
        child_result = await db.execute(select(Child).where(Child.id == body.child_id))
        if not child_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Ребёнок не найден")

    incident = Incident(
        type=body.type,
        description=body.description,
        reported_by=body.reported_by,
        child_id=body.child_id,
        photo_url=body.photo_url,
        session_id=body.session_id,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident
