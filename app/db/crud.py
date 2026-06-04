from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActionLog, Squad, Staff, StaffRole


# --- Staff ---

async def get_staff_by_telegram_id(session: AsyncSession, telegram_id: int) -> Staff | None:
    result = await session.execute(select(Staff).where(Staff.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_staff_by_id(session: AsyncSession, staff_id: int) -> Staff | None:
    result = await session.execute(select(Staff).where(Staff.id == staff_id))
    return result.scalar_one_or_none()


async def get_all_active_staff(session: AsyncSession) -> list[Staff]:
    result = await session.execute(
        select(Staff).where(Staff.is_active == True).order_by(Staff.full_name)
    )
    return list(result.scalars().all())


async def get_all_staff_paginated(
    session: AsyncSession, offset: int = 0, limit: int = 10
) -> tuple[list[Staff], int]:
    count_result = await session.execute(select(Staff))
    total = len(list(count_result.scalars().all()))
    result = await session.execute(
        select(Staff).order_by(Staff.full_name).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def create_staff(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    role: StaffRole,
    squad_id: int | None = None,
) -> Staff:
    staff = Staff(
        telegram_id=telegram_id,
        full_name=full_name,
        role=role,
        squad_id=squad_id,
    )
    session.add(staff)
    await session.commit()
    await session.refresh(staff)
    return staff


async def update_staff(
    session: AsyncSession,
    staff_id: int,
    **kwargs,
) -> Staff | None:
    await session.execute(
        update(Staff).where(Staff.id == staff_id).values(**kwargs)
    )
    await session.commit()
    return await get_staff_by_id(session, staff_id)


async def deactivate_staff(session: AsyncSession, staff_id: int) -> Staff | None:
    return await update_staff(session, staff_id, is_active=False)


# --- Squads ---

async def get_all_squads(session: AsyncSession) -> list[Squad]:
    result = await session.execute(select(Squad).order_by(Squad.name))
    return list(result.scalars().all())


async def get_squad_by_id(session: AsyncSession, squad_id: int) -> Squad | None:
    result = await session.execute(select(Squad).where(Squad.id == squad_id))
    return result.scalar_one_or_none()


async def create_squad(session: AsyncSession, name: str) -> Squad:
    squad = Squad(name=name)
    session.add(squad)
    await session.commit()
    await session.refresh(squad)
    return squad


# --- Action logs ---

async def log_action(
    session: AsyncSession,
    actor_id: int,
    action: str,
    target_id: int | None = None,
) -> ActionLog:
    log = ActionLog(actor_id=actor_id, action=action, target_id=target_id)
    session.add(log)
    await session.commit()
    return log
