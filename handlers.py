"""
Telegram Bot Handlerlər - Bütün komandalar və vəziyyət maşını
"""

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, FSInputFile
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import os
import json
from datetime import datetime

from config import (
    ADMIN_IDS, ROOMS, WORK_CATEGORIES, CURRENCY,
    DEFAULT_VAT, DEFAULT_MARGIN, DEFAULT_DISCOUNT,
    COMPANY_NAME
)
from database import (
    save_smeta, get_smeta, get_user_smetas,
    update_smeta_status, generate_smeta_number,
    save_project, get_active_projects, update_project_progress
)
from generators import generate_excel, generate_pdf

router = Router()


# ═══════════════════════════════════════════════════════════════════════════════
#  FSM Vəziyyətləri
# ═══════════════════════════════════════════════════════════════════════════════

class SmetaForm(StatesGroup):
    client_name  = State()
    client_phone = State()
    address      = State()
    room_select  = State()
    category_select = State()
    add_items    = State()
    item_name    = State()
    item_unit    = State()
    item_qty     = State()
    item_price   = State()
    settings     = State()
    notes        = State()
    confirm      = State()

class ProjectForm(StatesGroup):
    name       = State()
    address    = State()
    start_date = State()
    end_date   = State()

class UpdateForm(StatesGroup):
    select_project = State()
    progress       = State()
    message        = State()


# ═══════════════════════════════════════════════════════════════════════════════
#  Klaviaturalar
# ═══════════════════════════════════════════════════════════════════════════════

