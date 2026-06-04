from app.db.models import ROLE_LABELS, StaffRole

ONBOARDING = {
    StaffRole.admin: "👋 Добро пожаловать, Администратор!\n\nИспользуйте кнопки меню внизу для управления лагерем.",
    StaffRole.senior_counselor: "👋 Добро пожаловать, Старший вожатый!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.counselor: "👋 Добро пожаловать, Вожатый!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.educator: "👋 Добро пожаловать, Воспитатель!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.coach: "👋 Добро пожаловать, Тренер!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.swim_coach: "👋 Добро пожаловать, Тренер по плаванию!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.music: "👋 Добро пожаловать, Музыкальный руководитель!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.circle_leader: "👋 Добро пожаловать, Руководитель кружка!\n\nИспользуйте кнопки меню внизу.",
}


def format_staff_item(staff) -> str:
    squad_name = staff.squad.name if staff.squad else "—"
    status = "✅" if staff.is_active else "❌"
    return (
        f"{status} <b>{staff.full_name}</b>\n"
        f"   Роль: {ROLE_LABELS.get(staff.role, staff.role)}\n"
        f"   Отряд: {squad_name}\n"
        f"   ID: <code>{staff.telegram_id}</code>"
    )
