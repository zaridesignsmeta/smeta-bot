"""
Ödəniş İzləmə — Feature 1
"""

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, CURRENCY
from database import (
    get_user_smeta_numbers, get_smeta_by_number,
    add_payment, get_payments, get_total_paid,
    get_all_smetas_admin,
)

router = Router()

PAYMENT_TYPES = {
    "advance": "💰 Avans",
    "interim": "💵 Ara ödəniş",
    "final":   "✅ Son ödəniş",
}


class PaymentForm(StatesGroup):
    smeta_select    = State()
    amount          = State()
    payment_type    = State()
    material_amount = State()
    labor_amount    = State()
    other_amount    = State()
    notes           = State()
    confirm         = State()


def payment_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Avans",       callback_data="ptype_advance")],
        [InlineKeyboardButton(text="💵 Ara ödəniş",  callback_data="ptype_interim")],
        [InlineKeyboardButton(text="✅ Son ödəniş",  callback_data="ptype_final")],
    ])


def smeta_select_kb(smetas: list, prefix: str = "pay_smeta_") -> InlineKeyboardMarkup:
    buttons = []
    for s in smetas:
        buttons.append([InlineKeyboardButton(
            text=f"📋 {s['smeta_number']} — {s['client_name']}",
            callback_data=f"{prefix}{s['smeta_number']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("payment"))
async def cmd_payment(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ Bu komanda yalnız adminlər üçündür.")
        return
    await state.clear()
    smetas = await get_all_smetas_admin()
    if not smetas:
        await msg.answer("📂 Hələ smeta yoxdur.")
        return
    await state.set_state(PaymentForm.smeta_select)
    await msg.answer(
        "💳 *Ödəniş Əlavə Et*\n\nHansı smetaya ödəniş əlavə edilsin?",
        parse_mode="Markdown",
        reply_markup=smeta_select_kb(smetas)
    )


@router.callback_query(F.data.startswith("pay_smeta_"), PaymentForm.smeta_select)
async def payment_smeta_selected(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[10:]
    smeta = await get_smeta_by_number(smeta_number)
    if not smeta:
        await cq.answer("Smeta tapılmadı", show_alert=True)
        return

    total_paid = await get_total_paid(smeta_number)
    remaining = smeta["total"] - total_paid

    await state.update_data(
        smeta_number=smeta_number,
        smeta_total=smeta["total"],
        total_paid=total_paid,
    )
    await state.set_state(PaymentForm.amount)
    await cq.message.edit_text(
        f"📋 *{smeta_number}* — {smeta['client_name']}\n\n"
        f"💰 Ümumi: `{smeta['total']:,.2f} {CURRENCY}`\n"
        f"✅ Ödənilib: `{total_paid:,.2f} {CURRENCY}`\n"
        f"⏳ Qalıq: `{remaining:,.2f} {CURRENCY}`\n\n"
        f"💵 Ödəniş məbləğini daxil edin (AZN):",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.message(PaymentForm.amount)
async def payment_amount_entered(msg: Message, state: FSMContext):
    try:
        amount = float(msg.text.replace(",", ".").replace(" ", ""))
        if amount <= 0:
            raise ValueError
        await state.update_data(amount=amount)
        await state.set_state(PaymentForm.payment_type)
        await msg.answer(
            f"✅ *{amount:,.2f} {CURRENCY}*\n\nÖdəniş növünü seçin:",
            parse_mode="Markdown",
            reply_markup=payment_type_kb()
        )
    except ValueError:
        await msg.answer("⚠️ Düzgün məbləğ daxil edin (məs: 2500)")


@router.callback_query(F.data.startswith("ptype_"), PaymentForm.payment_type)
async def payment_type_selected(cq: CallbackQuery, state: FSMContext):
    ptype = cq.data[6:]
    ptype_name = PAYMENT_TYPES.get(ptype, ptype)
    await state.update_data(payment_type=ptype, payment_type_name=ptype_name)
    await state.set_state(PaymentForm.material_amount)
    data = await state.get_data()
    await cq.message.edit_text(
        f"✅ *{ptype_name}* seçildi.\n\n"
        f"Məbləğin bölgüsü (toplam: *{data['amount']:,.2f} {CURRENCY}*):\n\n"
        f"📦 Material üçün neçə AZN? _(Yoxdursa 0 yazın)_",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.message(PaymentForm.material_amount)
async def payment_material_amount(msg: Message, state: FSMContext):
    try:
        mat_amt = float(msg.text.replace(",", ".").replace(" ", ""))
        if mat_amt < 0:
            raise ValueError
        await state.update_data(material_amount=mat_amt)
        await state.set_state(PaymentForm.labor_amount)
        await msg.answer("👷 İşçilik üçün neçə AZN? _(Yoxdursa 0 yazın)_",
                         parse_mode="Markdown")
    except ValueError:
        await msg.answer("⚠️ Düzgün rəqəm daxil edin")


@router.message(PaymentForm.labor_amount)
async def payment_labor_amount(msg: Message, state: FSMContext):
    try:
        labor_amt = float(msg.text.replace(",", ".").replace(" ", ""))
        if labor_amt < 0:
            raise ValueError
        await state.update_data(labor_amount=labor_amt)
        await state.set_state(PaymentForm.other_amount)
        await msg.answer("📋 Digər xərclər neçə AZN? _(Yoxdursa 0 yazın)_",
                         parse_mode="Markdown")
    except ValueError:
        await msg.answer("⚠️ Düzgün rəqəm daxil edin")


@router.message(PaymentForm.other_amount)
async def payment_other_amount(msg: Message, state: FSMContext):
    try:
        other_amt = float(msg.text.replace(",", ".").replace(" ", ""))
        if other_amt < 0:
            raise ValueError
        await state.update_data(other_amount=other_amt)
        await state.set_state(PaymentForm.notes)
        await msg.answer("📝 Qeyd yazın (istəyə görə) — /skip:")
    except ValueError:
        await msg.answer("⚠️ Düzgün rəqəm daxil edin")


@router.message(PaymentForm.notes)
@router.message(Command("skip"), PaymentForm.notes)
async def payment_notes(msg: Message, state: FSMContext):
    notes = "" if msg.text == "/skip" else msg.text.strip()
    data = await state.get_data()

    mat = data.get("material_amount", 0)
    lab = data.get("labor_amount", 0)
    oth = data.get("other_amount", 0)

    await state.update_data(notes=notes)
    await state.set_state(PaymentForm.confirm)

    note_line = f"📝 Qeyd: {notes}\n" if notes else ""
    await msg.answer(
        f"✅ *Ödəniş Təsdiqi*\n\n"
        f"📋 Smeta: *{data['smeta_number']}*\n"
        f"💰 Məbləğ: *{data['amount']:,.2f} {CURRENCY}*\n"
        f"📌 Növ: {data['payment_type_name']}\n"
        f"├─ 📦 Material: {mat:,.2f} {CURRENCY}\n"
        f"├─ 👷 İşçilik: {lab:,.2f} {CURRENCY}\n"
        f"└─ 📋 Digər: {oth:,.2f} {CURRENCY}\n"
        f"{note_line}\n"
        f"Təsdiqləyirsiniz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Bəli, saxla", callback_data="pay_confirm"),
            InlineKeyboardButton(text="❌ Ləğv et",    callback_data="pay_cancel"),
        ]])
    )


@router.callback_query(F.data == "pay_confirm", PaymentForm.confirm)
async def payment_confirmed(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await add_payment(
        smeta_number=data["smeta_number"],
        amount=data["amount"],
        payment_type=data["payment_type"],
        material_amount=data.get("material_amount", 0),
        labor_amount=data.get("labor_amount", 0),
        other_amount=data.get("other_amount", 0),
        notes=data.get("notes", ""),
        created_by=cq.from_user.id,
    )

    total_paid = await get_total_paid(data["smeta_number"])
    remaining = data["smeta_total"] - total_paid

    await state.clear()
    await cq.message.edit_text(
        f"✅ *Ödəniş əlavə edildi!*\n\n"
        f"📋 Smeta: *{data['smeta_number']}*\n"
        f"💰 Bu ödəniş: *{data['amount']:,.2f} {CURRENCY}*\n"
        f"✅ Ümumi ödənilib: *{total_paid:,.2f} {CURRENCY}*\n"
        f"⏳ Qalıq: *{remaining:,.2f} {CURRENCY}*",
        parse_mode="Markdown"
    )
    await cq.answer("✅ Ödəniş saxlandı!")


@router.callback_query(F.data == "pay_cancel")
async def payment_cancelled(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    await cq.message.edit_text("❌ Ödəniş ləğv edildi.")
    await cq.answer()
