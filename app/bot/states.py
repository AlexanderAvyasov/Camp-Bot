from aiogram.fsm.state import State, StatesGroup


class AddStaffFSM(StatesGroup):
    waiting_telegram_id = State()
    waiting_full_name = State()
    waiting_role = State()


class SessionFSM(StatesGroup):
    waiting_name = State()
    waiting_start_date = State()
    waiting_end_date = State()


class ScheduleAddFSM(StatesGroup):
    waiting_day_type = State()
    waiting_time = State()
    waiting_label = State()


class SquadNewFSM(StatesGroup):
    waiting_name = State()
    waiting_counselor = State()
    waiting_educator = State()


class SquadEditFSM(StatesGroup):
    waiting_field = State()
    waiting_staff = State()
