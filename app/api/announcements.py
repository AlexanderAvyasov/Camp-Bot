from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import Announcement, AnnouncementRead, Staff

router = APIRouter(prefix="/api/announcements", tags=["announcements"])


class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str
    created_by: int
    session_id: Optional[int]
    created_at: datetime


class AnnouncementCreate(BaseModel):
    text: str
    created_by: int
    session_id: Optional[int] = None


class MarkReadBody(BaseModel):
    staff_id: int


class ReadEntry(BaseModel):
    staff_id: int
    full_name: str
    read_at: datetime


class AnnouncementStats(BaseModel):
    announcement_id: int
    read_count: int
    total_staff: int
    readers: list[ReadEntry]


@router.get("", response_model=list[AnnouncementOut])
async def list_announcements(
    session_id: Optional[int] = Query(None),
    unread_for: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    q = select(Announcement)
    if session_id is not None:
        q = q.where(Announcement.session_id == session_id)
    if unread_for is not None:
        read_subq = (
            select(AnnouncementRead.announcement_id)
            .where(AnnouncementRead.staff_id == unread_for)
        )
        q = q.where(Announcement.id.not_in(read_subq))
    q = q.order_by(Announcement.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("", response_model=AnnouncementOut, status_code=201)
async def create_announcement(
    body: AnnouncementCreate,
    db: AsyncSession = Depends(get_session),
):
    staff_result = await db.execute(select(Staff).where(Staff.id == body.created_by))
    if not staff_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    ann = Announcement(text=body.text, created_by=body.created_by, session_id=body.session_id)
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return ann


@router.post("/{announcement_id}/read", status_code=200)
async def mark_read(
    announcement_id: int,
    body: MarkReadBody,
    db: AsyncSession = Depends(get_session),
):
    ann_result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    if not ann_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    existing = await db.execute(
        select(AnnouncementRead).where(
            AnnouncementRead.announcement_id == announcement_id,
            AnnouncementRead.staff_id == body.staff_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(AnnouncementRead(announcement_id=announcement_id, staff_id=body.staff_id))
        await db.commit()
    return {"ok": True}


@router.get("/{announcement_id}/stats", response_model=AnnouncementStats)
async def announcement_stats(
    announcement_id: int,
    db: AsyncSession = Depends(get_session),
):
    ann_result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    if not ann_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Объявление не найдено")

    total_staff = (
        await db.execute(select(func.count(Staff.id)).where(Staff.is_active == True))
    ).scalar_one()

    rows = (
        await db.execute(
            select(AnnouncementRead, Staff)
            .join(Staff, Staff.id == AnnouncementRead.staff_id)
            .where(AnnouncementRead.announcement_id == announcement_id)
            .order_by(AnnouncementRead.read_at)
        )
    ).all()

    readers = [
        ReadEntry(staff_id=r.staff_id, full_name=s.full_name, read_at=r.read_at)
        for r, s in rows
    ]
    return AnnouncementStats(
        announcement_id=announcement_id,
        read_count=len(readers),
        total_staff=total_staff,
        readers=readers,
    )
