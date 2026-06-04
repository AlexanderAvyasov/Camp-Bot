from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ActionLog, DaySchedule, DayType,
    Event, EventMember, EventType,
    Session, Squad, Staff, StaffRole,
    Task, TaskLog, TaskPhoto, TaskPriority, TaskStatus, TaskTemplate, RecurrenceType,
)


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


async def create_squad(
    session: AsyncSession,
    name: str,
    counselor_id: int | None = None,
    educator_id: int | None = None,
    educator_id_2: int | None = None,
) -> Squad:
    squad = Squad(name=name, counselor_id=counselor_id, educator_id=educator_id, educator_id_2=educator_id_2)
    session.add(squad)
    await session.flush()
    for sid in filter(None, [counselor_id, educator_id, educator_id_2]):
        await session.execute(update(Staff).where(Staff.id == sid).values(squad_id=squad.id))
    await session.commit()
    await session.refresh(squad)
    return squad


async def update_squad(
    session: AsyncSession,
    squad_id: int,
    counselor_id: int | None = None,
    educator_id: int | None = None,
    educator_id_2: int | None = None,
) -> Squad | None:
    squad = await get_squad_by_id(session, squad_id)
    if not squad:
        return None
    updates: dict = {}
    # Helper: unassign old, assign new
    async def _swap(old_id, new_id, field):
        if new_id is not None:
            if old_id and old_id != new_id:
                await session.execute(update(Staff).where(Staff.id == old_id).values(squad_id=None))
            await session.execute(update(Staff).where(Staff.id == new_id).values(squad_id=squad_id))
            updates[field] = new_id
    await _swap(squad.counselor_id, counselor_id, "counselor_id")
    await _swap(squad.educator_id, educator_id, "educator_id")
    await _swap(squad.educator_id_2, educator_id_2, "educator_id_2")
    if updates:
        await session.execute(update(Squad).where(Squad.id == squad_id).values(**updates))
    await session.commit()
    return await get_squad_by_id(session, squad_id)


async def get_free_staff_by_role(session: AsyncSession, role: StaffRole) -> list[Staff]:
    result = await session.execute(
        select(Staff).where(
            Staff.role == role,
            Staff.is_active == True,
            Staff.squad_id == None,
        ).order_by(Staff.full_name)
    )
    return list(result.scalars().all())


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


# --- Tasks ---

