from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import StaffCreate, StaffOut, StaffUpdate
from app.db.base import get_session
from app.db.crud import (
    create_staff,
    get_all_active_staff,
    get_staff_by_id,
    get_staff_by_telegram_id,
    update_staff,
)

router = APIRouter(prefix="/api/staff", tags=["staff"])


@router.get("", response_model=list[StaffOut])
async def list_staff(session: AsyncSession = Depends(get_session)):
    return await get_all_active_staff(session)


@router.post("", response_model=StaffOut, status_code=201)
async def create_staff_endpoint(
    body: StaffCreate, session: AsyncSession = Depends(get_session)
):
    existing = await get_staff_by_telegram_id(session, body.telegram_id)
    if existing:
        raise HTTPException(status_code=409, detail="Сотрудник с таким Telegram ID уже существует")
    return await create_staff(session, body.telegram_id, body.full_name, body.role, body.squad_id)


@router.get("/{staff_id}", response_model=StaffOut)
async def get_staff_endpoint(staff_id: int, session: AsyncSession = Depends(get_session)):
    staff = await get_staff_by_id(session, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return staff


@router.patch("/{staff_id}", response_model=StaffOut)
async def update_staff_endpoint(
    staff_id: int, body: StaffUpdate, session: AsyncSession = Depends(get_session)
):
    staff = await get_staff_by_id(session, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        return staff

    updated = await update_staff(session, staff_id, **updates)
    return updated
