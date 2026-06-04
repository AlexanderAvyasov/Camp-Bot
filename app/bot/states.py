from aiogram.fsm.state import State, StatesGroup


class AddStaffFSM(StatesGroup):
    waiting_telegram_id = State()
    waiting_full_name = State()
    waiting_role = State()
