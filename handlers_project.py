"""
Layihə Başlatma və Alış Siyahısı — Feature 3
"""

import os
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from config import ADMIN_IDS, CURRENCY
from database import (
    get_smeta_by_number, update_smeta_status,
    get_all_smetas_admin, add_reminder,
    add_shopping_item, get_shopping_list, update_shopping_item,
)

router = Router()

PRIORITY_LABELS = {
    "urgent": "🔴 TƏCİLİ (1-ci həftə)",
    "normal": "🟡 Normal (2-ci həftə)",
    "late":   "🟢 Son mərhələ",
}

SHOPPING_TEMPLATE = {
    "urgent": [
        ("Suvaq kütləsi",        "kisə", 20),
        ("Sement",               "kisə", 10),
        ("Qum",                  "m³",   2),
        ("Şpatlevka (start)",    "kisə", 15),
        ("Primer",               "litr", 10),
        ("Gips blok",            "m²",   0),
        ("Kərpic",               "ədəd", 0),
    ],
    "normal": [
        ("Şpatlevka (finish)",   "kisə", 10),
        ("Kafel yapışdırıcı",    "kisə", 15),
        ("Kafel/Keramogranit",   "m²",   20),
        ("Laminat",              "m²",   30),
        ("Elektrik kabelı",      "m",    100),
        ("Alçipan lövhə",        "ədəd", 0),
    ],
    "late": [
        ("Boya (lat)",           "litr", 15),
        ("Plintus",              "m",    30),
        ("Qapı qolu dəsti",      "ədəd", 5),
        ("Rozetka/Açar",         "ədəd", 10),
        ("Stekloxolst",          "m²",   0),
    ],
}


class ShoppingForm(StatesGroup):
    smeta_select = State()
    action       = State()
    item_name    = State()
    item_unit    = State()
    item_qty     = State()
    item_priority = State()
    mark_item    = State()
    mark_price   = State()


def smeta_select_kb(smetas: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in smetas:
        buttons.append([InlineKeyboardButton(
            text=f"📋 {s['smeta_number']} — {s['client_name']}",
            callback_data=f"shop_smeta_{s['smeta_number']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shopping_action_kb(smeta_number: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Siyahıya bax",    callback_data=f"shop_view_{smeta_number}")],
        [InlineKeyboardButton(text="➕ Yeni əlavə et",   callback_data=f"shop_add_{smeta_number}")],
        [InlineKeyboardButton(text="✅ Alındı işarələ",  callback_data=f"shop_mark_{smeta_number}")],
    ])


def priority_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 TƏCİLİ (1-ci həftə)", callback_data="shopri_urgent")],
        [InlineKeyboardButton(text="🟡 Normal (2-ci həftə)",  callback_data="shopri_normal")],
        [InlineKeyboardButton(text="🟢 Son mərhələ",           callback_data="shopri_late")],
    ])


def pending_items_kb(items: list) -> InlineKeyboardMarkup:
    buttons = []
    for item in items:
        icon = "⏳" if item["status"] == "pending" else ("✅" if item["status"] == "bought" else "🚚")
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {item['item_name']} ({item['qty']} {item['unit']})",
            callback_data=f"shopmark_{item['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("shopping"))
async def cmd_shopping(msg: Message, state: FSMContext):
    await state.clear()
    smetas = await get_all_smetas_admin()
    if not smetas:
        await msg.answer("📂 Hələ smeta yoxdur.")
        return
    await state.set_state(ShoppingForm.smeta_select)
    await msg.answer(
        "🛒 *Alış Siyahısı*\n\nHansı smeta?",
        parse_mode="Markdown",
        reply_markup=smeta_select_kb(smetas)
    )


