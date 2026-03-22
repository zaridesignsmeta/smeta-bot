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
    DEFAULT_MARGIN, DEFAULT_DISCOUNT,
    COMPANY_NAME, OBJECT_TYPES, OBJECT_ROOMS, PRICE_CATEGORIES
)
from database import (
    save_smeta, get_smeta, get_user_smetas,
    update_smeta_status, generate_smeta_number,
    save_project, get_active_projects, update_project_progress,
    update_room_progress, get_room_progress, save_photo, get_photos,
    get_smeta_by_number, get_user_smeta_numbers,
    link_group_to_smeta, get_smeta_by_group, get_group_by_smeta,
    get_total_paid, init_checklist_for_smeta,
)
from generators import generate_excel, generate_pdf

# New feature routers
from handlers_payment  import router as payment_router
from handlers_worker   import router as worker_router
from handlers_project  import router as project_router
from handlers_reminder import router as reminder_router
from handlers_report   import router as report_router

router = Router()
router.include_router(payment_router)
router.include_router(worker_router)
router.include_router(project_router)
router.include_router(reminder_router)
router.include_router(report_router)


# ═══════════════════════════════════════════════════════════════════════════════
#  FSM Vəziyyətləri
# ═══════════════════════════════════════════════════════════════════════════════

class SmetaForm(StatesGroup):
    object_type    = State()
    price_category = State()
    area_m2        = State()
    client_name    = State()
    client_phone   = State()
    address        = State()
    room_select    = State()
    category_select = State()
    add_items      = State()
    item_name      = State()
    item_unit      = State()
    item_qty       = State()
    item_price     = State()
    settings       = State()
    notes          = State()
    confirm        = State()

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

def room_items_qty_kb(room: str, categories: dict) -> InlineKeyboardMarkup:
    """Otaqdakı bütün işlər üçün miqdar daxiletmə klaviaturası"""
    buttons = []
    for cat, items in categories.items():
        for item in items:
            qty_text = f"✅ {item['qty']}" if item['qty'] > 0 else "➕ 0"
            buttons.append([InlineKeyboardButton(
                text=f"{qty_text}  |  {item['name']} ({item['unit']})",
                callback_data=f"setqty_{item['name'][:30]}"
            )])
    buttons.append([
        InlineKeyboardButton(text="✅ Bu otaq hazırdır", callback_data="room_qty_done"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def object_type_kb() -> InlineKeyboardMarkup:
    buttons = []
    for name in OBJECT_TYPES:
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"obj_{OBJECT_TYPES[name]}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def price_category_kb() -> InlineKeyboardMarkup:
    buttons = []
    for name, data in PRICE_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"price_{data['key']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_menu_kb(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📋 Yeni Smeta"), KeyboardButton(text="📁 Smetalarım")],
        [KeyboardButton(text="🏗️ Layihələr"),  KeyboardButton(text="📊 Statistika")],
    ]
    if user_id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="👷 İşçilər"), KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def rooms_kb(selected_rooms: list, room_list: list = None) -> InlineKeyboardMarkup:
    if room_list is None:
        room_list = ROOMS
    buttons = []
    for room in room_list:
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


@router.message(Command("newsmeta"))
async def cmd_newsmeta(msg: Message, state: FSMContext):
    await new_smeta_start(msg, state)


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
        object_type=None,
        price_category=None,
    )
    await state.set_state(SmetaForm.object_type)
    await msg.answer(
        "📋 *Yeni Smeta*\n\n"
        "🏗️ Obyekt növünü seçin:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await msg.answer(
        "Növü seçin:",
        reply_markup=object_type_kb()
    )


