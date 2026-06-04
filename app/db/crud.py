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

import time as _time

# Simple in-memory caches
_active_session_cache: tuple | None = None  # (session_obj, expire_ts)
_SESSION_CACHE_TTL = 300.0  # 5 minutes


def _invalidate_session_cache():
    global _active_session_cache
    _active_session_cache = None



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


async def get_staff_by_role(session: AsyncSession, role: StaffRole) -> list[Staff]:
    result = await session.execute(
        select(Staff).where(
            Staff.role == role,
            Staff.is_active == True,
        ).order_by(Staff.full_name)
    )
    return list(result.scalars().all())


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
    global _active_session_cache
    if _active_session_cache is not None and _time.monotonic() < _active_session_cache[1]:
        return _active_session_cache[0]
    result = await session.execute(select(Session).where(Session.is_active == True))
    obj = result.scalar_one_or_none()
    _active_session_cache = (obj, _time.monotonic() + _SESSION_CACHE_TTL)
    return obj


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
    _invalidate_session_cache()
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


# --- Children ---

async def get_child_by_id(session: AsyncSession, child_id: int) -> "Child | None":
    from app.db.models import Child
    result = await session.execute(select(Child).where(Child.id == child_id))
    return result.scalar_one_or_none()


async def search_children(
    session: AsyncSession,
    search: Optional[str] = None,
    squad_id: Optional[int] = None,
    session_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list, int]:
    from sqlalchemy import func as sa_func, or_, text
    from app.db.models import Child

    def _apply_filters(q, include_search=True):
        if squad_id is not None:
            q = q.where(Child.squad_id == squad_id)
        if session_id is not None:
            q = q.where(Child.session_id == session_id)
        if include_search and search:
            pattern = f"%{search}%"
            q = q.where(or_(
                Child.full_name.ilike(pattern),
                Child.dormitory.ilike(pattern),
                Child.food_type.ilike(pattern),
                Child.allergies.ilike(pattern),
                text(
                    "EXISTS (SELECT 1 FROM jsonb_each_text(COALESCE(children.raw_data, '{}')) "
                    "WHERE value ILIKE :pat)"
                ).bindparams(pat=pattern),
            ))
        return q

    count_q = _apply_filters(select(sa_func.count()).select_from(Child))
    total = (await session.execute(count_q)).scalar_one()

    rows_q = _apply_filters(select(Child)).order_by(Child.full_name).offset(offset).limit(limit)
    result = await session.execute(rows_q)
    return list(result.scalars().all()), total


async def search_children_by_field(
    session: AsyncSession, field: str, value: str
) -> list:
    from sqlalchemy import or_, text
    from app.db.models import Child
    pattern = f"%{value}%"
    model_fields = {"full_name", "dormitory", "food_type", "allergies", "medications"}
    if field in model_fields:
        col = getattr(Child, field)
        q = select(Child).where(col.ilike(pattern))
    else:
        # search in raw_data jsonb key
        q = select(Child).where(
            text(
                "children.raw_data ->> :key ILIKE :pat"
            ).bindparams(key=field, pat=pattern)
        )
    result = await session.execute(q.order_by(Child.full_name).limit(50))
    return list(result.scalars().all())


