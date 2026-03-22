"""
Smart Smeta - Claude AI ilə avtomatik smeta yaratma
İstifadəçi yalnız 7 sual cavablayır, AI hər şeyi hesablayır.
"""

import json
import logging
import os

import anthropic
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message, ReplyKeyboardRemove,
)

from config import ANTHROPIC_API_KEY, AI_MODEL, CURRENCY, DEFAULT_MARGIN, DEFAULT_DISCOUNT
from database import (
    generate_smeta_number, save_smeta,
    init_checklist_for_smeta,
)

logger = logging.getLogger(__name__)
router = Router()

# ── FSM ──────────────────────────────────────────────────────────────────────

class SmartSmetaForm(StatesGroup):
    client_info    = State()   # ad + telefon
    address        = State()
    room_config    = State()   # "3+1", "2+1" ...
    area_m2        = State()
    price_category = State()
    flooring       = State()   # keramika/laminat/parket m²
    special_rooms  = State()   # texniki/qaraj/server/camaşır/digər
    generating     = State()   # AI işləyir


# ── Klaviaturalar ─────────────────────────────────────────────────────────────

def _price_cat_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥈 250 AZN/m² — Standart", callback_data="ssp_250")],
        [InlineKeyboardButton(text="🥇 350 AZN/m² — Orta",     callback_data="ssp_350")],
        [InlineKeyboardButton(text="💎 500 AZN/m² — Premium",  callback_data="ssp_500")],
    ])


