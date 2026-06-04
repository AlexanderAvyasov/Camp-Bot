import json
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Document,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.states import ChildrenImportFSM
from app.db.base import async_session_factory
from app.db.crud import (
    get_child_by_id,
    search_children,
    upsert_child,
    get_all_squads,
    update_child,
)
from app.db.models import Staff, StaffRole

router = Router(name="children")

_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}
_D_FMT = "%d.%m.%Y"

_SQUAD_NAMES = [f"Отряд {i}" for i in range(1, 15)]


def _squad_select_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, 14, 2):
        row = [InlineKeyboardButton(text=_SQUAD_NAMES[i], callback_data=f"import_squad:{_SQUAD_NAMES[i]}")]
        if i + 1 < 14:
            row.append(InlineKeyboardButton(text=_SQUAD_NAMES[i + 1], callback_data=f"import_squad:{_SQUAD_NAMES[i + 1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _child_card(child) -> str:
    squad = child.squad.name if child.squad else "—"
    bd = child.birth_date.strftime(_D_FMT) if child.birth_date else "—"
    raw = child.raw_data or {}
    voucher_raw = str(raw.get("voucher", "") or "")
    voucher = voucher_raw.zfill(6) if voucher_raw.isdigit() else (voucher_raw or "—")

    parents_lines = []
    for p in child.parents:
        phone = f" | <a href='tel:{p.phone}'>{p.phone}</a>" if p.phone else ""
        rel = f" ({p.relation})" if p.relation else ""
        parents_lines.append(f"  👤 {p.full_name}{rel}{phone}")

    parents_text = (
        "\n\n<b>Родители:</b>\n" + "\n".join(parents_lines)
        if parents_lines else ""
    )

    return (
        f"👦 <b>{child.full_name}</b>\n"
        f"Отряд: {squad}\n"
        f"Дата рождения: {bd}\n"
        f"№ путёвки: {voucher}"
        + parents_text
    )


def _child_list_kb(children: list) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=f"👦 {c.full_name}",
        callback_data=f"child_view:{c.id}",
    )] for c in children]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _child_actions_kb(child_id: int, is_admin: bool) -> InlineKeyboardMarkup | None:
    rows = []
    if is_admin:
        rows.append([InlineKeyboardButton(
            text="🏕 Сменить отряд",
            callback_data=f"child_squad_select:{child_id}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


# ── /child {name} ─────────────────────────────────────────────────────────────

@router.message(Command("child"))
async def cmd_child(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("❌ Введите имя: /child Иванов")
        return
    query = args[1].strip()
    squad_id = staff.squad_id if staff.role == StaffRole.counselor else None
    async with async_session_factory() as session:
        children, total = await search_children(session, search=query, squad_id=squad_id, limit=10)

    if not children:
        await message.answer(f"❌ Ничего не найдено по запросу «{query}».")
        return
    if len(children) == 1:
        is_admin = staff.role in _ADMIN_ROLES
        await message.answer(
            _child_card(children[0]),
            parse_mode="HTML",
            reply_markup=_child_actions_kb(children[0].id, is_admin),
        )
        return

    await message.answer(
        f"🔍 Найдено: {total}. Выберите:",
        reply_markup=_child_list_kb(children),
    )


@router.callback_query(F.data.startswith("child_view:"))
async def cb_child_view(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer()
        return
    child_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        child = await get_child_by_id(session, child_id)
    if not child:
        await callback.answer("❌ Не найден", show_alert=True)
        return
    is_admin = staff.role in _ADMIN_ROLES
    kb = _child_actions_kb(child_id, is_admin)
    try:
        await callback.message.edit_text(_child_card(child), parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(_child_card(child), parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ── Смена отряда ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("child_squad_select:"))
async def cb_child_squad_select(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    child_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        squads = await get_all_squads(session)
    if not squads:
        await callback.answer("❌ Нет отрядов", show_alert=True)
        return
    rows = [[InlineKeyboardButton(
        text=f"🏕 Отряд {s.name}",
        callback_data=f"child_squad_set:{child_id}:{s.id}",
    )] for s in squads]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data=f"child_view:{child_id}")])
    await callback.message.edit_text(
        "Выберите отряд:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("child_squad_set:"))
async def cb_child_squad_set(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    _, child_id_s, squad_id_s = callback.data.split(":")
    child_id, squad_id = int(child_id_s), int(squad_id_s)
    async with async_session_factory() as session:
        child = await update_child(session, child_id, squad_id=squad_id)
    if not child:
        await callback.answer("❌ Ребёнок не найден", show_alert=True)
        return
    is_admin = staff.role in _ADMIN_ROLES
    kb = _child_actions_kb(child_id, is_admin)
    await callback.message.edit_text(_child_card(child), parse_mode="HTML", reply_markup=kb)
    await callback.answer("✅ Отряд обновлён")


# ── WebApp → отправить карточку ───────────────────────────────────────────────

@router.message(F.web_app_data)
async def handle_web_app_data(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    try:
        payload = json.loads(message.web_app_data.data)
    except Exception:
        return

    if payload.get("action") != "child_card":
        return

    child_id = payload.get("child_id")
    if not child_id:
        return

    async with async_session_factory() as session:
        child = await get_child_by_id(session, child_id)
    if not child:
        await message.answer("❌ Ребёнок не найден")
        return

    is_admin = staff.role in _ADMIN_ROLES
    await message.answer(
        _child_card(child),
        parse_mode="HTML",
        reply_markup=_child_actions_kb(child_id, is_admin),
    )


# ── /children_import — шаг 1: выбор отряда ───────────────────────────────────

async def _start_import(message_or_callback, state: FSMContext):
    """Показывает выбор отряда и переводит в FSM."""
    kb = _squad_select_kb()
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(
            "📊 <b>Импорт детей из Excel</b>\n\nВыберите отряд для импортируемых детей:",
            reply_markup=kb, parse_mode="HTML",
        )
    else:
        await message_or_callback.message.answer(
            "📊 <b>Импорт детей из Excel</b>\n\nВыберите отряд для импортируемых детей:",
            reply_markup=kb, parse_mode="HTML",
        )
        await message_or_callback.answer()
    await state.set_state(ChildrenImportFSM.waiting_squad)


@router.message(Command("children_import"))
async def cmd_children_import(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав.")
        return
    await _start_import(message, state)


@router.callback_query(ChildrenImportFSM.waiting_squad, F.data.startswith("import_squad:"))
async def fsm_import_squad(callback: CallbackQuery, state: FSMContext):
    squad_name = callback.data.split(":", 1)[1]
    await state.update_data(import_squad_name=squad_name)
    await callback.message.edit_text(
        f"✅ Отряд: <b>{squad_name}</b>\n\nТеперь отправьте файл <b>.xlsx</b>:",
        parse_mode="HTML",
    )
    await state.set_state(ChildrenImportFSM.waiting_file)
    await callback.answer()


# ── Шаг 2: приём файла и импорт ──────────────────────────────────────────────

async def _do_import(message: Message, state: FSMContext, squad_name: str):
    doc: Document = message.document
    if not doc.file_name.endswith((".xlsx", ".xls")):
        await message.answer("❌ Нужен файл .xlsx или .xls. Отправьте ещё раз:")
        return

    await message.answer(f"⏳ Обрабатываю файл для <b>{squad_name}</b>...", parse_mode="HTML")
    await state.clear()

    file = await message.bot.get_file(doc.file_id)
    buf = BytesIO()
    await message.bot.download_file(file.file_path, destination=buf)
    buf.seek(0)

    from app.children_import import parse_excel
    rows, warnings = parse_excel(buf)

    if not rows:
        warn_text = "\n".join(warnings[:5]) if warnings else "Файл пустой."
        await message.answer(f"❌ Нет данных.\n{warn_text}")
        return

    async with async_session_factory() as session:
        squads = await get_all_squads(session)
    squad_map: dict = {s.name.strip(): s.id for s in squads}
    squad_map.update({s.name.strip().lower(): s.id for s in squads})

    selected_squad_id = squad_map.get(squad_name) or squad_map.get(squad_name.lower())

    added = updated = 0
    errors = []
    async with async_session_factory() as session:
        for row in rows:
            try:
                row.pop("squad_name", None)
                _, is_new = await upsert_child(
                    session,
                    full_name=row["full_name"],
                    birth_date=row.get("birth_date"),
                    squad_id=selected_squad_id,
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
            except Exception as e:
                errors.append(str(e)[:80])
        try:
            await session.commit()
        except Exception as e:
            errors.append(f"commit: {e}"[:80])

    result = f"✅ <b>Импорт завершён</b>\nОтряд: <b>{squad_name}</b>\n\nДобавлено: {added}\nОбновлено: {updated}"
    if warnings:
        result += f"\n\n⚠️ Предупреждения ({len(warnings)}):\n" + "\n".join(warnings[:5])
    if errors:
        result += f"\n\n❌ Ошибки ({len(errors)}):\n" + "\n".join(errors[:3])
    await message.answer(result, parse_mode="HTML")


@router.message(ChildrenImportFSM.waiting_file, F.document)
async def fsm_import_file(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await state.clear()
        return
    data = await state.get_data()
    await _do_import(message, state, data.get("import_squad_name", "Неизвестный отряд"))


# ── Кнопка «Дети» в меню ──────────────────────────────────────────────────────

@router.message(F.text == "👦 Дети")
async def menu_children(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поиск ребёнка", callback_data="children_search_prompt")],
            *([[InlineKeyboardButton(text="📊 Импорт Excel", callback_data="children_import_prompt")]]
              if staff.role in _ADMIN_ROLES else []),
        ]
    )
    await message.answer("👦 <b>Дети</b>:", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "children_search_prompt")
async def cb_children_search_prompt(callback: CallbackQuery):
    await callback.message.answer("Введите имя для поиска:\n/child Иванов")
    await callback.answer()


@router.callback_query(F.data == "children_import_prompt")
async def cb_children_import_prompt(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await _start_import(callback, state)