async def upsert_child(
    session: AsyncSession,
    full_name: str,
    birth_date,
    squad_id: Optional[int] = None,
    session_id: Optional[int] = None,
    dormitory: Optional[str] = None,
    food_type: Optional[str] = None,
    allergies: Optional[str] = None,
    medications: Optional[str] = None,
    raw_data: Optional[dict] = None,
    parents: Optional[list[dict]] = None,
) -> tuple:
    from app.db.models import Child, Parent
    # match by full_name + birth_date
    q = select(Child).where(Child.full_name == full_name)
    if birth_date is not None:
        q = q.where(Child.birth_date == birth_date)
    result = await session.execute(q)
    child = result.scalar_one_or_none()

    if child:
        # update
        if squad_id is not None:
            child.squad_id = squad_id
        if session_id is not None:
            child.session_id = session_id
        if dormitory is not None:
            child.dormitory = dormitory
        if food_type is not None:
            child.food_type = food_type
        if allergies is not None:
            child.allergies = allergies
        if medications is not None:
            child.medications = medications
        if raw_data:
            child.raw_data = {**(child.raw_data or {}), **raw_data}
        was_new = False
    else:
        child = Child(
            full_name=full_name, birth_date=birth_date, squad_id=squad_id,
            session_id=session_id, dormitory=dormitory, food_type=food_type,
            allergies=allergies, medications=medications, raw_data=raw_data,
        )
        session.add(child)
        was_new = True

    await session.flush()  # get child.id without committing

    if parents:
        await session.execute(
            __import__("sqlalchemy").delete(Parent).where(Parent.child_id == child.id)
        )
        for p in parents:
            session.add(Parent(
                child_id=child.id,
                full_name=p.get("full_name", ""),
                phone=p.get("phone"),
                relation=p.get("relation"),
            ))

    return child, was_new


async def update_child(session: AsyncSession, child_id: int, **kwargs):
    from app.db.models import Child
    await session.execute(update(Child).where(Child.id == child_id).values(**kwargs))
    await session.commit()
    return await get_child_by_id(session, child_id)


async def get_children_with_birthday(session: AsyncSession, month: int, day: int) -> list:
    from sqlalchemy import extract
    from app.db.models import Child
    result = await session.execute(
        select(Child).where(
            extract("month", Child.birth_date) == month,
            extract("day", Child.birth_date) == day,
        )
    )
    return list(result.scalars().all())


# ── Reminders ─────────────────────────────────────────────────────────────────

async def create_reminder(session: AsyncSession, staff_id: int, send_at, text: str,
                          event_id=None, task_id=None):
    from app.db.models import Reminder
    r = Reminder(staff_id=staff_id, send_at=send_at, text=text, event_id=event_id, task_id=task_id)
    session.add(r)
    await session.commit()
    return r


async def get_pending_reminders(session: AsyncSession):
    from app.db.models import Reminder
    from sqlalchemy import func as sf
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    result = await session.execute(
        select(Reminder).where(Reminder.send_at <= now, Reminder.sent == False)
    )
    return list(result.scalars().all())


async def mark_reminder_sent(session: AsyncSession, reminder_id: int):
    from app.db.models import Reminder
    await session.execute(update(Reminder).where(Reminder.id == reminder_id).values(sent=True))
    await session.commit()


async def create_event_reminders(session: AsyncSession, event_id: int, staff_ids: list[int], start_time):
    from app.db.models import Reminder, Event
    from datetime import timedelta, timezone
    result = await session.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        return
    offsets = [
        (timedelta(hours=24), "за 24 часа"),
        (timedelta(hours=3), "за 3 часа"),
        (timedelta(minutes=30), "за 30 минут"),
    ]
    for sid in staff_ids:
        for delta, label in offsets:
            send_at = start_time - delta
            if send_at > __import__("datetime").datetime.now(timezone.utc):
                r = Reminder(staff_id=sid, event_id=event_id, send_at=send_at,
                             text=f"🔔 Напоминание {label}: <b>{event.title}</b>\n"
                                  f"Начало: {start_time.strftime('%d.%m %H:%M')}\n"
                                  f"Место: {event.location or '—'}")
                session.add(r)
    await session.commit()


# ── Duties ────────────────────────────────────────────────────────────────────

async def generate_duties(session: AsyncSession, session_id: int):
    from app.db.models import Duty, DutyType, Session as CampSession, Staff
    from datetime import timedelta
    camp = (await session.execute(select(CampSession).where(CampSession.id == session_id))).scalar_one_or_none()
    if not camp:
        return 0
    staff_list = (await session.execute(select(Staff).where(Staff.is_active == True))).scalars().all()
    if not staff_list:
        return 0
    # delete existing
    await session.execute(__import__("sqlalchemy").delete(Duty).where(Duty.session_id == session_id))
    duty_types = list(DutyType)
    staff_cycle = list(staff_list)
    created = 0
    current = camp.start_date
    idx = 0
    while current <= camp.end_date:
        for dtype in duty_types:
            s = staff_cycle[idx % len(staff_cycle)]
            session.add(Duty(type=dtype, staff_id=s.id, date=current, session_id=session_id))
            idx += 1
            created += 1
        current += timedelta(days=1)
    await session.commit()
    return created


