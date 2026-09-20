from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="➕ Добавить ДЗ", callback_data="admin_add_hw"),
            InlineKeyboardButton(text="🗑 Удалить ДЗ", callback_data="admin_delete_hw")
        ],
        [
            InlineKeyboardButton(text="🔄 Замена урока", callback_data="admin_add_sub"),
            InlineKeyboardButton(text="📢 Срочное объявление", callback_data="admin_broadcast_custom")
        ],
        [
            InlineKeyboardButton(text="📅 Расписание на дату", callback_data="admin_edit_date_schedule"),
            InlineKeyboardButton(text="🗓 Постоянное расписание", callback_data="admin_edit_schedule")
        ],
        [
            InlineKeyboardButton(text="📢 Скинуть расписание", callback_data="admin_broadcast_schedule")
        ],
        [
            InlineKeyboardButton(text="🔔 Звонки и перемены", callback_data="admin_edit_bells")
        ],
        [
            InlineKeyboardButton(text="🧹 Дежурства", callback_data="admin_manage_duty"),
            InlineKeyboardButton(text="📢 Объявление дежурным", callback_data="admin_duty_broadcast")
        ],
        [
            InlineKeyboardButton(text="👥 Заявки на вход", callback_data="admin_view_pending"),
            InlineKeyboardButton(text="📋 Права доступа", callback_data="admin_view_students")
        ],
        [
            InlineKeyboardButton(text="🪙 Выдать монеты", callback_data="admin_give_coins"),
            InlineKeyboardButton(text="📊 Опросы класса", callback_data="admin_polls_menu")
        ]
    ]
    try:
        from backend.bot.handlers.admin.pug_prank import get_pug_keyboard_button
        pug_btn = get_pug_keyboard_button()
        if pug_btn:
            rows.append([pug_btn])
    except Exception:
        pass
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ]
    )

def get_notify_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Скинуть в чат", callback_data="sub_notify_groups")],
            [InlineKeyboardButton(text="👤 Всем в ЛС", callback_data="sub_notify_pm")],
            [InlineKeyboardButton(text="📢 В чат + ЛС", callback_data="sub_notify_all")],
            [InlineKeyboardButton(text="🔇 Без оповещения", callback_data="sub_notify_no")]
        ]
    )

def get_date_schedule_notify_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Скинуть в чат", callback_data="adm_dt_notify_groups")],
            [InlineKeyboardButton(text="👤 Всем в ЛС", callback_data="adm_dt_notify_pm")],
            [InlineKeyboardButton(text="📢 В чат + ЛС", callback_data="adm_dt_notify_all")],
            [InlineKeyboardButton(text="🔇 Без оповещения", callback_data="adm_dt_notify_no")]
        ]
    )

def get_date_bells_notify_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Скинуть в чат", callback_data="adm_dtb_notify_groups")],
            [InlineKeyboardButton(text="👤 Всем в ЛС", callback_data="adm_dtb_notify_pm")],
            [InlineKeyboardButton(text="📢 В чат + ЛС", callback_data="adm_dtb_notify_all")],
            [InlineKeyboardButton(text="🔇 Без оповещения", callback_data="adm_dtb_notify_no")]
        ]
    )

def get_broadcast_destination_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Всему классу (в ЛС)", callback_data="bcast_dest_users")
            ],
            [
                InlineKeyboardButton(text="👥 В беседы (групповые чаты)", callback_data="bcast_dest_groups")
            ],
            [
                InlineKeyboardButton(text="📢 Всем (в ЛС + беседы)", callback_data="bcast_dest_all")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
            ]
        ]
    )

def get_hw_notify_keyboard(hw_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📢 В беседу класса", callback_data=f"adm_hwnotif_grp_{hw_id}")
            ],
            [
                InlineKeyboardButton(text="📢 В беседу + всем в ЛС", callback_data=f"adm_hwnotif_all_{hw_id}")
            ],
            [
                InlineKeyboardButton(text="🔇 Без оповещения", callback_data="adm_hwnotif_none")
            ],
            [
                InlineKeyboardButton(text="🗑 Удалить это ДЗ (если ошибка)", callback_data=f"adm_hw_del_{hw_id}")
            ]
        ]
    )

def get_duty_broadcast_destination_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Дежурным (в ЛС)", callback_data="duty_bcast_dest_pm")
            ],
            [
                InlineKeyboardButton(text="👥 В беседу класса", callback_data="duty_bcast_dest_groups")
            ],
            [
                InlineKeyboardButton(text="📢 Дежурным в ЛС + в беседу", callback_data="duty_bcast_dest_all")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
            ]
        ]
    )

def get_schedule_broadcast_day_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ На сегодня", callback_data="bcast_sched_day_today"),
                InlineKeyboardButton(text="➡️ На завтра", callback_data="bcast_sched_day_tomorrow")
            ],
            [
                InlineKeyboardButton(text="🗓 Выбрать дату (календарь)", callback_data="bcast_sched_day_cal")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
            ]
        ]
    )

def get_schedule_broadcast_destination_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Скинуть в чат", callback_data="bcast_sched_dest_groups")],
            [InlineKeyboardButton(text="👤 Всем в ЛС", callback_data="bcast_sched_dest_pm")],
            [InlineKeyboardButton(text="📢 В чат + ЛС", callback_data="bcast_sched_dest_all")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ]
    )




