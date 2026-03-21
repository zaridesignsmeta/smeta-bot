"""
İşçi İdarəetmə — Feature 2
"""

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, date

from config import ADMIN_IDS, CURRENCY
from database import (
    add_worker, get_workers, get_worker,
    assign_worker, get_worker_assignments,
    add_worker_payment,
    get_all_smetas_admin,
)

router = Router()

WORKER_ROLES = ["Usta", "Köməkçi", "Elektrikçi", "Santexnik", "Rəssam"]


class AddWorkerForm(StatesGroup):
    name       = State()
    phone      = State()
    role       = State()
    daily_rate = State()


class AssignWorkerForm(StatesGroup):
    smeta_select  = State()
    worker_select = State()
    start_date    = State()
    end_date      = State()


class WorkerPayForm(StatesGroup):
    worker_select = State()
    smeta_select  = State()
    amount        = State()
    notes         = State()


def workers_kb(workers: list, prefix: str = "sel_worker_") -> InlineKeyboardMarkup:
    buttons = []
    for w in workers:
        buttons.append([InlineKeyboardButton(
            text=f"👷 {w['name']} — {w['role']}",
            callback_data=f"{prefix}{w['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def roles_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👷 {role}", callback_data=f"role_{role}")]
        for role in WORKER_ROLES
    ])