def main_menu_kb(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📋 Yeni Smeta"), KeyboardButton(text="📁 Smetalarım")],
        [KeyboardButton(text="🏗️ Layihələr"),  KeyboardButton(text="📊 Statistika")],
    ]
    if user_id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def rooms_kb(selected_rooms: list) -> InlineKeyboardMarkup:
    buttons = []
    for room in ROOMS:
        count = sum(1 for r in selected_rooms if r == room or r.startswith(f"{room} "))
        if count > 1:
            mark = f"✅ x{count} "
        elif count == 1:
            mark = "✅ "
        else:
            mark = ""
        buttons.append([InlineKeyboardButton(
            text=f"{mark}{room}", callback_data=f"room_{room}"
        )])
    buttons.append([
        InlineKeyboardButton(text="➕ Fərdi otaq", callback_data="room_custom"),
        InlineKeyboardButton(text="▶️ Davam et", callback_data="rooms_done"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def categories_kb(room: str) -> InlineKeyboardMarkup:
    buttons = []
    for cat in WORK_CATEGORIES:
        buttons.append([InlineKeyboardButton(
            text=cat, callback_data=f"cat_{cat}"
        )])
    buttons.append([
        InlineKeyboardButton(text="✅ Bu otaq hazırdır", callback_data="room_done"),
        InlineKeyboardButton(text="🔙 Otaqlar", callback_data="back_rooms"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def items_kb(items: list) -> InlineKeyboardMarkup:
    buttons = []
    for item in items:
        buttons.append([InlineKeyboardButton(
            text=f"+ {item[0]}", callback_data=f"item_{item[0]}|{item[1]}"
        )])
    buttons.append([
        InlineKeyboardButton(text="✏️ Fərdi iş əlavə et", callback_data="item_custom"),
        InlineKeyboardButton(text="🔙 Kateqoriyalar", callback_data="back_cats"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Smeta yarat və link al", callback_data="export_both")],
        [InlineKeyboardButton(text="❌ Ləğv et", callback_data="cancel_smeta")],
    ])


def smeta_list_kb(smetas: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in smetas:
        status_icon = {"draft": "📝", "sent": "📤", "approved": "✅", "rejected": "❌"}.get(s["status"], "📝")
        buttons.append([InlineKeyboardButton(
            text=f"{status_icon} {s['smeta_number']} — {s['client_name']} ({s['total']:,.0f} {CURRENCY})",
            callback_data=f"view_smeta_{s['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def smeta_action_kb(smeta_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Excel", callback_data=f"dl_excel_{smeta_id}"),
            InlineKeyboardButton(text="📄 PDF",   callback_data=f"dl_pdf_{smeta_id}"),
        ],
        [
            InlineKeyboardButton(text="✅ Təsdiqləndi", callback_data=f"status_approved_{smeta_id}"),
            InlineKeyboardButton(text="❌ Rədd edildi",  callback_data=f"status_rejected_{smeta_id}"),
        ],
    ])


# ═══════════════════════════════════════════════════════════════════════════════
#  Komandalar
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        f"👋 Salam, *{msg.from_user.first_name}*!\n\n"
        f"🏗️ *{COMPANY_NAME}* smeta botuna xoş gəldiniz.\n\n"
        "Aşağıdakı menyudan seçim edin:",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(msg.from_user.id)
    )


@router.message(F.text == "📋 Yeni Smeta")
async def new_smeta_start(msg: Message, state: FSMContext):
    await state.clear()
    await state.update_data(
        telegram_id=msg.from_user.id,
        rooms_data={},
        current_room=None,
        current_category=None,
        margin_pct=DEFAULT_MARGIN,
        discount_pct=DEFAULT_DISCOUNT,
        vat_pct=DEFAULT_VAT,
    )
    await state.set_state(SmetaForm.client_name)
    await msg.answer(
        "📋 *Yeni Smeta*\n\n"
        "👤 Müştərinin adını daxil edin:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(SmetaForm.client_name)
async def smeta_client_name(msg: Message, state: FSMContext):
    await state.update_data(client_name=msg.text.strip())
    await state.set_state(SmetaForm.client_phone)
    await msg.answer("📞 Telefon nömrəsini daxil edin (+994...):")


@router.message(SmetaForm.client_phone)
async def smeta_client_phone(msg: Message, state: FSMContext):
    await state.update_data(client_phone=msg.text.strip())
    await state.set_state(SmetaForm.address)
    await msg.answer("📍 Obyektin ünvanını daxil edin:")


@router.message(SmetaForm.address)
async def smeta_address(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text.strip())
    await state.set_state(SmetaForm.room_select)
    data = await state.get_data()
    await msg.answer(
        "🏠 *Otaqları seçin*\n"
        "Hansı otaqları smeta daxil etmək istəyirsiniz?",
        parse_mode="Markdown",
        reply_markup=rooms_kb(list(data["rooms_data"].keys()))
    )


@router.callback_query(F.data.startswith("room_"), SmetaForm.room_select)
async def room_toggle(cq: CallbackQuery, state: FSMContext):
    room = cq.data[5:]
    data = await state.get_data()
    rooms = data["rooms_data"]

    if room == "custom":
        await cq.message.answer("✏️ Fərdi otağın adını yazın:")
        await state.set_state(SmetaForm.item_name)
        await state.update_data(_waiting_for="custom_room")
        await cq.answer()
        return

    if room in rooms:
        # Artıq seçilibsə — sil
        del rooms[room]
        await state.update_data(rooms_data=rooms)
        await cq.message.edit_reply_markup(reply_markup=rooms_kb(list(rooms.keys())))
        await cq.answer(f"❌ {room} silindi")
    else:
        # Yeni seçim — say soruş
        await state.update_data(_pending_room=room)
        await state.set_state(SmetaForm.item_name)
        await state.update_data(_waiting_for="room_count")
        await cq.message.answer(
            f"🏠 *{room}* — neçə ədəd var?\n"
            f"Rəqəm yazın (məs: 1, 2, 3):",
            parse_mode="Markdown"
        )
        await cq.answer()


@router.callback_query(F.data == "rooms_done", SmetaForm.room_select)
async def rooms_done(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data["rooms_data"]:
        await cq.answer("⚠️ Ən azı bir otaq seçin!", show_alert=True)
        return

    # İlk otağa keç
    first_room = list(data["rooms_data"].keys())[0]
    await state.update_data(current_room=first_room, current_room_idx=0)
    await state.set_state(SmetaForm.category_select)
    await cq.message.edit_text(
        f"🏠 *{first_room}* — Kateqoriya seçin:",
        parse_mode="Markdown",
        reply_markup=categories_kb(first_room)
    )
    await cq.answer()


@router.callback_query(F.data.startswith("cat_"), SmetaForm.category_select)
async def category_selected(cq: CallbackQuery, state: FSMContext):
    cat = cq.data[4:]
    data = await state.get_data()
    await state.update_data(current_category=cat)
    await state.set_state(SmetaForm.add_items)

    items = WORK_CATEGORIES.get(cat, [])
    await cq.message.edit_text(
        f"🔧 *{cat}*\n\nİş növü seçin və ya fərdi əlavə edin:",
        parse_mode="Markdown",
        reply_markup=items_kb(items)
    )
    await cq.answer()


@router.callback_query(F.data.startswith("item_"), SmetaForm.add_items)
async def item_preset_selected(cq: CallbackQuery, state: FSMContext):
    parts = cq.data[5:].split("|")
    name  = parts[0]
    price = float(parts[1]) if len(parts) > 1 else 0.0

    # Parse unit from name e.g. "Suvaq (m²)"
    unit = "m²"
    if "(" in name and ")" in name:
        unit = name[name.index("(")+1:name.index(")")]
        name = name[:name.index("(")].strip()

    await state.update_data(_preset_name=name, _preset_price=price, _preset_unit=unit)
    await state.set_state(SmetaForm.item_qty)
    await cq.message.answer(
        f"📏 *{name}*\nMiqdar daxil edin ({unit}):",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.callback_query(F.data == "item_custom", SmetaForm.add_items)
async def item_custom(cq: CallbackQuery, state: FSMContext):
    await state.update_data(_preset_name=None, _preset_price=None, _preset_unit=None)
    await state.set_state(SmetaForm.item_name)
    await cq.message.answer("✏️ İşin adını daxil edin:")
    await cq.answer()


@router.message(SmetaForm.item_name)
async def item_name_entered(msg: Message, state: FSMContext):
    data = await state.get_data()

    if data.get("_waiting_for") == "room_count":
        try:
            count = int(msg.text.strip())
            if count < 1:
                raise ValueError
        except ValueError:
            await msg.answer("⚠️ Düzgün rəqəm yazın (məs: 1, 2, 3):")
            return

        room = data["_pending_room"]
        rooms = data["rooms_data"]

        # Otaq sayına görə adlandır
        if count == 1:
            rooms[room] = {}
        else:
            for i in range(1, count + 1):
                rooms[f"{room} {i}"] = {}

        await state.update_data(rooms_data=rooms, _waiting_for=None, _pending_room=None)
        await state.set_state(SmetaForm.room_select)
        count_text = f"{count} ədəd" if count > 1 else "1 ədəd"
        await msg.answer(
            f"✅ *{room}* — {count_text} əlavə edildi!\n\n"
            "🏠 Digər otaqları seçin və ya ▶️ *Davam et* basın:",
            parse_mode="Markdown",
            reply_markup=rooms_kb(list(rooms.keys()))
        )
        return

    if data.get("_waiting_for") == "custom_room":
        rooms = data["rooms_data"]
        rooms[msg.text.strip()] = {}
        await state.update_data(rooms_data=rooms, _waiting_for=None)
        await state.set_state(SmetaForm.room_select)
        await msg.answer(
            "🏠 Otaqları seçin:",
            reply_markup=rooms_kb(list(rooms.keys()))
        )
        return

    await state.update_data(_preset_name=msg.text.strip())
    await state.set_state(SmetaForm.item_unit)
    await msg.answer("📐 Ölçü vahidini daxil edin (m², ədəd, m, m³...):")


@router.message(SmetaForm.item_unit)
async def item_unit_entered(msg: Message, state: FSMContext):
    await state.update_data(_preset_unit=msg.text.strip())
    await state.set_state(SmetaForm.item_qty)
    await msg.answer("🔢 Miqdarı daxil edin:")


@router.message(SmetaForm.item_qty)
async def item_qty_entered(msg: Message, state: FSMContext):
    try:
        qty = float(msg.text.replace(",", "."))
        await state.update_data(_preset_qty=qty)
        await state.set_state(SmetaForm.item_price)
        data = await state.get_data()
        price_hint = f" (tövsiyə: {data['_preset_price']} {CURRENCY})" if data.get("_preset_price") else ""
        await msg.answer(f"💰 Qiyməti daxil edin{price_hint} ({CURRENCY}):")
    except ValueError:
        await msg.answer("⚠️ Rəqəm daxil edin (məs: 12.5)")


@router.message(SmetaForm.item_price)
async def item_price_entered(msg: Message, state: FSMContext):
    try:
        price = float(msg.text.replace(",", "."))
        data  = await state.get_data()
        rooms = data["rooms_data"]
        room  = data["current_room"]
        cat   = data["current_category"]
        name  = data["_preset_name"]
        unit  = data.get("_preset_unit", "m²")
        qty   = data.get("_preset_qty", 1.0)

        if room not in rooms:
            rooms[room] = {}
        if cat not in rooms[room]:
            rooms[room][cat] = []

        # Alçipan 2 tərəfli — avtomatik ×2
        display_qty = qty
        if "alçipan" in name.lower() and "2 tərəf" in name.lower():
            qty = qty * 2
            display_qty = qty

        rooms[room][cat].append({
            "name": name, "unit": unit, "qty": qty, "price": price
        })
        await state.update_data(rooms_data=rooms)
        await state.set_state(SmetaForm.add_items)

        items = WORK_CATEGORIES.get(cat, [])
        await msg.answer(
            f"✅ *{name}* əlavə edildi ({display_qty} {unit} × {price} = {display_qty*price:,.2f} {CURRENCY})\n\n"
            "Davam etmək istəyirsiniz?",
            parse_mode="Markdown",
            reply_markup=items_kb(items)
        )
    except ValueError:
        await msg.answer("⚠️ Rəqəm daxil edin")


@router.callback_query(F.data == "room_done", SmetaForm.category_select)
async def room_done(cq: CallbackQuery, state: FSMContext):
    data  = await state.get_data()
    rooms = list(data["rooms_data"].keys())
    idx   = data.get("current_room_idx", 0) + 1

    if idx < len(rooms):
        next_room = rooms[idx]
        await state.update_data(current_room=next_room, current_room_idx=idx)
        await cq.message.edit_text(
            f"🏠 *{next_room}* — Kateqoriya seçin:",
            parse_mode="Markdown",
            reply_markup=categories_kb(next_room)
        )
    else:
        # Bütün otaqlar hazırdır — tənzimləmələr
        await state.set_state(SmetaForm.notes)
        await cq.message.answer(
            "📝 Qeydlər (əlavə şərtlər, materiallar, s.s.) yazın\n"
            "Qeyd yoxdursa /skip yazın:"
        )
    await cq.answer()


@router.callback_query(F.data == "back_cats", SmetaForm.add_items)
async def back_to_cats(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    room = data["current_room"]
    await state.set_state(SmetaForm.category_select)
    await cq.message.edit_text(
        f"🏠 *{room}* — Kateqoriya seçin:",
        parse_mode="Markdown",
        reply_markup=categories_kb(room)
    )
    await cq.answer()


@router.message(SmetaForm.notes)
@router.message(Command("skip"), SmetaForm.notes)
async def smeta_notes(msg: Message, state: FSMContext):
    notes = "" if msg.text == "/skip" else msg.text.strip()
    await state.update_data(notes=notes)
    await _show_summary(msg, state)


async def _show_summary(msg: Message, state: FSMContext):
    data = await state.get_data()

    # Cəmi hesabla
    subtotal = 0.0
    for room, cats in data["rooms_data"].items():
        for cat, items in cats.items():
            for item in items:
                subtotal += item["qty"] * item["price"]

    margin_pct   = data.get("margin_pct", DEFAULT_MARGIN)
    discount_pct = data.get("discount_pct", DEFAULT_DISCOUNT)
    vat_pct      = data.get("vat_pct", DEFAULT_VAT)

    margin   = subtotal * margin_pct / 100
    after_m  = subtotal + margin
    discount = after_m * discount_pct / 100
    after_d  = after_m - discount
    vat      = after_d * vat_pct / 100
    total    = after_d + vat

    await state.update_data(subtotal=subtotal, total=total)

    lines = [f"📋 *Smeta Xülasəsi*\n"]
    lines.append(f"👤 {data['client_name']} | {data['client_phone']}")
    lines.append(f"📍 {data['address']}\n")

    for room, cats in data["rooms_data"].items():
        room_total = sum(i["qty"]*i["price"] for c in cats.values() for i in c)
        lines.append(f"🏠 *{room}* — {room_total:,.2f} {CURRENCY}")

    lines.append(f"\n💰 İşlər cəmi:   `{subtotal:,.2f} {CURRENCY}`")
    lines.append(f"📈 Marja ({margin_pct}%): `{margin:,.2f} {CURRENCY}`")
    if discount > 0:
        lines.append(f"🎁 Endirim ({discount_pct}%): `-{discount:,.2f} {CURRENCY}`")
    lines.append(f"🧾 ƏDV ({vat_pct}%):     `{vat:,.2f} {CURRENCY}`")
    lines.append(f"\n🏷️ *YEKUNİ: {total:,.2f} {CURRENCY}*")

    await state.set_state(SmetaForm.confirm)
    await msg.answer("\n".join(lines), parse_mode="Markdown", reply_markup=confirm_kb())


@router.callback_query(F.data.in_({"export_excel", "export_pdf", "export_both"}), SmetaForm.confirm)
async def export_smeta(cq: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    smeta_number = await generate_smeta_number()
    await state.update_data(smeta_number=smeta_number)
    data = await state.get_data()

    smeta_id = await save_smeta(data)
    data["smeta_number"] = smeta_number

    await cq.message.answer("⏳ Smeta hazırlanır...")

    try:
        WEB_URL = os.getenv("WEB_URL", "https://smeta-bot-production.up.railway.app")
        link = f"{WEB_URL}/smeta/{smeta_number}"

        await cq.message.answer(
            f"✅ *Smeta № {smeta_number} hazırdır!*\n\n"
            f"👤 Müştəri: {data['client_name']}\n"
            f"💰 Məbləğ: *{data['total']:,.2f} {CURRENCY}*\n\n"
            f"🔗 *Müştəriyə göndərin:*\n{link}",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(cq.from_user.id)
        )
        await state.clear()
    except Exception as e:
        await cq.message.answer(f"❌ Xəta: {e}")
    await cq.answer()


# ── Smetalarım ───────────────────────────────────────────────────────────────

@router.message(F.text == "📁 Smetalarım")
async def my_smetas(msg: Message):
    smetas = await get_user_smetas(msg.from_user.id)
    if not smetas:
        await msg.answer("📂 Hələ smeta yoxdur. *Yeni Smeta* düyməsini sıxın.",
                         parse_mode="Markdown")
        return
    await msg.answer(
        f"📁 *Son smetalarınız:*",
        parse_mode="Markdown",
        reply_markup=smeta_list_kb(smetas)
    )


@router.callback_query(F.data.startswith("view_smeta_"))
async def view_smeta(cq: CallbackQuery):
    smeta_id = int(cq.data.split("_")[-1])
    smeta = await get_smeta(smeta_id)
    if not smeta:
        await cq.answer("Smeta tapılmadı", show_alert=True)
        return

    status_map = {"draft": "📝 Qaralama", "sent": "📤 Göndərilib",
                  "approved": "✅ Təsdiqlənib", "rejected": "❌ Rədd edilib"}

    await cq.message.answer(
        f"📋 *Smeta № {smeta['smeta_number']}*\n"
        f"👤 {smeta['client_name']} | {smeta['client_phone']}\n"
        f"📍 {smeta['address']}\n"
        f"💰 *{smeta['total']:,.2f} {CURRENCY}*\n"
        f"📊 Status: {status_map.get(smeta['status'], smeta['status'])}\n"
        f"📅 {smeta['created_at'][:10]}",
        parse_mode="Markdown",
        reply_markup=smeta_action_kb(smeta_id)
    )
    await cq.answer()


@router.callback_query(F.data.startswith("dl_excel_"))
async def download_excel(cq: CallbackQuery, bot: Bot):
    smeta_id = int(cq.data.split("_")[-1])
    smeta = await get_smeta(smeta_id)
    await cq.message.answer("⏳ Excel hazırlanır...")
    path = generate_excel(smeta)
    await bot.send_document(
        cq.from_user.id,
        FSInputFile(path, filename=f"Smeta_{smeta['smeta_number']}.xlsx")
    )
    await cq.answer()


@router.callback_query(F.data.startswith("dl_pdf_"))
async def download_pdf(cq: CallbackQuery, bot: Bot):
    smeta_id = int(cq.data.split("_")[-1])
    smeta = await get_smeta(smeta_id)
    await cq.message.answer("⏳ PDF hazırlanır...")
    path = generate_pdf(smeta)
    await bot.send_document(
        cq.from_user.id,
        FSInputFile(path, filename=f"Smeta_{smeta['smeta_number']}.pdf")
    )
    await cq.answer()


@router.callback_query(F.data.startswith("status_"))
async def change_status(cq: CallbackQuery):
    parts   = cq.data.split("_")
    status  = parts[1]
    smeta_id = int(parts[2])
    await update_smeta_status(smeta_id, status)
    await cq.answer(f"✅ Status yeniləndi: {status}", show_alert=True)


# ── Layihələr ────────────────────────────────────────────────────────────────

@router.message(F.text == "🏗️ Layihələr")
async def projects_menu(msg: Message):
    projects = await get_active_projects()
    if not projects:
        await msg.answer(
            "🏗️ Aktiv layihə yoxdur.\n\n"
            "Layihə əlavə etmək üçün /newproject yazın.",
            reply_markup=main_menu_kb(msg.from_user.id)
        )
        return

    text = "🏗️ *Aktiv Layihələr:*\n\n"
    for p in projects:
        bar = "█" * (p["progress_pct"] // 10) + "░" * (10 - p["progress_pct"] // 10)
        text += (
            f"*{p['name']}*\n"
            f"📍 {p['address']}\n"
            f"📊 [{bar}] {p['progress_pct']}%\n"
            f"📅 {p.get('start_date','?')} → {p.get('end_date','?')}\n\n"
        )
    await msg.answer(text, parse_mode="Markdown")


@router.message(Command("newproject"))
async def new_project(msg: Message, state: FSMContext):
    await state.set_state(ProjectForm.name)
    await msg.answer("🏗️ Layihənin adını daxil edin:")


@router.message(ProjectForm.name)
async def project_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await state.set_state(ProjectForm.address)
    await msg.answer("📍 Ünvanı daxil edin:")


@router.message(ProjectForm.address)
async def project_address(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text.strip())
    await state.set_state(ProjectForm.start_date)
    await msg.answer("📅 Başlama tarixi (GG.AA.YYYY):")


@router.message(ProjectForm.start_date)
async def project_start(msg: Message, state: FSMContext):
    await state.update_data(start_date=msg.text.strip())
    await state.set_state(ProjectForm.end_date)
    await msg.answer("📅 Bitiş tarixi (GG.AA.YYYY):")


@router.message(ProjectForm.end_date)
async def project_end(msg: Message, state: FSMContext):
    await state.update_data(end_date=msg.text.strip())
    data = await state.get_data()
    pid = await save_project(data)
    await state.clear()
    await msg.answer(
        f"✅ *Layihə əlavə edildi!* (ID: {pid})\n"
        f"📌 {data['name']}\n"
        f"📍 {data['address']}\n"
        f"📅 {data['start_date']} → {data['end_date']}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(msg.from_user.id)
    )


# ── Statistika ───────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Statistika")
async def statistics(msg: Message):
    smetas = await get_user_smetas(msg.from_user.id, limit=100)
    if not smetas:
        await msg.answer("📊 Hələ məlumat yoxdur.")
        return

    total_count    = len(smetas)
    total_revenue  = sum(s["total"] for s in smetas)
    approved_count = sum(1 for s in smetas if s["status"] == "approved")
    draft_count    = sum(1 for s in smetas if s["status"] == "draft")

    await msg.answer(
        f"📊 *Statistika*\n\n"
        f"📋 Ümumi smeta: *{total_count}*\n"
        f"✅ Təsdiqlənmiş: *{approved_count}*\n"
        f"📝 Qaralama: *{draft_count}*\n"
        f"💰 Ümumi dəyər: *{total_revenue:,.2f} {CURRENCY}*\n"
        f"📈 Ortalama: *{total_revenue/total_count:,.2f} {CURRENCY}*",
        parse_mode="Markdown"
    )


@router.message(F.text == "⚙️ Admin Panel")
async def admin_panel(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ İcazə yoxdur.")
        return
    all_smetas = await get_user_smetas(0, limit=50)
    await msg.answer(
        f"⚙️ *Admin Panel*\n\n"
        f"Komandalar:\n"
        f"/newproject — Yeni layihə\n"
        f"/allsmetas — Bütün smetalar\n",
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "cancel_smeta")
async def cancel_smeta(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    await cq.message.answer(
        "❌ Smeta ləğv edildi.",
        reply_markup=main_menu_kb(cq.from_user.id)
    )
    await cq.answer()