@router.callback_query(F.data.startswith("obj_"), SmetaForm.object_type)
async def object_type_selected(cq: CallbackQuery, state: FSMContext):
    obj_key = cq.data[4:]
    obj_name = next(k for k, v in OBJECT_TYPES.items() if v == obj_key)
    await state.update_data(object_type=obj_key, object_type_name=obj_name)
    await state.set_state(SmetaForm.price_category)

    await cq.message.edit_text(
        f"✅ *{obj_name}* seçildi.\n\n"
        f"💰 İşçilik qiymət kateqoriyasını seçin:\n\n"
        f"_(Qiymətlər yalnız işçilik haqqını əhatə edir, materiallar ayrıca hesablanır)_",
        parse_mode="Markdown",
        reply_markup=price_category_kb()
    )
    await cq.answer()


@router.callback_query(F.data.startswith("price_"), SmetaForm.price_category)
async def price_category_selected(cq: CallbackQuery, state: FSMContext):
    price_key = cq.data[6:]
    price_data = next(v for v in PRICE_CATEGORIES.values() if v["key"] == price_key)
    price_name = next(k for k, v in PRICE_CATEGORIES.items() if v["key"] == price_key)

    includes_text = "\n".join([f"  ✅ {i}" for i in price_data["includes"]])
    excludes_text = "\n".join([f"  ❌ {i}" for i in price_data["excludes"]])

    await state.update_data(
        price_category=price_key,
        price_category_name=price_name,
        price_per_m2=price_data["price_per_m2"],
        price_multiplier=price_data["multiplier"],
    )
    await state.set_state(SmetaForm.area_m2)
    await cq.message.edit_text(
        f"✅ *{price_name}* seçildi.\n\n"
        f"*Daxildir:*\n" + "\n".join([f"  ✅ {i}" for i in price_data["includes"]]) + "\n\n"
        f"*Daxil deyil:*\n" + "\n".join([f"  ❌ {i}" for i in price_data["excludes"]]),
        parse_mode="Markdown"
    )
    await cq.message.answer(
        "📐 Obyektin ümumi sahəsini daxil edin (m²):\n"
        "_(məs: 85, 120.5)_",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.message(SmetaForm.area_m2)
async def area_m2_entered(msg: Message, state: FSMContext):
    try:
        area = float(msg.text.replace(",", "."))
        if area <= 0:
            raise ValueError
        data = await state.get_data()
        price_per_m2 = data.get("price_per_m2", 250)
        iscilik_total = area * price_per_m2
        margin = iscilik_total * DEFAULT_MARGIN / 100
        musteri_qiymeti = iscilik_total + margin

        await state.update_data(
            area_m2=area,
            iscilik_total=iscilik_total,
            musteri_qiymeti=musteri_qiymeti,
        )
        await state.set_state(SmetaForm.client_name)
        await msg.answer(
            f"✅ *{area} m²* — işçilik hesablandı:\n"
            f"💰 İşçilik: `{iscilik_total:,.0f} {CURRENCY}`\n\n"
            f"👤 Müştərinin adını daxil edin:",
            parse_mode="Markdown"
        )
    except ValueError:
        await msg.answer("⚠️ Düzgün rəqəm daxil edin (məs: 85 və ya 120.5)")


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

    # Obyekt növünə görə otaqlar
    obj_key = data.get("object_type", "manзil")
    room_list = OBJECT_ROOMS.get(obj_key, ROOMS)

    await msg.answer(
        f"🏠 *Otaqları seçin*\n"
        f"Smetaya daxil ediləcək otaqları seçin:",
        parse_mode="Markdown",
        reply_markup=rooms_kb(list(data["rooms_data"].keys()), room_list)
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

    # Bütün otaqlar üçün bütün işləri avtomatik əlavə et (miqdar=0, qiymət=standart)
    rooms = data["rooms_data"]
    multiplier = data.get("price_multiplier", 1.0)

    for room in rooms:
        rooms[room] = {}
        for cat, items in WORK_CATEGORIES.items():
            rooms[room][cat] = []
            for item_name, base_price in items:
                unit = "m²"
                if "(" in item_name and ")" in item_name:
                    unit = item_name[item_name.index("(")+1:item_name.index(")")]
                    clean_name = item_name[:item_name.index("(")].strip()
                else:
                    clean_name = item_name
                rooms[room][cat].append({
                    "name": clean_name,
                    "unit": unit,
                    "qty": 0,
                    "price": round(base_price * multiplier, 2),
                })

    await state.update_data(rooms_data=rooms)

    # İlk otağa keç — miqdar daxiletmə
    first_room = list(rooms.keys())[0]
    await state.update_data(current_room=first_room, current_room_idx=0)
    await state.set_state(SmetaForm.category_select)

    await cq.message.edit_text(
        f"✅ Bütün işlər avtomatik əlavə edildi!\n\n"
        f"🏠 *{first_room}* — İndi hər iş üçün miqdar daxil edin.\n"
        f"_(Etmək istəmədiklərinizi 0 buraxın)_",
        parse_mode="Markdown",
        reply_markup=room_items_qty_kb(first_room, rooms[first_room])
    )


@router.callback_query(F.data.startswith("setqty_"), SmetaForm.category_select)
async def set_qty_selected(cq: CallbackQuery, state: FSMContext):
    item_name = cq.data[7:]
    await state.update_data(_editing_item=item_name)
    await state.set_state(SmetaForm.item_qty)
    await cq.message.answer(
        f"📏 *{item_name}*\nMiqdar daxil edin (0 = daxil deyil):",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.message(SmetaForm.item_qty)
async def item_qty_entered(msg: Message, state: FSMContext):
    try:
        qty = float(msg.text.replace(",", "."))
        if qty < 0:
            raise ValueError
        data = await state.get_data()
        rooms = data["rooms_data"]
        room = data["current_room"]
        item_name = data.get("_editing_item", "")

        # Həmin işi tap və miqdarı yenilə
        for cat, items in rooms[room].items():
            for item in items:
                if item["name"] == item_name or item_name.startswith(item["name"][:20]):
                    item["qty"] = qty
                    break

        await state.update_data(rooms_data=rooms)
        await state.set_state(SmetaForm.category_select)
        await msg.answer(
            f"✅ *{item_name}* — {qty} olaraq qeyd edildi.\n\n"
            f"🏠 *{room}* — digər işləri daxil edin:",
            parse_mode="Markdown",
            reply_markup=room_items_qty_kb(room, rooms[room])
        )
    except ValueError:
        await msg.answer("⚠️ Düzgün rəqəm daxil edin (məs: 25 və ya 12.5)")


@router.callback_query(F.data == "room_qty_done", SmetaForm.category_select)
async def room_qty_done(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rooms = data["rooms_data"]
    room_keys = list(rooms.keys())
    idx = data.get("current_room_idx", 0) + 1

    if idx < len(room_keys):
        next_room = room_keys[idx]
        await state.update_data(current_room=next_room, current_room_idx=idx)
        await cq.message.edit_text(
            f"🏠 *{next_room}* — Miqdarları daxil edin:",
            parse_mode="Markdown",
            reply_markup=room_items_qty_kb(next_room, rooms[next_room])
        )
    else:
        await state.set_state(SmetaForm.notes)
        await cq.message.answer(
            "📝 Qeydlər yazın (istəyə görə)\n"
            "Yoxdursa /skip yazın:"
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

    # Əlavə işlərin cəmi
    extra_subtotal = 0.0
    for room, cats in data["rooms_data"].items():
        for cat, items in cats.items():
            for item in items:
                extra_subtotal += item["qty"] * item["price"]

    # İşçilik (m² əsaslı)
    iscilik = data.get("iscilik_total", 0.0)
    musteri_qiymeti = data.get("musteri_qiymeti", iscilik)

    # Ümumi müştəri qiyməti = işçilik (marjalı) + əlavə işlər
    margin_pct   = data.get("margin_pct", DEFAULT_MARGIN)
    discount_pct = data.get("discount_pct", DEFAULT_DISCOUNT)
    extra_with_margin = extra_subtotal * (1 + margin_pct / 100)
    discount = (musteri_qiymeti + extra_with_margin) * discount_pct / 100
    total = musteri_qiymeti + extra_with_margin - discount

    subtotal = iscilik + extra_subtotal

    await state.update_data(subtotal=subtotal, total=total, extra_subtotal=extra_subtotal)

    area = data.get("area_m2", 0)
    price_per_m2 = data.get("price_per_m2", 0)
    obj_name = data.get("object_type_name", "")
    price_name = data.get("price_category_name", "")

    lines = [f"📋 *Smeta Xülasəsi*\n"]
    lines.append(f"🏗️ {obj_name} | {price_name}")
    lines.append(f"👤 {data['client_name']} | {data['client_phone']}")
    lines.append(f"📍 {data['address']}")
    lines.append(f"📐 Sahə: {area} m² × {price_per_m2} AZN/m²\n")

    for room, cats in data["rooms_data"].items():
        room_total = sum(i["qty"]*i["price"] for c in cats.values() for i in c)
        if room_total > 0:
            lines.append(f"🏠 *{room}* — {room_total:,.2f} {CURRENCY}")

    lines.append(f"\n💰 İşçilik:      `{musteri_qiymeti:,.2f} {CURRENCY}`")
    if extra_subtotal > 0:
        lines.append(f"🔧 Əlavə işlər: `{extra_with_margin:,.2f} {CURRENCY}`")
    if discount > 0:
        lines.append(f"🎁 Endirim:     `-{discount:,.2f} {CURRENCY}`")
    lines.append(f"\n🏷️ *MÜŞTƏRİ QİYMƏTİ: {total:,.2f} {CURRENCY}*")

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

@router.message(Command("mysmetas"))
async def cmd_mysmetas(msg: Message):
    await my_smetas(msg)


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
async def change_status(cq: CallbackQuery, bot: Bot):
    parts    = cq.data.split("_")
    status   = parts[1]
    smeta_id = int(parts[2])
    await update_smeta_status(smeta_id, status)
    await cq.answer(f"✅ Status yeniləndi: {status}", show_alert=True)

    if status == "approved":
        smeta = await get_smeta(smeta_id)
        if smeta:
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"✅ *{smeta['smeta_number']} təsdiqləndi!*\n\n"
                        f"👤 Müştəri: {smeta['client_name']}\n"
                        f"💰 Məbləğ: *{smeta['total']:,.2f} {CURRENCY}*\n\n"
                        f"▶️ Layihəni başlatmaq üçün:\n"
                        f"/start_project {smeta['smeta_number']}",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass


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


@router.message(F.text == "👷 İşçilər")
async def workers_menu_btn(msg: Message):
    from handlers_worker import cmd_workers
    await cmd_workers(msg)


@router.message(F.text == "⚙️ Admin Panel")
async def admin_panel(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ İcazə yoxdur.")
        return
    await msg.answer(
        "⚙️ *Admin Panel*\n\n"
        "💳 Ödənişlər:\n"
        "  /payment — Ödəniş əlavə et\n\n"
        "👷 İşçilər:\n"
        "  /addworker — Yeni işçi\n"
        "  /workers — İşçilər siyahısı\n"
        "  /assign — İşçi təyin et\n"
        "  /workerpay — İşçiyə ödəniş\n\n"
        "🏗️ Layihə:\n"
        "  /start_project SM-XXXX — Başlat\n"
        "  /shopping — Alış siyahısı\n\n"
        "⏰ Digər:\n"
        "  /remind — Xatırlatma\n"
        "  /report — Aylıq hesabat\n"
        "  /contract SM-XXXX — Müqavilə\n"
        "  /update — Gedişat yenilə\n",
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


# ═══════════════════════════════════════════════════════════════════════════════
#  GEDİŞAT YENİLƏMƏ
# ═══════════════════════════════════════════════════════════════════════════════

class UpdateForm(StatesGroup):
    smeta_number  = State()
    room_select   = State()
    progress      = State()
    notes         = State()
    photos        = State()


def smeta_select_kb(smetas: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in smetas:
        buttons.append([InlineKeyboardButton(
            text=f"📋 {s['smeta_number']} — {s['client_name']}",
            callback_data=f"upd_smeta_{s['smeta_number']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def room_select_update_kb(rooms: list, progress_data: dict) -> InlineKeyboardMarkup:
    buttons = []
    for room in rooms:
        pct = progress_data.get(room, {}).get("progress_pct", 0)
        bar = "█" * (pct // 20) + "░" * (5 - pct // 20)
        buttons.append([InlineKeyboardButton(
            text=f"{bar} {room} ({pct}%)",
            callback_data=f"upd_room_{room}"
        )])
    buttons.append([InlineKeyboardButton(text="✅ Bitir", callback_data="upd_done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("update"))
async def cmd_update(msg: Message, state: FSMContext):
    await state.clear()
    smetas = await get_user_smeta_numbers(msg.from_user.id)
    if not smetas:
        await msg.answer("📂 Hələ smeta yoxdur.")
        return
    await state.set_state(UpdateForm.smeta_number)
    await msg.answer(
        "📊 *Gedişat Yeniləmə*\n\nHansı smetanı yeniləmək istəyirsiniz?",
        parse_mode="Markdown",
        reply_markup=smeta_select_kb(smetas)
    )


@router.callback_query(F.data.startswith("upd_smeta_"), UpdateForm.smeta_number)
async def update_smeta_selected(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[10:]
    smeta = await get_smeta_by_number(smeta_number)
    if not smeta:
        await cq.answer("Smeta tapılmadı", show_alert=True)
        return

    rooms = list(smeta["rooms_data"].keys())
    progress_data = await get_room_progress(smeta_number)

    await state.update_data(smeta_number=smeta_number, rooms=rooms)
    await state.set_state(UpdateForm.room_select)
    await cq.message.edit_text(
        f"📋 *{smeta_number}* — {smeta['client_name']}\n"
        f"📍 {smeta['address']}\n\n"
        f"🏠 Hansı otağı yeniləmək istəyirsiniz?",
        parse_mode="Markdown",
        reply_markup=room_select_update_kb(rooms, progress_data)
    )
    await cq.answer()


@router.callback_query(F.data.startswith("upd_room_"), UpdateForm.room_select)
async def update_room_selected(cq: CallbackQuery, state: FSMContext):
    room = cq.data[9:]
    await state.update_data(current_room=room)
    await state.set_state(UpdateForm.progress)
    await cq.message.answer(
        f"🏠 *{room}*\n\n"
        f"Hazırlıq faizini daxil edin (0-100):\n"
        f"_(məs: 50, 75, 100)_",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.message(UpdateForm.progress)
async def update_progress_entered(msg: Message, state: FSMContext):
    try:
        pct = int(msg.text.strip())
        if not 0 <= pct <= 100:
            raise ValueError
        await state.update_data(progress=pct)
        await state.set_state(UpdateForm.notes)
        await msg.answer(
            f"✅ *{pct}%* qeyd edildi.\n\n"
            f"📝 Qeyd yazın (istəyə görə) və ya /skip:\n"
            f"_(məs: 'Divarlar hazırdır, tavan növbəti həftə')_",
            parse_mode="Markdown"
        )
    except ValueError:
        await msg.answer("⚠️ 0-100 arasında rəqəm daxil edin")


@router.message(UpdateForm.notes)
@router.message(Command("skip"), UpdateForm.notes)
async def update_notes_entered(msg: Message, state: FSMContext):
    notes = "" if msg.text == "/skip" else msg.text.strip()
    await state.update_data(notes=notes)
    await state.set_state(UpdateForm.photos)
    await msg.answer(
        "📸 Foto göndərin (istəyə görə)\n"
        "Bir neçə foto göndərə bilərsiniz.\n"
        "Bitirdikdə /done yazın:",
    )


@router.message(UpdateForm.photos, F.photo)
async def update_photo_received(msg: Message, state: FSMContext):
    data = await state.get_data()
    file_id = msg.photo[-1].file_id
    caption = msg.caption or ""
    await save_photo(
        data["smeta_number"],
        data["current_room"],
        file_id,
        caption,
        msg.from_user.id
    )
    await msg.answer("✅ Foto əlavə edildi. Daha foto göndərin və ya /done yazın.")


@router.message(UpdateForm.photos, F.document & F.document.mime_type.startswith("image/"))
async def update_photo_document_received(msg: Message, state: FSMContext):
    """Fayl kimi göndərilmiş şəkillər (orijinal keyfiyyət)"""
    data = await state.get_data()
    file_id = msg.document.file_id
    caption = msg.caption or ""
    await save_photo(
        data["smeta_number"],
        data["current_room"],
        file_id,
        caption,
        msg.from_user.id
    )
    await msg.answer("✅ Foto əlavə edildi. Daha foto göndərin və ya /done yazın.")


@router.message(UpdateForm.photos)
@router.message(Command("done"), UpdateForm.photos)
async def update_done(msg: Message, state: FSMContext):
    data = await state.get_data()
    await update_room_progress(
        data["smeta_number"],
        data["current_room"],
        data["progress"],
        data.get("notes", ""),
        msg.from_user.id
    )

    smeta = await get_smeta_by_number(data["smeta_number"])
    rooms = data.get("rooms", [])
    progress_data = await get_room_progress(data["smeta_number"])

    await state.set_state(UpdateForm.room_select)
    await msg.answer(
        f"✅ *{data['current_room']}* — {data['progress']}% yeniləndi!\n\n"
        f"Başqa otaq yeniləmək istəyirsiniz?",
        parse_mode="Markdown",
        reply_markup=room_select_update_kb(rooms, progress_data)
    )


@router.callback_query(F.data == "upd_done")
async def update_finish(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    smeta_number = data.get("smeta_number", "")
    WEB_URL = os.getenv("WEB_URL", "https://smeta-bot-production.up.railway.app")
    link = f"{WEB_URL}/smeta/{smeta_number}"

    await state.clear()
    await cq.message.answer(
        f"✅ *Gedişat yeniləndi!*\n\n"
        f"🔗 Müştəri linki:\n{link}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(cq.from_user.id)
    )
    await cq.answer()


# ═══════════════════════════════════════════════════════════════════════════════
#  TELEGRAM QRUP SİSTEMİ
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(Command("linksmeta"))
async def cmd_linksmeta(msg: Message, bot: Bot):
    """Qrupu smetaya bağla: /linksmeta SM-2026-0001"""
    if msg.chat.type not in ("group", "supergroup"):
        await msg.answer("⚠️ Bu komanda yalnız qrupda istifadə edilir.")
        return

    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer("❌ Smeta nömrəsi yazın: /linksmeta SM-2026-0001")
        return

    smeta_number = parts[1].upper()
    smeta = await get_smeta_by_number(smeta_number)
    if not smeta:
        await msg.answer(f"❌ *{smeta_number}* tapılmadı. Nömrəni yoxlayın.")
        return

    await link_group_to_smeta(msg.chat.id, smeta_number)

    WEB_URL = os.getenv("WEB_URL", "https://smeta-bot-production.up.railway.app")
    link = f"{WEB_URL}/smeta/{smeta_number}"

    await msg.answer(
        f"✅ *Bu qrup smetaya bağlandı!*\n\n"
        f"📋 Smeta: *{smeta_number}*\n"
        f"👤 Müştəri: {smeta['client_name']}\n"
        f"📍 Ünvan: {smeta['address']}\n\n"
        f"📌 *İndi bu qrupda:*\n"
        f"• Foto göndərin → avtomatik smetaya əlavə olunur\n"
        f"• Sənəd göndərin → saxlanılır\n"
        f"• /progress yazın → gedişatı yeniləyin\n\n"
        f"🔗 Müştəri linki: {link}",
        parse_mode="Markdown"
    )


@router.message(F.photo & F.chat.type.in_({"group", "supergroup"}))
async def group_photo_received(msg: Message, bot: Bot):
    """Qrupda foto gəldikdə avtomatik smetaya əlavə et"""
    if not msg.photo:
        return

    smeta_number = await get_smeta_by_group(msg.chat.id)
    if not smeta_number:
        await msg.reply(
            "⚠️ Bu qrup heç bir smetaya bağlı deyil.\n"
            "Bağlamaq üçün /linksmeta əmrindən istifadə edin."
        )
        return

    file_id = msg.photo[-1].file_id
    caption = msg.caption or ""
    room_name = "Ümumi"

    if caption:
        smeta = await get_smeta_by_number(smeta_number)
        if smeta:
            for room in smeta["rooms_data"].keys():
                if room.lower() in caption.lower():
                    room_name = room
                    break

    await save_photo(smeta_number, room_name, file_id, caption, msg.from_user.id)
    await msg.reply(
        f"✅ Foto *{smeta_number}* smetasına əlavə edildi.\n"
        f"🏠 Otaq: {room_name}",
        parse_mode="Markdown"
    )


@router.message(Command("progress") & F.chat.type.in_({"group", "supergroup"}))
async def group_progress(msg: Message, state: FSMContext, bot: Bot):
    """Qrupda gedişat yenilə: /progress Qonaq otağı 75"""
    smeta_number = await get_smeta_by_group(msg.chat.id)
    if not smeta_number:
        await msg.reply("⚠️ Bu qrup heç bir smetaya bağlı deyil. /linksmeta istifadə edin.")
        return

    parts = msg.text.split()
    if len(parts) < 2:
        smeta = await get_smeta_by_number(smeta_number)
        progress_data = await get_room_progress(smeta_number)
        rooms = list(smeta["rooms_data"].keys())
        lines = [f"📊 *{smeta_number}* — Gedişat:\n"]
        for room in rooms:
            pct = progress_data.get(room, {}).get("progress_pct", 0)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            lines.append(f"{bar} {room}: {pct}%")
        lines.append(f"\n_İstifadə: /progress Otaq adı faiz_")
        lines.append(f"_Məs: /progress Qonaq otağı 75_")
        await msg.reply("\n".join(lines), parse_mode="Markdown")
        return

    try:
        pct = int(parts[-1])
        room_name = " ".join(parts[1:-1])
        await update_room_progress(smeta_number, room_name, pct, "", msg.from_user.id)
        await msg.reply(
            f"✅ *{room_name}* — {pct}% yeniləndi!",
            parse_mode="Markdown"
        )
    except (ValueError, IndexError):
        await msg.reply("❌ Format: /progress Otaq adı faiz\nMəs: /progress Qonaq otağı 75")


# ═══════════════════════════════════════════════════════════════════════════════
#  ŞƏKİL ƏLAVƏ ET  (/addphoto)
# ═══════════════════════════════════════════════════════════════════════════════

class PhotoForm(StatesGroup):
    smeta_select = State()
    room_select  = State()
    uploading    = State()


def _photo_smeta_kb(smetas: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"📋 {s['smeta_number']} — {s['client_name']}",
            callback_data=f"aphoto_smeta_{s['smeta_number']}"
        )]
        for s in smetas
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _photo_room_kb(rooms: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🏠 {r}", callback_data=f"aphoto_room_{r}")]
        for r in rooms
    ]
    buttons.append([InlineKeyboardButton(text="🏗️ Ümumi", callback_data="aphoto_room_Ümumi")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("addphoto"))
async def cmd_addphoto(msg: Message, state: FSMContext):
    """Birbaşa şəkil əlavə et: smeta → otaq → şəkil(lər) → /done"""
    await state.clear()
    smetas = await get_user_smeta_numbers(msg.from_user.id)
    if not smetas:
        await msg.answer("📂 Hələ smeta yoxdur.")
        return
    await state.set_state(PhotoForm.smeta_select)
    await msg.answer(
        "📸 *Şəkil Əlavə Et*\n\nHansı smetaya şəkil əlavə etmək istəyirsiniz?",
        parse_mode="Markdown",
        reply_markup=_photo_smeta_kb(smetas),
    )


@router.callback_query(F.data.startswith("aphoto_smeta_"), PhotoForm.smeta_select)
async def aphoto_smeta_selected(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[13:]
    smeta = await get_smeta_by_number(smeta_number)
    if not smeta:
        await cq.answer("Smeta tapılmadı", show_alert=True)
        return
    rooms = list(smeta["rooms_data"].keys())
    await state.update_data(smeta_number=smeta_number, rooms=rooms)
    await state.set_state(PhotoForm.room_select)
    await cq.message.edit_text(
        f"📋 *{smeta_number}* — {smeta['client_name']}\n\n🏠 Hansı otaq üçün şəkil əlavə edilsin?",
        parse_mode="Markdown",
        reply_markup=_photo_room_kb(rooms),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("aphoto_room_"), PhotoForm.room_select)
async def aphoto_room_selected(cq: CallbackQuery, state: FSMContext):
    room_name = cq.data[12:]
    await state.update_data(current_room=room_name, photo_count=0)
    await state.set_state(PhotoForm.uploading)
    await cq.message.answer(
        f"🏠 *{room_name}*\n\n"
        "📸 Şəkil(lər) göndərin.\n"
        "Bitirdikdə /done yazın.",
        parse_mode="Markdown",
    )
    await cq.answer()


@router.message(PhotoForm.uploading, F.photo)
async def aphoto_photo_received(msg: Message, state: FSMContext):
    data = await state.get_data()
    file_id = msg.photo[-1].file_id
    caption = msg.caption or ""
    await save_photo(
        data["smeta_number"],
        data["current_room"],
        file_id,
        caption,
        msg.from_user.id,
    )
    count = data.get("photo_count", 0) + 1
    await state.update_data(photo_count=count)
    await msg.answer(f"✅ Şəkil {count} əlavə edildi. Daha göndərin və ya /done yazın.")


@router.message(PhotoForm.uploading, F.document & F.document.mime_type.startswith("image/"))
async def aphoto_document_received(msg: Message, state: FSMContext):
    """Fayl kimi göndərilmiş şəkillər (orijinal keyfiyyət)"""
    data = await state.get_data()
    file_id = msg.document.file_id
    caption = msg.caption or ""
    await save_photo(
        data["smeta_number"],
        data["current_room"],
        file_id,
        caption,
        msg.from_user.id,
    )
    count = data.get("photo_count", 0) + 1
    await state.update_data(photo_count=count)
    await msg.answer(f"✅ Şəkil {count} əlavə edildi. Daha göndərin və ya /done yazın.")


@router.message(PhotoForm.uploading)
@router.message(Command("done"), PhotoForm.uploading)
async def aphoto_done(msg: Message, state: FSMContext):
    data = await state.get_data()
    count = data.get("photo_count", 0)
    smeta_number = data.get("smeta_number", "")
    room_name = data.get("current_room", "")
    await state.clear()
    if count == 0:
        await msg.answer(
            "⚠️ Heç şəkil göndərilmədi.",
            reply_markup=main_menu_kb(msg.from_user.id),
        )
        return
    await msg.answer(
        f"✅ *{count} şəkil əlavə edildi!*\n"
        f"📋 Smeta: {smeta_number}\n"
        f"🏠 Otaq: {room_name}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(msg.from_user.id),
    )