def smeta_select_kb(smetas: list, prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    for s in smetas:
        buttons.append([InlineKeyboardButton(
            text=f"📋 {s['smeta_number']} — {s['client_name']}",
            callback_data=f"{prefix}{s['smeta_number']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Yeni işçi əlavə et ────────────────────────────────────────────────────────

@router.message(Command("addworker"))
async def cmd_addworker(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ Bu komanda yalnız adminlər üçündür.")
        return
    await state.clear()
    await state.set_state(AddWorkerForm.name)
    await msg.answer(
        "👷 *Yeni İşçi*\n\nİşçinin adını daxil edin:",
        parse_mode="Markdown"
    )


@router.message(AddWorkerForm.name)
async def worker_name_entered(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await state.set_state(AddWorkerForm.phone)
    await msg.answer("📞 Telefon nömrəsi (+994...):")


@router.message(AddWorkerForm.phone)
async def worker_phone_entered(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text.strip())
    await state.set_state(AddWorkerForm.role)
    await msg.answer("👷 Vəzifəni seçin:", reply_markup=roles_kb())


@router.callback_query(F.data.startswith("role_"), AddWorkerForm.role)
async def worker_role_selected(cq: CallbackQuery, state: FSMContext):
    role = cq.data[5:]
    await state.update_data(role=role)
    await state.set_state(AddWorkerForm.daily_rate)
    await cq.message.edit_text(
        f"✅ *{role}* seçildi.\n\n💰 Günlük qiymət (AZN):",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.message(AddWorkerForm.daily_rate)
async def worker_daily_rate_entered(msg: Message, state: FSMContext):
    try:
        rate = float(msg.text.replace(",", "."))
        if rate < 0:
            raise ValueError
        data = await state.get_data()
        wid = await add_worker(
            telegram_id=0,
            name=data["name"],
            phone=data["phone"],
            role=data["role"],
            daily_rate=rate,
        )
        await state.clear()
        await msg.answer(
            f"✅ *İşçi əlavə edildi!*\n\n"
            f"👷 {data['name']}\n"
            f"📞 {data['phone']}\n"
            f"🔧 {data['role']}\n"
            f"💰 {rate:,.0f} AZN/gün\n"
            f"🆔 ID: {wid}",
            parse_mode="Markdown"
        )
    except ValueError:
        await msg.answer("⚠️ Düzgün rəqəm daxil edin")


# ── İşçiləri göstər ───────────────────────────────────────────────────────────

@router.message(Command("workers"))
async def cmd_workers(msg: Message):
    workers = await get_workers()
    if not workers:
        await msg.answer(
            "👷 Hələ işçi əlavə edilməyib.\n"
            "/addworker ilə əlavə edin."
        )
        return

    lines = ["👷 *İşçilər siyahısı*\n"]
    for w in workers:
        assignments = await get_worker_assignments(worker_id=w["id"])
        today = date.today().isoformat()
        active_smetas = [
            a["smeta_number"] for a in assignments
            if not a.get("end_date") or a["end_date"] >= today
        ]
        status = f"📌 {', '.join(active_smetas[:2])}" if active_smetas else "🟢 Boş"
        lines.append(
            f"• *{w['name']}* — {w['role']}\n"
            f"  📞 {w['phone']} | 💰 {w['daily_rate']:,.0f} AZN/gün\n"
            f"  {status}"
        )

    await msg.answer("\n".join(lines), parse_mode="Markdown")


# ── İşçi təyin et ─────────────────────────────────────────────────────────────

@router.message(Command("assign"))
async def cmd_assign(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ Bu komanda yalnız adminlər üçündür.")
        return
    await state.clear()
    smetas = await get_all_smetas_admin()
    if not smetas:
        await msg.answer("📂 Hələ smeta yoxdur.")
        return
    await state.set_state(AssignWorkerForm.smeta_select)
    await msg.answer(
        "👷 *İşçi Təyin Et*\n\nHansı smetaya işçi təyin edilsin?",
        parse_mode="Markdown",
        reply_markup=smeta_select_kb(smetas, "asgn_smeta_")
    )


@router.callback_query(F.data.startswith("asgn_smeta_"), AssignWorkerForm.smeta_select)
async def assign_smeta_selected(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[11:]
    workers = await get_workers()
    if not workers:
        await cq.answer("İşçi yoxdur! /addworker ilə əlavə edin.", show_alert=True)
        return
    await state.update_data(smeta_number=smeta_number)
    await state.set_state(AssignWorkerForm.worker_select)
    await cq.message.edit_text(
        f"📋 *{smeta_number}*\n\nHansı işçini təyin edirsiniz?",
        parse_mode="Markdown",
        reply_markup=workers_kb(workers, "asgn_worker_")
    )
    await cq.answer()


@router.callback_query(F.data.startswith("asgn_worker_"), AssignWorkerForm.worker_select)
async def assign_worker_selected(cq: CallbackQuery, state: FSMContext):
    worker_id = int(cq.data[12:])
    worker = await get_worker(worker_id)
    await state.update_data(worker_id=worker_id, worker_name=worker["name"])
    await state.set_state(AssignWorkerForm.start_date)
    await cq.message.edit_text(
        f"✅ *{worker['name']}* seçildi.\n\n"
        f"📅 Başlama tarixi (YYYY-MM-DD):",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.message(AssignWorkerForm.start_date)
async def assign_start_date(msg: Message, state: FSMContext):
    date_str = msg.text.strip()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        await msg.answer("⚠️ Format: YYYY-MM-DD (məs: 2026-03-25)")
        return
    await state.update_data(start_date=date_str)
    await state.set_state(AssignWorkerForm.end_date)
    await msg.answer("📅 Bitmə tarixi (YYYY-MM-DD) — /skip:")


@router.message(AssignWorkerForm.end_date)
@router.message(Command("skip"), AssignWorkerForm.end_date)
async def assign_end_date(msg: Message, state: FSMContext):
    end_date = "" if msg.text == "/skip" else msg.text.strip()
    if end_date:
        try:
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            await msg.answer("⚠️ Format: YYYY-MM-DD — ya da /skip")
            return
    data = await state.get_data()
    await assign_worker(
        smeta_number=data["smeta_number"],
        worker_id=data["worker_id"],
        start_date=data["start_date"],
        end_date=end_date,
    )
    await state.clear()
    end_line = f"\n📅 Bitmə: {end_date}" if end_date else ""
    await msg.answer(
        f"✅ *{data['worker_name']}* → *{data['smeta_number']}* təyin edildi!\n"
        f"📅 Başlama: {data['start_date']}{end_line}",
        parse_mode="Markdown"
    )


# ── İşçiyə ödəniş et ──────────────────────────────────────────────────────────

@router.message(Command("workerpay"))
async def cmd_workerpay(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ Bu komanda yalnız adminlər üçündür.")
        return
    workers = await get_workers()
    if not workers:
        await msg.answer("👷 Hələ işçi yoxdur.")
        return
    await state.clear()
    await state.set_state(WorkerPayForm.worker_select)
    await msg.answer(
        "💰 *İşçiyə Ödəniş*\n\nHansı işçiyə ödəniş edilsin?",
        parse_mode="Markdown",
        reply_markup=workers_kb(workers, "wpay_worker_")
    )


@router.callback_query(F.data.startswith("wpay_worker_"), WorkerPayForm.worker_select)
async def workerpay_worker_selected(cq: CallbackQuery, state: FSMContext):
    worker_id = int(cq.data[12:])
    worker = await get_worker(worker_id)
    await state.update_data(worker_id=worker_id, worker_name=worker["name"])
    smetas = await get_all_smetas_admin()
    await state.set_state(WorkerPayForm.smeta_select)
    await cq.message.edit_text(
        f"👷 *{worker['name']}*\n\nHansı smeta üçün ödəniş?",
        parse_mode="Markdown",
        reply_markup=smeta_select_kb(smetas, "wpay_smeta_")
    )
    await cq.answer()


@router.callback_query(F.data.startswith("wpay_smeta_"), WorkerPayForm.smeta_select)
async def workerpay_smeta_selected(cq: CallbackQuery, state: FSMContext):
    smeta_number = cq.data[11:]
    await state.update_data(smeta_number=smeta_number)
    await state.set_state(WorkerPayForm.amount)
    await cq.message.edit_text(
        f"📋 Smeta: *{smeta_number}*\n\n💵 Ödəniş məbləği (AZN):",
        parse_mode="Markdown"
    )
    await cq.answer()


@router.message(WorkerPayForm.amount)
async def workerpay_amount(msg: Message, state: FSMContext):
    try:
        amount = float(msg.text.replace(",", ".").replace(" ", ""))
        if amount <= 0:
            raise ValueError
        await state.update_data(amount=amount)
        await state.set_state(WorkerPayForm.notes)
        await msg.answer("📝 Qeyd yazın — /skip:")
    except ValueError:
        await msg.answer("⚠️ Düzgün məbləğ daxil edin")


@router.message(WorkerPayForm.notes)
@router.message(Command("skip"), WorkerPayForm.notes)
async def workerpay_notes(msg: Message, state: FSMContext):
    notes = "" if msg.text == "/skip" else msg.text.strip()
    data = await state.get_data()
    today = date.today().isoformat()

    await add_worker_payment(
        smeta_number=data["smeta_number"],
        worker_id=data["worker_id"],
        amount=data["amount"],
        date=today,
        notes=notes,
        created_by=msg.from_user.id,
    )
    await state.clear()
    await msg.answer(
        f"✅ *İşçi ödənişi qeyd edildi!*\n\n"
        f"👷 {data['worker_name']}\n"
        f"📋 {data['smeta_number']}\n"
        f"💰 {data['amount']:,.2f} {CURRENCY}\n"
        f"📅 {today}",
        parse_mode="Markdown"
    )