async def get_duties_by_date(session: AsyncSession, dt, session_id: int):
    from app.db.models import Duty
    result = await session.execute(
        select(Duty).where(Duty.date == dt, Duty.session_id == session_id)
    )
    return list(result.scalars().all())


async def get_duties_by_staff(session: AsyncSession, staff_id: int):
    from app.db.models import Duty
    from datetime import date
    today = date.today()
    result = await session.execute(
        select(Duty).where(Duty.staff_id == staff_id, Duty.date >= today).order_by(Duty.date)
    )
    return list(result.scalars().all())


async def get_night_duties_active(session: AsyncSession):
    from app.db.models import Duty, DutyStatus, DutyType
    from datetime import date
    today = date.today()
    result = await session.execute(
        select(Duty).where(
            Duty.date == today,
            Duty.type == DutyType.night,
            Duty.status == DutyStatus.active,
        )
    )
    return list(result.scalars().all())


async def duty_add_checkpoint(session: AsyncSession, duty_id: int, label: str):
    from app.db.models import DutyCheckpoint
    from datetime import datetime, timezone
    cp = DutyCheckpoint(duty_id=duty_id, label=label, confirmed_at=datetime.now(timezone.utc))
    session.add(cp)
    await session.commit()
    return cp


async def update_duty_status(session: AsyncSession, duty_id: int, status):
    from app.db.models import Duty
    await session.execute(update(Duty).where(Duty.id == duty_id).values(status=status))
    await session.commit()


# ── Incidents ─────────────────────────────────────────────────────────────────

async def create_incident(session: AsyncSession, type_: str, description: str, reported_by: int,
                          session_id=None, child_id=None, photo_url=None):
    from app.db.models import Incident
    inc = Incident(type=type_, description=description, reported_by=reported_by,
                   session_id=session_id, child_id=child_id, photo_url=photo_url)
    session.add(inc)
    await session.commit()
    await session.refresh(inc)
    return inc


async def get_incidents_today(session: AsyncSession, session_id=None):
    from app.db.models import Incident
    from datetime import date, datetime, timezone
    today = date.today()
    start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    q = select(Incident).where(Incident.created_at >= start).order_by(Incident.created_at.desc())
    if session_id:
        q = q.where(Incident.session_id == session_id)
    return list((await session.execute(q)).scalars().all())


async def get_incidents_all(session: AsyncSession, session_id=None, offset=0, limit=20):
    from app.db.models import Incident
    q = select(Incident).order_by(Incident.created_at.desc()).offset(offset).limit(limit)
    if session_id:
        q = q.where(Incident.session_id == session_id)
    return list((await session.execute(q)).scalars().all())


# ── Checklists ────────────────────────────────────────────────────────────────

async def create_checklist_template(session: AsyncSession, type_, title, session_id, items: list[str]):
    from app.db.models import ChecklistTemplate, ChecklistItem
    tmpl = ChecklistTemplate(type=type_, title=title, session_id=session_id)
    session.add(tmpl)
    await session.flush()
    for i, text in enumerate(items):
        session.add(ChecklistItem(template_id=tmpl.id, text=text, order_index=i))
    await session.commit()
    await session.refresh(tmpl)
    return tmpl


async def get_checklist_templates(session: AsyncSession, type_=None, session_id=None):
    from app.db.models import ChecklistTemplate
    q = select(ChecklistTemplate)
    if type_:
        q = q.where(ChecklistTemplate.type == type_)
    if session_id:
        q = q.where(ChecklistTemplate.session_id == session_id)
    return list((await session.execute(q)).scalars().all())


