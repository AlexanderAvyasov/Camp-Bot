import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
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

    counselor: Mapped["Staff | None"] = relationship(
        "Staff", foreign_keys=[counselor_id], lazy="selectin"
    )
    educator: Mapped["Staff | None"] = relationship(
        "Staff", foreign_keys=[educator_id], lazy="selectin"
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