async def create_task(
    session: AsyncSession,
    title: str,
    created_by: int,
    session_id: Optional[int] = None,
    description: Optional[str] = None,
    assigned_to: Optional[int] = None,
    group_role: Optional[StaffRole] = None,
    priority: TaskPriority = TaskPriority.medium,
    deadline: Optional[datetime] = None,
    is_recurring: bool = False,
    recurrence_type: Optional[RecurrenceType] = None,
    template_id: Optional[int] = None,
) -> Task:
    task = Task(
        title=title, description=description, created_by=created_by,
        assigned_to=assigned_to, group_role=group_role, priority=priority,
        status=TaskStatus.new, deadline=deadline, is_recurring=is_recurring,
        recurrence_type=recurrence_type, template_id=template_id, session_id=session_id,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_task_by_id(session: AsyncSession, task_id: int) -> Task | None:
    result = await session.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def get_tasks_for_staff(session: AsyncSession, staff_id: int) -> list[Task]:
    result = await session.execute(
        select(Task)
        .where(Task.assigned_to == staff_id, Task.status != TaskStatus.done)
        .order_by(Task.priority.desc(), Task.deadline)
    )
    return list(result.scalars().all())


async def get_all_tasks(
    session: AsyncSession,
    status: Optional[TaskStatus] = None,
    assigned_to: Optional[int] = None,
    session_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 10,
) -> tuple[list[Task], int]:
    q = select(Task)
    if status:
        q = q.where(Task.status == status)
    if assigned_to:
        q = q.where(Task.assigned_to == assigned_to)
    if session_id:
        q = q.where(Task.session_id == session_id)
    count_q = select(Task)
    if status:
        count_q = count_q.where(Task.status == status)
    if assigned_to:
        count_q = count_q.where(Task.assigned_to == assigned_to)
    if session_id:
        count_q = count_q.where(Task.session_id == session_id)
    total = len(list((await session.execute(count_q)).scalars().all()))
    result = await session.execute(q.order_by(Task.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def get_overdue_tasks(session: AsyncSession) -> list[Task]:
    now = datetime.utcnow()
    result = await session.execute(
        select(Task).where(
            Task.deadline < now,
            Task.status.not_in([TaskStatus.done, TaskStatus.overdue]),
        )
    )
    return list(result.scalars().all())


async def get_recurring_tasks(session: AsyncSession) -> list[Task]:
    today = datetime.utcnow().date()
    result = await session.execute(
        select(Task).where(
            Task.is_recurring == True,
            Task.status == TaskStatus.done,
            or_(Task.paused_until == None, Task.paused_until <= today),
        )
    )
    return list(result.scalars().all())


async def update_task_status(
    session: AsyncSession, task_id: int, actor_id: int, status: TaskStatus, action_text: str
) -> Task | None:
    await session.execute(update(Task).where(Task.id == task_id).values(status=status))
    log = TaskLog(task_id=task_id, actor_id=actor_id, action=action_text)
    session.add(log)
    await session.commit()
    return await get_task_by_id(session, task_id)


async def update_task(session: AsyncSession, task_id: int, **kwargs) -> Task | None:
    await session.execute(update(Task).where(Task.id == task_id).values(**kwargs))
    await session.commit()
    return await get_task_by_id(session, task_id)


async def add_task_log(
    session: AsyncSession, task_id: int, actor_id: int, action: str
) -> TaskLog:
    log = TaskLog(task_id=task_id, actor_id=actor_id, action=action)
    session.add(log)
    await session.commit()
    return log


async def get_task_logs(session: AsyncSession, task_id: int) -> list[TaskLog]:
    result = await session.execute(
        select(TaskLog).where(TaskLog.task_id == task_id).order_by(TaskLog.timestamp)
    )
    return list(result.scalars().all())


async def add_task_photo(session: AsyncSession, task_id: int, photo_url: str) -> TaskPhoto:
    photo = TaskPhoto(task_id=task_id, photo_url=photo_url)
    session.add(photo)
    await session.commit()
    return photo


# --- Task templates ---

async def create_template(
    session: AsyncSession,
    title: str,
    description: Optional[str],
    group_role: Optional[StaffRole],
    priority: TaskPriority,
    recurrence_type: Optional[RecurrenceType],
) -> TaskTemplate:
    tmpl = TaskTemplate(
        title=title, description=description, group_role=group_role,
        priority=priority, recurrence_type=recurrence_type,
    )
    session.add(tmpl)
    await session.commit()
    await session.refresh(tmpl)
    return tmpl


async def get_all_templates(session: AsyncSession) -> list[TaskTemplate]:
    result = await session.execute(select(TaskTemplate).order_by(TaskTemplate.title))
    return list(result.scalars().all())


async def get_template_by_id(session: AsyncSession, tmpl_id: int) -> TaskTemplate | None:
    result = await session.execute(select(TaskTemplate).where(TaskTemplate.id == tmpl_id))
    return result.scalar_one_or_none()


# --- Events ---

async def check_location_conflict(
    session: AsyncSession,
    location: str,
    start_time: datetime,
    end_time: datetime,
    session_id: Optional[int],
    exclude_id: Optional[int] = None,
) -> list[Event]:
    q = select(Event).where(
        Event.location == location,
        Event.start_time < end_time,
        Event.end_time > start_time,
    )
    if session_id:
        q = q.where(Event.session_id == session_id)
    if exclude_id:
        q = q.where(Event.id != exclude_id)
    result = await session.execute(q)
    return list(result.scalars().all())


async def check_responsible_conflict(
    session: AsyncSession,
    responsible_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_id: Optional[int] = None,
) -> list[Event]:
    q = select(Event).where(
        Event.responsible_id == responsible_id,
        Event.start_time < end_time,
        Event.end_time > start_time,
    )
    if exclude_id:
        q = q.where(Event.id != exclude_id)
    result = await session.execute(q)
    return list(result.scalars().all())


async def create_event(
    session: AsyncSession,
    title: str,
    event_type: EventType,
    start_time: datetime,
    end_time: datetime,
    location: Optional[str] = None,
    responsible_id: Optional[int] = None,
    session_id: Optional[int] = None,
    member_ids: Optional[list[int]] = None,
    copied_from: Optional[int] = None,
) -> Event:
    event = Event(
        title=title, type=event_type, location=location,
        responsible_id=responsible_id, start_time=start_time,
        end_time=end_time, session_id=session_id, copied_from=copied_from,
    )
    session.add(event)
    await session.flush()
    if member_ids:
        for staff_id in set(member_ids):
            session.add(EventMember(event_id=event.id, staff_id=staff_id))
    await session.commit()
    await session.refresh(event)
    return event


async def get_event_by_id(session: AsyncSession, event_id: int) -> Event | None:
    result = await session.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def get_events(
    session: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    session_id: Optional[int] = None,
    staff_id: Optional[int] = None,
) -> list[Event]:
    q = select(Event)
    if date_from:
        q = q.where(Event.start_time >= date_from)
    if date_to:
        q = q.where(Event.start_time < date_to)
    if session_id:
        q = q.where(Event.session_id == session_id)
    if staff_id:
        member_subq = select(EventMember.event_id).where(EventMember.staff_id == staff_id)
        q = q.where(or_(Event.responsible_id == staff_id, Event.id.in_(member_subq)))
    result = await session.execute(q.order_by(Event.start_time))
    return list(result.scalars().all())


async def update_event(session: AsyncSession, event_id: int, **kwargs) -> Event | None:
    member_ids = kwargs.pop("member_ids", None)
    await session.execute(update(Event).where(Event.id == event_id).values(**kwargs))
    if member_ids is not None:
        await session.execute(
            EventMember.__table__.delete().where(EventMember.event_id == event_id)
        )
        for staff_id in set(member_ids):
            session.add(EventMember(event_id=event_id, staff_id=staff_id))
    await session.commit()
    return await get_event_by_id(session, event_id)


async def delete_event(session: AsyncSession, event_id: int) -> bool:
    event = await get_event_by_id(session, event_id)
    if not event:
        return False
    await session.delete(event)
    await session.commit()
    return True


async def copy_event(
    session: AsyncSession, event_id: int, new_date: date
) -> Event | None:
    src = await get_event_by_id(session, event_id)
    if not src:
        return None
    delta_days = (new_date - src.start_time.date())
    from datetime import timedelta
    new_start = src.start_time + timedelta(days=delta_days.days)
    new_end = src.end_time + timedelta(days=delta_days.days)
    member_ids = [m.staff_id for m in src.members]
    return await create_event(
        session, title=src.title, event_type=src.type,
        start_time=new_start, end_time=new_end,
        location=src.location, responsible_id=src.responsible_id,
        session_id=src.session_id, member_ids=member_ids,
        copied_from=src.id,
    )


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