async def start_checklist_run(session: AsyncSession, template_id: int, staff_id: int, event_id=None):
    from app.db.models import ChecklistRun, ChecklistItemResult, ChecklistTemplate
    tmpl = (await session.execute(select(ChecklistTemplate).where(ChecklistTemplate.id == template_id))).scalar_one_or_none()
    if not tmpl:
        return None
    run = ChecklistRun(template_id=template_id, staff_id=staff_id, event_id=event_id)
    session.add(run)
    await session.flush()
    for item in tmpl.items:
        session.add(ChecklistItemResult(run_id=run.id, item_id=item.id))
    await session.commit()
    await session.refresh(run)
    return run


async def get_checklist_run(session: AsyncSession, run_id: int):
    from app.db.models import ChecklistRun
    return (await session.execute(select(ChecklistRun).where(ChecklistRun.id == run_id))).scalar_one_or_none()


async def confirm_checklist_item(session: AsyncSession, result_id: int):
    from app.db.models import ChecklistItemResult
    from datetime import datetime, timezone
    await session.execute(
        update(ChecklistItemResult).where(ChecklistItemResult.id == result_id)
        .values(confirmed_at=datetime.now(timezone.utc))
    )
    await session.commit()


async def complete_checklist_run(session: AsyncSession, run_id: int):
    from app.db.models import ChecklistRun
    from datetime import datetime, timezone
    await session.execute(
        update(ChecklistRun).where(ChecklistRun.id == run_id)
        .values(completed_at=datetime.now(timezone.utc))
    )
    await session.commit()


# ── Announcements ─────────────────────────────────────────────────────────────

async def create_announcement(session: AsyncSession, text: str, created_by: int, session_id=None):
    from app.db.models import Announcement
    ann = Announcement(text=text, created_by=created_by, session_id=session_id)
    session.add(ann)
    await session.commit()
    await session.refresh(ann)
    return ann


async def get_announcements(session: AsyncSession, session_id=None, limit=10, offset=0):
    from app.db.models import Announcement
    q = select(Announcement).order_by(Announcement.created_at.desc()).offset(offset).limit(limit)
    if session_id:
        q = q.where(Announcement.session_id == session_id)
    return list((await session.execute(q)).scalars().all())


async def mark_announcement_read(session: AsyncSession, announcement_id: int, staff_id: int):
    from app.db.models import AnnouncementRead
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = pg_insert(AnnouncementRead).values(announcement_id=announcement_id, staff_id=staff_id)
    stmt = stmt.on_conflict_do_nothing()
    await session.execute(stmt)
    await session.commit()


async def get_announcement_reads(session: AsyncSession, announcement_id: int):
    from app.db.models import AnnouncementRead
    result = await session.execute(
        select(AnnouncementRead).where(AnnouncementRead.announcement_id == announcement_id)
    )
    return list(result.scalars().all())


# ── Event Ratings ─────────────────────────────────────────────────────────────

async def save_event_rating(session: AsyncSession, event_id: int, staff_id: int, rating: int, comment=None):
    from app.db.models import EventRating
    r = EventRating(event_id=event_id, staff_id=staff_id, rating=rating, comment=comment)
    session.add(r)
    await session.commit()
    return r


async def get_event_ratings(session: AsyncSession, event_id: int):
    from app.db.models import EventRating
    result = await session.execute(select(EventRating).where(EventRating.event_id == event_id))
    return list(result.scalars().all())


async def get_staff_task_stats(session: AsyncSession, staff_id: int, session_id=None):
    from app.db.models import Task, TaskStatus
    from sqlalchemy import func as sf
    q = select(Task.status, sf.count(Task.id)).where(
        (Task.assigned_to == staff_id) | (Task.created_by == staff_id)
    ).group_by(Task.status)
    if session_id:
        q = q.where(Task.session_id == session_id)
    rows = (await session.execute(q)).all()
    return {row[0]: row[1] for row in rows}


