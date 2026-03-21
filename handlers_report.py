"""
Aylıq Hesabat və Müqavilə Generatoru — Feature 5 & 6
"""

from aiogram import Router
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from datetime import datetime

from config import ADMIN_IDS, CURRENCY
from database import (
    get_monthly_report, get_all_smetas_for_report,
    get_smeta_by_number,
)

router = Router()

MONTH_NAMES_AZ = {
    "01": "Yanvar",  "02": "Fevral",  "03": "Mart",
    "04": "Aprel",   "05": "May",     "06": "İyun",
    "07": "İyul",    "08": "Avqust",  "09": "Sentyabr",
    "10": "Oktyabr", "11": "Noyabr",  "12": "Dekabr",
}


@router.message(Command("report"))
async def cmd_report(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ Bu komanda yalnız adminlər üçündür.")
        return

    parts = msg.text.split()
    if len(parts) >= 2:
        month = parts[1]
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            await msg.answer("⚠️ Format: /report 2026-03")
            return
    else:
        month = datetime.now().strftime("%Y-%m")

    await msg.answer("📊 Hesabat hazırlanır...")

    report = await get_monthly_report(month)
    smetas = await get_all_smetas_for_report(month)

    year, mon = month.split("-")
    month_name = MONTH_NAMES_AZ.get(mon, mon)

    profit_sign = "+" if report["profit"] >= 0 else ""
    text = (
        f"📊 *{month_name} {year} Hesabatı*\n\n"
        f"├── 📋 Yeni smetalar: *{report['new_smetas']}*\n"
        f"├── ✅ Tamamlanan: *{report['completed']}*\n"
        f"├── 🏗️ Aktiv layihələr: *{report['active']}*\n"
        f"├── 💰 Ümumi smeta dəyəri: *{report['total_value']:,.2f} {CURRENCY}*\n"
        f"├── ✅ Alınan ödənişlər: *{report['received_payments']:,.2f} {CURRENCY}*\n"
        f"├── ⏳ Gözlənilən ödənişlər: *{report['expected_payments']:,.2f} {CURRENCY}*\n"
        f"├── 📦 Material xərcləri: *{report['material_costs']:,.2f} {CURRENCY}*\n"
        f"└── 💹 Mənfəət (təxmini): *{profit_sign}{report['profit']:,.2f} {CURRENCY}*"
    )
    await msg.answer(text, parse_mode="Markdown")

    # Excel hesabat
    try:
        from generators import generate_monthly_excel
        excel_path = generate_monthly_excel(report, smetas, month)
        file = FSInputFile(excel_path)
        await msg.answer_document(
            file,
            caption=f"📊 {month_name} {year} — Excel Hesabat"
        )
    except Exception as e:
        await msg.answer(f"⚠️ Excel yaradılarkən xəta: {e}")


@router.message(Command("contract"))
async def cmd_contract(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("⛔ Bu komanda yalnız adminlər üçündür.")
        return

    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer("❌ Smeta nömrəsi yazın: /contract SM-2026-0001")
        return

    smeta_number = parts[1].upper()
    smeta = await get_smeta_by_number(smeta_number)
    if not smeta:
        await msg.answer(f"❌ *{smeta_number}* tapılmadı.", parse_mode="Markdown")
        return

    await msg.answer("📄 Müqavilə hazırlanır...")

    try:
        from generators import generate_contract_pdf
        pdf_path = generate_contract_pdf(smeta)
        file = FSInputFile(pdf_path)
        await msg.answer_document(
            file,
            caption=f"📄 *{smeta_number}* — Müqavilə\n👤 {smeta['client_name']}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await msg.answer(f"⚠️ Müqavilə yaradılarkən xəta: {e}")
