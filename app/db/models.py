import enum
from datetime import date, datetime, time

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
        "Squad", foreign_keys=[squad_id], back_populates="members", lazy="selectin"
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
        "DaySchedule", back_populates="session", lazy="selectin", cascade="all, delete-orphan"
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