async def get_session_stats(session: AsyncSession, session_id: int):
    from app.db.models import Task, TaskStatus, Event, Incident
    from sqlalchemy import func as sf
    total_tasks = (await session.execute(
        select(sf.count(Task.id)).where(Task.session_id == session_id)
    )).scalar_one()
    done_tasks = (await session.execute(
        select(sf.count(Task.id)).where(Task.session_id == session_id, Task.status == TaskStatus.done)
    )).scalar_one()
    total_events = (await session.execute(
        select(sf.count(Event.id)).where(Event.session_id == session_id)
    )).scalar_one()
    total_incidents = (await session.execute(
        select(sf.count(Incident.id)).where(Incident.session_id == session_id)
    )).scalar_one()
    return {
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "total_events": total_events,
        "total_incidents": total_incidents,
    }


# ── Circles ───────────────────────────────────────────────────────────────────

async def create_circle(session: AsyncSession, name: str, leader_id=None, session_id=None):
    from app.db.models import Circle
    c = Circle(name=name, leader_id=leader_id, session_id=session_id)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def get_circles(session: AsyncSession, session_id=None, leader_id=None):
    from app.db.models import Circle
    q = select(Circle)
    if session_id:
        q = q.where(Circle.session_id == session_id)
    if leader_id:
        q = q.where(Circle.leader_id == leader_id)
    return list((await session.execute(q)).scalars().all())


async def get_circle_by_id(session: AsyncSession, circle_id: int):
    from app.db.models import Circle
    return (await session.execute(select(Circle).where(Circle.id == circle_id))).scalar_one_or_none()


async def add_circle_schedule(session: AsyncSession, circle_id: int, day_of_week: int, time_):
    from app.db.models import CircleSchedule
    cs = CircleSchedule(circle_id=circle_id, day_of_week=day_of_week, time=time_)
    session.add(cs)
    await session.commit()
    return cs


async def add_circle_member(session: AsyncSession, circle_id: int, child_id: int):
    from app.db.models import CircleMember
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = pg_insert(CircleMember).values(circle_id=circle_id, child_id=child_id)
    stmt = stmt.on_conflict_do_nothing()
    await session.execute(stmt)
    await session.commit()


async def get_circle_members(session: AsyncSession, circle_id: int):
    from app.db.models import CircleMember
    result = await session.execute(
        select(CircleMember).where(CircleMember.circle_id == circle_id)
    )
    return list(result.scalars().all())


async def save_circle_attendance(session: AsyncSession, circle_id: int, child_id: int, date_, present: bool):
    from app.db.models import CircleAttendance
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = pg_insert(CircleAttendance).values(
        circle_id=circle_id, child_id=child_id, date=date_, present=present
    ).on_conflict_do_update(
        index_elements=["circle_id", "child_id", "date"],
        set_={"present": present}
    )
    await session.execute(stmt)
    await session.commit()


async def get_today_circles(session: AsyncSession):
    from app.db.models import Circle, CircleSchedule
    from datetime import date
    dow = date.today().weekday()
    result = await session.execute(
        select(Circle).join(CircleSchedule, CircleSchedule.circle_id == Circle.id)
        .where(CircleSchedule.day_of_week == dow)
    )
    return list(result.scalars().unique().all())


async def get_birthdays_range(session: AsyncSession, days: int = 7):
    from app.db.models import Child
    from datetime import date, timedelta
    from sqlalchemy import extract, or_
    today = date.today()
    result_list = []
    for i in range(days):
        d = today + timedelta(days=i)
        rows = (await session.execute(
            select(Child).where(
                extract("month", Child.birth_date) == d.month,
                extract("day", Child.birth_date) == d.day,
            )
        )).scalars().all()
        for c in rows:
            result_list.append((d, c))
    return result_list


async def get_active_session(session: AsyncSession):
    from app.db.models import Session as CampSession
    return (await session.execute(
        select(CampSession).where(CampSession.is_active == True)
    )).scalar_one_or_none()
