from datetime import date, time

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActionLog, DaySchedule, DayType, Session, Squad, Staff, StaffRole


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


# --- Sessions ---

async def get_all_sessions(session: AsyncSession) -> list[Session]:
    result = await session.execute(select(Session).order_by(Session.start_date.desc()))
    return list(result.scalars().all())


async def get_session_by_id(session: AsyncSession, session_id: int) -> Session | None:
    result = await session.execute(select(Session).where(Session.id == session_id))
    return result.scalar_one_or_none()


async def get_active_session(session: AsyncSession) -> Session | None:
    result = await session.execute(select(Session).where(Session.is_active == True))
    return result.scalar_one_or_none()


async def create_session(
    session: AsyncSession, name: str, start_date: date, end_date: date
) -> Session:
    obj = Session(name=name, start_date=start_date, end_date=end_date, is_active=False)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def activate_session(session: AsyncSession, session_id: int) -> Session | None:
    await session.execute(update(Session).values(is_active=False))
    await session.execute(update(Session).where(Session.id == session_id).values(is_active=True))
    await session.commit()
    return await get_session_by_id(session, session_id)


# --- Day schedule ---

async def get_schedule(session: AsyncSession, session_id: int) -> list[DaySchedule]:
    result = await session.execute(
        select(DaySchedule)
        .where(DaySchedule.session_id == session_id)
        .order_by(DaySchedule.day_type, DaySchedule.time)
    )
    return list(result.scalars().all())


async def add_schedule_item(
    session: AsyncSession,
    session_id: int,
    day_type: DayType,
    time_val: time,
    label: str,
) -> DaySchedule:
    item = DaySchedule(session_id=session_id, day_type=day_type, time=time_val, label=label)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def copy_schedule(
    session: AsyncSession, to_session_id: int, from_session_id: int
) -> int:
    items = await get_schedule(session, from_session_id)
    for item in items:
        new_item = DaySchedule(
            session_id=to_session_id,
            day_type=item.day_type,
            time=item.time,
            label=item.label,
        )
        session.add(new_item)
    await session.commit()
    return len(items)


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
