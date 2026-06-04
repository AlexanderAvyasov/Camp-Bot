import enum
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StaffRole(str, enum.Enum):
    admin = "admin"
    senior_counselor = "senior_counselor"
    counselor = "counselor"
    educator = "educator"
    coach = "coach"
    swim_coach = "swim_coach"
    music = "music"
    circle_leader = "circle_leader"


ROLE_LABELS = {
    StaffRole.admin: "Администратор",
    StaffRole.senior_counselor: "Старший вожатый",
    StaffRole.counselor: "Вожатый",
    StaffRole.educator: "Воспитатель",
    StaffRole.coach: "Тренер",
    StaffRole.swim_coach: "Тренер по плаванию",
    StaffRole.music: "Музыкальный руководитель",
    StaffRole.circle_leader: "Руководитель кружка",
}


class Squad(Base):
    __tablename__ = "squads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    counselor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("staff.id", use_alter=True, name="fk_squad_counselor"), nullable=True
    )
    educator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("staff.id", use_alter=True, name="fk_squad_educator"), nullable=True
    )
    educator_id_2: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("staff.id", use_alter=True, name="fk_squad_educator_2"), nullable=True
    )

    counselor: Mapped["Staff | None"] = relationship(
        "Staff", foreign_keys=[counselor_id], lazy="selectin"
    )
    educator: Mapped["Staff | None"] = relationship(
        "Staff", foreign_keys=[educator_id], lazy="selectin"
    )
    educator_2: Mapped["Staff | None"] = relationship(
        "Staff", foreign_keys=[educator_id_2], lazy="selectin"
    )
    members: Mapped[list["Staff"]] = relationship(
        "Staff", foreign_keys="Staff.squad_id", back_populates="squad", lazy="selectin"
    )


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole), nullable=False)
    squad_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("squads.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    squad: Mapped["Squad | None"] = relationship(
        "Squad", foreign_keys=[squad_id], back_populates="members", lazy="noload"
    )
    action_logs: Mapped[list["ActionLog"]] = relationship(
        "ActionLog", foreign_keys="ActionLog.actor_id", back_populates="actor", lazy="noload"
    )


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    actor: Mapped["Staff"] = relationship(
        "Staff", foreign_keys=[actor_id], back_populates="action_logs", lazy="selectin"
    )


class DayType(str, enum.Enum):
    weekday = "weekday"
    weekend = "weekend"


DAY_TYPE_LABELS = {
    DayType.weekday: "Будний день",
    DayType.weekend: "Выходной день",
}


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    schedule: Mapped[list["DaySchedule"]] = relationship(
        "DaySchedule", back_populates="session", lazy="noload", cascade="all, delete-orphan"
    )


class DaySchedule(Base):
    __tablename__ = "day_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    day_type: Mapped[DayType] = mapped_column(Enum(DayType), nullable=False)
    time: Mapped[time] = mapped_column(Time, nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["Session"] = relationship("Session", back_populates="schedule", lazy="noload")


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskStatus(str, enum.Enum):
    new = "new"
    accepted = "accepted"
    in_progress = "in_progress"
    done = "done"
    overdue = "overdue"


class RecurrenceType(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"


PRIORITY_LABELS = {
    TaskPriority.low: "🟢 Низкий",
    TaskPriority.medium: "🟡 Средний",
    TaskPriority.high: "🔴 Высокий",
}

STATUS_LABELS = {
    TaskStatus.new: "🆕 Новая",
    TaskStatus.accepted: "✅ Принята",
    TaskStatus.in_progress: "🔄 В работе",
    TaskStatus.done: "✔️ Выполнена",
    TaskStatus.overdue: "⚠️ Просрочена",
}


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_role: Mapped[StaffRole | None] = mapped_column(Enum(StaffRole), nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority), nullable=False, default=TaskPriority.medium
    )
    recurrence_type: Mapped[RecurrenceType | None] = mapped_column(Enum(RecurrenceType), nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    assigned_to: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    group_role: Mapped[StaffRole | None] = mapped_column(Enum(StaffRole), nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority), nullable=False, default=TaskPriority.medium
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.new
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurrence_type: Mapped[RecurrenceType | None] = mapped_column(Enum(RecurrenceType), nullable=True)
    paused_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("task_templates.id"), nullable=True
    )
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    creator: Mapped["Staff"] = relationship("Staff", foreign_keys=[created_by], lazy="selectin")
    assignee: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[assigned_to], lazy="selectin")
    logs: Mapped[list["TaskLog"]] = relationship(
        "TaskLog", back_populates="task", lazy="noload", cascade="all, delete-orphan"
    )
    photos: Mapped[list["TaskPhoto"]] = relationship(
        "TaskPhoto", back_populates="task", lazy="noload", cascade="all, delete-orphan"
    )


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped["Task"] = relationship("Task", back_populates="logs", lazy="noload")
    actor: Mapped["Staff"] = relationship("Staff", foreign_keys=[actor_id], lazy="selectin")


