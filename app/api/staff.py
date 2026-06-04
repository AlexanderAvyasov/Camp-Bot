import json
from urllib.parse import parse_qs, unquote

from fastapi import APIRouter, Depends, Header, HTTPException
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


def _telegram_id_from_init_data(init_data: str) -> int | None:
    """Parse telegram user id from Telegram WebApp initData string."""
    try:
        params = dict(pair.split("=", 1) for pair in init_data.split("&") if "=" in pair)
        user = json.loads(unquote(params.get("user", "{}")))
        uid = user.get("id")
        return int(uid) if uid else None
    except Exception:
        return None


@router.get("/me", response_model=StaffOut)
async def get_staff_me(
    x_telegram_init_data: str = Header(default=""),
    session: AsyncSession = Depends(get_session),
):
    telegram_id = _telegram_id_from_init_data(x_telegram_init_data)
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Invalid initData")
    staff = await get_staff_by_telegram_id(session, telegram_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return staff


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