@router.callback_query(F.data.startswith("shop_smeta_"), ShoppingForm.smeta_select)
async def shopping_smeta_selected(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[11:]
    await state.update_data(smeta_number=smeta_number)
    await state.set_state(ShoppingForm.action)
    await cq.message.edit_text(
        f"🛒 *{smeta_number}* — Alış Siyahısı",
        parse_mode="Markdown",
        reply_markup=shopping_action_kb(smeta_number)
    )
    await cq.answer()


@router.callback_query(F.data.startswith("shop_view_"), ShoppingForm.action)
async def shopping_view(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[10:]
    items = await get_shopping_list(smeta_number)

    if not items:
        await cq.answer("Alış siyahısı boşdur", show_alert=True)
        return

    urgent = [i for i in items if i["priority"] == "urgent"]
    normal = [i for i in items if i["priority"] == "normal"]
    late   = [i for i in items if i["priority"] == "late"]
    other  = [i for i in items if i["priority"] not in ("urgent", "normal", "late")]

    lines = [f"🛒 *{smeta_number}* — Alış Siyahısı\n"]

    for label, group in [
        ("🔴 TƏCİLİ", urgent),
        ("🟡 Normal",  normal),
        ("🟢 Son mərhələ", late),
        ("📋 Digər",   other),
    ]:
        if group:
            lines.append(f"\n*{label}*")
            for item in group:
                st = "✅" if item["status"] == "bought" else ("🚚" if item["status"] == "delivered" else "⏳")
                price_txt = f" — {item['price_paid']:,.2f} AZN" if item.get("price_paid") else ""
                lines.append(f"{st} {item['item_name']}: {item['qty']} {item['unit']}{price_txt}")

    await cq.message.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=shopping_action_kb(smeta_number)
    )
    await cq.answer()


@router.callback_query(F.data.startswith("shop_add_"), ShoppingForm.action)
async def shopping_add_start(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[9:]
    await state.update_data(smeta_number=smeta_number)
    await state.set_state(ShoppingForm.item_name)
    await cq.message.answer("📦 Material adını daxil edin:")
    await cq.answer()


@router.message(ShoppingForm.item_name)
async def shopping_item_name(msg: Message, state: FSMContext):
    await state.update_data(shop_item_name=msg.text.strip())
    await state.set_state(ShoppingForm.item_unit)
    await msg.answer("📏 Ölçü vahidi (məs: kisə, m², ədəd, litr, m):")


@router.message(ShoppingForm.item_unit)
async def shopping_item_unit(msg: Message, state: FSMContext):
    await state.update_data(shop_item_unit=msg.text.strip())
    await state.set_state(ShoppingForm.item_qty)
    await msg.answer("🔢 Miqdar:")


@router.message(ShoppingForm.item_qty)
async def shopping_item_qty(msg: Message, state: FSMContext):
    try:
        qty = float(msg.text.replace(",", "."))
        await state.update_data(shop_item_qty=qty)
        await state.set_state(ShoppingForm.item_priority)
        await msg.answer("⚡ Prioritet seçin:", reply_markup=priority_kb())
    except ValueError:
        await msg.answer("⚠️ Düzgün rəqəm daxil edin")


@router.callback_query(F.data.startswith("shopri_"), ShoppingForm.item_priority)
async def shopping_item_priority(cq: CallbackQuery, state: FSMContext):
    priority = cq.data[7:]
    data = await state.get_data()

    await add_shopping_item(
        smeta_number=data["smeta_number"],
        item_name=data["shop_item_name"],
        unit=data["shop_item_unit"],
        qty=data["shop_item_qty"],
        priority=priority,
    )

    await state.set_state(ShoppingForm.action)
    label = PRIORITY_LABELS.get(priority, priority)
    await cq.message.edit_text(
        f"✅ *{data['shop_item_name']}* əlavə edildi!\n"
        f"📦 {data['shop_item_qty']} {data['shop_item_unit']} — {label}",
        parse_mode="Markdown",
        reply_markup=shopping_action_kb(data["smeta_number"])
    )
    await cq.answer("✅ Əlavə edildi!")


@router.callback_query(F.data.startswith("shop_mark_"), ShoppingForm.action)
async def shopping_mark_start(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[10:]
    items = await get_shopping_list(smeta_number)
    pending = [i for i in items if i["status"] == "pending"]

    if not pending:
        await cq.answer("Alınacaq material yoxdur!", show_alert=True)
        return

    await state.update_data(smeta_number=smeta_number)
    await state.set_state(ShoppingForm.mark_item)
    await cq.message.edit_text(
        "✅ Hansı material alındı?",
        reply_markup=pending_items_kb(pending)
    )
    await cq.answer()


@router.callback_query(F.data.startswith("shopmark_"), ShoppingForm.mark_item)
async def shopping_mark_item(cq: CallbackQuery, state: FSMContext):
    item_id = int(cq.data[9:])
    await state.update_data(mark_item_id=item_id)
    await state.set_state(ShoppingForm.mark_price)
    await cq.message.answer("💰 Ödənilən məbləğ (AZN) — /skip:")
    await cq.answer()


@router.message(ShoppingForm.mark_price)
@router.message(Command("skip"), ShoppingForm.mark_price)
async def shopping_mark_price(msg: Message, state: FSMContext):
    price = 0.0
    if msg.text != "/skip":
        try:
            price = float(msg.text.replace(",", ".").replace(" ", ""))
        except ValueError:
            await msg.answer("⚠️ Düzgün rəqəm — /skip to skip")
            return

    data = await state.get_data()
    await update_shopping_item(data["mark_item_id"], "bought", price)

    await state.set_state(ShoppingForm.action)
    price_txt = f" — {price:,.2f} {CURRENCY}" if price else ""
    await msg.answer(
        f"✅ *Material alındı qeyd edildi!*{price_txt}",
        parse_mode="Markdown",
        reply_markup=shopping_action_kb(data["smeta_number"])
    )


# ── Layihə başlatma ───────────────────────────────────────────────────────────

@router.message(Command("start_project"))
async def cmd_start_project(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ Bu komanda yalnız adminlər üçündür.")
        return

    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer("❌ Smeta nömrəsi yazın: /start_project SM-2026-0001")
        return

    smeta_number = parts[1].upper()
    smeta = await get_smeta_by_number(smeta_number)
    if not smeta:
        await msg.answer(f"❌ *{smeta_number}* tapılmadı.", parse_mode="Markdown")
        return

    await update_smeta_status(smeta["id"], "active")

    # Auto shopping list
    for priority, items in SHOPPING_TEMPLATE.items():
        for name, unit, qty in items:
            if qty > 0:
                await add_shopping_item(smeta_number, name, unit, qty, priority)

    # Auto reminder — 14 days
    remind_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
    await add_reminder(
        smeta_number,
        f"⚠️ {smeta_number} — layihə 2 həftədir başladı! Gedişatı yoxlayın.",
        remind_date,
        msg.from_user.id,
    )

    WEB_URL = os.getenv("WEB_URL", "https://smeta-bot-production.up.railway.app")
    link = f"{WEB_URL}/smeta/{smeta_number}"

    await msg.answer(
        f"▶️ *Layihə başladıldı!*\n\n"
        f"📋 Smeta: *{smeta_number}*\n"
        f"👤 Müştəri: {smeta['client_name']}\n"
        f"📍 {smeta['address']}\n"
        f"💰 {smeta['total']:,.2f} {CURRENCY}\n\n"
        f"🛒 Alış siyahısı avtomatik yaradıldı (/shopping)\n"
        f"👷 /assign ilə işçilər təyin edin\n\n"
        f"🔗 {link}",
        parse_mode="Markdown"
    )