class TaskPhoto(Base):
    __tablename__ = "task_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    photo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped["Task"] = relationship("Task", back_populates="photos", lazy="noload")


# ── Events ────────────────────────────────────────────────────────────────────

class EventType(str, enum.Enum):
    sport = "sport"
    creative = "creative"
    camp_wide = "camp_wide"
    squad = "squad"


EVENT_TYPE_LABELS = {
    EventType.sport: "🏃 Спорт",
    EventType.creative: "🎨 Творчество",
    EventType.camp_wide: "🏕 Общелагерное",
    EventType.squad: "👥 Отрядное",
}

EVENT_TYPE_COLORS = {
    EventType.sport: "#4CAF50",
    EventType.creative: "#FF9800",
    EventType.camp_wide: "#2196F3",
    EventType.squad: "#9C27B0",
}


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsible_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=True)
    copied_from: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    responsible: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[responsible_id], lazy="selectin")
    members: Mapped[list["EventMember"]] = relationship(
        "EventMember", back_populates="event", lazy="noload", cascade="all, delete-orphan"
    )


class EventMember(Base):
    __tablename__ = "event_members"

    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), primary_key=True)

    event: Mapped["Event"] = relationship("Event", back_populates="members", lazy="noload")
    staff: Mapped["Staff"] = relationship("Staff", lazy="selectin")


# ── Children ──────────────────────────────────────────────────────────────────

class Child(Base):
    __tablename__ = "children"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    squad_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("squads.id"), nullable=True)
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=True)
    dormitory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    food_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    medications: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    squad: Mapped["Squad | None"] = relationship("Squad", foreign_keys=[squad_id], lazy="selectin")
    parents: Mapped[list["Parent"]] = relationship(
        "Parent", back_populates="child", lazy="selectin", cascade="all, delete-orphan"
    )


class Parent(Base):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_id: Mapped[int] = mapped_column(Integer, ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(300), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relation: Mapped[str | None] = mapped_column(String(100), nullable=True)

    child: Mapped["Child"] = relationship("Child", back_populates="parents", lazy="noload")


# ── Reminders ─────────────────────────────────────────────────────────────────

class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=True)
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


# ── Duties ────────────────────────────────────────────────────────────────────

class DutyType(str, enum.Enum):
    dining = "dining"
    territory = "territory"
    dormitory = "dormitory"
    night = "night"


DUTY_TYPE_LABELS = {
    DutyType.dining: "🍽 Столовая",
    DutyType.territory: "🌿 Территория",
    DutyType.dormitory: "🏠 Корпус",
    DutyType.night: "🌙 Ночное",
}


class DutyStatus(str, enum.Enum):
    scheduled = "scheduled"
    active = "active"
    completed = "completed"


class Duty(Base):
    __tablename__ = "duties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[DutyType] = mapped_column(Enum(DutyType), nullable=False)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DutyStatus] = mapped_column(Enum(DutyStatus), default=DutyStatus.scheduled, nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    staff: Mapped["Staff"] = relationship("Staff", foreign_keys=[staff_id], lazy="selectin")
    checkpoints: Mapped[list["DutyCheckpoint"]] = relationship(
        "DutyCheckpoint", back_populates="duty", lazy="selectin", cascade="all, delete-orphan"
    )


class DutyCheckpoint(Base):
    __tablename__ = "duty_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    duty_id: Mapped[int] = mapped_column(Integer, ForeignKey("duties.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    duty: Mapped["Duty"] = relationship("Duty", back_populates="checkpoints", lazy="noload")


