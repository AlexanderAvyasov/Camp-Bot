from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import FreeStaffOut, SquadCreate, SquadDetailOut, SquadUpdate
from app.db.base import get_session
from app.db.crud import (
    create_squad,
    get_all_squads,
    get_free_staff_by_role,
    get_squad_by_id,
    get_staff_by_id,
    update_squad,
)
from app.db.models import StaffRole

router = APIRouter(prefix="/api/squads", tags=["squads"])

_COUNSELOR_ROLES = {StaffRole.counselor, StaffRole.senior_counselor}
_EDUCATOR_ROLES = {StaffRole.educator}


@router.get("", response_model=list[SquadDetailOut])
async def list_squads(session: AsyncSession = Depends(get_session)):
    return await get_all_squads(session)


@router.get("/free_staff", response_model=list[FreeStaffOut])
async def free_staff(
    role: StaffRole = Query(...),
    session: AsyncSession = Depends(get_session),
):
    return await get_free_staff_by_role(session, role)


@router.get("/{squad_id}", response_model=SquadDetailOut)
async def get_squad(squad_id: int, session: AsyncSession = Depends(get_session)):
    squad = await get_squad_by_id(session, squad_id)
    if not squad:
        raise HTTPException(status_code=404, detail="Отряд не найден")
    return squad


@router.post("", response_model=SquadDetailOut, status_code=201)
async def create_squad_endpoint(body: SquadCreate, session: AsyncSession = Depends(get_session)):
    if body.counselor_id:
        person = await get_staff_by_id(session, body.counselor_id)
        if not person:
            raise HTTPException(status_code=404, detail="Вожатый не найден")
        if person.role not in _COUNSELOR_ROLES:
            raise HTTPException(status_code=422, detail="Сотрудник не является вожатым")
    if body.educator_id:
        person = await get_staff_by_id(session, body.educator_id)
        if not person:
            raise HTTPException(status_code=404, detail="Воспитатель не найден")
        if person.role not in _EDUCATOR_ROLES:
            raise HTTPException(status_code=422, detail="Сотрудник не является воспитателем")
    return await create_squad(session, body.name, body.counselor_id, body.educator_id)


@router.patch("/{squad_id}", response_model=SquadDetailOut)
async def update_squad_endpoint(
    squad_id: int, body: SquadUpdate, session: AsyncSession = Depends(get_session)
):
    squad = await get_squad_by_id(session, squad_id)
    if not squad:
        raise HTTPException(status_code=404, detail="Отряд не найден")
    if body.counselor_id:
        person = await get_staff_by_id(session, body.counselor_id)
        if not person:
            raise HTTPException(status_code=404, detail="Вожатый не найден")
        if person.role not in _COUNSELOR_ROLES:
            raise HTTPException(status_code=422, detail="Сотрудник не является вожатым")
    if body.educator_id:
        person = await get_staff_by_id(session, body.educator_id)
        if not person:
            raise HTTPException(status_code=404, detail="Воспитатель не найден")
        if person.role not in _EDUCATOR_ROLES:
            raise HTTPException(status_code=422, detail="Сотрудник не является воспитателем")
    updated = await update_squad(session, squad_id, body.counselor_id, body.educator_id)
    return updated
