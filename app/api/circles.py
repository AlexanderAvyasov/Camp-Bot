from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import (
    Child, Circle, CircleAttendance, CircleMember, CircleSchedule,
)

router = APIRouter(prefix="/api/circles", tags=["circles"])


class LeaderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    day_of_week: int
    time: time


class CircleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    leader_id: Optional[int]
    session_id: Optional[int]
    leader: Optional[LeaderOut]
    member_count: int = 0


class CircleDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    leader_id: Optional[int]
    session_id: Optional[int]
    leader: Optional[LeaderOut]
    schedule: list[ScheduleOut]


class ChildMemberOut(BaseModel):
    id: int
    full_name: str
    squad_id: Optional[int]


class AttendanceRecord(BaseModel):
    child_id: int
    present: bool


class AttendanceSave(BaseModel):
    date: str
    records: list[AttendanceRecord]


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    circle_id: int
    child_id: int
    date: date
    present: bool


@router.get("", response_model=list[CircleOut])
async def list_circles(
    session_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    q = select(Circle)
    if session_id is not None:
        q = q.where(Circle.session_id == session_id)
    q = q.order_by(Circle.name)
    circles = list((await db.execute(q)).scalars().all())

    result = []
    for circle in circles:
        count_result = await db.execute(
            select(CircleMember).where(CircleMember.circle_id == circle.id)
        )
        member_count = len(list(count_result.scalars().all()))
        result.append(CircleOut(
            id=circle.id,
            name=circle.name,
            leader_id=circle.leader_id,
            session_id=circle.session_id,
            leader=circle.leader,
            member_count=member_count,
        ))
    return result


@router.get("/{circle_id}", response_model=CircleDetailOut)
async def get_circle(
    circle_id: int,
    db: AsyncSession = Depends(get_session),
):
    circle = (
        await db.execute(select(Circle).where(Circle.id == circle_id))
    ).scalar_one_or_none()
    if not circle:
        raise HTTPException(status_code=404, detail="Кружок не найден")

    schedules = list(
        (
            await db.execute(
                select(CircleSchedule)
                .where(CircleSchedule.circle_id == circle_id)
                .order_by(CircleSchedule.day_of_week, CircleSchedule.time)
            )
        ).scalars().all()
    )
    return CircleDetailOut(
        id=circle.id,
        name=circle.name,
        leader_id=circle.leader_id,
        session_id=circle.session_id,
        leader=circle.leader,
        schedule=schedules,
    )


@router.get("/{circle_id}/members", response_model=list[ChildMemberOut])
async def list_circle_members(
    circle_id: int,
    db: AsyncSession = Depends(get_session),
):
    circle = (
        await db.execute(select(Circle).where(Circle.id == circle_id))
    ).scalar_one_or_none()
    if not circle:
        raise HTTPException(status_code=404, detail="Кружок не найден")

    members = list(
        (
            await db.execute(
                select(CircleMember).where(CircleMember.circle_id == circle_id)
            )
        ).scalars().all()
    )
    children = []
    for m in members:
        child = (
            await db.execute(select(Child).where(Child.id == m.child_id))
        ).scalar_one_or_none()
        if child:
            children.append(ChildMemberOut(
                id=child.id,
                full_name=child.full_name,
                squad_id=child.squad_id,
            ))
    return children


@router.post("/{circle_id}/attendance", status_code=200)
async def save_attendance(
    circle_id: int,
    body: AttendanceSave,
    db: AsyncSession = Depends(get_session),
):
    circle = (
        await db.execute(select(Circle).where(Circle.id == circle_id))
    ).scalar_one_or_none()
    if not circle:
        raise HTTPException(status_code=404, detail="Кружок не найден")

    try:
        att_date = datetime.strptime(body.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Формат даты: YYYY-MM-DD")

    for record in body.records:
        stmt = (
            pg_insert(CircleAttendance)
            .values(
                circle_id=circle_id,
                child_id=record.child_id,
                date=att_date,
                present=record.present,
            )
            .on_conflict_do_update(
                index_elements=["circle_id", "child_id", "date"],
                set_={"present": record.present},
            )
        )
        await db.execute(stmt)
    await db.commit()
    return {"ok": True, "saved": len(body.records)}


@router.get("/{circle_id}/attendance", response_model=list[AttendanceOut])
async def get_attendance(
    circle_id: int,
    date_filter: Optional[str] = Query(None, alias="date"),
    db: AsyncSession = Depends(get_session),
):
    circle = (
        await db.execute(select(Circle).where(Circle.id == circle_id))
    ).scalar_one_or_none()
    if not circle:
        raise HTTPException(status_code=404, detail="Кружок не найден")

    q = select(CircleAttendance).where(CircleAttendance.circle_id == circle_id)
    if date_filter is not None:
        try:
            parsed_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            q = q.where(CircleAttendance.date == parsed_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="Формат даты: YYYY-MM-DD")
    q = q.order_by(CircleAttendance.date.desc(), CircleAttendance.child_id)
    result = await db.execute(q)
    return list(result.scalars().all())
