from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import (
    Announcement, AnnouncementRead, Event, Staff, Task, TaskStatus,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class DashboardStats(BaseModel):
    tasks_today: int
    events_today: int
    unread_announcements: int
    my_tasks: int


class StaffTaskStats(BaseModel):
    staff_id: int
    full_name: str
    tasks_done: int
    tasks_overdue: int
    tasks_total: int


class LeaderboardEntry(BaseModel):
    rank: int
    staff_id: int
    full_name: str
    tasks_done: int


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    staff_id: Optional[int] = Query(None),
    session_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    today = date.today()
    day_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    day_end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc)

    tasks_q = select(func.count(Task.id)).where(
        Task.created_at >= day_start,
        Task.created_at <= day_end,
    )
    if session_id is not None:
        tasks_q = tasks_q.where(Task.session_id == session_id)
    tasks_today = (await db.execute(tasks_q)).scalar_one()

    events_q = select(func.count(Event.id)).where(
        Event.start_time >= day_start,
        Event.start_time <= day_end,
    )
    if session_id is not None:
        events_q = events_q.where(Event.session_id == session_id)
    events_today = (await db.execute(events_q)).scalar_one()

    unread_announcements = 0
    if staff_id is not None:
        ann_q = select(func.count(Announcement.id))
        if session_id is not None:
            ann_q = ann_q.where(Announcement.session_id == session_id)
        read_subq = (
            select(AnnouncementRead.announcement_id)
            .where(AnnouncementRead.staff_id == staff_id)
        )
        ann_q = ann_q.where(Announcement.id.not_in(read_subq))
        unread_announcements = (await db.execute(ann_q)).scalar_one()

    my_tasks = 0
    if staff_id is not None:
        my_q = select(func.count(Task.id)).where(
            Task.assigned_to == staff_id,
            Task.status != TaskStatus.done,
        )
        if session_id is not None:
            my_q = my_q.where(Task.session_id == session_id)
        my_tasks = (await db.execute(my_q)).scalar_one()

    return DashboardStats(
        tasks_today=tasks_today,
        events_today=events_today,
        unread_announcements=unread_announcements,
        my_tasks=my_tasks,
    )


@router.get("/staff/{staff_id}", response_model=StaffTaskStats)
async def staff_stats(
    staff_id: int,
    session_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    staff = (
        await db.execute(select(Staff).where(Staff.id == staff_id))
    ).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    def base_q():
        q = select(func.count(Task.id)).where(Task.assigned_to == staff_id)
        if session_id is not None:
            q = q.where(Task.session_id == session_id)
        return q

    tasks_done = (await db.execute(base_q().where(Task.status == TaskStatus.done))).scalar_one()
    tasks_overdue = (await db.execute(base_q().where(Task.status == TaskStatus.overdue))).scalar_one()
    tasks_total = (await db.execute(base_q())).scalar_one()

    return StaffTaskStats(
        staff_id=staff_id,
        full_name=staff.full_name,
        tasks_done=tasks_done,
        tasks_overdue=tasks_overdue,
        tasks_total=tasks_total,
    )


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard(
    session_id: Optional[int] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
):
    q = (
        select(Staff.id, Staff.full_name, func.count(Task.id).label("tasks_done"))
        .join(Task, Task.assigned_to == Staff.id)
        .where(Task.status == TaskStatus.done, Staff.is_active == True)
    )
    if session_id is not None:
        q = q.where(Task.session_id == session_id)
    q = q.group_by(Staff.id, Staff.full_name).order_by(func.count(Task.id).desc()).limit(limit)
    rows = (await db.execute(q)).all()

    return [
        LeaderboardEntry(
            rank=idx + 1,
            staff_id=row.id,
            full_name=row.full_name,
            tasks_done=row.tasks_done,
        )
        for idx, row in enumerate(rows)
    ]
