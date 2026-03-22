"""
Material (Alış Siyahısı) Handlerlər
/shopping → smeta seç → siyahı → əlavə et / oldu işarələ
"""

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    get_user_smeta_numbers,
    add_material,
    get_materials,
    update_material_status,
)

router = Router()

STATUS_ICON = {"pending": "⬜", "bought": "✅", "delivered": "📦"}


# ── State-lər ─────────────────────────────────────────────────────────────────

class MaterialForm(StatesGroup):
    smeta_select = State()
    viewing      = State()
    adding       = State()


# ── Klaviaturalar ─────────────────────────────────────────────────────────────

def _smeta_kb(smetas: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"📋 {s['smeta_number']} — {s['client_name']}",
            callback_data=f"mat_smeta_{s['smeta_number']}"
        )]
        for s in smetas
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _list_kb(materials: list, smeta_number: str) -> InlineKeyboardMarkup:
    buttons = []
    for m in materials:
        icon = STATUS_ICON.get(m["status"], "⬜")
        label = f"{icon} {m['name']}"
        if m.get("unit"):
            label += f" — {m['qty_needed']} {m['unit']}"
        if m["status"] == "pending":
            buttons.append([InlineKeyboardButton(
                text=label,
                callback_data=f"mat_done_{m['id']}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=label,
                callback_data="mat_noop"
            )])

    buttons.append([
        InlineKeyboardButton(text="➕ Əlavə et", callback_data=f"mat_add_{smeta_number}"),
        InlineKeyboardButton(text="🔄 Yenilə",   callback_data=f"mat_refresh_{smeta_number}"),
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Çıx", callback_data="mat_exit"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _list_text(materials: list, smeta_number: str) -> str:
    if not materials:
        return (
            f"📦 *{smeta_number}* — Alış Siyahısı\n\n"
            "Hələ heç nə əlavə edilməyib.\n"
            "Aşağıdakı ➕ düyməsini basın."
        )

    pending  = [m for m in materials if m["status"] == "pending"]
    done     = [m for m in materials if m["status"] != "pending"]

    lines = [f"📦 *{smeta_number}* — Alış Siyahısı\n"]

    if pending:
        lines.append("*Alınacaqlar:*")
        for m in pending:
            qty = f" — {m['qty_needed']} {m['unit']}" if m.get("unit") else ""
            lines.append(f"⬜ {m['name']}{qty}")

    if done:
        lines.append("\n*Alındı:*")
        for m in done:
            qty = f" — {m['qty_needed']} {m['unit']}" if m.get("unit") else ""
            lines.append(f"✅ {m['name']}{qty}")

    lines.append(f"\n_⬜ düyməsinə bas → 'Oldu' işarələnir_")
    return "\n".join(lines)


# ── /shopping ─────────────────────────────────────────────────────────────────

@router.message(Command("shopping"))
async def cmd_shopping(msg: Message, state: FSMContext):
    await state.clear()
    smetas = await get_user_smeta_numbers(msg.from_user.id)
    if not smetas:
        await msg.answer("📂 Hələ smeta yoxdur.")
        return
    if len(smetas) == 1:
        # Yalnız bir smeta varsa birbaşa aç
        sn = smetas[0]["smeta_number"]
        materials = await get_materials(sn)
        await state.set_state(MaterialForm.viewing)
        await state.update_data(smeta_number=sn)
        await msg.answer(
            _list_text(materials, sn),
            parse_mode="Markdown",
            reply_markup=_list_kb(materials, sn),
        )
        return

    await state.set_state(MaterialForm.smeta_select)
    await msg.answer(
        "📦 *Alış Siyahısı*\n\nHansı smeta?",
        parse_mode="Markdown",
        reply_markup=_smeta_kb(smetas),
    )


@router.callback_query(F.data.startswith("mat_smeta_"), MaterialForm.smeta_select)
async def mat_smeta_selected(cq: CallbackQuery, state: FSMContext):
    sn = cq.data[10:]
    materials = await get_materials(sn)
    await state.set_state(MaterialForm.viewing)
    await state.update_data(smeta_number=sn)
    await cq.message.edit_text(
        _list_text(materials, sn),
        parse_mode="Markdown",
        reply_markup=_list_kb(materials, sn),
    )
    await cq.answer()


# ── "Oldu" işarələ ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("mat_done_"))
async def mat_mark_done(cq: CallbackQuery, state: FSMContext):
    mat_id = int(cq.data[9:])
    await update_material_status(mat_id, qty_bought=0, status="bought")
    data = await state.get_data()
    sn = data.get("smeta_number", "")
    materials = await get_materials(sn)
    await cq.message.edit_text(
        _list_text(materials, sn),
        parse_mode="Markdown",
        reply_markup=_list_kb(materials, sn),
    )
    await cq.answer("✅ Alındı!")


@router.callback_query(F.data == "mat_noop")
async def mat_noop(cq: CallbackQuery):
    await cq.answer()


# ── Yenilə ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("mat_refresh_"))
async def mat_refresh(cq: CallbackQuery, state: FSMContext):
    sn = cq.data[12:]
    materials = await get_materials(sn)
    await cq.message.edit_text(
        _list_text(materials, sn),
        parse_mode="Markdown",
        reply_markup=_list_kb(materials, sn),
    )
    await cq.answer("🔄 Yeniləndi")


# ── Əlavə et ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("mat_add_"))
async def mat_add_start(cq: CallbackQuery, state: FSMContext):
    sn = cq.data[8:]
    await state.update_data(smeta_number=sn)
    await state.set_state(MaterialForm.adding)
    await cq.message.answer(
        "✏️ Material adını yazın.\n\n"
        "Misal: `Sement`\n"
        "Miqdarla: `Sement 50 kisə`\n\n"
        "Bir neçə material — hər biri ayrı sətirdə.\n"
        "Bitirdikdə /done yazın.",
        parse_mode="Markdown",
    )
    await cq.answer()


@router.message(MaterialForm.adding, Command("done"))
async def mat_add_done(msg: Message, state: FSMContext):
    data = await state.get_data()
    sn = data.get("smeta_number", "")
    await state.set_state(MaterialForm.viewing)
    materials = await get_materials(sn)
    await msg.answer(
        _list_text(materials, sn),
        parse_mode="Markdown",
        reply_markup=_list_kb(materials, sn),
    )


@router.message(MaterialForm.adding, F.text)
async def mat_add_item(msg: Message, state: FSMContext):
    data = await state.get_data()
    sn = data.get("smeta_number", "")

    for line in msg.text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        name = parts[0]
        qty = 0.0
        unit = ""
        if len(parts) >= 2:
            try:
                qty = float(parts[1])
                unit = " ".join(parts[2:]) if len(parts) > 2 else "ədəd"
            except ValueError:
                name = line
        await add_material(sn, name, unit, qty, 0, msg.from_user.id)

    await msg.answer(
        "✅ Əlavə edildi. Daha yaza bilərsiniz və ya /done ilə bitirin."
    )


# ── Çıx ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "mat_exit")
async def mat_exit(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    await cq.message.edit_text("📦 Alış siyahısı bağlandı.")
    await cq.answer()
