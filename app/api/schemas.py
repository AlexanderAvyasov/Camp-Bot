from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict

from app.db.models import DayType, StaffRole


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


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    start_date: date
    end_date: date
    is_active: bool


class SessionCreate(BaseModel):
    name: str
    start_date: date
    end_date: date


class DayScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    day_type: DayType
    time: time
    label: str
    created_at: datetime


class DayScheduleCreate(BaseModel):
    day_type: DayType
    time: time
    label: str


class SquadStaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    role: StaffRole
    telegram_id: int


class SquadDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    counselor_id: int | None
    educator_id: int | None
    counselor: SquadStaffOut | None
    educator: SquadStaffOut | None


class SquadCreate(BaseModel):
    name: str
    counselor_id: int | None = None
    educator_id: int | None = None


class SquadUpdate(BaseModel):
    counselor_id: int | None = None
    educator_id: int | None = None


class FreeStaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    role: StaffRole
    telegram_id: int
