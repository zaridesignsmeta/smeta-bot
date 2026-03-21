"""
Xatırlatma Sistemi — Feature 4
"""

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from config import ADMIN_IDS
from database import get_all_smetas_admin, add_reminder

router = Router()


class ReminderForm(StatesGroup):
    smeta_select   = State()
    message_text   = State()
    date_time      = State()


def smeta_select_kb(smetas: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in smetas:
        buttons.append([InlineKeyboardButton(
            text=f"📋 {s['smeta_number']} — {s['client_name']}",
            callback_data=f"rem_smeta_{s['smeta_number']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("remind"))
async def cmd_remind(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ Bu komanda yalnız adminlər üçündür.")
        return
    await state.clear()
    smetas = await get_all_smetas_admin()
    if not smetas:
        await msg.answer("📂 Hələ smeta yoxdur.")
        return
    await state.set_state(ReminderForm.smeta_select)
    await msg.answer(
        "⏰ *Xatırlatma Əlavə Et*\n\nHansı smeta üçün?",
        parse_mode="Markdown",
        reply_markup=smeta_select_kb(smetas)
    )


@router.callback_query(F.data.startswith("rem_smeta_"), ReminderForm.smeta_select)
async def reminder_smeta_selected(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[10:]
    await state.update_data(smeta_number=smeta_number)
    await state.set_state(ReminderForm.message_text)
    await cq.message.edit_text(
        f"📋 *{smeta_number}*\n\n📝 Xatırlatma mesajını yazın:",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.message(ReminderForm.message_text)
async def reminder_message(msg: Message, state: FSMContext):
    await state.update_data(reminder_message=msg.text.strip())
    await state.set_state(ReminderForm.date_time)
    await msg.answer(
        "📅 Tarix və vaxt daxil edin:\n"
        "Format: YYYY-MM-DD HH:MM\n"
        "_(məs: 2026-04-01 09:00)_",
        parse_mode="Markdown"
    )


@router.message(ReminderForm.date_time)
async def reminder_datetime(msg: Message, state: FSMContext):
    date_str = msg.text.strip()
    try:
        datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        await msg.answer("⚠️ Format: YYYY-MM-DD HH:MM (məs: 2026-04-01 09:00)")
        return

    data = await state.get_data()
    await add_reminder(
        smeta_number=data["smeta_number"],
        message=data["reminder_message"],
        remind_at=date_str,
        created_by=msg.from_user.id,
    )
    await state.clear()
    await msg.answer(
        f"✅ *Xatırlatma əlavə edildi!*\n\n"
        f"📋 Smeta: *{data['smeta_number']}*\n"
        f"📝 {data['reminder_message']}\n"
        f"⏰ {date_str}",
        parse_mode="Markdown"
    )
