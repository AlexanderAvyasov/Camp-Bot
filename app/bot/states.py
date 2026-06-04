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
    waiting_educator_2 = State()


class SquadEditFSM(StatesGroup):
    waiting_field = State()
    waiting_value = State()


class TaskCreateFSM(StatesGroup):
    waiting_title = State()
    waiting_group = State()
    waiting_assignee = State()
    waiting_priority = State()
    waiting_deadline = State()


class TemplateFSM(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_role = State()
    waiting_priority = State()
    waiting_recurrence = State()


class TaskFromTemplateFSM(StatesGroup):
    waiting_group = State()
    waiting_assignee = State()
    waiting_deadline = State()


class EventAddFSM(StatesGroup):
    waiting_title = State()
    waiting_type = State()
    waiting_location = State()
    waiting_responsible = State()
    waiting_members = State()
    waiting_start = State()
    waiting_end = State()
    confirm = State()


class EventEditFSM(StatesGroup):
    waiting_field = State()
    waiting_value = State()


class EventCopyFSM(StatesGroup):
    waiting_date = State()


class BroadcastFSM(StatesGroup):
    waiting_text = State()
    confirm = State()


class IncidentFSM(StatesGroup):
    waiting_type = State()
    waiting_description = State()
    waiting_child = State()
    waiting_photo = State()


class ChecklistAddFSM(StatesGroup):
    waiting_type = State()
    waiting_title = State()
    waiting_items = State()


class AnnounceFSM(StatesGroup):
    waiting_text = State()
    confirm = State()


class RateEventFSM(StatesGroup):
    waiting_rating = State()
    waiting_comment = State()


class CircleAddFSM(StatesGroup):
    waiting_name = State()
    waiting_leader = State()


class CircleScheduleFSM(StatesGroup):
    waiting_day = State()
    waiting_time = State()


class CircleMemberFSM(StatesGroup):
    waiting_name = State()


class DutyDoneFSM(StatesGroup):
    waiting_confirm = State()


class TaskPauseFSM(StatesGroup):
    waiting_task_id = State()
    waiting_days = State()


class ChildrenImportFSM(StatesGroup):
    waiting_squad = State()
    waiting_file = State()