def _special_rooms_kb(selected: list) -> InlineKeyboardMarkup:
    options = [
        ("🔧 Texniki otaq",  "texniki"),
        ("🚗 Qaraj",          "qaraj"),
        ("🖥️ Server otağı",  "server"),
        ("🧺 Camaşırxana",   "camasir"),
        ("📦 Digər",          "diger"),
    ]
    rows = []
    for label, key in options:
        check = "✅ " if key in selected else ""
        rows.append([InlineKeyboardButton(
            text=f"{check}{label}", callback_data=f"sspr_{key}"
        )])
    rows.append([InlineKeyboardButton(text="▶️ Davam et", callback_data="sspr_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Smeta yaratma flow-u ──────────────────────────────────────────────────────

@router.message(F.text == "📋 Yeni Smeta")
@router.message(Command("newsmeta"))
async def smart_smeta_start(msg: Message, state: FSMContext):
    await state.clear()
    await state.update_data(
        telegram_id=msg.from_user.id,
        selected_special=[],
    )
    await state.set_state(SmartSmetaForm.client_info)
    await msg.answer(
        "🤖 *Smart Smeta* — AI ilə avtomatik hesablama\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ Müştərinin *adı və telefonu* nədir?\n\n"
        "_Məs: Əli Həsənov, +994501234567_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(SmartSmetaForm.client_info)
async def ss_client_info(msg: Message, state: FSMContext):
    text = msg.text.strip()
    # Ad + telefon bir xəttdə: "Əli Həsənov, +994501234567"
    if "," in text:
        parts = text.split(",", 1)
        name  = parts[0].strip()
        phone = parts[1].strip()
    else:
        name  = text
        phone = ""
    await state.update_data(client_name=name, client_phone=phone)

    if not phone:
        # Telefon ayrıca soruş
        await state.set_state(SmartSmetaForm.address)   # skip phone step
        await msg.answer(
            "📞 Telefon nömrəsini daxil edin _(ya da /skip)_:",
            parse_mode="Markdown",
        )
        # Actually ask for phone first
        await state.set_state(SmartSmetaForm.client_info)
        await state.update_data(_waiting_phone=True)
        await msg.answer(
            "📞 Telefon nömrəsini daxil edin:",
        )
        return

    await state.set_state(SmartSmetaForm.address)
    await msg.answer(
        "2️⃣ Obyektin *ünvanı* nədir?\n\n"
        "_Məs: Neftçilər pr. 123, Bakı_",
        parse_mode="Markdown",
    )


@router.message(SmartSmetaForm.client_info)
async def ss_phone(msg: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("_waiting_phone"):
        phone = msg.text.strip()
        if phone == "/skip":
            phone = ""
        await state.update_data(client_phone=phone, _waiting_phone=False)
        await state.set_state(SmartSmetaForm.address)
        await msg.answer(
            "2️⃣ Obyektin *ünvanı* nədir?\n\n"
            "_Məs: Neftçilər pr. 123, Bakı_",
            parse_mode="Markdown",
        )


@router.message(SmartSmetaForm.address)
async def ss_address(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text.strip())
    await state.set_state(SmartSmetaForm.room_config)
    await msg.answer(
        "3️⃣ *Neçə otaqlıdır?*\n\n"
        "Format: `yataq+qonaq` — yataq otaqları + qonaq + mətbəx + hamamlar\n\n"
        "Nümunələr:\n"
        "• `3+1` — 3 yataq, 1 qonaq, mətbəx, 2 hamam\n"
        "• `2+1` — 2 yataq, 1 qonaq, mətbəx, 1 hamam\n"
        "• `1+1` — 1 yataq, 1 qonaq, mətbəx, 1 hamam\n"
        "• `studio` — studiya tip mənzil\n"
        "• `5 otaq villa` — fərdi təsvir",
        parse_mode="Markdown",
    )


@router.message(SmartSmetaForm.room_config)
async def ss_room_config(msg: Message, state: FSMContext):
    await state.update_data(room_config=msg.text.strip())
    await state.set_state(SmartSmetaForm.area_m2)
    await msg.answer(
        "4️⃣ *Ümumi sahə* neçə m²-dir?\n\n"
        "_Məs: 85 və ya 120.5_",
        parse_mode="Markdown",
    )


@router.message(SmartSmetaForm.area_m2)
async def ss_area(msg: Message, state: FSMContext):
    try:
        area = float(msg.text.replace(",", ".").strip())
        if area <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("⚠️ Düzgün rəqəm daxil edin. Məs: `85` və ya `120.5`",
                         parse_mode="Markdown")
        return
    await state.update_data(area_m2=area)
    await state.set_state(SmartSmetaForm.price_category)
    await msg.answer(
        "5️⃣ *Qiymət kateqoriyası* seçin:",
        parse_mode="Markdown",
        reply_markup=_price_cat_kb(),
    )


@router.callback_query(F.data.startswith("ssp_"), SmartSmetaForm.price_category)
async def ss_price_selected(cq: CallbackQuery, state: FSMContext):
    price_per_m2 = int(cq.data[4:])
    cat_names = {250: "Standart", 350: "Orta", 500: "Premium"}
    await state.update_data(
        price_per_m2=price_per_m2,
        price_category=str(price_per_m2),
        price_category_name=cat_names[price_per_m2],
    )
    await state.set_state(SmartSmetaForm.flooring)
    await cq.message.edit_text(
        f"✅ *{price_per_m2} AZN/m²* seçildi.\n\n"
        "6️⃣ *Döşəmə* haqqında məlumat verin:\n\n"
        "Format: `keramika_m2 / laminat_m2 / parket_m2`\n\n"
        "Nümunə:\n"
        "• `30 / 45 / 0` — 30m² keramika, 45m² laminat, 0m² parket\n"
        "• `20 / 0 / 60` — 20m² keramika, 0m² laminat, 60m² parket\n"
        "• `yoxdur` — döşəmə məlumatı yoxdur",
        parse_mode="Markdown",
    )
    await cq.answer()


@router.message(SmartSmetaForm.flooring)
async def ss_flooring(msg: Message, state: FSMContext):
    text = msg.text.strip()
    if text.lower() in ("yoxdur", "yox", "/skip"):
        flooring = {"keramika": 0, "laminat": 0, "parket": 0}
    else:
        parts = [p.strip() for p in text.replace(",", "/").split("/")]
        try:
            flooring = {
                "keramika": float(parts[0]) if len(parts) > 0 else 0,
                "laminat":  float(parts[1]) if len(parts) > 1 else 0,
                "parket":   float(parts[2]) if len(parts) > 2 else 0,
            }
        except (ValueError, IndexError):
            await msg.answer(
                "⚠️ Format: `30 / 45 / 0`  (keramika / laminat / parket)\n"
                "Yoxdursa `yoxdur` yazın.",
                parse_mode="Markdown",
            )
            return
    await state.update_data(flooring_data=flooring)
    await state.set_state(SmartSmetaForm.special_rooms)
    await msg.answer(
        "7️⃣ *Xüsusi otaqlar* var?\n\n"
        "İstədiklərinizi seçin (birindən çox ola bilər), sonra ▶️ *Davam et* basın:",
        parse_mode="Markdown",
        reply_markup=_special_rooms_kb([]),
    )


@router.callback_query(F.data.startswith("sspr_"), SmartSmetaForm.special_rooms)
async def ss_special_toggle(cq: CallbackQuery, state: FSMContext):
    key = cq.data[5:]
    if key == "done":
        await _start_ai_generation(cq.message, state)
        await cq.answer()
        return
    data = await state.get_data()
    selected = list(data.get("selected_special", []))
    if key in selected:
        selected.remove(key)
    else:
        selected.append(key)
    await state.update_data(selected_special=selected)
    await cq.message.edit_reply_markup(reply_markup=_special_rooms_kb(selected))
    await cq.answer()


# ── AI hesablama ──────────────────────────────────────────────────────────────

async def _start_ai_generation(msg: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(SmartSmetaForm.generating)
    await msg.answer(
        "🤖 *Claude AI smeta hesablayır...*\n\n"
        "⏳ Bir neçə saniyə gözləyin.",
        parse_mode="Markdown",
    )

    special_names = {
        "texniki": "Texniki otaq",
        "qaraj":   "Qaraj",
        "server":  "Server otağı",
        "camasir": "Camaşırxana",
        "diger":   "Digər xüsusi otaq",
    }
    special_list = [special_names[k] for k in data.get("selected_special", []) if k in special_names]
    flooring = data.get("flooring_data", {})

    prompt = f"""Sən tikinti şirkəti üçün smeta hesablayan AI assistantsın. Azərbaycan dili ilə cavab ver.

Müştəri məlumatları:
- Ad: {data.get('client_name')}
- Ünvan: {data.get('address')}
- Otaq konfiqurasiyası: {data.get('room_config')} (məs: 3+1 = 3 yataq + 1 qonaq otağı + mətbəx + 2 hamam)
- Ümumi sahə: {data.get('area_m2')} m²
- Qiymət kateqoriyası: {data.get('price_per_m2')} AZN/m² ({data.get('price_category_name')})
- Döşəmə: keramika {flooring.get('keramika',0)} m², laminat {flooring.get('laminat',0)} m², parket {flooring.get('parket',0)} m²
- Xüsusi otaqlar: {', '.join(special_list) if special_list else 'yoxdur'}

Vəzifən: Bu məlumatlara əsasən tam bir tikinti smetası üçün rooms_data strukturunu yarat.

Qaydalar:
1. Otaq konfiqurasiyasından real otaq siyahısı çıxar:
   - "3+1" = ["Yataq otağı 1", "Yataq otağı 2", "Yataq otağı 3", "Qonaq otağı", "Mətbəx", "Hamam 1", "Hamam 2", "Koridor"]
   - "2+1" = ["Yataq otağı 1", "Yataq otağı 2", "Qonaq otağı", "Mətbəx", "Hamam", "Koridor"]
   - "1+1" = ["Yataq otağı", "Qonaq otağı", "Mətbəx", "Hamam", "Koridor"]
   - "studio" = ["Yaşayış sahəsi", "Mətbəx/Yemək", "Hamam", "Koridor"]
2. Hər otaq üçün {data.get('price_per_m2')} AZN/m² kateqoriyasına uyğun işlər əlavə et
3. Sahəni otaqlar arasında məntiqi böl (ümumi sahə: {data.get('area_m2')} m²)
4. Döşəmə məlumatından istifadə et: keramika hamamlara/mətbəxə, laminat/parket qonaq+yataq otaqlarına
5. Xüsusi otaqlar əlavə et: {special_list}
6. Qiymətlər {data.get('price_per_m2')} AZN/m² standartına uyğun olsun

JSON formatında cavab ver (başqa heç nə yazma):
{{
  "rooms_data": {{
    "Otaq adı": {{
      "Kateqoriya adı": [
        {{"name": "İş adı", "unit": "m²", "qty": 0.0, "price": 0.0}}
      ]
    }}
  }},
  "room_list": ["otaq1", "otaq2"],
  "bathroom_list": ["Hamam 1", "Hamam 2"],
  "total_labor": 0.0,
  "summary": "qısa izah"
}}

Kateqoriyalar (Azərbaycanca): "🔨 Sökülüb-yığılma işləri", "🏗️ Divar işləri", "🏠 Tavan işləri", "🪵 Döşəmə işləri", "🚰 Santexnika işləri", "⚡ Elektrik işləri", "🚪 Qapı / Pəncərə işləri"

Hər otaq üçün ən azı 3-4 kateqoriya, hər kateqoriyada 2-5 iş növü olsun. qty sahəsi otağın hesablanmış sahəsinə görə dol. Qiymətlər {data.get('price_per_m2')} AZN/m² əsasına görə hesabla."""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        with client.messages.stream(
            model=AI_MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            response = stream.get_final_message()

        text = next((b.text for b in response.content if b.type == "text"), "")

        # JSON çıxar
        text = text.strip()
        if "```json" in text:
            text = text[text.index("```json") + 7:]
            text = text[:text.index("```")]
        elif "```" in text:
            text = text[text.index("```") + 3:]
            text = text[:text.index("```")]
        text = text.strip()

        ai_result = json.loads(text)
        rooms_data   = ai_result.get("rooms_data", {})
        room_list    = ai_result.get("room_list", list(rooms_data.keys()))
        bathroom_list = ai_result.get("bathroom_list", [r for r in room_list if "hamam" in r.lower() or "Hamam" in r])
        total_labor  = ai_result.get("total_labor", 0)
        summary      = ai_result.get("summary", "")

        # Həmçinin xüsusi otaqları rooms_data-ya əlavə et
        for sp in special_list:
            if sp not in rooms_data:
                rooms_data[sp] = {
                    "⚡ Elektrik işləri": [
                        {"name": "Elektrik xətti", "unit": "m", "qty": 10, "price": round(8 * data.get('price_per_m2', 250)/250, 1)},
                        {"name": "Rozetka/Açar", "unit": "ədəd", "qty": 2, "price": round(15 * data.get('price_per_m2', 250)/250, 1)},
                    ],
                }

        # Cəmi hesabla
        subtotal = sum(
            item["qty"] * item["price"]
            for cats in rooms_data.values()
            for items in cats.values()
            for item in items
        )
        margin    = subtotal * DEFAULT_MARGIN / 100
        total     = subtotal + margin

        await state.update_data(
            rooms_data=rooms_data,
            room_list=room_list,
            bathroom_list=bathroom_list,
            special_rooms=special_list,
            subtotal=subtotal,
            total=total,
            margin_pct=DEFAULT_MARGIN,
            discount_pct=DEFAULT_DISCOUNT,
            ai_summary=summary,
        )

        # Xülasə göstər
        area = data.get("area_m2", 0)
        price_per_m2 = data.get("price_per_m2", 250)
        lines = [
            "✅ *AI Smeta Hazırdır!*\n",
            f"👤 {data.get('client_name')} | {data.get('client_phone', '')}",
            f"📍 {data.get('address')}",
            f"🏠 {data.get('room_config')} | {area} m² | {price_per_m2} AZN/m²\n",
        ]
        if flooring.get("keramika"): lines.append(f"🔶 Keramika: {flooring['keramika']} m²")
        if flooring.get("laminat"):  lines.append(f"🟫 Laminat:  {flooring['laminat']} m²")
        if flooring.get("parket"):   lines.append(f"🟤 Parket:   {flooring['parket']} m²")
        if special_list:             lines.append(f"🔧 Xüsusi:   {', '.join(special_list)}")
        lines.append("")

        room_lines = []
        for room, cats in rooms_data.items():
            r_total = sum(i["qty"]*i["price"] for c in cats.values() for i in c)
            if r_total > 0:
                room_lines.append(f"🏠 {room}: `{r_total:,.0f} {CURRENCY}`")
        lines.extend(room_lines[:8])
        if len(room_lines) > 8:
            lines.append(f"... və {len(room_lines)-8} otaq daha")

        lines.append(f"\n💰 Ara cəm: `{subtotal:,.0f} {CURRENCY}`")
        lines.append(f"📈 Marja ({DEFAULT_MARGIN}%): `{margin:,.0f} {CURRENCY}`")
        lines.append(f"\n🏷️ *MÜŞTƏRİ QİYMƏTİ: {total:,.0f} {CURRENCY}*")
        if summary:
            lines.append(f"\n💡 _{summary}_")

        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Smeta yarat və link al", callback_data="ss_confirm")],
            [InlineKeyboardButton(text="❌ Ləğv et", callback_data="ss_cancel")],
        ])
        await msg.answer("\n".join(lines), parse_mode="Markdown", reply_markup=confirm_kb)

    except anthropic.AuthenticationError:
        await state.clear()
        await msg.answer(
            "❌ Claude AI açarı düzgün deyil.\n"
            "Adminə xəbər verin: ANTHROPIC_API_KEY mühit dəyişənini yoxlayın."
        )
    except json.JSONDecodeError as e:
        logger.error(f"AI JSON parse xətası: {e}\nText: {text[:500]}")
        await state.clear()
        await msg.answer(
            "❌ AI cavabı parse edilə bilmədi. Yenidən cəhd edin: /newsmeta"
        )
    except Exception as e:
        logger.error(f"AI smeta xətası: {e}", exc_info=True)
        await state.clear()
        await msg.answer(
            f"❌ Xəta baş verdi: {str(e)[:200]}\n\nYenidən cəhd edin: /newsmeta"
        )


@router.callback_query(F.data == "ss_confirm", SmartSmetaForm.generating)
async def ss_confirm(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await cq.message.answer("⏳ Smeta qeyd edilir...")

    smeta_number = await generate_smeta_number()
    await state.update_data(smeta_number=smeta_number)
    data["smeta_number"] = smeta_number

    try:
        smeta_id = await save_smeta(data)

        # Standart checklist
        room_list = data.get("room_list", list(data.get("rooms_data", {}).keys()))
        await init_checklist_for_smeta(smeta_number, room_list)

        WEB_URL = os.getenv("WEB_URL", "https://smeta-bot-production.up.railway.app")
        link = f"{WEB_URL}/smeta/{smeta_number}"

        from handlers import main_menu_kb
        await cq.message.answer(
            f"✅ *Smeta № {smeta_number} hazırdır!*\n\n"
            f"👤 Müştəri: {data['client_name']}\n"
            f"💰 Məbləğ: *{data['total']:,.0f} {CURRENCY}*\n\n"
            f"🔗 *Müştəriyə göndərin:*\n{link}",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(cq.from_user.id),
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Smeta save xətası: {e}", exc_info=True)
        await cq.message.answer(f"❌ Xəta: {e}")
    await cq.answer()


@router.callback_query(F.data == "ss_cancel", SmartSmetaForm.generating)
async def ss_cancel(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    from handlers import main_menu_kb
    await cq.message.answer(
        "❌ Smeta ləğv edildi.",
        reply_markup=main_menu_kb(cq.from_user.id),
    )
    await cq.answer()
