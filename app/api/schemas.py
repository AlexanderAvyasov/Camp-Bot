from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import StaffRole


class SquadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    telegram_id: int
    full_name: str
    role: StaffRole
    squad_id: int | None
    squad: SquadOut | None
    is_active: bool
    created_at: datetime


class StaffCreate(BaseModel):
    telegram_id: int
    full_name: str
    role: StaffRole
    squad_id: int | None = None


class StaffUpdate(BaseModel):
    role: StaffRole | None = None
    squad_id: int | None = None
    is_active: bool | None = None
