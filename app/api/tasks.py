from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.crud import (
    add_task_log,
    add_task_photo,
    create_task,
    create_template,
    get_all_tasks,
    get_all_templates,
    get_task_by_id,
    get_task_logs,
    update_task,
)
from app.db.models import (
    RecurrenceType, Staff, StaffRole, TaskPriority, TaskStatus, TaskTemplate,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str]
    created_by: int
    assigned_to: Optional[int]
    group_role: Optional[StaffRole]
    priority: TaskPriority
    status: TaskStatus
    deadline: Optional[datetime]
    is_recurring: bool
    recurrence_type: Optional[RecurrenceType]
    session_id: Optional[int]
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    group_role: Optional[StaffRole] = None
    priority: TaskPriority = TaskPriority.medium
    deadline: Optional[datetime] = None
    is_recurring: bool = False
    recurrence_type: Optional[RecurrenceType] = None
    session_id: Optional[int] = None
    created_by: int


class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    deadline: Optional[datetime] = None
    assigned_to: Optional[int] = None


class TaskLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    actor_id: int
    action: str
    timestamp: datetime


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str]
    group_role: Optional[StaffRole]
    priority: TaskPriority
    recurrence_type: Optional[RecurrenceType]


class TemplateCreate(BaseModel):
    title: str
    description: Optional[str] = None
    group_role: Optional[StaffRole] = None
    priority: TaskPriority = TaskPriority.medium
    recurrence_type: Optional[RecurrenceType] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TaskOut])
async def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    assigned_to: Optional[int] = Query(None),
    session_id: Optional[int] = Query(None),
    page: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    tasks, _ = await get_all_tasks(session, status=status, assigned_to=assigned_to, session_id=session_id, offset=page * 20, limit=20)
    return tasks


@router.post("", response_model=TaskOut, status_code=201)
async def create_task_endpoint(body: TaskCreate, session: AsyncSession = Depends(get_session)):
    task = await create_task(
        session, title=body.title, description=body.description,
        created_by=body.created_by, session_id=body.session_id,
        assigned_to=body.assigned_to, group_role=body.group_role,
        priority=body.priority, deadline=body.deadline,
        is_recurring=body.is_recurring, recurrence_type=body.recurrence_type,
    )
    return task


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task_endpoint(
    task_id: int, body: TaskUpdate, session: AsyncSession = Depends(get_session)
):
    task = await get_task_by_id(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return task
    updated = await update_task(session, task_id, **updates)
    if body.status:
        await add_task_log(session, task_id, task.created_by, f"status changed to {body.status}")
    return updated


@router.get("/{task_id}/logs", response_model=list[TaskLogOut])
async def get_task_logs_endpoint(task_id: int, session: AsyncSession = Depends(get_session)):
    task = await get_task_by_id(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return await get_task_logs(session, task_id)


@router.post("/{task_id}/photos", status_code=201)
async def upload_photo(task_id: int, photo_url: str, session: AsyncSession = Depends(get_session)):
    task = await get_task_by_id(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    photo = await add_task_photo(session, task_id, photo_url)
    return {"id": photo.id, "task_id": photo.task_id, "photo_url": photo.photo_url}


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(session: AsyncSession = Depends(get_session)):
    return await get_all_templates(session)


@router.post("/templates", response_model=TemplateOut, status_code=201)
async def create_template_endpoint(body: TemplateCreate, session: AsyncSession = Depends(get_session)):
    return await create_template(session, body.title, body.description, body.group_role, body.priority, body.recurrence_type)