# ── Incidents ─────────────────────────────────────────────────────────────────

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reported_by: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    child_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("children.id"), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    reporter: Mapped["Staff"] = relationship("Staff", foreign_keys=[reported_by], lazy="selectin")
    child: Mapped["Child | None"] = relationship("Child", foreign_keys=[child_id], lazy="selectin")


# ── Checklists ────────────────────────────────────────────────────────────────

class ChecklistType(str, enum.Enum):
    pre_event = "pre_event"
    lights_out = "lights_out"


CHECKLIST_TYPE_LABELS = {
    ChecklistType.pre_event: "📋 Перед мероприятием",
    ChecklistType.lights_out: "🌙 Отбой",
}


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[ChecklistType] = mapped_column(Enum(ChecklistType), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=True)

    items: Mapped[list["ChecklistItem"]] = relationship(
        "ChecklistItem", back_populates="template", lazy="selectin",
        order_by="ChecklistItem.order_index", cascade="all, delete-orphan"
    )


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("checklist_templates.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    template: Mapped["ChecklistTemplate"] = relationship("ChecklistTemplate", back_populates="items", lazy="noload")


class ChecklistRun(Base):
    __tablename__ = "checklist_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("checklist_templates.id"), nullable=False)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    event_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("events.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped["ChecklistTemplate"] = relationship("ChecklistTemplate", lazy="selectin")
    results: Mapped[list["ChecklistItemResult"]] = relationship(
        "ChecklistItemResult", back_populates="run", lazy="selectin", cascade="all, delete-orphan"
    )


class ChecklistItemResult(Base):
    __tablename__ = "checklist_item_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("checklist_runs.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("checklist_items.id"), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["ChecklistRun"] = relationship("ChecklistRun", back_populates="results", lazy="noload")
    item: Mapped["ChecklistItem"] = relationship("ChecklistItem", lazy="selectin")


# ── Announcements ─────────────────────────────────────────────────────────────

class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    author: Mapped["Staff"] = relationship("Staff", foreign_keys=[created_by], lazy="selectin")
    reads: Mapped[list["AnnouncementRead"]] = relationship(
        "AnnouncementRead", back_populates="announcement", lazy="noload", cascade="all, delete-orphan"
    )


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"

    announcement_id: Mapped[int] = mapped_column(Integer, ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    announcement: Mapped["Announcement"] = relationship("Announcement", back_populates="reads", lazy="noload")


# ── Event Ratings ─────────────────────────────────────────────────────────────

class EventRating(Base):
    __tablename__ = "event_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    event: Mapped["Event"] = relationship("Event", foreign_keys=[event_id], lazy="selectin")
    staff: Mapped["Staff"] = relationship("Staff", foreign_keys=[staff_id], lazy="selectin")


# ── Circles ───────────────────────────────────────────────────────────────────

class Circle(Base):
    __tablename__ = "circles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    leader_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=True)

    leader: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[leader_id], lazy="selectin")
    schedule: Mapped[list["CircleSchedule"]] = relationship(
        "CircleSchedule", back_populates="circle", lazy="noload", cascade="all, delete-orphan"
    )
    members: Mapped[list["CircleMember"]] = relationship(
        "CircleMember", back_populates="circle", lazy="noload", cascade="all, delete-orphan"
    )


class CircleSchedule(Base):
    __tablename__ = "circle_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    circle_id: Mapped[int] = mapped_column(Integer, ForeignKey("circles.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon … 6=Sun
    time: Mapped[time] = mapped_column(Time, nullable=False)

    circle: Mapped["Circle"] = relationship("Circle", back_populates="schedule", lazy="noload")


class CircleMember(Base):
    __tablename__ = "circle_members"

    circle_id: Mapped[int] = mapped_column(Integer, ForeignKey("circles.id", ondelete="CASCADE"), primary_key=True)
    child_id: Mapped[int] = mapped_column(Integer, ForeignKey("children.id", ondelete="CASCADE"), primary_key=True)

    circle: Mapped["Circle"] = relationship("Circle", back_populates="members", lazy="noload")
    child: Mapped["Child"] = relationship("Child", lazy="selectin")


class CircleAttendance(Base):
    __tablename__ = "circle_attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    circle_id: Mapped[int] = mapped_column(Integer, ForeignKey("circles.id"), nullable=False)
    child_id: Mapped[int] = mapped_column(Integer, ForeignKey("children.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
