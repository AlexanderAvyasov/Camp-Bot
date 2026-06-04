from io import BytesIO
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from app.db.base import async_session_factory
from app.db.crud import (
    get_child_by_id,
    get_all_squads,
    search_children,
    update_child,
    upsert_child,
)

router = APIRouter(prefix="/api/children", tags=["children"])


def _child_out(child) -> dict:
    raw = child.raw_data or {}
    return {
        "id": child.id,
        "full_name": child.full_name,
        "birth_date": child.birth_date.isoformat() if child.birth_date else None,
        "squad_id": child.squad_id,
        "squad_name": child.squad.name if child.squad else None,
        "address": raw.get("Адрес"),
        "voucher": raw.get("voucher"),
        "parents": [
            {"id": p.id, "full_name": p.full_name, "phone": p.phone, "relation": p.relation}
            for p in child.parents
        ],
    }


@router.get("")
async def list_children(
    squad_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    async with async_session_factory() as session:
        children, total = await search_children(
            session,
            search=search,
            squad_id=squad_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
    return {
        "total": total,
        "page": page,
        "items": [_child_out(c) for c in children],
    }


@router.get("/{child_id}")
async def get_child(child_id: int):
    async with async_session_factory() as session:
        child = await get_child_by_id(session, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return _child_out(child)


@router.patch("/{child_id}")
async def patch_child(child_id: int, data: dict):
    allowed = {"squad_id", "session_id"}
    kwargs = {k: v for k, v in data.items() if k in allowed}
    if not kwargs:
        raise HTTPException(status_code=400, detail="No valid fields")
    async with async_session_factory() as session:
        child = await update_child(session, child_id, **kwargs)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return _child_out(child)


@router.post("/import")
async def import_children(
    file: UploadFile = File(...),
    squad_id: Optional[int] = Query(None),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx/.xls files are supported")

    from app.children_import import parse_excel
    content = await file.read()
    rows, warnings = parse_excel(BytesIO(content))

    if not rows:
        return {"added": 0, "updated": 0, "warnings": warnings}

    # If squad_id provided by caller — override everything from Excel
    # Otherwise resolve squad names from Excel header
    resolved_squad_map: dict = {}
    if squad_id is None:
        async with async_session_factory() as session:
            squads = await get_all_squads(session)
        for s in squads:
            resolved_squad_map[s.name.strip().lower()] = s.id
            resolved_squad_map[s.name.strip()] = s.id

    added = updated = 0
    async with async_session_factory() as session:
        for row in rows:
            squad_name = row.pop("squad_name", None)
            effective_squad_id = squad_id
            if effective_squad_id is None and squad_name:
                effective_squad_id = (
                    resolved_squad_map.get(squad_name.lower())
                    or resolved_squad_map.get(squad_name)
                )

            _, is_new = await upsert_child(
                session,
                full_name=row["full_name"],
                birth_date=row.get("birth_date"),
                squad_id=effective_squad_id,
                dormitory=row.get("dormitory"),
                food_type=row.get("food_type"),
                allergies=row.get("allergies"),
                medications=row.get("medications"),
                raw_data=row.get("raw_data") or {},
                parents=row.get("parents") or [],
            )
            if is_new:
                added += 1
            else:
                updated += 1
        await session.commit()

    return {"added": added, "updated": updated, "warnings": warnings}
