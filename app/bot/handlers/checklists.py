"""Чек-листы перед мероприятием и отбоем."""
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards import cancel_kb
from app.bot.states import ChecklistAddFSM
from app.db.base import async_session_factory
from app.db.crud import (
    complete_checklist_run,
    confirm_checklist_item,
    create_checklist_template,
    get_active_session,
    get_all_active_staff,
    get_checklist_run,
    get_checklist_templates,
    start_checklist_run,
)
from app.db.models import CHECKLIST_TYPE_LABELS, ChecklistType, Staff, StaffRole

router = Router(name="checklists")
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}


def _checklist_type_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=CHECKLIST_TYPE_LABELS[t], callback_data=f"cl_type:{t.value}")]
        for t in ChecklistType
    ]
    rows.append([InlineKeyboardButton(text="✕ Отмена", callback_data="cancel_fsm")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _run_kb(run_id: int, results) -> InlineKeyboardMarkup:
    rows = []
    for r in results:
        checked = "✅" if r.confirmed_at else "⬜"
        rows.append([InlineKeyboardButton(
            text=f"{checked} {r.item.text}",
            callback_data=f"cl_check:{run_id}:{r.id}",
        )])
    rows.append([InlineKeyboardButton(text="✔️ Завершить", callback_data=f"cl_finish:{run_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── /checklist_add — создать шаблон ──────────────────────────────────────────

@router.message(Command("checklist_add"))
async def cmd_checklist_add(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ Нет прав.")
        return
    await message.answer(
        "📋 <b>Новый чек-лист</b>\n\nВыберите тип:",
        reply_markup=_checklist_type_kb(),
        parse_mode="HTML",
    )
    await state.set_state(ChecklistAddFSM.waiting_type)


@router.callback_query(ChecklistAddFSM.waiting_type, F.data.startswith("cl_type:"))
async def cl_type(callback: CallbackQuery, state: FSMContext):
    cl_type_val = callback.data.split(":")[1]
    await state.update_data(cl_type=cl_type_val, items=[])
    await callback.message.edit_text(
        "Введите название чек-листа:", parse_mode="HTML"
    )
    await state.set_state(ChecklistAddFSM.waiting_title)
    await callback.answer()


@router.message(ChecklistAddFSM.waiting_title)
async def cl_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data="cl_items_done")],
    ])
    await message.answer(
        "Вводите пункты чек-листа по одному.\nКогда закончите, нажмите «Готово»:",
        reply_markup=kb,
    )
    await state.set_state(ChecklistAddFSM.waiting_items)


@router.message(ChecklistAddFSM.waiting_items)
async def cl_add_item(message: Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("items", [])
    items.append(message.text.strip())
    await state.update_data(items=items)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data="cl_items_done")],
    ])
    await message.answer(f"Добавлено: «{message.text.strip()}». Ещё пункт или завершите:", reply_markup=kb)


@router.callback_query(ChecklistAddFSM.waiting_items, F.data == "cl_items_done")
async def cl_items_done(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    data = await state.get_data()
    await state.clear()
    if not data.get("items"):
        await callback.answer("❌ Нет пунктов", show_alert=True)
        return
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        tmpl = await create_checklist_template(
            session, data["cl_type"], data["title"],
            sess.id if sess else None, data["items"]
        )
    await callback.message.edit_text(
        f"✅ Чек-лист <b>{tmpl.title}</b> создан ({len(data['items'])} пунктов).",
        parse_mode="HTML",
    )
    await callback.answer()


# ── /checklist_event {event_id} — запустить чек-лист мероприятия ─────────────

@router.message(Command("checklist_event"))
async def cmd_checklist_event(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    args = message.text.split(maxsplit=1)
    event_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    async with async_session_factory() as session:
        templates = await get_checklist_templates(session, type_=ChecklistType.pre_event)
    if not templates:
        await message.answer("❌ Нет шаблонов чек-листа перед мероприятием. Создайте: /checklist_add")
        return
    tmpl = templates[0]
    async with async_session_factory() as session:
        run = await start_checklist_run(session, tmpl.id, staff.id, event_id=event_id)
    await message.answer(
        f"📋 <b>{tmpl.title}</b>",
        reply_markup=_run_kb(run.id, run.results),
        parse_mode="HTML",
    )


# ── /checklist_lights_out — чек-лист отбоя ───────────────────────────────────

@router.message(Command("checklist_lights_out"))
async def cmd_checklist_lights_out(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    async with async_session_factory() as session:
        templates = await get_checklist_templates(session, type_=ChecklistType.lights_out)
    if not templates:
        await message.answer("❌ Нет шаблона чек-листа отбоя. Создайте: /checklist_add")
        return
    tmpl = templates[0]
    async with async_session_factory() as session:
        run = await start_checklist_run(session, tmpl.id, staff.id)
    await message.answer(
        f"🌙 <b>{tmpl.title}</b>",
        reply_markup=_run_kb(run.id, run.results),
        parse_mode="HTML",
    )


# ── Callbacks для пометки пунктов ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("cl_check:"))
async def cl_check_item(callback: CallbackQuery):
    _, run_id_s, result_id_s = callback.data.split(":")
    run_id, result_id = int(run_id_s), int(result_id_s)
    async with async_session_factory() as session:
        await confirm_checklist_item(session, result_id)
        run = await get_checklist_run(session, run_id)
    if run:
        try:
            await callback.message.edit_reply_markup(reply_markup=_run_kb(run.id, run.results))
        except Exception:
            pass
    await callback.answer("✅")


@router.callback_query(F.data.startswith("cl_finish:"))
async def cl_finish(callback: CallbackQuery, staff: Staff | None = None):
    run_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        run = await get_checklist_run(session, run_id)
        if not run:
            await callback.answer("❌ Не найден", show_alert=True)
            return
        done = sum(1 for r in run.results if r.confirmed_at)
        total = len(run.results)
        await complete_checklist_run(session, run_id)

    # Notify admins
    from app.bot.bot import get_bot
    bot = get_bot()
    async with async_session_factory() as session:
        from app.db.crud import get_all_active_staff
        all_s = await get_all_active_staff(session)
    name = staff.full_name if staff else "Сотрудник"
    for s in all_s:
        if s.role in _ADMIN_ROLES:
            try:
                await bot.send_message(
                    s.telegram_id,
                    f"✅ Чек-лист завершён\n{name}: {done}/{total} пунктов выполнено.",
                )
            except Exception:
                pass

    await callback.message.edit_text(f"✅ Чек-лист завершён! {done}/{total} выполнено.")
    await callback.answer()
